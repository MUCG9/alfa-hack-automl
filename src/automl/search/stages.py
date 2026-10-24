"""Pure recipe scheduling for the explicitly enabled four-stage procedure.

No API requests, feature fitting, model fitting or coordinator selector flags
are created here. The existing default portfolio remains unchanged.
"""
from copy import deepcopy
import json

from automl.execution.api import validate_feature_view
from automl.search.policy import normalize, signature


def initial_assessment_status(content, call):
    """Validate only the EDA section; valid recipes remain independently usable.

    Calling this helper means the initial assessment stage was attempted. The
    coordinator separately records the default/skipped ``attempted=False`` case.
    No response text or provider error message is copied into this safe receipt.
    """
    call_status=call.get('status','unknown') if isinstance(call,dict) else 'unknown'
    result={'status':'call_failed','attempted':True,'call_status':call_status,
            'assessment_valid':False,'error':None}
    if call_status!='ok':
        result['error']='Initial assessment call did not succeed'
        return result
    try:
        if not isinstance(content,str):
            raise ValueError('Missing terminal JSON response')
        value=json.loads(content)
    except (ValueError,TypeError):
        result.update(status='invalid_json',error='Initial assessment response is not valid JSON')
        return result
    assessment=value.get('data_assessment') if isinstance(value,dict) else None
    if not isinstance(assessment,dict):
        result.update(status='invalid_assessment',error='data_assessment must be an object')
        return result
    for field in ('validation_risks','feature_hypotheses','model_priorities'):
        entry=assessment.get(field)
        valid=(isinstance(entry,str) and bool(entry.strip())) or (
            isinstance(entry,list) and bool(entry)
            and all(isinstance(item,str) and bool(item.strip()) for item in entry))
        if not valid:
            result.update(status='invalid_assessment',error=field+' must be a nonempty string or list of nonempty strings')
            return result
    result.update(status='ok',assessment_valid=True)
    return result


def choose_hpo_anchor(ranked_records):
    """Pick the best supported successful record from an already valid ranking.

    The caller's ``ordered`` function owns primary-objective/finite validation;
    this helper never substitutes another metric or changes ranking/recipes.
    """
    for record in ranked_records:
        if (isinstance(record,dict) and record.get('status')=='ok'
                and isinstance(record.get('recipe'),dict)
                and record['recipe'].get('engine') in {'lightgbm','catboost','xgboost'}):
            return record
    return None


