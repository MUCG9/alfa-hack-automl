"""Pure recipe scheduling for the explicitly enabled four-stage procedure.

No API requests, feature fitting, model fitting or coordinator selector flags
are created here. The existing default portfolio remains unchanged.
"""
from copy import deepcopy
import json
import hashlib, os, stat
from pathlib import Path

from automl.execution.api import CAPABILITIES, validate_feature_view, validate_target_smearing
from automl.search.policy import normalize, signature
from automl.contracts.messages import validate_loss_profiles


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


CHAMPION_RECIPE_MAX_BYTES = 32768
_CHAMPION_FIELDS = frozenset({'engine', 'params', 'feature_code', 'hypothesis', 'data_policy'})


def validate_champion_recipe(value, spec):
    """Accept one bounded, selector-free SINGLE tree recipe, never instructions.

    V1 deliberately excludes free feature code, ensembles and augmentation.
    Generic FE, target encoding, history and feature views retain their existing
    trusted validators and fitting scope. Provenance/claims in a sidecar cannot
    authorize anything: this function does not read a sidecar or its paths.
    """
    if not isinstance(value, dict) or set(value) - _CHAMPION_FIELDS:
        raise ValueError('Champion must contain only supported SINGLE recipe fields')
    engine = value.get('engine')
    if not isinstance(engine, str) or engine not in CAPABILITIES or engine == 'linear_text':
        raise ValueError('Champion requires a supported SINGLE tree learner')
    if not isinstance(spec, dict) or spec.get('kind') not in {'regression', 'classification'}:
        raise ValueError('Champion requires an ordinary supervised task')
    if spec.get('text_features') or spec.get('task_family') == 'pointwise_ranking':
        raise ValueError('Champion V1 does not support text or ranking tasks')
    params = value.get('params', {})
    if not isinstance(params, dict) or set(params) - set(CAPABILITIES[engine]['parameters']):
        raise ValueError('Champion contains unsupported model parameters')
    if 'hypothesis' in value and (not isinstance(value['hypothesis'], str) or len(value['hypothesis']) > 1000):
        raise ValueError('Champion hypothesis must be a bounded string')
    if value.get('feature_code', '') != '':
        raise ValueError('Champion V1 requires empty feature_code')
    # Reject nonfinite JSON numbers even when the JSON spelling is 1e309.
    json.dumps(value, allow_nan=False)
    recipe = normalize(deepcopy(value))
    if recipe['params'].get('feature_selection_top_k', 0) or recipe['params'].get('feature_selection_protect_original', False):
        raise ValueError('Champion must not activate a second feature selector')
    if recipe.get('data_policy'):
        raise ValueError('Champion V1 requires noop data policy')
    validate_feature_view(recipe, spec)
    validate_target_smearing(recipe, spec)
    features = set(spec.get('features', []))
    for group in recipe['params'].get('target_encoding_groups', []):
        if not set(group) <= features:
            raise ValueError('Champion encoding references unavailable feature columns')
    if recipe['params'].get('history_asof'):
        time_column = spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
        if spec['kind'] != 'regression' or time_column not in features:
            raise ValueError('Champion history requires a regression time feature')
    return recipe


