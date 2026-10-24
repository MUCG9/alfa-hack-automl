"""Fixed24-test entry: initialize standard dependencies before per-test guards.

Only dependency imports may perform native CPU metadata discovery. Network
tripwire is active first. No candidate module/model is imported until byte
binding; the unchanged tests retain every per-test Popen/model/network guard.
The enclosing qualified supervisor owns all imports and metadata subprocesses.
"""
from pathlib import Path
import argparse,hashlib,json,math,runpy,socket,sys,time

HERE=Path(__file__).resolve().parent;WORK=HERE.parent
TEST_SHA='afb77e68bd87003ff33068744b9411d6fc8fa40c44d9e3d853f033f7f754bad1'

def need(v,code):
    if not v:raise RuntimeError(code)

def current_campaign(cfg,manifest_sha,role,read_json):
    """Resolve only the actual hash-bound parent output; no legacy OUT fallback."""
    need(cfg.get('schema')=='standard-repair-qualification-private-v1'
        and cfg.get('readiness')=='READY_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[]
        and cfg.get('common_seconds')==6000,'qualified_current_parent_manifest_required')
    output=Path(cfg['output'])
    need(output.is_absolute() and output.resolve()==output and output.parent==WORK
        and output.is_dir() and not output.is_symlink(),'absolute_actual_parent_output_required')
    state=read_json(output/'campaign.json')
    owner=state.get('owned_root')
    need(state.get('schema')=='standard-repair-qualification-campaign-v1'
        and state.get('status')=='setup' and state.get('manifest_sha256')==manifest_sha
        and state.get('common_seconds')==6000 and type(owner) is dict
        and set(owner)=={'pid','create_time'} and type(owner['pid']) is int and owner['pid']>0
        and type(owner['create_time']) in (int,float) and math.isfinite(owner['create_time'])
        and owner['create_time']>0 and state.get('launch_parent_observation',{}).get('verified') is True,
        'current_parent_campaign_manifest_or_owner_mismatch')
    # Parent supervises the entire child/import subtree. The child is NOT a second
    # resource observer, and never fabricates/advances a parent's sample timestamp.
    coor=WORK/'verified-supervision-next-dev-r2/coordinator.py'
    expected='bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76'
    need(cfg['helpers']['coordinator']==dict(path=str(coor),sha256=expected)
        and cfg['immutable_files'].get(str(coor))==expected,
        'qualified_independent_parent_supervision_required')
    return output,state


def clock_only_checkpoint(state,previous,now,wall):
    """Original clock only; native import gaps are owned by the live supervisor."""
    values=[state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')]
    need(all(type(v) in (int,float) and math.isfinite(v) for v in values+[previous,now,wall]),
        'finite_original_clock_required')
    need(now>=previous and now>=state['start_monotonic'] and wall>=state['start_unix'],
        'original_clock_rollback')
    need(state['absolute_deadline_unix']==state['start_unix']+6000
        and state['common_deadline_monotonic']==state['start_monotonic']+6000,'same_original6000_required')
    need(now<state['common_deadline_monotonic'] and wall<state['absolute_deadline_unix']
        and abs((state['common_deadline_monotonic']-now)-(state['absolute_deadline_unix']-wall))<=5,
        'original_common_deadline')
    return now


def main():
    entered=time.monotonic();previous=entered
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--role',required=True,choices=['source','unpacked'])
    for key in ('test','manifest','manifest-sha256','self-sha256'):p.add_argument('--'+key,required=True)
    a=p.parse_args()
    def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    need(__debug__ and Path(a.manifest).is_absolute() and digest(a.manifest)==a.manifest_sha256
        and digest(__file__)==a.self_sha256,'fixed_technical_bootstrap_source_and_binding')
    cfg=json.loads(Path(a.manifest).read_text('utf-8'))
    output,state=current_campaign(cfg,a.manifest_sha256,a.role,lambda p:json.loads(p.read_text('utf-8')))
    def check():
        nonlocal previous
        previous=clock_only_checkpoint(state,previous,time.monotonic(),time.time())
    need(cfg['immutable_files'].get(str(Path(__file__).resolve()))==a.self_sha256,'bootstrap_in_complete_source_map')
    test=Path(a.test);need(test.is_absolute() and not test.is_symlink(),'absolute_fixed_test')
    if a.role=='source':expected=WORK/'last-submission-repair-next-dev-r4/tests/test_supervised_class_release.py'
    else:
        temporary=Path(state['temporary_root']);need(temporary.is_relative_to((WORK/'t').resolve())
            and temporary.name.startswith('bq-') and not temporary.is_symlink(),'receipt_owned_unpacked_root')
        expected=temporary/'flat/tests/test_supervised_class_release.py'
    need(test==expected and digest(test)==TEST_SHA,'same24_test_source_bytes_required')
    candidate=test.parent.parent/'candidate'
    def frozen():
        check();need(digest(test)==TEST_SHA and digest(a.manifest)==a.manifest_sha256,'test_or_private_binding_changed')
        for name,h in cfg['executor']['members_sha256'].items():check();need(digest(candidate/name)==h,'actual81_candidate_member_changed')
        check()
    frozen();old_network=socket.create_connection;old_argv=sys.argv
    def no_network(*args,**kwargs):raise AssertionError('No network in technical initialization or contracts')
    socket.create_connection=no_network;primary=None
    try:
        # Explicit dependency-only imports; no fit/candidate/entry import here.
        import numpy
        check()
        import numpy.testing
        check()
        import scipy
        import scipy.sparse
        check()
        import sklearn
        import sklearn.metrics
        import sklearn.model_selection
        check();frozen();sys.argv=[str(test),'-v']
        try:runpy.run_path(str(test),run_name='__main__')
        except SystemExit as exc:
            if exc.code not in (0,None):raise
    except BaseException as exc:primary=exc;raise
    finally:
        sys.argv=old_argv;socket.create_connection=old_network
        try:frozen();need(digest(__file__)==a.self_sha256,'technical_entry_posthash_changed')
        except BaseException as secondary:
            if primary is None:raise
            try:primary.add_note('secondary_bootstrap_postcheck:'+type(secondary).__name__)
            except BaseException:pass
    return 0

if __name__=='__main__':raise SystemExit(main())