def prepare_four_stage_recipes(spec, base_recipes, proposals, maximum_initial=9):
    """Return ``(queue, receipts)`` with a bounded, diverse normalized queue.

    The first available semantic history/two-view baseline is protected as the
    anchor. Up to two distinct Qwen proposals follow, with slots reserved for
    missing baseline model families when the cap permits their coverage. One
    baseline per missing engine follows; remaining slots use baseline order.

    Tree recipes explicitly use trusted broad features. Linear text recipes
    retain their existing feature settings. Caller-owned objects are never
    mutated. Invalid recipes, duplicates and omitted proposals have compact
    receipts with source/index/engine/status/reason, without copying payloads.
    """
    if type(maximum_initial) is not int or maximum_initial <= 0:
        raise ValueError('maximum_initial must be a positive integer')
    if not isinstance(spec, dict):
        raise ValueError('Task specification must be an object')
    if not isinstance(base_recipes, (list, tuple)) or not isinstance(proposals, (list, tuple)):
        raise ValueError('Baselines and proposals must be recipe sequences')

    receipts = []

    def receipt(source, index, candidate, status, reason):
        engine = candidate.get('engine') if isinstance(candidate, dict) else None
        receipts.append({'source': source, 'index': index,
                         'engine': engine if isinstance(engine, str) else None,
                         'status': status, 'reason': str(reason)[:500]})

    def prepare(candidates, source):
        result = []
        local_signatures = set()
        for index, candidate in enumerate(candidates):
            try:
                # Validate the supplied recipe before forcing broad, so a typo
                # or malformed recipe is not silently repaired into a success.
                recipe = normalize(deepcopy(candidate))
                if recipe['engine'] != 'linear_text':
                    recipe['params']['generic_features'] = 'broad'
                    recipe = normalize(recipe)
                validate_feature_view(recipe, spec)
                key = signature(recipe)
            except (ValueError, TypeError, KeyError) as exc:
                receipt(source, index, candidate, 'rejected', exc)
                continue
            if key in local_signatures:
                receipt(source, index, candidate, 'duplicate', 'Duplicate normalized recipe')
                continue
            local_signatures.add(key)
            result.append({'recipe': recipe, 'signature': key, 'source': source, 'index': index})
        return result

    baselines = prepare(base_recipes, 'baseline')
    planned = prepare(proposals, 'qwen')
    queue = []
    scheduled = set()
    engines = set()

    def add(record):
        if len(queue) >= maximum_initial or record['signature'] in scheduled:
            return False
        queue.append(record['recipe'])
        scheduled.add(record['signature'])
        engines.add(record['recipe']['engine'])
        return True

    if baselines:
        anchor = next((record for record in baselines
                       if record['recipe']['params'].get('history_asof')
                       or record['recipe']['params'].get('feature_views')), baselines[0])
        add(anchor)

    baseline_engines = {record['recipe']['engine'] for record in baselines}
    # Diversity is feasible iff one slot per baseline family fits. Otherwise the
    # requested priority order still governs a deliberately smaller queue.
    reserve_families = maximum_initial >= len(baseline_engines)
    proposed_count = 0
    for record in planned:
        if record['signature'] in scheduled:
            receipt('qwen', record['index'], record['recipe'], 'duplicate', 'Recipe already scheduled as anchor')
            continue
        if proposed_count >= 2:
            receipt('qwen', record['index'], record['recipe'], 'omitted', 'Two-proposal limit')
            continue
        missing_after = baseline_engines - (engines | {record['recipe']['engine']})
        if reserve_families and len(queue) + 1 + len(missing_after) > maximum_initial:
            receipt('qwen', record['index'], record['recipe'], 'omitted', 'Family budget reservation')
            continue
        if add(record):
            proposed_count += 1
        else:
            receipt('qwen', record['index'], record['recipe'], 'omitted', 'Initial queue budget exhausted')

    for record in baselines:
        if record['recipe']['engine'] not in engines:
            add(record)
    for record in baselines:
        add(record)
    if not queue:
        reasons = '; '.join(item['reason'] for item in receipts[:3])
        raise ValueError('No valid four-stage recipes' + (': ' + reasons if reasons else ''))
    return queue, receipts


# Research-only trusted input. These helpers are never reached by ordinary
# planner JSON, task prose, or the default scheduler.
RETENTION_MAX_BYTES = 32768
RETENTION_SCHEMA = 'uar-strong-retention-v1'


