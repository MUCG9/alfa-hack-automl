"""Owned outer launch guard; root explicitly assigns one new7200-second clock."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent;P=W/'cache-pilot-launch-r2'
MANIFEST='c4c381b639ca31ed76be0df536b872c149532034f0a8a0427ce6479517a66438'
REVIEW='f2c844540c13d1be956e363e7867ce3fa0ebc2139435fa58ae07eb5ef5310278'
SOURCE='5a2237a401c1ff65029cd7ed2fb463e9e7ac4b0ede98a39bfc9ad14e3f8d769d'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text('utf-8'))
def save(p,x):
    t=p.with_name(p.name+'.pending');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');t.replace(p)
def module(n,p):
    spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def require(x,code):
    if not x:raise RuntimeError(code)
def main():
    pa=argparse.ArgumentParser(description=__doc__);pa.add_argument('--expect-source-sha256',required=True);a=pa.parse_args()
    require(sha(__file__)==a.expect_source_sha256,'outer_launch_source_changed')
    receipt=P/'outer-launch.json';require(not receipt.exists() and not (W/'k1').exists(),'no_retry_or_resume')
    require(sha(P/'manifest.json')==MANIFEST and sha(P/'review.json')==REVIEW and
        sha(W/'cache_pilot_coordinator_r2.py')==SOURCE,'exact_reviewed_source_required')
    m=load(P/'manifest.json')
    def guard():
        require(sha(__file__)==a.expect_source_sha256 and sha(P/'manifest.json')==MANIFEST and sha(P/'review.json')==REVIEW,'outer_review_drift')
        for n,h in m['immutable_files'].items():require(sha(W/n)==h,'immutable_changed:'+n)
    guard()
    owner=module('_cache_outer_owner',W/'support_component_coordinator.py')
    processes=module('_cache_outer_processes',W/'alfa-hack-automl/src/automl/infrastructure/processes.py')
    fence=module('_cache_outer_fence',W/'terminal_identity_fence_r1.py')
    locks=module('_cache_outer_lock',W/'alfa-hack-automl/tools/research_lock.py')
    binding=load(W/m['predecessor_binding']);known=binding['owned_identities']
    def fresh():return fence.strict_orphan_check_with_one_fence(owner,known,
        W/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json')
    fresh()
    me=psutil.Process();launchers=[{'pid':me.pid,'create_time':me.create_time()}];parent=me.parent()
    while parent is not None and parent.name().lower() in {'python.exe','pythonw.exe'}:
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if Path(v).name==Path(__file__).name):break
        launchers.append({'pid':parent.pid,'create_time':parent.create_time()});parent=parent.parent()
    with locks.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        lock.write_identity(launchers[0]);guard();fresh()
    # The coordinator independently repeats admission and acquires this same
    # lock. The outer guard records itself before any heavy child can exist.
    start=time.time();tick=time.monotonic();deadline=start+7200;mono=tick+7200
    r={'status':'launching_owned_cache_pilot','launcher_source_sha256':a.expect_source_sha256,
        'launcher_identities':launchers,'manifest_sha256':MANIFEST,'root_review_sha256':REVIEW,
        'coordinator_source_sha256':SOURCE,'common_start_unix':start,'common_deadline_unix':deadline,
        'common_start_monotonic':tick,'common_deadline_monotonic':mono,'common_seconds':7200,
        'outer_cleanup_reserve_seconds_within_common_clock':15,'whole_memory_bytes':2*2**30,
        'new_clock_assigned_once':True,'old_clocks_resumed':False,'cleanup_confirmed':False,
        'quality_gain':None,'measured_savings':None,'promotion':False,'submit':False,
        'outer_can_certify_campaign':False}
    save(receipt,r)
    sp=W/'SESSION_STATE.json';s=load(sp)
    s['cache_pilot_preparation'].update(status='launching_one_owned_7200_campaign',clock_assigned=True,
        actual_launch='work/cache-pilot-launch-r2/outer-launch.json',actual_campaign='work/k1/campaign.json',
        common_start_unix=start,common_deadline_unix=deadline,launcher_identities=launchers)
    s['updated_epoch']=time.time();save(sp,s)
    child=tree=None;verified=False;observer=owner.StrictOwnedObserver();peak=me.memory_info().rss
    try:
        command=[sys.executable,'-B','-X','utf8','-u',str(W/'cache_pilot_coordinator_r2.py'),
            '--work-root',str(W),'--packet','cache-pilot-launch-r2','--manifest-sha256',MANIFEST,
            '--launch','--common-start-unix',repr(start),'--deadline-unix',repr(deadline)]
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','LOCALAPPDATA'}}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
            OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        with (P/'outer-launch.log').open('xb') as stream:
            child=subprocess.Popen(command,cwd=W.parent,env=env,stdin=subprocess.DEVNULL,
                stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            root=psutil.Process(child.pid);rootid=(root.pid,root.create_time());observer.remember([rootid])
            tree=processes.ProcessTree(child);observer.remember(tree.members);verified=rootid in tree.members
            require(verified,'outer_child_identity_unverified')
            r.update(status='owned_cache_coordinator_running',owned_root={'pid':rootid[0],'create_time':rootid[1]});save(receipt,r)
            last=0.
            while True:
                live=observer.observe();require(not observer.denials,'outer_owned_identity_denial');tree.members.update(live)
                total=me.memory_info().rss
                for ancestor in launchers[1:]:
                    try:
                        p=psutil.Process(ancestor['pid'])
                        if p.create_time()==ancestor['create_time']:total+=p.memory_info().rss
                    except psutil.NoSuchProcess:pass
                for p in live.values():
                    try:total+=p.memory_info().rss
                    except psutil.NoSuchProcess:pass
                peak=max(peak,total);require(total<=2*2**30,'outer_whole_tree_memory_limit')
                require(time.monotonic()<mono-15 and time.time()<deadline-15,'outer_common_cleanup_reserve_exhausted')
                if time.monotonic()-last>10:
                    r.update(seconds=time.monotonic()-tick,peak_outer_owned_rss_mib=peak/2**20,
                        owned_process_identities=[{'pid':p,'create_time':c} for p,c in sorted(observer.seen)])
                    save(receipt,r);last=time.monotonic()
                if child.poll() is not None:break
                time.sleep(.25)
        r.update(status='outer_child_completed',coordinator_exit_code=child.returncode)
    except BaseException as e:r.update(status='outer_launch_technical_failure',exception_type=type(e).__name__,failure_code=str(e) if isinstance(e,RuntimeError) else 'outer_guard_operation_failed')
    finally:
        r.update(owner.cleanup_owned(child,tree,observer,verified,processes.ProcessTree))
        try:guard();require(time.monotonic()<mono and time.time()<deadline,'outer_terminal_common_clock_exhausted');r['source_unchanged']=True
        except BaseException as e:r.update(status='outer_launch_technical_failure',source_unchanged=False,terminal_exception=type(e).__name__)
        if not r['cleanup_confirmed']:r['status']='outer_launch_technical_failure'
        def invalidate_campaign():
            campaign=W/'k1/campaign.json'
            if not campaign.exists():return
            raw=campaign.read_bytes();prior=P/'campaign-before-outer-invalidation.json'
            if not prior.exists():
                with prior.open('xb') as out:out.write(raw)
            c=load(campaign)
            c.update(status='outer_guard_technical_failure',qualification='FAIL',complete_six=False,
                mechanism_pass=False,positive_descriptive_time_label=False,
                total_parent_delta_OFF_minus_ON=None,measured_savings=None,quality_gain=None,
                full_agent_gain=None,outer_can_certify_campaign=False,
                outer_failure_receipt='cache-pilot-launch-r2/outer-launch.json',
                preserved_campaign_before_outer_invalidation_sha256=sha(prior))
            for slot in c.get('slots',[]):
                slot.update(qualified=False,paired_speedup=None,mechanism_pass=False)
            if isinstance(c.get('audit'),dict):
                c['audit'].update(explicitly_unqualified_after_outer_failure=True,qualified_result=None)
            save(campaign,c);r['campaign_qualification_overridden']=True
        r['outer_can_certify_campaign']=(r['status']=='outer_child_completed' and r.get('coordinator_exit_code')==0
            and r.get('cleanup_confirmed') is True and r.get('source_unchanged') is True)
        if not r['outer_can_certify_campaign']:invalidate_campaign()
        r.update(end_unix=time.time(),seconds=time.monotonic()-tick,peak_outer_owned_rss_mib=peak/2**20)
        save(receipt,r)
        if time.monotonic()>=mono or time.time()>=deadline:
            r.update(status='outer_launch_technical_failure',outer_can_certify_campaign=False,
                failure_code='outer_terminal_receipt_write_over_common_cap',seconds=time.monotonic()-tick,end_unix=time.time())
            invalidate_campaign();save(receipt,r)
    print(json.dumps({'status':r['status'],'coordinator_exit_code':r.get('coordinator_exit_code'),'cleanup_confirmed':r['cleanup_confirmed'],'seconds':r['seconds']}))
    raise SystemExit(0 if r['status']=='outer_child_completed' and r.get('coordinator_exit_code')==0 else 1)
if __name__=='__main__':main()
