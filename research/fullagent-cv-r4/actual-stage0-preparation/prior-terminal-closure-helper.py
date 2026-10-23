"""Close the failed technical attempt using exact, fresh owned identities only."""
from pathlib import Path
import hashlib
import importlib.util
import json
import time
import psutil

W=Path(__file__).resolve().parent
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    return json.loads(p.read_text('utf-8'))
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
assert sha(W/'build_fullagent_cv_binding.py')=='84a519c3f6a916c82c568be1944f5c9e0fac6409b5ac50f8fbafac2a7398b5ff'
assert sha(W/'fullagent_cv_coordinator.py')=='45dd8bc9e56b4874e43e051cf279f0497c0b82f628d5c1db7cb6ec2e2bad8a24'
builder=module('_cv_failure_closure_builder',W/'build_fullagent_cv_binding.py')
owner=module('_cv_failure_closure_owner',W/'fullagent-cv-launch-r1/ownership.py')
lockmod=module('_cv_failure_closure_lock',W/'fullagent-cv-launch-r1/research_lock.py')
assert sha(W/'fullagent-cv-launch-r1/ownership.py')=='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
assert sha(W/'fullagent-cv-launch-r1/research_lock.py')=='78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'
paths=['f3/stage0.json','fullagent-cv-stage0-launch-r1.json','f3/gate-a_source.json',
    'f3/gates/a_source/results.json','f3/gates/a_source/test_error_preparation.py.log']
files={n:sha(W/n) for n in paths}
stage,launch,gate,result=[load(W/n) for n in paths[:4]]
assert stage['status']=='failed_stage0' and stage['cleanup_confirmed'] is True and stage['source_unchanged'] is True
assert launch['status']=='stage0_exec_completed' and launch['exec_exit_code']==1
assert gate['cleanup_confirmed'] is True and gate['exit_code']==1
assert result['unique_checks_passed']==435 and result['unique_checks_skipped']==0
assert result['fixture_cleanup_confirmed'] is True and result['source_unchanged'] is True
assert len(result['checks'])==46
assert [r['script'] for r in result['checks'] if not r['passed']]==['test_error_preparation.py']
known_tuples=builder.identities(stage)|builder.identities(launch)|builder.identities(gate)
known=[{'pid':p,'create_time':c} for p,c in sorted(known_tuples)]
fresh_before=builder.strict_orphan_check(owner,known)
manifest=load(W/'fullagent-cv-launch-r1/manifest.json')
def guard():
    for n,expected in manifest['immutable_files'].items():
        assert sha(W/n)==expected,n
    for n,expected in files.items():
        assert sha(W/n)==expected,n
with lockmod.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
    lock.write_identity({'pid':psutil.Process().pid,'create_time':psutil.Process().create_time()})
    guard()
    tracked=builder.strict_orphan_check(owner,fresh_before+known)
    receipt={
        'status':'failed_technical_Stage0_terminal_owned_absence_confirmed',
        'recorded_epoch':time.time(),'stage_status':stage['status'],
        'stage_receipt':'f3/stage0.json','stage_receipt_sha256':files['f3/stage0.json'],
        'launcher_receipt':'fullagent-cv-stage0-launch-r1.json',
        'launcher_receipt_sha256':files['fullagent-cv-stage0-launch-r1.json'],
        'original_absolute_deadline_unix':stage['absolute_deadline_unix'],
        'original_stage_seconds':3600,'clock_reset_or_retry':False,
        'exec_session':73088,'exec_exit_code_observed_by_root':1,
        'cleanup_confirmed':True,'active_owned_processes':[],
        'fresh_absence_before_and_inside_canonical_lock':True,
        'strict_known_parent_orphan_scan':True,'no_process_signalled':True,
        'launcher_identities':[launch['launcher_identity'],launch['coordinator_launcher_identity']],
        'tracked_identities':tracked,
        'source_unchanged':True,'immutable_files_rehashed':len(manifest['immutable_files']),
        'source_checks_observed':451,'source_checks_passed':435,'source_checks_skipped':0,
        'failed_script':'test_error_preparation.py','test_errors':2,
        'missing_deployed_fixture_metadata':'docs/handoff/public_inputs.json',
        'remaining_three_gates_status':'not_attempted_due_prior_technical_gate_failure',
        'CV_started':False,'model_quality_inferred':False,'metrics':None,
        'evidence_sha256':files,'helper_sha256':sha(Path(__file__)),
        'promotion':False,'official_submission':False,
    }
    guard()
    assert builder.strict_orphan_check(owner,tracked+known)==tracked
    with (W/'fullagent-cv-stage0-terminal-ownership-r1.json').open('xb') as out:
        out.write((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'cleanup_confirmed':True,'tracked_count':len(tracked),'all_absent':True,'new_fits':0,'process_signals':0}))
