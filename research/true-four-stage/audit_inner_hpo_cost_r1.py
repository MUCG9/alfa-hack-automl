"""Audit terminal inner-HPO timing/count metadata; do not score live outer runs."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import statistics
import time

W = Path(__file__).resolve().parent
R = W / 'alfa-hack-automl'
def load(p):
    return json.loads(p.read_text('utf-8'))
def sha(p):
    return hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')

manifest = load(W / 'true-four-stage-launch-r1/manifest.json')
for rel, expected in manifest['immutable_files'].items():
    assert sha(W / rel) == expected, rel
campaign = load(R / 'test-runs/tm1/campaign.json')
assert campaign['absolute_deadline_unix'] == 1792735776.7207654
tasks = {}
for task, name in [('r', 'regression'), ('c', 'classification')]:
    root = R / 'test-runs/tm1' / task / 'automl_runs/true4/inner-hpo'
    path = root / 'hpo.json'
    before = sha(path)
    hpo = load(path)
    assert hpo['status'] == 'ok', 'Only terminal inner-study metadata may be summarized'
    assert hpo['sampler'] == 'tpe' and hpo['maximum_trials'] == 8 and hpo['startup_trials'] == 3
    phases = {k: Counter(attempted=0, completed=0, failed=0) for k in ('anchor', 'startup', 'guided', 'random')}
    completed = 0
    trials = []
    artifact_hashes = {}
    for number, entry in enumerate(hpo['trials']):
        assert entry['number'] == number and entry['completed_before_sampling'] == completed
        expected_phase = 'anchor' if number == 0 else 'startup' if completed < 3 else 'guided'
        assert entry['sampling_phase'] == expected_phase
        valid = entry['objective_valid']
        assert type(valid) is bool
        if valid:
            assert entry['status'] == 'ok' and isinstance(entry['value'], (int, float)) and math.isfinite(entry['value'])
            result_path = root / f'trial-{number:02d}/result.json'
            result = load(result_path)
            assert result['status'] == 'ok' and result['wall_seconds'] == entry['seconds']
            artifact_hashes[str(result_path.relative_to(W))] = sha(result_path)
            completed += 1
        else:
            assert entry['value'] is None and entry['status'] != 'ok'
        seconds = entry['seconds']
        assert isinstance(seconds, (int, float)) and math.isfinite(seconds) and seconds > 0
        phases[expected_phase]['attempted'] += 1
        phases[expected_phase]['completed' if valid else 'failed'] += 1
        trials.append({k: entry[k] for k in ('number', 'sampling_phase', 'completed_before_sampling', 'status', 'objective_valid', 'seconds')} |
                      {'objective_value': None, 'numeric_quality_not_scored_by_this_audit': True})
    actual_phases = {k: dict(v) for k, v in phases.items()}
    assert actual_phases == hpo['phase_counts']
    assert len(trials) == hpo['attempted_trials'] and completed == hpo['completed_trials']
    assert len(trials) - completed == hpo['failed_trials']
    assert 8 - len(trials) == hpo['unattempted_trials']
    assert phases['guided']['attempted'] == hpo['guided_attempts']
    assert phases['guided']['completed'] == hpo['guided_successful_trials']
    assert sha(path) == before
    worker_seconds = sum(t['seconds'] for t in trials)
    tasks[name] = {
        'hpo_receipt': str(path.relative_to(W)), 'hpo_receipt_sha256': before,
        'engine': hpo['control_recipe']['engine'], 'sampler': 'tpe',
        'planned_trials': 8, 'startup_success_threshold': 3,
        'attempted': len(trials), 'completed_objectives_reported': completed,
        'failed': len(trials) - completed, 'unattempted': 8 - len(trials),
        'phase_counts_recounted': actual_phases, 'trials': trials,
        'study_seconds': hpo['seconds'], 'worker_callback_seconds_sum': round(worker_seconds, 3),
        'study_minus_worker_callback_seconds': round(hpo['seconds'] - worker_seconds, 3),
        'successful_callback_median_seconds': statistics.median(t['seconds'] for t in trials if t['objective_valid']),
        'failure_callback_seconds': round(sum(t['seconds'] for t in trials if not t['objective_valid']), 3),
        'successful_worker_result_hashes': artifact_hashes,
        'numeric_objectives_independently_recomputed': False,
        'quality_or_admission_gain_established': False,
    }
report = {
    'status': 'terminal_inner_HPO_execution_metadata_verified_outer_campaign_still_running',
    'recorded_epoch': time.time(), 'campaign_status_at_audit': campaign['status'],
    'source_archive_sha256': campaign['source_archive_sha256'],
    'absolute_deadline_unix': campaign['absolute_deadline_unix'],
    'frozen_manifest_files_verified': len(manifest['immutable_files']),
    'source': str(Path(__file__).relative_to(W)), 'source_sha256': sha(Path(__file__)),
    'tasks': tasks,
    'interpretation': [
        'Identical nominal trial counts do not mean identical adaptive search: classification never reached guided TPE.',
        'Regression stopped at eight requested trials; classification exhausted the 900-second study envelope after three attempts.',
        'Callback time includes worker work and controller costs; residual is observational and is not a measured cache saving.',
        'These are different task workloads, not a causal benchmark between samplers or recipes.',
        'Current MVP is unchanged. Future measured admission/random-vs-TPE/cache hypotheses require their own prospective runs.',
    ],
    'independent_API_ledger_read': False, 'new_fits': 0, 'LLM_calls': 0,
    'outer_quality_scored': False, 'promotion': False,
}
target = W / 'true-mvp-inner-hpo-cost-r1.json'
with target.open('xb') as out:
    out.write(encoded(report))
dest = R / 'docs/experiments/true-four-stage-tm1/hpo-cost-r1.json'
assert not dest.exists()
dest.write_bytes(target.read_bytes())
text = '\n'.join([
    'Стоимость завершённых внутренних Optuna studies настоящего MVP tm1.',
    f"Регрессия: 8/8 успешных trials; anchor1 + startup2 + guided5. Study83.563s; median успешного worker callback{tasks['regression']['successful_callback_median_seconds']:.3f}s.",
    'Классификация: 3 попытки из8, успешны2, timeout1, не начаты5. Anchor1 + startup2; guided0.',
    'Классификация: study900.344s; успешные callbacks328.110s/336.406s; timeout226.375s с отсутствующим objective. TPE не перешёл к адаптивному выбору.',
    'Study−сумма callbacks — наблюдаемые затраты контроллера/подготовки/прочего; это не измеренный выигрыш от cache.',
    'Проверены фазы по completed_before_sampling, статусы/counts, успешные worker receipts и252замороженных файла. Численные objective здесь не пересчитывались и не публиковались.',
    'Это анализ стоимости внутренних studies; полный MVP классификации ещё выполняется. Выигрыш модели или admission/cache этим не доказан.',
]) + '\n'
(W.parent / 'outputs/true-mvp-hpo-cost.txt').write_bytes(text.encode('utf-8'))
(W.parent / 'outputs/true-mvp-hpo-cost.json').write_bytes(encoded(report))
with (R / '.gitattributes').open('ab') as out:
    out.write(b'\ndocs/experiments/true-four-stage-tm1/hpo-cost-r1.json -text\n')
print(json.dumps({'inner_studies': len(tasks), 'classification_guided_attempts': phases['guided']['attempted'], 'new_fits': 0, 'outer_scores_read': False}))