def load_champion_recipe(path, spec):
    """Read at most 32KiB from one regular, non-linked JSON file.

    Return a normalized recipe and a safe receipt. The caller freezes both the
    original input and its normalized output snapshot in protected provenance.
    No metadata path, candidate instruction or executable module is followed.
    """
    path = Path(path).absolute()
    for component in (path, *path.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('Champion path must not traverse symlinks or reparse points')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Champion input must be a regular file')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not 0 < before.st_size <= CHAMPION_RECIPE_MAX_BYTES:
            raise ValueError('Champion JSON must contain from1 to32768 bytes')
        data = stream.read(CHAMPION_RECIPE_MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda entry: (entry.st_dev, entry.st_ino, entry.st_size, entry.st_mtime_ns)
    if len(data) > CHAMPION_RECIPE_MAX_BYTES or len(data) != before.st_size or identity(before) != identity(after) or identity(after) != identity(path.stat()):
        raise ValueError('Champion input changed during bounded reading')
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Champion JSON contains duplicate object keys')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('Champion JSON contains nonfinite numbers')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs, parse_constant=invalid_constant)
        recipe = validate_champion_recipe(value, spec)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Champion input is not bounded UTF-8 recipe JSON') from exc
    return recipe, {'status': 'validated_input', 'input_sha256': hashlib.sha256(data).hexdigest(),
                    'input_bytes': len(data), 'recipe_signature': signature(recipe),
                    'metric': None, 'measurement_status': 'not_run',
                    'authority': 'recipe_only; external provenance claims are not trusted'}


LOSS_SEED_PROFILE_ID = 'lgbm_l1_v1'


def make_loss_seed_l1_recipe(spec, control):
    """Copy the protected raw SINGLE, changing only its fixed loss profile ID.

    This constructor reads no external candidate file or provenance claims.
    Normalization validates a copy only; the measured raw package is retained.
    """
    if (not isinstance(spec, dict) or spec.get('kind') != 'regression'
            or spec.get('metric') != 'rmse' or spec.get('text_features')
            or spec.get('task_family') == 'pointwise_ranking'):
        raise ValueError('Fixed L1 seed requires nontext ordinary RMSE regression')
    if (not isinstance(control, dict) or control.get('engine') != 'ensemble'
            or not isinstance(control.get('components'), list) or not control['components']):
        raise ValueError('Fixed L1 seed requires the preserved complete control')
    anchor = control['components'][0]
    if (not isinstance(anchor, dict) or anchor.get('engine') != 'lightgbm'
            or not isinstance(anchor.get('params'), dict)):
        raise ValueError('Fixed L1 seed requires the protected LightGBM SINGLE')
    params = anchor['params']
    if ('loss_profile_id' in params or params.get('early_metric') != 'primary'
            or params.get('nested_stopping') is not True):
        raise ValueError('Fixed L1 seed requires unchanged unprofiled primary nested control')
    validate_champion_recipe(deepcopy(anchor), spec)
    seed = deepcopy(anchor)
    seed['params']['loss_profile_id'] = LOSS_SEED_PROFILE_ID
    validate_loss_profiles(seed, 'regression')
    normalized = normalize(deepcopy(seed))
    if signature(seed) != signature(normalized):
        raise ValueError('L1 seed normalization would change the measured executable package')
    return seed


def prepare_preserved_four_stage_recipes(spec, base_recipes, proposals, control,
                                         top_k=32, maximum_initial=7, champion=None, loss_seed_l1=False):
    """Keep the saved complete control and its first SINGLE component intact.

    Only one explicit FE candidate receives broad expansion and the selector.
    This avoids imposing an unverified transform on every model comparison.
    """
    if type(loss_seed_l1) is not bool:
        raise ValueError('loss_seed_l1 must be a boolean')
    if loss_seed_l1 and (champion is None or maximum_initial != 7):
        raise ValueError('L1 seed requires prior champion and exactly seven initial slots')
    if not isinstance(control,dict) or control.get('engine')!='ensemble':
        raise ValueError('Preserved complete control must be an ensemble recipe')
    components=control.get('components',[])
    weights=control.get('weights',[])
    if (not 2<=len(components)<=3 or len(weights)!=len(components)
            or any(type(v) not in (int,float) or not 0<v<float('inf') for v in weights)):
        raise ValueError('Invalid preserved control components/weights')
    for component in components:
        normalized=normalize(deepcopy(component))
        validate_feature_view(normalized,spec)
        if component.get('params',{}).get('feature_selection_top_k'):
            raise ValueError('Preserved control must be selector-free')
    if type(maximum_initial) is not int or maximum_initial<5:
        raise ValueError('Preserved procedure requires at least five initial slots')
    control=deepcopy(control)
    anchor=deepcopy(components[0])
    if anchor.get('engine') not in {'lightgbm','catboost','xgboost'}:
        raise ValueError('Control first component must support inner HPO')
    variant=deepcopy(anchor)
    variant['hypothesis']='Separate broad features with raw-original protection'
    variant['params']=dict(variant.get('params',{}),generic_features='broad',
        feature_selection_top_k=top_k,feature_selection_protect_original=True)
    variant=normalize(variant)
    queue=[]; seen=set(); receipts=[]
    def add(recipe,source):
        key=signature(recipe)
        if key in seen or len(queue)>=maximum_initial: return False
        seen.add(key);queue.append(deepcopy(recipe))
        receipts.append({'source':source,'engine':recipe['engine'],'status':'scheduled',
            'signature':key,'selector_applied':bool(recipe.get('params',{}).get('feature_selection_top_k'))})
        return True
    add(control,'preserved_complete_control')
    add(anchor,'preserved_single_anchor')
    add(variant,'separate_feature_engineering')
    # Family coverage and the strong reference have priority over new proposals.
    for engine in ('catboost','xgboost'):
        candidate=next((r for r in base_recipes if r.get('engine')==engine),None)
        if candidate is not None: add(normalize(deepcopy(candidate)),'baseline_family')
    if champion is not None:
        if maximum_initial < 6:
            raise ValueError('Champion needs six required initial slots')
        champion = validate_champion_recipe(champion, spec)
        if not {'lightgbm', 'catboost', 'xgboost'} <= {r['engine'] for r in queue}:
            raise ValueError('Champion cannot displace required model-family coverage')
        key = signature(champion)
        if add(champion, 'prior_champion'):
            receipts[-1]['queue_index'] = len(queue) - 1
        else:
            receipts.append({'source': 'prior_champion', 'engine': champion['engine'],
                'status': 'duplicate', 'signature': key,
                'queue_index': next(i for i, r in enumerate(queue) if signature(r) == key),
                'reason': 'Executable signature is already a required seed'})
    if loss_seed_l1:
        if len(queue) != 6 or signature(queue[5]) != signature(champion):
            raise ValueError('L1 seed requires a distinct prior champion preserved in slot5')
        seed = make_loss_seed_l1_recipe(spec, control)
        if not {'lightgbm', 'catboost', 'xgboost'} <= {r['engine'] for r in queue}:
            raise ValueError('L1 seed cannot displace required model-family coverage')
        key = signature(seed)
        if add(seed, 'fixed_regression_loss_seed'):
            receipts[-1]['queue_index'] = len(queue) - 1
            receipts[-1]['loss_profile_id'] = LOSS_SEED_PROFILE_ID
        else:
            receipts.append({'source': 'fixed_regression_loss_seed', 'engine': 'lightgbm',
                'status': 'duplicate', 'signature': key, 'loss_profile_id': LOSS_SEED_PROFILE_ID,
                'queue_index': next(i for i, r in enumerate(queue) if signature(r) == key),
                'reason': 'Fixed L1 executable signature is already a required seed'})
    for i,candidate in enumerate(proposals[:2]):
        try:
            candidate=normalize(deepcopy(candidate)); validate_feature_view(candidate,spec)
            # Selector activation belongs to the explicitly recorded FE branch.
            candidate['params'].pop('feature_selection_top_k',None)
            candidate['params'].pop('feature_selection_protect_original',None)
            added = add(candidate,'qwen')
            if champion is not None and not added:
                key = signature(candidate)
                receipts.append({'source': 'qwen', 'index': i, 'engine': candidate['engine'],
                    'status': 'duplicate' if key in seen else 'not_scheduled_initial_capacity',
                    'signature': key, 'reason': 'Initial queue remains bounded; HPO/followup slots reserved'})
        except (ValueError,TypeError,KeyError) as exc:
            receipts.append({'source':'qwen','index':i,'status':'rejected','reason':str(exc)[:300]})
    return queue,receipts,anchor


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
