"""Post-exit offline suite closure; own30s stays inside the original180s clock."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,math,re,time

WORK=Path(__file__).resolve().parents[1]
ROOT=WORK/'remote-queue-checks-r1'
PINS={
    'run_remote_queue_checks_r1.py':'ae9930e92f61e303780740c5ad78a11b9bc0c00ee3e9514dea8430c126ca0526',
    'run_lean_mvp_r2.py':'43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
    'support_component_coordinator.py':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'alfa-hack-automl/tools/research_lock.py':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
    'remote-experiment-queue-next-dev/remote_queue.py':'d42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49',
    'remote-experiment-queue-next-dev/test_remote_queue.py':'af46ed5174694104d0368e35ac235f83a3425210b3be9dff8e088efeceafe6ed'}

def read(path):return json.loads(path.read_text('utf-8'))
def need(value,code):
    if not value:raise RuntimeError(code)
def local(name):
    target=(WORK/name).resolve()
    need(not Path(name).is_absolute() and target.is_relative_to(WORK),'reference_outside_work')
    return target
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-sha256',required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    p.add_argument('--actual-tool-evidence',required=True)
    a=p.parse_args();begin=time.monotonic();c=read(ROOT/'campaign.json')
    need(__debug__ and bool(a.actual_tool_evidence.strip()),'actual_nonoptimized_terminal_evidence_required')
    out=ROOT/'terminal-root-closure.json';need(not out.exists(),'exclusive_closure_no_rewrite')
    fields=['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic']
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in fields),'actual_terminal_clocks_required')
    need(c['common_seconds']==180 and abs(c['absolute_deadline_unix']-c['start_unix']-180)<1e-6
         and abs(c['common_deadline_monotonic']-c['start_monotonic']-180)<1e-6,'original180_clock_required')
    def check():
        need(time.monotonic()-begin<30,'root_closure30_exhausted')
        need(time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'original180_deadline_exhausted')
        need(abs((c['absolute_deadline_unix']-time.time())-(c['common_deadline_monotonic']-time.monotonic()))<=5,'clock_disagreement')
    def sha(path):
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(2**20),b''):check();h.update(block)
        check();return h.hexdigest()
    need(sha(Path(__file__))==a.self_sha256,'closer_source_changed')
    expected=dict(c['immutable_files']);bad=[]
    for name,digest in PINS.items():
        need(expected.get(name)==digest,'required_suite_source_binding_changed')
    for name,digest in expected.items():
        path=local(name)
        if not path.is_file() or sha(path)!=digest:bad.append(name)
    need(not bad,'immutable_source_or_predecessor_changed')
    coor=imported('_remote_close_coor',local('run_lean_mvp_r2.py'))
    owner=imported('_remote_close_owner',local('support_component_coordinator.py'))
    locker=imported('_remote_close_lock',local('alfa-hack-automl/tools/research_lock.py'))
    import psutil
    known=coor.identities([c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[]))
    predecessor_refs=[]
    for name,digest in c['immutable_files'].items():
        if not name.endswith('.json'):continue
        proof=read(local(name))
        if not isinstance(proof,dict) or 'owned_identities' not in proof or 'closure_preparer_identities' not in proof:continue
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and not proof.get('active_owned_processes') and not proof.get('uncertain_owned'),'prior_closure_not_clean')
        known|=coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
        predecessor_refs.append(dict(path=name,sha256=digest))
    suites=[]
    for ref in c.get('supervisors',[]):
        name=ref['path'];need(sha(local(name))==ref['sha256'],'saved_supervisor_changed')
        expected[name]=ref['sha256'];suite=read(local(name));suites.append(suite)
        known|=coor.identities(suite.get('owned_process_identities',[])+suite.get('observed_worker_roots',[]))
        if suite.get('owned_root'):known|=coor.identities([suite['owned_root']])
    suite_ok=(len(suites)==1 and c['supervisors'][0]['path']=='remote-queue-checks-r1/suite.json'
        and suites[0].get('status')=='ok' and suites[0].get('exit_code')==0
        and suites[0].get('cleanup_confirmed') is True and suites[0].get('cleanup_observation',{}).get('unresolved')==[]
        and not suites[0].get('error_history') and suites[0].get('parent_cap_seconds')==150 and suites[0].get('child_cap_seconds')==120)
    log=ROOT/'suite.log';text=log.read_text('utf-8',errors='replace') if log.exists() else ''
    counts=re.findall(r'Ran (\d+) tests?',text)
    log_ok=counts==['13'] and re.search(r'\nOK\s*$',text) is not None and 'skipped=' not in text
    if log.exists():expected['remote-queue-checks-r1/suite.log']=sha(log)
    test_ast=ast.parse(local('remote-experiment-queue-next-dev/test_remote_queue.py').read_text('utf-8'))
    methods=[n.name for cls in test_ast.body if isinstance(cls,ast.ClassDef) for n in cls.body
             if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
    need(len(methods)==len(set(methods))==13,'exact13_source_methods_required')
    def absent():
        ob=owner.StrictOwnedObserver();ob.remember(known)
        need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],'owned_or_preparer_live_or_denied')
    absent()
    with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'):
        absent();check()
        for name,digest in expected.items():
            path=local(name)
            if not path.is_file() or sha(path)!=digest:bad.append(name)
        passed=(a.actual_exit_code==0 and c.get('passed') is True and c.get('checks_observed')==13
            and c.get('status')=='ok' and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
            and not c.get('error_history') and c.get('active_supervisor') is None and not bad and suite_ok and log_ok
            and c.get('model_fits')==0 and c.get('API_calls')==0 and c.get('awake_guard',{}).get('release_API_verified') is True
            and c['start_unix']<=c['finished_unix']<c['absolute_deadline_unix']
            and c['start_monotonic']<=c['finished_monotonic']<c['common_deadline_monotonic'])
        me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
            need(parent.create_time()==birth,'closer_bootstrap_identity_changed')
            preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        result=dict(status='qualified_offline' if passed else 'offline_suite_failed_or_unqualified',technical_procedure_passed=passed,
            actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=True,source_unchanged=not bad,owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
            closure_preparer_identities=preparers,active_owned_processes=[],uncertain_owned=[],changed_source=bad,
            immutable_and_supervisor_refs_rehashed=len(expected),terminal_predecessor_receipts=predecessor_refs,
            original_common_seconds=180,original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            checks_observed=c.get('checks_observed'),qualified_checks=13 if passed else None,suite_log_sha256=expected.get('remote-queue-checks-r1/suite.log'),
            campaign_sha256=sha(ROOT/'campaign.json'),suite_passed=suite_ok and log_ok,model_fits=0,API_calls=0,quality_metric=None,
            error_history=c.get('error_history',[]),promotion=False,submit=False,official_score=None,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        absent();check()
        with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        check();absent()
    check();print(json.dumps({k:result[k] for k in ['status','technical_procedure_passed','qualified_checks','model_fits','API_calls']}))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
