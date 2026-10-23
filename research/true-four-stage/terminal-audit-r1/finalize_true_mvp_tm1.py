"""Combine terminal task audits without retrying a known-denied API ledger.

Preparation only unless --write is passed. No solver, signal or API calls.
Run classification-only frozen verification first; regression audit is reused
only after every ordinary recorded artifact and source hash is rechecked.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import time

W = Path(__file__).resolve().parent
R = W / 'alfa-hack-automl'
ROOT = R / 'test-runs/tm1'
REG_SHA = 'c9f71c3b48e200079d4ac9e9704e0e0ade8b798d3c8d243e110ee2a6236c1447'
OWNER_SOURCE_SHA = '4abc86b070c8f629cf60a77ffa7dcfe24b3a5369945759b3907f51f67d222205'
VERIFIER_SHA = '161a55202d7824f21f954d66455e8449de4056d24fb5912c79a316ac7dca6355'

def load(path):
    return json.loads(path.read_text('utf-8'))

def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if not args.write:
        print(json.dumps({'status': 'preparation_only', 'requires': ['terminal campaign',
            'fresh root closure proof', 'classification-only frozen task audit'],
            'new_fits': 0, 'API_calls': 0}))
        return
    target = W / 'true-four-stage-terminal-summary-tm1.json'
    assert not target.exists(), 'Preserve earlier summaries; no overwrite'
    owner_source = W / 'true_four_stage_mvp.py'
    assert sha(owner_source) == OWNER_SOURCE_SHA
    assert sha(W / 'verify_true_mvp_tm1.py') == VERIFIER_SHA
    assert sha(W / 'tm1-independent-verification-plan-r3.json') == '662b348fb2b4f04a0ea538615804f7f5e0d8a3ed5c7f8343c623ceddc3093f4c'
    helper = module('_tm1_terminal_owner', owner_source)
    helper.configure(W)
    campaign_path = ROOT / 'campaign.json'
    campaign = load(campaign_path)
    assert campaign['status'] != 'running' and campaign['cleanup_confirmed'] is True
    assert campaign['source_unchanged'] is True and campaign['absolute_deadline_unix'] == 1792735776.7207654
    closure_path = W / 'true-mvp-completion-ownership.json'
    closure = load(closure_path)
    assert closure['cleanup_confirmed'] is True and closure['active_owned_processes'] == []
    assert closure['campaign_receipt_sha256'] == sha(campaign_path)
    assert closure['source_input_packet_unchanged'] is True
    assert closure['exec_result_verified'] is True, 'Actual exec completion must be observed'
    guard_path = W / 'tm1-classification-audit-guard-r1/supervisor.json'
    guard = load(guard_path)
    assert guard['status'] == 'PASS' and guard['exit_code'] == 0
    assert guard['cleanup_confirmed'] is True and guard['source_unchanged'] is True
    assert guard['seconds'] <= 300 and guard['peak_owned_rss_mib'] <= 1024 and guard['threads'] == 1
    assert guard['source_sha256'] == VERIFIER_SHA
    assert guard['guard_source_sha256'] == sha(W / 'run_tm1_classification_audit.py')
    assert guard['plan_sha256'] == sha(W / 'tm1-independent-verification-plan-r3.json')
    known = [*closure['launcher_identities'], *closure['tracked_identities']]
    known.extend([guard['owned_root'], guard['child_root']])
    known.extend(guard.get('observed_owned_identities', []))
    known.extend(guard.get('owned_process_identities', []))
    manifest = load(helper.BUNDLE / 'manifest.json')
    helper.guard(manifest)
    _, owner = helper.libraries()
    first = owner.predecessor_snapshot(known)
    assert first['cleanup_confirmed'] and not first['active']
    lock = module('_tm1_terminal_lock', R / 'tools/research_lock.py')
    with lock.ResearchLock(R / 'test-runs/.owned-research.lock'):
        fresh = owner.predecessor_snapshot([*known, *first['tracked']])
        assert fresh['cleanup_confirmed'] and not fresh['active']
        files = {'regression': W / 'true-four-stage-regression-independent-tm1.json',
                 'classification': W / 'true-four-stage-classification-independent-tm1.json'}
        assert sha(files['regression']) == REG_SHA
        summaries = {}
        for name, path in files.items():
            audit = load(path)
            assert audit['new_model_fits'] == audit['api_calls'] == 0
            assert audit['runtime_archive_sha256'] == manifest['archive_sha256']
            assert audit['manifest_sha256'] == campaign['manifest_sha256']
            if name == 'classification':
                assert audit['campaign_sha256'] == sha(campaign_path)
                assert audit['campaign_still_active_at_task_only_verification'] is False
            task = audit['tasks'][name]
            code = 'r' if name == 'regression' else 'c'
            directory = ROOT / code
            runs = directory / 'automl_runs/true4'
            deployed_task = next(t for t in manifest['tasks'] if t['kind'] == name)
            assert deployed_task['code'] == code
            for basename, expected in {**manifest['compiled_sha256'], **deployed_task['files']}.items():
                assert Path(basename).name == basename
                assert sha(directory / basename) == expected, basename
            # Never open, stat or query the private run-budget location.
            for relative, expected in task['actual_artifact_sha256'].items():
                artifact = (runs / relative).resolve()
                assert artifact.is_relative_to(runs.resolve())
                assert not any(p.startswith('run-budget-') for p in artifact.parts)
                assert sha(artifact) == expected, relative
            for relative, expected in task['job_sha256'].items():
                assert sha(runs / relative) == expected, relative
            assert sha(directory / 'supervisor.json') == task['stage_hashes']['supervisor']
            report = load(runs / 'report.json')
            assert sha(directory / 'submission.csv') == report['submission_sha256']
            values = {phase: cut['value'] for phase, cut in task['cuts'].items()}
            assert set(values) == {'primary', 'confirmation'}
            assert abs(sum(values.values()) / 2 - task['selected_cut_mean']) < 1e-12
            summaries[name] = {
                'audit_path': str(path.relative_to(W)), 'audit_sha256': sha(path),
                'core_saved_artifacts_unchanged': True,
                'ordinary_artifacts_rehashed': len(task['actual_artifact_sha256']),
                'job_files_rehashed': len(task['job_sha256']),
                'deployed_runtime_files_rehashed': len(manifest['compiled_sha256']),
                'deployed_task_files_rehashed': len(deployed_task['files']),
                'selected_cuts': values, 'selected_two_cut_mean': task['selected_cut_mean'],
                'metric': task['cuts']['primary']['metric'],
                'independent_procedure_passed': task['procedure_passed'], 'errors': task['errors'],
                'API': task['api'], 'baseline_comparisons': task['baseline_comparisons'],
                'successful_model_families': task['successful_model_families'],
                'actual_teacher_receipts': len(task['actual_teacher_receipts']),
                'selector_recorded_seconds': round(sum(x['selector_seconds'] for x in task['actual_teacher_receipts']), 3),
                'hpo_completed': task['hpo_completed'], 'hpo_guided_successful': task['hpo_guided_successful'],
                'fresh_control_refit': False,
            }
        helper.guard(manifest)
        last = owner.predecessor_snapshot([*known, *fresh['tracked']])
        assert last['cleanup_confirmed'] and not last['active']
        report = {
            'status': 'terminal_core_artifacts_verified_with_explicit_independent_API_limits',
            'recorded_epoch': time.time(), 'campaign_status': campaign['status'],
            'campaign_sha256': sha(campaign_path), 'closure_receipt_sha256': sha(closure_path),
            'classification_audit_guard_sha256': sha(guard_path),
            'original_absolute_deadline_unix': campaign['absolute_deadline_unix'],
            'campaign_finished_unix': campaign['finished_unix'],
            'original_procedure_within_common_deadline': campaign['finished_unix'] <= campaign['absolute_deadline_unix']
                and campaign['finished_monotonic'] <= campaign['common_deadline_monotonic'],
            'posthoc_independent_audit_is_not_extra_training_time': True,
            'tasks': summaries, 'regression_known_API_denial_retried': False,
            'all_independent_procedure_gates_passed': all(t['independent_procedure_passed'] for t in summaries.values()),
            'all_saved_baseline_quality_gates_passed': all(
                b['each_cut_primary_gate_passed'] and b['class_each_cut_gate_passed']
                for t in summaries.values() for b in t['baseline_comparisons'].values()),
            'fresh_owned_processes_absent': True, 'frozen_files_verified': len(manifest['immutable_files']),
            'summary_source_sha256': sha(Path(__file__)),
            'new_fits': 0, 'API_calls': 0, 'private_or_official_score': None,
            'promotion': False, 'official_submission': False,
            'scope': 'Saved selected predictions and pristine labels on reused public research cuts. Preserved historical control evidence, no fresh control refit; no official score claim.',
        }
        with target.open('xb') as out:
            out.write(encoded(report))
        outdir = W.parent / 'outputs'
        (outdir / 'true-four-stage-results.json').write_bytes(encoded(report))
        for name, path in files.items():
            (outdir / f'true-four-stage-{name}-independent.json').write_bytes(path.read_bytes())
        lines = ['Четырёхэтапный MVP tm1 завершён. Независимая проверка сохранённых артефактов.',
            'Все замороженные источники и входы совпадают; принадлежащие нам процессы завершены, очередь свободна.']
        for name, label in [('regression', 'Регрессия'), ('classification', 'Классификация')]:
            task = summaries[name]
            lines.append(f"{label}: {task['metric']} {task['selected_cuts']['primary']:.9f} / {task['selected_cuts']['confirmation']:.9f}; среднее {task['selected_two_cut_mean']:.9f}.")
            lines.append(f"{label}: успешных внутренних Optuna trials {task['hpo_completed']}, из них адаптивных {task['hpo_guided_successful']}.")
        lines.extend([
            'Лучший полный V11/V16 сохраняется: средний RMSE 35.447231558, средний Macro F1 0.659317843.',
            'На регрессии оба среза хуже V11/V16; общий критерий улучшения не выполнен. Продвижения и официального submit нет.',
            'Независимая полнота API ограничена: неизвестные calls/tokens/usage остаются null. Ранее недоступный закрытый журнал регрессии повторно не открывался; данные отчёта процесса выделены отдельно.',
            'Старый исторический MVP не выполнял начальный анализ Qwen и расширение признаков; его метрики и исходные часы сохранены отдельно.',
            'Текущий результат относится к повторно используемым public срезам, без нового контрольного refit и без официального score.',
            'Далее — ранее объявленные проверки исходников и распакованных архивов A/B, затем групповая CV всей процедуры кандидата с фиксированной смесью.',
        ])
        text = '\n'.join(lines) + '\n'
        (outdir / 'true-four-stage-results.txt').write_bytes(text.encode('utf-8'))
        (outdir / 'night-research-status.txt').write_bytes(text.encode('utf-8'))
        sf = W / 'SESSION_STATE.json'
        state = load(sf)
        state['true_four_stage_mvp'].update(status=campaign['status'],
            terminal_summary='work/' + target.name, terminal_summary_sha256=sha(target),
            cleanup_confirmed=True, exec_exit_code=closure['exec_exit_code'],
            terminal_selected_metrics={k: v['selected_two_cut_mean'] for k, v in summaries.items()},
            original_procedure_within_common_deadline=report['original_procedure_within_common_deadline'],
            independent_API_limits_preserved=True, promotion=False)
        state['true_four_stage_mvp']['latest_task_supervision'] = [
            {k: load(ROOT / code / 'supervisor.json').get(k) for k in
             ['kind', 'status', 'cleanup_confirmed', 'seconds', 'seconds_including_verification']}
            for code in ('r', 'c')]
        state['true_four_stage_mvp']['latest_observation'] = {
            'checked_epoch': time.time(), 'campaign_status': campaign['status'],
            'current_task': None, 'fresh_owned_identities': [],
            'cleanup_confirmed': True, 'frozen_manifest_files_verified': len(manifest['immutable_files']),
            'frozen_bytes_unchanged': True, 'original_absolute_deadline_unix': campaign['absolute_deadline_unix']}
        state['mvp']['status'] = 'completed_legacy_procedure_only_scope_corrected'
        state['mvp']['scope_correction']['true_four_stage_public_campaign'] = 'Separate tm1 terminal; see true_four_stage_mvp and its terminal summary. No promotion.'
        state['heartbeat_last'] = {'epoch': time.time(), 'campaign': 'tm1', 'status': campaign['status'],
            'cleanup_confirmed': True, 'active_owned_launchers': [], 'source_unchanged': True,
            'absolute_deadline_unix': campaign['absolute_deadline_unix'], 'official_submission': False}
        state['next'] = [
            'tm1 terminal core metrics/CSV/source verified; independent API limits explicit. Never retry the known-denied regression ledger; preserved V11/V16 remains strongest qualified control.',
            'Next: reviewed/published fixed-half full-agent candidate Stage0 source+unpacked gates, then frozen3fold whole-selection CV under prospective immutable clocks; fresh ownership/lock checks required.',
        ] + [n for n in state['next'] if not n.startswith(('ACTIVE actualfourstage', 'Aftertm1 terminal', 'Frozen canonicalsrc'))]
        for filename in ['true-four-stage-results.txt', 'true-four-stage-results.json', 'true-four-stage-classification-independent.json']:
            rel = 'outputs/' + filename
            if rel not in state['deliverables_current']:
                state['deliverables_current'].append(rel)
        state['updated_epoch'] = time.time()
        pending = sf.with_suffix('.json.tmp')
        pending.write_bytes(encoded(state))
        pending.replace(sf)
    print(json.dumps({'summary': target.name, 'status': report['status'],
        'selected_means': {k: v['selected_two_cut_mean'] for k, v in summaries.items()},
        'known_denied_regression_ledger_retried': False, 'new_fits': 0}))

if __name__ == '__main__':
    main()
