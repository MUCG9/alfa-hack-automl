"""SEL-01 fit-free diagnostic replay; never changes runtime or fits missing caches."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.contracts.messages import canonical_hash
from automl.error_analysis.api import ErrorAnalysisRequest, ErrorAnalysisProtocol, AnalysisBudget
from automl.error_analysis.artifacts import load, Guard
from automl.evaluation.api import evaluate
from automl.infrastructure.atomic import atomic_json
from automl.search.selection import select_third


def measured(data, ids, weights):
    fold = data.request.predictions[0].fold_id
    values = [data.predictions[(identity, fold)] for identity in ids]
    weights = np.asarray(weights, dtype=float)
    weights /= weights.sum()
    task = data.request.task
    first = values[0]
    if task.kind == 'classification':
        matrix = sum(w * v.probabilities for w, v in zip(weights, values))
        prediction = np.asarray(first.classes)[matrix.argmax(axis=1)]
    else:
        matrix = None
        prediction = sum(w * v.predicted for w, v in zip(weights, values))
    return float(evaluate(first.truth, prediction, task.kind, task.metric,
                          matrix, list(first.classes) or None)[task.metric])


def fixed_grid(search, confirmation, ids):
    if len(ids) != 3 or len(set(ids)) != 3:
        raise ValueError('The unchanged grid requires three distinct slots')
    task = search.request.task
    ranked = sorted(ids, key=lambda identity: (measured(search, [identity], [1.])
                  + measured(confirmation, [identity], [1.])) / 2,
                  reverse=task.greater_is_better)
    best = {'ids': ranked[:1], 'weights': [1.]}
    best.update(search=measured(search, best['ids'], best['weights']),
                confirmation=measured(confirmation, best['ids'], best['weights']))
    best['mean'] = (best['search'] + best['confirmation']) / 2
    grid = []
    for pair in itertools.combinations(range(3), 2):
        grid.extend(([ranked[i] for i in pair], [w, 1-w]) for w in [.5, .25, .75, .1, .9])
    grid.extend((ranked, w) for w in [[1/3]*3, [.5, .25, .25], [.25, .5, .25], [.25, .25, .5]])
    for models, weights in grid:
        a, b = measured(search, models, weights), measured(confirmation, models, weights)
        mean = (a + b) / 2
        improves = mean > best['mean'] if task.greater_is_better else mean < best['mean']
        if improves:
            best = {'ids': models, 'weights': weights, 'search': a, 'confirmation': b, 'mean': mean}
    return best


def replay(search_path, confirmation_path, report_path, output):
    if output.exists():
        raise FileExistsError('Never overwrite a previous replay')
    requests = [ErrorAnalysisRequest.from_json(p.read_text()) for p in (search_path, confirmation_path)]
    if [r.predictions[0].fold_id for r in requests] != ['search', 'confirmation']:
        raise ValueError('Explicit original search/confirmation requests required')
    if requests[0].task != requests[1].task or requests[0].dataset != requests[1].dataset:
        raise ValueError('Cannot replay different tasks/datasets')
    guards = [Guard(AnalysisBudget(90, 768, 1)) for _ in requests]
    data = [load(request, guard) for request, guard in zip(requests, guards)]
    report = json.loads(report_path.read_text())
    if not report.get('integrity_ok') or report.get('final_fit_status') != 'ok':
        raise ValueError('Expected verified original baseline report')
    if report['spec']['metric'] != requests[0].task.metric:
        raise ValueError('Report metric mismatch')
    report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    protocol = ErrorAnalysisProtocol.from_json(Path(requests[0].protocol.path).read_text())
    if not any(ref.sha256 == report_sha for ref in protocol.evidence):
        raise ValueError('Replay report is not the original protocol evidence')
    records = sorted([r for r in report['experiments'] if r['status'] == 'ok'],
                     key=lambda r: r['metrics'][requests[0].task.metric],
                     reverse=requests[0].task.greater_is_better)
    identities = ['model-' + canonical_hash(r['recipe'])[:20] for r in records]
    first = data[0].predictions[(identities[0], 'search')]
    matrices = {}
    for identity in identities:
        value = data[0].predictions[(identity, 'search')]
        matrices[identity] = {'rows': value.rows, 'classes': value.classes,
                             'values': value.probabilities if value.probabilities is not None else value.predicted}
    task = requests[0].task
    proposal = select_third(identities, matrices, first.truth, kind=task.kind,
        metric=task.metric, greater_is_better=task.greater_is_better,
        classes=first.classes, scope='diagnostic_reused_public')
    family = {r['recipe']['engine'] for r in records[:2]}
    third = next((i for i in range(2, len(records)) if records[i]['recipe']['engine'] not in family), 2) if len(family) == 1 else 2
    control_ids = identities[:2] + [identities[third]]
    control = fixed_grid(*data, control_ids)
    ensemble = report.get('ensemble')
    expected = ([ensemble['primary']['metrics'][task.metric], ensemble['confirmation']['metrics'][task.metric], ensemble['mean']]
                if ensemble else None)
    if expected is None or not np.allclose([control[k] for k in ('search', 'confirmation', 'mean')], expected, rtol=0, atol=1e-12):
        raise ValueError('Legacy replay does not reproduce the original selected ensemble')
    missing = [identity for identity in proposal['selected_ids'] if (identity, 'confirmation') not in data[1].predictions]
    result = {'scope': 'Diagnostic adaptive replay of reused public cuts, NOT independent/outer/private performance',
              'protocol': 'SEL-01-fixed-third-marginal', 'new_model_fits': 0,
              'proposal': proposal, 'control_shortlist': control_ids, 'control': control,
              'legacy_replay_matches': True, 'missing_confirmation_ids': missing,
              'recommendation': 'needs_confirmation_fit' if missing else 'cached_screen_only',
              'runtime_enabled': False}
    if not missing:
        candidate = fixed_grid(*data, proposal['selected_ids'])
        result['candidate'] = candidate
        result['both_cached_cuts_strictly_improve'] = all(
            candidate[k] > control[k] if task.greater_is_better else candidate[k] < control[k]
            for k in ('search', 'confirmation'))
        result['recommendation'] = ('identity_no_new_quality_result' if proposal['selected_ids'] == control_ids else
            'eligible_for_nested_research_only' if result['both_cached_cuts_strictly_improve'] else 'reject_cached_screen')
    for guard in guards:
        guard.verify_unchanged()
    result['verified_artifacts_sha256'] = {str(path): sha for guard in guards for path, sha in guard.verified.items()}
    result['request_sha256'] = [r.sha256 for r in requests]
    result['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    atomic_json(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search-request', type=Path, required=True)
    parser.add_argument('--confirmation-request', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.search_request, args.confirmation_request, args.report, args.output)
    print(json.dumps({k: result[k] for k in ('recommendation', 'control', 'missing_confirmation_ids')}))
