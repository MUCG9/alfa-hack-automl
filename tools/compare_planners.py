"""Generate matched baseline/staged Qwen proposals from measured screen feedback.

No training or secret loading here; use the private coordinator environment.
Candidate files can be evaluated by benchmark_candidates.py. A valid proposal
is not an ML improvement.
"""
from pathlib import Path
import argparse
from copy import deepcopy
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
from automl.evaluation.api import choose_validation
from automl.contracts.messages import SplitPlan
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.run_budget import RunBudget
from automl.search.policy import signature, normalize
from automl.search.runner import ordered, planner_context
import automl.search.runner as runner
from automl.task_understanding.api import discover
from benchmark_hpo import digest


def proposal_diagnostics(content, best):
    if content is None:
        return {'status': 'no_response', 'raw_candidates': None, 'candidates': []}
    document = None
    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char not in '{[':
            continue
        try:
            document, _ = decoder.raw_decode(content[index:])
            break
        except json.JSONDecodeError:
            continue
    proposals = document.get('candidates', [document]) if isinstance(document, dict) else document
    if not isinstance(proposals, list):
        return {'status': 'invalid_envelope', 'raw_candidates': None, 'candidates': []}
    outcomes = []
    for index, candidate in enumerate(proposals):
        outcome = {'proposal': index+1}
        if index >= 3:
            outcome.update(status='outside_runtime_parser_limit')
        else:
            try:
                normalize(candidate, best)
                outcome.update(status='supported')
            except (ValueError, TypeError) as exc:
                outcome.update(status='rejected', reason=str(exc)[:180])
        outcomes.append(outcome)
    return {'status': 'decoded', 'raw_candidates': len(proposals), 'candidates': outcomes}


def plan_with_receipt(context, output, mode):
    """Observe the existing planner without changing its prompt/parser/call cap."""
    original = runner.request_json
    captured = {}
    def observe(*args, **kwargs):
        content, call = original(*args, **kwargs)
        captured['content'] = content
        atomic_json(output/f'{mode}-raw.json', {'content': content})
        return content, call
    runner.request_json = observe
    try:
        plans, call = runner.llm_plan(context, output, max_output=5000, timeout=120, prompt_mode=mode)
    finally:
        runner.request_json = original
    return plans, call, proposal_diagnostics(captured.get('content'), context.get('best_recipe'))


def measured_support(spec, train, hashes, fitting, validation):
    SplitPlan(tuple(fitting.tolist()), tuple(validation.tolist())).validate(len(train))
    if spec['kind'] != 'classification':
        return {'fitting_rows': len(fitting), 'validation_rows': len(validation)}
    if np.intersect1d(hashes[fitting], hashes[validation]).size:
        raise ValueError('Planner support requires disjoint fitting/validation feature groups')
    labels = train[spec['target']].astype(str).to_numpy()
    groups = {c: len(np.unique(hashes[fitting][labels[fitting] == c])) for c in spec['classes']}
    return {'independent_fitting_feature_groups_per_class': groups,
            'validation_rows_per_class': {c: int(np.sum(labels[validation] == c)) for c in spec['classes']},
            'rarest_fitting_class': min(spec['classes'], key=lambda c: groups[c]),
            'scope': 'Fitting-group support and outer search validation counts; not independent private evidence'}


def bounded_candidates(control, proposals, mode):
    """Apply the declared two-distinct-candidate cap before any benchmark fits."""
    selected = [{'name': 'qualified-control', 'recipe': deepcopy(control)}]
    names = {signature(control)}
    rejected = []
    for number, recipe in enumerate(proposals):
        if recipe.get('params', {}).get('feature_selection_top_k', 0):
            rejected.append({'proposal': number+1, 'reason': 'feature_selection_not_in_prompt_screen'})
            continue
        fingerprint = signature(recipe)
        if fingerprint in names:
            rejected.append({'proposal': number+1, 'reason': 'duplicate'})
            continue
        if len(selected) >= 3:
            rejected.append({'proposal': number+1, 'reason': 'two_candidate_limit'})
            continue
        selected.append({'name': f'{mode}-{number+1}', 'recipe': deepcopy(recipe)})
        names.add(fingerprint)
    return selected, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen', type=Path, required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    screen = json.loads(args.screen.read_text())
    spec, profile, train, _, _, text, hashes = discover(args.task)
    spec = choose_validation(spec, train, 'auto')
    if screen['input_sha256'] != {n: digest(p) for n, p in spec['paths'].items()}:
        raise ValueError('Planner feedback comes from different inputs')
    records = list(screen['cuts'][0]['outcomes'].values())
    ranked = ordered(records, spec)
    if not ranked:
        raise ValueError('Measured control feedback is required')
    context = planner_context(spec, profile, text, screen['cuts'][0]['split'],
                              records, ranked[0], 1800, 1)
    cut = screen['cuts'][0]['cut']
    with np.load(args.screen.parent/f'cut-{cut}/outer-split.npz', allow_pickle=False) as partition:
        context['measured_support'] = measured_support(spec, train, hashes, partition['train'], partition['validation'])
    context['study_work'] = {name: {key: screen['cuts'][0].get(name, {}).get(key) for key in
        ['completed_trials', 'maximum_trials', 'startup_trials', 'seconds', 'status']} for name in ['random', 'tpe']}
    context['comparison_rule'] = ('Propose at most two small experiments. Keep all preprocessing, '
        'data policies and calibration fixed unless the hypothesis explicitly changes ONE of them. '
        'Do not enable feature selection: its independent experiment has not passed a gate. '
        'Check independent fitting-group support before treating rare-class F1 changes as reliable. '
        'No fixed calendar year or hardcoded task-specific model switch.')
    summary = {'scope': 'Matched live prompt proposals; ML quality requires separate paired workers',
               'input_sha256': screen['input_sha256'], 'context': context, 'modes': {}}
    with RunBudget(300, 2, output):
        for mode in ['baseline', 'staged']:
            candidates, call, diagnostics = plan_with_receipt(context, output, mode)
            selected, rejected = bounded_candidates(screen['control_recipe'], candidates, mode)
            receipt = {k: v for k, v in call.items() if k != 'error_message'}
            atomic_json(output/f'{mode}-candidates.json', selected)
            summary['modes'][mode] = {'call': receipt, 'distinct_candidates': len(selected)-1,
                                     'raw_supported_proposals': len(candidates), 'candidate_limit': 2,
                                     'rejected': rejected, 'diagnostics': diagnostics, 'candidates': selected}
            atomic_json(output/'proposals.json', summary)
            print(json.dumps({'mode': mode, 'call': receipt, 'distinct_candidates': len(selected)-1}), flush=True)
    if any(r['call'].get('status') != 'ok' for r in summary['modes'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
