"""One bounded pure filesystem test run; no ML or service is launched."""
from pathlib import Path
import hashlib,importlib.util,json,os,sys,time
import psutil
WORK=Path(__file__).resolve().parent
OUT=WORK/'queue-checks-r2'
PINS={
 'queue-checks/terminal-root-closure.json':'4006102127dd971c97843642754a748fc97199e20505c037f1688a80b8e12d27',
 'conveyor-next-dev/conveyor.py':'3f1078e1234c14a703be31ae75271c0da791cc923eb6ceee66f98de5f98fab5a',
 'conveyor-next-dev/test_conveyor.py':'e911c5a56c85704c989e513516ebeb5f3545cf2c9fe436d0d8205dbb2c81a154',
 'run_lean_mvp_r2.py':'43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
 'loss0/terminal-root-closure.json':'c4916f2e7c7bd38e394bcb2ab33a51daf7a472a2aec8e08ff4b8a79a8fd5ba69',
 'conveyor-kernel-independent-review-r1.json':'0a313dee5b4b8e69c996a813b3cb6890fd4a4e27b3498b5b5537fef0cf6166f1',
 'awake-next-dev/awake_guard.py':'9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b',
 'support_component_coordinator.py':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
 'alfa-hack-automl/src/automl/infrastructure/processes.py':'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
 'alfa-hack-automl/tools/research_lock.py':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def need(value,code):
    if not value:raise RuntimeError(code)
def main():
    need(not OUT.exists(),'exclusive_pure_suite_no_retry')
    start,mono=time.time(),time.monotonic();unix,end=start+60,mono+60
    OUT.mkdir();PINS[Path(__file__).name]=sha(Path(__file__))
    need(all(sha(WORK/n)==h for n,h in PINS.items()),'pinned_source_changed')
    coor=imported('_queue_proven_supervisor',WORK/'run_lean_mvp_r2.py')
    owner=imported('_queue_owner',WORK/'support_component_coordinator.py')
    processes=imported('_queue_processes',WORK/'alfa-hack-automl/src/automl/infrastructure/processes.py')
    locker=imported('_queue_lock',WORK/'alfa-hack-automl/tools/research_lock.py')
    awake_type=imported('_queue_awake',WORK/'awake-next-dev/awake_guard.py').PowerRequestGuard
    state={'status':'starting','start_unix':start,'start_monotonic':mono,'absolute_deadline_unix':unix,
        'common_deadline_monotonic':end,'common_seconds':60,'owned_root':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},
        'supervisors':[],'active_supervisor':None,'error_history':[],'_manifest':{},'model_fits':0,'API_calls':0,'quality_metric':None}
    def persist():coor.save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def absence():
        proof=coor.load(WORK/'loss0/terminal-root-closure.json')
        failed=coor.load(WORK/'queue-checks/terminal-root-closure.json')
        proof={k:proof[k]+failed[k] for k in ['owned_identities','closure_preparer_identities']}
        observer=owner.StrictOwnedObserver();observer.remember(coor.identities(proof['owned_identities']+proof['closure_preparer_identities']))
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],'previous_stage0_not_absent')
    with awake_type('Alfa conveyor pure filesystem checks',10) as awake:
        def frozen(parent_end=None,code='parent_cap'):
            coor.cooperative_checkpoint(awake,end,unix,parent_end,code)
            need(all(sha(WORK/n)==h for n,h in PINS.items()),'source_changed')
        state['_pulse']=lambda:coor.cooperative_checkpoint(awake,end,unix)
        with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
            lock.write_identity(state['owned_root']);absence();persist()
            record=coor.supervise([sys.executable,'-B','-X','utf8',str(WORK/'conveyor-next-dev/test_conveyor.py')],
                WORK/'conveyor-next-dev',OUT/'suite.json','filesystem',mono,40,30,end,unix,60,
                state,persist,frozen,owner,processes,[])
            coor.child_errors(state,record)
            state.update(status=record['status'],passed=record['status']=='ok' and record['exit_code']==0,
                cleanup_confirmed=record['cleanup_confirmed'],source_unchanged=all(sha(WORK/n)==h for n,h in PINS.items()),
                immutable_files=PINS,elapsed_seconds=time.monotonic()-mono,owned_process_identities=record['owned_process_identities'])
            frozen();persist()
    state['awake_guard']=awake.record;state['finished_unix']=time.time();persist()
    print(json.dumps({k:state[k] for k in ['status','passed','cleanup_confirmed','source_unchanged','elapsed_seconds','model_fits','API_calls']}))
    raise SystemExit(0 if state['passed'] and state['cleanup_confirmed'] and state['source_unchanged'] and not state['error_history'] else 1)
if __name__=='__main__':main()