def _retention_sha(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('Retention requires a lowercase SHA256')
    return value


def _retention_json_shape(value, depth=0):
    """Bound non-executable JSON before normalization/recursive validators."""
    import math
    if depth > 10:
        raise ValueError('Retention JSON nesting exceeds ten levels')
    if isinstance(value, dict):
        if len(value) > 80 or any(not isinstance(k, str) or len(k) > 100 for k in value):
            raise ValueError('Retention object is too large')
        for item in value.values():
            _retention_json_shape(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 80:
            raise ValueError('Retention list is too large')
        for item in value:
            _retention_json_shape(item, depth + 1)
    elif isinstance(value, str):
        if len(value) > 1000:
            raise ValueError('Retention text is too large')
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError('Retention accepts JSON values only')
    elif type(value) in (int, float) and not math.isfinite(value):
        raise ValueError('Retention numbers must be finite')


def validate_retention_single(value, spec):
    """Validate a raw measured tree package without injecting new defaults."""
    from automl.contracts.messages import DataPolicy, validate_loss_profiles
    from automl.execution.api import CAPABILITIES, validate_target_smearing
    fields = {'engine', 'params', 'feature_code', 'hypothesis', 'data_policy'}
    if not isinstance(value, dict) or set(value) - fields:
        raise ValueError('Retained SINGLE has unknown fields or nesting')
    engine = value.get('engine')
    if engine not in ('lightgbm', 'catboost', 'xgboost'):
        raise ValueError('Retention supports boosting SINGLE recipes only')
    params = value.get('params')
    if not isinstance(params, dict) or set(params) - set(CAPABILITIES[engine]['parameters']):
        raise ValueError('Retained SINGLE has unsupported parameters')
    if 'loss_profile_id' in params:
        raise ValueError('External retained recipes must be unprofiled')
    if value.get('feature_code', '') != '' or not DataPolicy.parse(value.get('data_policy')).is_noop:
        raise ValueError('Retention requires empty feature code and noop data policy')
    if ('hypothesis' in value and (not isinstance(value['hypothesis'], str)
                                   or len(value['hypothesis']) > 1000)):
        raise ValueError('Retention hypothesis must be bounded text')
    if (params.get('early_metric') != 'primary' or params.get('nested_stopping') is not True
            or params.get('feature_selection_top_k', 0)
            or params.get('feature_selection_protect_original', False)):
        raise ValueError('Retained models require primary nested stopping and no selector')
    normalized = normalize(deepcopy(value))
    validate_loss_profiles(normalized, spec['kind'])
    validate_feature_view(normalized, spec)
    validate_target_smearing(normalized, spec)
    if signature(normalized) != signature(value):
        raise ValueError('Retention normalization would change the executable package')
    features = set(spec.get('features', []))
    for group in params.get('target_encoding_groups', []):
        if not set(group) <= features:
            raise ValueError('Retention references unavailable encoding features')
    if params.get('history_asof'):
        time_column = spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
        if spec['kind'] != 'regression' or time_column not in features:
            raise ValueError('Retained history needs a declared regression time feature')
    return deepcopy(value)


def make_retention_l1(spec, control):
    """Only the fixed profile changes; original-scale RMSE remains the metric."""
    from automl.contracts.messages import validate_loss_profiles
    if (spec.get('kind') != 'regression' or spec.get('metric') != 'rmse'
            or spec.get('validation_strategy') != 'time'):
        raise ValueError('L1 retention requires ordinary forward RMSE regression')
    anchor = validate_retention_single(control['components'][0], spec)
    hint = spec.get('time_candidate') or {}
    if hint.get('representation') != 'numeric' or hint.get('split_mode') != 'period':
        raise ValueError('L1 retention requires explicit numeric period history support')
    if anchor['engine'] != 'lightgbm' or anchor['params'].get('history_asof') is not True:
        raise ValueError('L1 retention needs an unprofiled declared-history LightGBM anchor')
    seed = deepcopy(anchor)
    seed['params']['loss_profile_id'] = 'lgbm_l1_v1'
    validate_loss_profiles(seed, spec['kind'])
    if signature(normalize(deepcopy(seed))) != signature(seed):
        raise ValueError('Fixed L1 profile was dropped or changed by normalization')
    return seed


def validate_retention_packet(value, spec):
    """Closed typed authority; source SHAs are declared lineage, not ML claims."""
    _retention_json_shape(value)
    if (not isinstance(spec, dict) or spec.get('kind') not in ('regression', 'classification')
            or spec.get('text_features') or spec.get('task_family') == 'pointwise_ranking'
            or spec.get('metric') != ('rmse' if spec.get('kind') == 'regression' else 'macro_f1')):
        raise ValueError('Retention supports nontext ordinary RMSE or Macro F1 only')
    if (not isinstance(value, dict) or set(value) - {'schema', 'mode', 'control', 'champion', 'retained_signature'}
            or value.get('schema') != RETENTION_SCHEMA):
        raise ValueError('Unsupported retention packet schema')
    mode = value.get('mode')
    if mode not in ('control', 'l1_composite'):
        raise ValueError('Unsupported retention mode')
    if spec['kind'] == 'classification' and mode != 'control':
        raise ValueError('Classification retains its complete control without regression seeds')
    def entry(name, complete=False):
        item = value.get(name)
        if not isinstance(item, dict) or set(item) != {'recipe', 'recipe_signature', 'source_sha256'}:
            raise ValueError('Retention entry requires recipe, signature and declared source SHA')
        _retention_sha(item['source_sha256']); _retention_sha(item['recipe_signature'])
        recipe = item['recipe']
        if complete:
            if (not isinstance(recipe, dict) or set(recipe) - {'engine', 'params', 'feature_code', 'hypothesis', 'components', 'weights'}
                    or recipe.get('engine') != 'ensemble' or recipe.get('params', {}) != {}
                    or recipe.get('feature_code', '') != ''):
                raise ValueError('Complete control must be a non-nested ensemble')
            children, weights = recipe.get('components'), recipe.get('weights')
            if (not isinstance(children, list) or not 2 <= len(children) <= 3
                    or not isinstance(weights, list) or len(weights) != len(children)
                    or any(type(w) not in (int, float) or not 0 < w < float('inf') for w in weights)):
                raise ValueError('Invalid complete control component/weight contract')
            import math
            if not math.isfinite(sum(weights)):
                raise ValueError('Complete control weight sum must be finite')
            for child in children:
                validate_retention_single(child, spec)
            if children[0]['engine'] != 'lightgbm':
                raise ValueError('First protected SINGLE must be the LightGBM HPO anchor')
        else:
            validate_retention_single(recipe, spec)
        if signature(recipe) != item['recipe_signature']:
            raise ValueError('Retained executable signature does not match its authority')
        return deepcopy(recipe)
    control = entry('control', True)
    champion = entry('champion') if mode != 'control' else None
    if mode == 'control' and ('champion' in value or 'retained_signature' in value):
        raise ValueError('Control mode cannot silently ignore extra retained entries')
    result = {'mode': mode, 'control': control, 'champion': champion, 'retained': None}
    if mode == 'l1_composite':
        seed = make_retention_l1(spec, control)
        retained = {
            'engine': 'ensemble', 'params': {},
            'hypothesis': 'Fixed retained L1 SINGLE and prior champion; no weight search',
            'components': [seed, deepcopy(champion)], 'weights': [.75, .25]}
        if signature(retained) != _retention_sha(value.get('retained_signature')):
            raise ValueError('Fixed retained recipe signature differs from declared authority')
        result['retained'] = retained
    elif 'retained_signature' in value:
        raise ValueError('This mode has no loss-profile recipe to bind')
    result['declared_sources'] = {name: value[name]['source_sha256'] for name in ('control', 'champion') if name in value}
    return result


def load_retention_packet(path, spec, expected_sha256):
    """Read one bounded non-linked file; callers freeze the source and snapshot."""
    import hashlib, os, stat
    from pathlib import Path
    expected_sha256 = _retention_sha(expected_sha256)
    path = Path(path).absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('Retention input must not traverse a link or reparse point')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= RETENTION_MAX_BYTES:
            raise ValueError('Retention input must be a regular JSON file of at most32KiB')
        data = stream.read(RETENTION_MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if (len(data) != before.st_size or identity(before) != identity(after)
            or identity(after) != identity(path.stat()) or hashlib.sha256(data).hexdigest() != expected_sha256):
        raise ValueError('Retention input changed or does not match trusted CLI SHA')
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('Retention input acquired a link or reparse point during reading')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result: raise ValueError('Duplicate retention JSON object key')
            result[key] = item
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite retention JSON constant')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
        result = validate_retention_packet(value, spec)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Retention input is not bounded UTF-8 JSON') from exc
    result['receipt'] = {'status': 'validated_research_input', 'schema': RETENTION_SCHEMA,
        'input_sha256': expected_sha256, 'input_bytes': len(data), 'mode': result['mode'],
        'declared_source_sha256': result['declared_sources'], 'actual_metrics': None,
        'authority': 'trusted CLI byte/signature binding; declared lineage is not independent ML qualification'}
    return result


def retention_fit_cost(recipe, spec):
    """Structural callback upper bounds, never actual fits or seconds saved."""
    from automl.execution.api import feature_view_components
    if recipe['engine'] == 'ensemble':
        children = [retention_fit_cost(r, spec) for r in recipe['components']]
        return {k: sum(c[k] for c in children) for k in children[0]}
    if 'feature_views' in recipe.get('params', {}):
        children = [retention_fit_cost(r, spec) for r in feature_view_components(recipe, spec)]
        return {k: sum(c[k] for c in children) for k in children[0]}
    p = recipe.get('params', {})
    calibrate = spec['kind'] == 'classification' and spec['metric'] == 'macro_f1' and bool(p.get('calibrate'))
    folds = int(p.get('calibration_folds', 1)) if calibrate else 1
    oof = min(3, max(2, folds)) if folds > 1 else 0
    # Nested search: inner stopping + possible matching-iteration calibration
    # refit + outer fit. Full refit has no stopping but may calibrate internally.
    search = 2 + int(calibrate or bool(p.get('target_smearing'))) + oof
    full = 1 + int(calibrate or bool(p.get('target_smearing'))) + oof
    selected = bool(p.get('feature_selection_top_k'))
    return {'model_leaves': 1, 'search_learner_fits_upper': search,
        'full_refit_learner_fits_upper': full,
        'search_teacher_fits_upper': search if selected else 0,
        'full_refit_teacher_fits_upper': full if selected else 0}


def prepare_retention_recipes(spec, base_recipes, proposals, retention, top_k=32):
    """Required first5 plus at most2 retained seeds; max9 reserves HPO/followup."""
    if type(top_k) is not int or not 1 <= top_k <= 512:
        raise ValueError('Retention requires a bounded positive isolated selector')
    control = deepcopy(retention['control']); anchor = deepcopy(control['components'][0])
    variant = deepcopy(anchor)
    variant['hypothesis'] = 'Separate broad features with protected originals'
    variant['params'].update(generic_features='broad', feature_selection_top_k=top_k,
                             feature_selection_protect_original=True)
    variant = normalize(variant); validate_feature_view(variant, spec)
    queue = []; receipts = []; seen = set()
    def add(recipe, source, required=True):
        key = signature(recipe)
        if key in seen or len(queue) >= 7:
            if required: raise ValueError('Required retention slot is duplicate or exceeds seven initial candidates')
            receipts.append({'source': source, 'status': 'not_scheduled_initial_capacity', 'signature': key})
            return
        seen.add(key); queue.append(deepcopy(recipe))
        receipts.append({'source': source, 'status': 'scheduled', 'queue_index': len(queue) - 1,
            'signature': key, 'engine': recipe['engine'], 'fit_cost_upper': retention_fit_cost(recipe, spec)})
    add(control, 'protected_complete_control'); add(anchor, 'unprofiled_hpo_single')
    add(variant, 'isolated_feature_engineering')
    for engine in ('catboost', 'xgboost'):
        candidate = next((r for r in base_recipes if r.get('engine') == engine), None)
        if candidate is None: raise ValueError('Missing required baseline model family')
        add(validate_retention_single(normalize(deepcopy(candidate)), spec), 'required_' + engine)
    if retention['champion'] is not None: add(retention['champion'], 'prior_champion')
    if retention['retained'] is not None: add(retention['retained'], 'fixed_' + retention['mode'])
    for index, candidate in enumerate(proposals[:2]):
        try:
            candidate = normalize(deepcopy(candidate))
            candidate['params'].pop('feature_selection_top_k', None)
            candidate['params'].pop('feature_selection_protect_original', None)
            validate_feature_view(candidate, spec)
            add(candidate, 'qwen_initial', False)
        except (ValueError, TypeError, KeyError) as exc:
            receipts.append({'source': 'qwen_initial', 'index': index, 'status': 'rejected', 'reason': str(exc)[:300]})
    return queue, receipts, anchor


def retention_worker_timeout(remaining, reserve, hpo_budget, initial_left=0, hpo_pending=True):
    """Allocate within the existing deadline; reserve full HPO, not fake fits."""
    import math
    if (any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
            for v in (remaining, reserve, hpo_budget)) or type(initial_left) is not int
            or initial_left < 0 or type(hpo_pending) is not bool):
        raise ValueError('Invalid retention budget accounting')
    available = remaining - reserve - 30 - (hpo_budget + 30 if hpo_pending else 0) - 5 * initial_left
    if available < 5: raise TimeoutError('Retention has no complete minimum worker slice after reserved phases')
    return min(900, available)


def choose_retention_hpo_anchor(ranked_records, single_anchor):
    """Only an actual successful raw unprofiled SINGLE may seed inner HPO."""
    key = signature(single_anchor)
    return next((r for r in ranked_records if r.get('status') == 'ok'
                 and signature(r['recipe']) == key), None)
