"""Metadata-only evidence cards and a fixed qualification contract for Qwen.

These cards describe supplied, independently verified receipts. They do not
verify predictions themselves or execute any proposal returned by the model.
"""

import math

CONTRACT_ID = 'paired-support-v1'
CONTROLS = {
    'CLS_SINGLE': 'Qualified categorical two-view LightGBM component, no selector',
    'REG_SINGLE': 'Qualified as-of/history LightGBM component, no selector',
    'COMPLETE_AGENT': 'Qualified complete V11/V16 procedure on both public tasks',
}
CONTRACT = {
    'id': CONTRACT_ID,
    'provenance': 'Original HPO-01/FE-01 protocol, before component outcomes',
    'component_control': {'classification': 'CLS_SINGLE', 'regression': 'REG_SINGLE'},
    'all_predeclared_outer_cuts_must_improve': True,
    'classification_minimum_independent_fitting_groups': 100,
    'classification_maximum_supported_class_f1_loss': .01,
    'floating_tolerance': 1e-12,
    'classification_positive_gain_excluding_rarest_class': True,
    'hpo_tpe_mean_must_also_beat_equal_cap_random': True,
    'positive_screen_requires_further_whole_procedure_qualification': True,
    'complete_agent_control': 'COMPLETE_AGENT',
    'incomplete_screens_cannot_pass': True,
    'metric_directions': {'macro_f1': 'maximize', 'rmse': 'minimize'},
}


def compact(value):
    """Retain metrics, gates and work counts; omit bulky model/cache details."""
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()
                if not k.endswith('sha256') and k not in {
                    'recipe', 'selected_recipe', 'per_class_f1', 'independent_inner_verification',
                    'final_fit_iterations', 'trials', 'source', 'directory'}}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def evidence_context(documents):
    cards = {}

    def card(key, path, value):
        cards[key] = {'source_path': path, 'facts': compact(value)}

    for name, value in documents['mvp']['tasks'].items():
        # MVP receipts compare complete procedures. Emit unit and direction
        # explicitly, rather than asking a remote reviewer to infer them.
        metric = value['metric']
        if metric not in CONTRACT['metric_directions']:
            raise ValueError('Unknown MVP metric direction')
        greater = CONTRACT['metric_directions'][metric] == 'maximize'
        mean, control = float(value['mean']), float(value['control_mean'])
        if not all(math.isfinite(v) for v in [mean, control]):
            raise ValueError('Nonfinite MVP aggregate')
        oriented = (mean-control)*(1 if greater else -1)
        facts = dict(value, comparison_unit='complete_agent', control_id='COMPLETE_AGENT',
                     metric_direction=CONTRACT['metric_directions'][metric],
                     observed_mean_oriented_gain=oriented, observed_mean_improved=oriented > 0)
        card('MVP_' + name.upper(), 'mvp.tasks.' + name, facts)
    cost = documents.get('cost', {})
    for key, value in cost.items():
        card(key.upper(), 'cost.' + key, value)
    diag = cost.get('selector_diagnostic')
    if diag:
        classes = diag['per_class']
        violations = {k: v['delta'] for k, v in classes.items()
                      if v['independent_fitting_groups'] >= 100 and v['delta'] < -.01-1e-12}
        # Independently derive the original numeric gate rather than trusting
        # a model's interpretation of the boolean saved in the receipt.
        gate = {'minimum_groups': 100, 'maximum_f1_loss': .01,
                'supported_class_violations': violations,
                'supported_class_drop_gate_passed': not violations,
                'rarest_class': diag['rarest_class'],
                'rarest_fitting_groups': classes[diag['rarest_class']]['independent_fitting_groups']}
        if gate['supported_class_drop_gate_passed'] != diag['supported_class_drop_gate_passed']:
            raise ValueError('Supplied diagnostic disagrees with fixed numeric contract')
        card('SELECTOR_GATE', 'derived from cost.selector_diagnostic.per_class', gate)
    screens = documents.get('screens', {})
    for name, value in screens.get('screens', {}).items():
        card('SCREEN_' + name.upper().replace('-', '_'), 'screens.screens.' + name, value)
    card('PLANNER_GENERATION', 'screens.planner_generation', screens.get('planner_generation', {}))
    return {'evidence_cards': cards, 'qualification_contract': CONTRACT,
            'qualified_controls': CONTROLS,
            'local_resource_contract': {'host_fitting_concurrency': 1, 'threads': 2,
                'worker_seconds': 600, 'worker_memory_mib': 1536, 'max_fits': 12,
                'total_seconds': 10800, 'additional_agents': False, 'paid_compute': False},
            'already_predeclared_probes': ['FE-01', 'HPO-01', 'HAR-01', 'HAR-02', 'FE-02'],
            'status_rule': 'Frozen supplied receipts only. Missing outcomes remain unknown. Do not duplicate pending probes.'}


def validate_review(document, context):
    if not isinstance(document, dict) or set(document) != {'hypotheses', 'next_experiments', 'unknowns'}:
        raise ValueError('Invalid review envelope')
    for key, limit in [('hypotheses', 6), ('next_experiments', 3), ('unknowns', 12)]:
        if not isinstance(document[key], list) or len(document[key]) > limit:
            raise ValueError('Invalid review list limits')
    evidence_ids = set(context['evidence_cards'])
    for item in document['hypotheses'] + document['next_experiments']:
        ids = item.get('evidence_ids') if isinstance(item, dict) else None
        if not isinstance(ids, list) or not ids or not all(isinstance(k, str) and k in evidence_ids for k in ids):
            raise ValueError('Unknown or missing evidence ID')
    for item in document['hypotheses']:
        if set(item) != {'hypothesis', 'evidence_ids', 'limitation'} or not all(
                isinstance(item[k], str) and item[k].strip() for k in ['hypothesis', 'limitation']):
            raise ValueError('Invalid hypothesis schema')
    for item in document['next_experiments']:
        if set(item) != {'hypothesis', 'single_change', 'evidence_ids', 'control_id',
                         'acceptance_contract_id', 'falsification', 'budget'}:
            raise ValueError('Invalid experiment schema')
        if item['control_id'] not in CONTROLS:
            raise ValueError('Unqualified control')
        if item['acceptance_contract_id'] != CONTRACT_ID:
            raise ValueError('Changed acceptance contract')
        for key in ['hypothesis', 'single_change', 'falsification']:
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError('Missing experiment description')
        budget = item['budget']
        caps = context['local_resource_contract']
        if not isinstance(budget, dict) or set(budget) != {'threads', 'worker_seconds', 'worker_memory_mib', 'max_fits', 'total_seconds'}:
            raise ValueError('Invalid budget schema')
        if any(type(v) is not int or v < 1 or v > caps[k] for k, v in budget.items()):
            raise ValueError('Resource cap exceeded')
    if not all(isinstance(s, str) for s in document['unknowns']):
        raise ValueError('Invalid unknowns')
    return document
