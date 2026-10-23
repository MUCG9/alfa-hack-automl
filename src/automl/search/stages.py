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
