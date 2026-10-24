"""Fixed16-test entry: initialize standard dependencies before per-test guards.

Only dependency imports may perform native CPU metadata discovery. Network
tripwire is active first. No candidate module/model is imported until byte
binding; the unchanged tests retain every per-test Popen/model/network guard.
The enclosing qualified supervisor owns all imports and metadata subprocesses.
"""
from pathlib import Path
import argparse,hashlib,json,math,runpy,socket,sys,time

HERE=Path(__file__).resolve().parent;WORK=HERE.parent;OUT=WORK/'rq3'
TEST_SHA='fd5b7982a20d1037f8519bd0dab17bbefb7cd262563dc8cc82cdddfab5ae67a5'

def need(v,code):
    if not v:raise RuntimeError(code)

def main():
    entered=time.monotonic();previous=entered
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--role',required=True,choices=['source','unpacked'])
    for key in ('test','manifest','manifest-sha256','self-sha256'):p.add_argument('--'+key,required=True)
    a=p.parse_args()
    def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    need(__debug__ and Path(a.manifest).is_absolute() and digest(a.manifest)==a.manifest_sha256
        and digest(__file__)==a.self_sha256,'fixed_technical_bootstrap_source_and_binding')
    cfg=json.loads(Path(a.manifest).read_text('utf-8'));state=json.loads((OUT/'campaign.json').read_text('utf-8'))
    def check():
        nonlocal previous
        now=time.monotonic();wall=time.time()
        need(now>=previous and now-previous<=10,'dependency_initialization_observation_gap10');previous=now
        need(state['absolute_deadline_unix']==state['start_unix']+6000 and state['common_deadline_monotonic']==state['start_monotonic']+6000,
            'same_original6000_required')
        need(now<state['common_deadline_monotonic'] and wall<state['absolute_deadline_unix']
            and abs((state['common_deadline_monotonic']-now)-(state['absolute_deadline_unix']-wall))<=5,'original_common_deadline')
    need(cfg['immutable_files'].get(str(Path(__file__).resolve()))==a.self_sha256,'bootstrap_in_complete_source_map')
    test=Path(a.test);need(test.is_absolute() and not test.is_symlink(),'absolute_fixed_test')
    if a.role=='source':expected=WORK/'last-submission-repair-next-dev-r2/tests/test_supervised_class_release.py'
    else:
        temporary=Path(state['temporary_root']);need(temporary.is_relative_to((WORK/'t').resolve())
            and temporary.name.startswith('bq-') and not temporary.is_symlink(),'receipt_owned_unpacked_root')
        expected=temporary/'flat/tests/test_supervised_class_release.py'
    need(test==expected and digest(test)==TEST_SHA,'same16_test_source_bytes_required')
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
