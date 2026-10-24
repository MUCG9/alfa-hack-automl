"""Focused no-network/no-fit contracts; old supervisor must own this process."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import ast,copy,hashlib,importlib.util,json,os,sys,tempfile,time,unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'execution-r3'))
import portable_harness as h
import experiment_driver as d
import fixedcaller as caller
spec=importlib.util.spec_from_file_location('actual_queue_fixture',HERE/'refs/remote_queue.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
REAL_POPEN=h.subprocess.Popen
REAL_SELECTOR=h.selectors.DefaultSelector
REAL_TIME=time
OBSERVATIONS=[]
class StopBeforeModel(Exception):pass
class SimTime:
    def __init__(self,release_after=12.):self.m=100.;self.w=100000.;self.release=100.+release_after
    def monotonic(self):return self.m
    def time(self):return self.w+self.m
    def advance(self,v):self.m+=v
    def sleep(self,v):self.advance(v);REAL_TIME.sleep(.001)
class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cooperative-fixture-');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def context(self,seconds=5400):
        now=REAL_TIME.time();claim=dict(schema=1,job_id='fixture-job',job_sha256='1'*64,dispatch_sha='d'*40,worker_id='fixture-worker',claimed_at_unix=now-1,deadline_unix=now-1+seconds,nonce='fixture')
        raw=q.encode(claim);p=self.root/'claim.json';p.write_bytes(raw)
        ctx=dict(local_claim_path=str(p),local_claim_sha256=q.digest(raw),claim_sha='a'*40,job_id=claim['job_id'],worker_id=claim['worker_id'],dispatch_sha=claim['dispatch_sha'],wall_seconds=seconds,clock_path=str(self.root/'clock.json'))
        return ctx,claim
    def clock(self):
        ctx,claim=self.context();return h.bootstrap_clock(ctx,initialize=True),ctx,claim
    def git(self,code='import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())',data=b'fixture',sim=None,step=.5,parent=None,ok=True):
        if sim:
            clock=h.Clock(sim.time(),sim.monotonic(),sim.time()+900,sim.monotonic()+900,sim.monotonic(),context={'fixture':True},telemetry=[])
        else:
            clock,_,_=self.clock()
        calls=[]
        def spawn(argv,**kw):
            self.assertEqual(argv[0],'git');self.assertIn('protocol.ext.allow=never',argv)
            self.assertFalse(kw['shell']);self.assertEqual(kw['env']['GIT_TERMINAL_PROMPT'],'0')
            self.assertEqual(kw['env']['GCM_INTERACTIVE'],'Never');self.assertNotIn('OPENAI_API_KEY',kw['env'])
            calls.append(argv)
            return REAL_POPEN([sys.executable,'-B','-c',code],**kw)
        class Selecting:
            def __init__(inner):inner.selector=REAL_SELECTOR()
            def __enter__(inner):return inner
            def __exit__(inner,*args):inner.selector.close()
            def register(inner,*a,**kw):return inner.selector.register(*a,**kw)
            def unregister(inner,*a):return inner.selector.unregister(*a)
            def get_map(inner):return inner.selector.get_map()
            def select(inner,timeout):
                if sim:
                    sim.advance(step)
                    # Deterministic readiness latency, independent of process
                    # startup speed or host psutil enumeration overhead.
                    if sim.m<sim.release:return []
                return inner.selector.select(.001 if sim else timeout)
        patches=[mock.patch.object(h.subprocess,'Popen',side_effect=spawn),mock.patch.object(h.selectors,'DefaultSelector',Selecting)]
        if sim:patches.append(mock.patch.object(h,'time',sim))
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            g=h.cooperative_git(q,self.root,clock,parent)
            self.last_clock=clock;self.last_git=g;self.last_calls=calls
            try:return g.run('status','--porcelain',data=data,ok=ok)
            finally:OBSERVATIONS.extend(dict(v,simulated_clock=sim is not None) for v in clock.telemetry)
    def test_exact_binary_stdin_stdout_and_environment(self):
        payload=bytes(range(256))*1000
        with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'fixture-only-value','GIT_CONFIG_COUNT':'7'}):self.assertEqual(self.git(data=payload),payload)
        self.assertTrue(self.last_clock.telemetry[-1]['cleanup_confirmed'])
    def test_pipe_pressure_no_stdin_loss_or_deadlock(self):
        code='import sys;sys.stderr.buffer.write(b"e"*200000);sys.stderr.flush();sys.stdout.buffer.write(sys.stdin.buffer.read())'
        payload=b'x'*500000;self.assertEqual(self.git(code,payload),payload)
    def test_nonzero_ok_false_preserves_completed_bytes(self):
        result=self.git('import sys;sys.stdout.buffer.write(b"a\\x00b");sys.stderr.buffer.write(b"ordinary");raise SystemExit(7)',ok=False)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(7,b'a\x00b',b'ordinary'))
        self.assertEqual(result.args[0],'git')
    def test_input_cap_fails_without_a_command(self):
        with self.assertRaisesRegex(h.Blocked,'git_input_cap'):self.git(data=b'x'*(4194304+1))
        self.assertEqual(self.last_calls,[])
    def test_simulated_over10_latency_mainthread_ticks(self):
        sim=SimTime();self.assertEqual(self.git('import time;time.sleep(.04);print("done")',sim=sim,step=.3),b'done\n')
        self.assertGreater(sim.m-100,10);self.assertLess(sim.m-100,45)
        self.assertGreater(self.last_clock.telemetry[-1]['ticks'],20)
        self.assertLessEqual(self.last_clock.telemetry[-1]['max_gap_seconds'],.5+1e-9)
    def test_uninstrumented_gap_fails_before_git(self):
        clock,ctx,_=self.clock();clock.last-=11
        with mock.patch.object(h.subprocess,'Popen') as spawn:
            with self.assertRaises(h.Blocked):h.cooperative_git(q,self.root,clock).run('status')
            spawn.assert_not_called()
    def test_original45_command_timeout(self):
        with self.assertRaises(Exception):self.git('import time;time.sleep(.3)',sim=SimTime(release_after=60),step=2.)
        self.assertGreaterEqual(self.last_clock.telemetry[-1]['seconds'],45)
    def test_parent_deadline_exhaustion_is_fatal(self):
        with self.assertRaises(h.Blocked):self.git('import time;time.sleep(.1)',sim=SimTime(),parent=102.)
    def test_stdout_cap_is_fatal(self):
        with self.assertRaisesRegex(h.Blocked,'git_output_cap'):self.git('import sys;sys.stdout.buffer.write(b"x"*(4194304+65536))',data=None)
    def test_stderr_cap_is_fatal(self):
        with self.assertRaisesRegex(h.Blocked,'git_stderr_cap'):self.git('import sys;sys.stderr.buffer.write(b"x"*(4194304+65536))',data=None)
    def test_nonzero_and_auth_errors_remain_safe(self):
        with self.assertRaisesRegex(q.QueueError,'git_operation_failed'):self.git('raise SystemExit(7)')
        # One independent real owned child per subcase, not a retry of an experiment.
        self.root=self.root/'second-fixture';self.root.mkdir()
        with self.assertRaisesRegex(q.QueueError,'git_authentication_blocked'):self.git('import sys;sys.stderr.write("authentication failed");raise SystemExit(1)')
    def test_observation_denial_stays_fatal(self):
        with mock.patch.object(h.OwnedTree,'sample',side_effect=h.psutil.AccessDenied(0)):
            with self.assertRaises(Exception):self.git('pass')
        self.assertFalse(self.last_clock.telemetry[-1]['cleanup_confirmed'])
    def test_RSS_limit_is_fatal(self):
        with mock.patch.object(h.OwnedTree,'sample',return_value=1600*2**20):
            with self.assertRaisesRegex(h.Blocked,'git_RSS_cap'):self.git('pass')
    def test_cleanup_denial_cannot_become_success(self):
        with mock.patch.object(h.OwnedTree,'absent',return_value=False):
            with self.assertRaisesRegex(h.Blocked,'git_cleanup_or_observation_failed'):self.git('pass')
    def test_local_claim_tamper_before_network(self):
        ctx,claim=self.context();Path(ctx['local_claim_path']).write_text('{}')
        with mock.patch.object(h.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(h.Blocked,'local_claim_byte_pin'):h.bootstrap_clock(ctx,initialize=True)
            spawn.assert_not_called()
    def test_oversized_local_claim_is_refused_boundedly(self):
        ctx,_=self.context();Path(ctx['local_claim_path']).write_bytes(b'x'*32769)
        with self.assertRaisesRegex(h.Blocked,'local_claim_byte_pin'):h.bootstrap_clock(ctx,initialize=True)
    def test_retained_origin_and_sample_tamper_fail(self):
        clock,ctx,claim=self.clock();p=Path(ctx['clock_path']);state=h.load(p);state['last']-=11;p.write_text(json.dumps(state))
        with self.assertRaises(h.Blocked):h.bootstrap_clock(ctx)
        p.write_text(json.dumps(dict(origin_sha256=h.canonical(clock.origin),last=clock.last)))
        origin_path=p.with_name(p.name+'.origin.json');origin=h.load(origin_path);origin['mono_deadline']+=1;origin_path.write_text(json.dumps(origin))
        with self.assertRaisesRegex(h.Blocked,'clock_origin_changed'):h.bootstrap_clock(ctx)
    def test_missing_retained_evidence_never_reinitializes(self):
        _,ctx,_=self.clock();Path(ctx['clock_path']).unlink()
        with self.assertRaisesRegex(h.Blocked,'missing_retained_clock_evidence'):h.bootstrap_clock(ctx,initialize=True)
    def test_claim_cannot_rebase_to_another_clock_path(self):
        _,ctx,_=self.clock();changed=dict(ctx,clock_path=str(self.root/'different.json'))
        with self.assertRaisesRegex(h.Blocked,'claim_clock_context_changed'):h.bootstrap_clock(changed,initialize=True)
    def test_audit_handoff_retains_original_origin_and_sample(self):
        clock,ctx,claim=self.clock();snap=clock.snapshot();other=h.bootstrap_clock(ctx,handoff=snap,handoff_sha=h.canonical(snap))
        self.assertEqual(other.origin,clock.origin);self.assertEqual(other.mono_deadline,clock.mono_deadline)
        self.assertIsNone(other.evidence_path);bad=copy.deepcopy(snap);bad['last']-=11
        with self.assertRaises(h.Blocked):h.bootstrap_clock(ctx,handoff=bad,handoff_sha=h.canonical(snap))
    def test_wall_common_and_cleanup_deadline_fail(self):
        clock,_,_=self.clock();clock.wall_deadline=REAL_TIME.time()-1
        with self.assertRaises(h.Blocked):clock.tick()
        sim=SimTime()
        original_cleanup=h.OwnedTree.cleanup
        def late(tree,tick):
            result=original_cleanup(tree,tick);sim.advance(1000);tick();return result
        with mock.patch.object(h.OwnedTree,'cleanup',late):
            with self.assertRaises(Exception):self.git('pass',sim=sim,step=.1)
    def test_terminal_late_observation_never_succeeds(self):
        sim=SimTime();original=h.terminal_poll
        def late(proc,end):
            value=original(proc,end);sim.advance(1000);return value
        with mock.patch.object(h,'terminal_poll',side_effect=late):
            with self.assertRaises(Exception):self.git('pass',sim=sim,step=.1)
    def test_45_limit_includes_successful_cleanup_boundary(self):
        sim=SimTime(release_after=1);original=h.OwnedTree.cleanup
        def late(tree,tick):
            result=original(tree,tick)
            while sim.m<145.1:sim.advance(min(.4,145.1-sim.m));tick()
            return result
        with mock.patch.object(h.OwnedTree,'cleanup',side_effect=late,autospec=True):
            with self.assertRaisesRegex(q.QueueError,'git_operation_timeout'):self.git('pass',sim=sim,step=.1)
    def test_unchanged_queue_file_and_source_pin(self):
        self.assertEqual(h.sha(HERE/'refs/remote_queue.py'),d.QUEUE_SHA)
        clock,ctx,_=self.clock()
        with mock.patch.object(h,'cooperative_git') as g:
            with self.assertRaisesRegex(h.Blocked,'queue_source_pin'):h.queue_admission('.',str(HERE/'refs/remote_queue.py'),'0'*64,ctx['job_id'],ctx['worker_id'],ctx['claim_sha'],clock)
            g.assert_not_called()
    def test_driver_and_model_same_clock_before_admission(self):
        clock,ctx,_=self.clock();seen=[]
        def admission(*args,**kwargs):seen.append(args[6]);raise StopBeforeModel()
        with mock.patch.object(h,'queue_admission',side_effect=admission):
            with self.assertRaises(StopBeforeModel):d.execute('.',str(HERE/'refs/remote_queue.py'),ctx['job_id'],ctx['worker_id'],ctx['claim_sha'],str(self.root),'prepared',ctx['clock_path'],clock,ctx)
            with self.assertRaises(StopBeforeModel):h.model_driver('.',str(HERE/'refs/remote_queue.py'),d.QUEUE_SHA,ctx['job_id'],ctx['worker_id'],ctx['claim_sha'],self.root,{},'unused','unused',ctx['clock_path'],'unused','unused',common_clock=clock)
        self.assertEqual(seen,[clock,clock])
    def test_audit_child_bootstraps_before_network(self):
        clock,ctx,_=self.clock();snap=clock.snapshot();request=dict(repo='fixture',queue_file=str(HERE/'refs/remote_queue.py'),job_id=ctx['job_id'],worker=ctx['worker_id'],claim_sha=ctx['claim_sha'],clock_context=ctx,clock_handoff=snap,clock_handoff_sha256=h.canonical(snap),clock_path=ctx['clock_path'])
        p=self.root/'audit.json';p.write_text(json.dumps(request));seen=[]
        def admission(*args):seen.append(args[6]);raise StopBeforeModel()
        with mock.patch.object(h,'queue_admission',side_effect=admission):
            with self.assertRaises(StopBeforeModel):d.audit_child(p,h.sha(p))
        self.assertEqual(seen[0].origin,clock.origin)
    def test_caller_bootstrap_execute_preserve_identical_clock(self):
        clockctx,claim=self.context();root=self.root/'newroot';root.mkdir();exe=root/'execution-r3';exe.mkdir()
        for n in caller.EXECUTION:(exe/n).write_bytes((HERE/'execution-r3'/n).read_bytes())
        job=dict(source_refs=[dict(path='fixedcaller.py',sha256=h.sha(HERE/'fixedcaller.py'))]);binding=dict(execution_sha256=caller.EXECUTION)
        seen=[]
        def admission(*args):seen.append(args[6]);return claim,job,binding
        def execute(*args):self.assertIs(args[8],seen[0]);self.assertEqual(args[9],clockctx);raise StopBeforeModel()
        queue=HERE/'research/remote-experiments/queue/remote_queue.py'
        with mock.patch.object(h,'queue_admission',side_effect=admission),mock.patch.object(d,'execute',side_effect=execute):
            with self.assertRaises(StopBeforeModel):caller.invoke(HERE,queue,root,'prepared',clockctx)
        self.assertEqual(seen[0].context,clockctx)
    def test_protected_queue_validation_semantic_parity_and_remote_mismatch(self):
        ctx,local=self.context();worker=ctx['worker_id'];jobid=ctx['job_id'];dispatch=ctx['dispatch_sha'];claimoid=ctx['claim_sha'];dep='fixture-source';depoid='e'*40;resultoid='f'*40
        caps=dict(wall_seconds=5400,cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048,max_fits=16,max_api_calls=0)
        sourcecaps=dict(caps,wall_seconds=1800,max_fits=0)
        approval_path='research/remote-experiments/reviews/'+dep+'.json';bind_path='research/remote-experiments/sources/'+jobid+'-execution-binding.json';source_path='research/remote-experiments/sources/fixture.json'
        approval=q.encode(dict(schema=1,job_id=dep,result_sha=resultoid,worker_id=worker,approved_for_bounded_experiments=True,caps=caps));bind=q.encode(dict(job_id=jobid,worker_id=worker,entrypoint='automl_worker.py'))
        base=dict(schema=1,readiness='ready',objective='fixture only',dependencies=[],expected_outputs=['summary.txt'])
        sourcejob=dict(base,id=dep,kind='source_only',caps=sourcecaps,source_refs=[dict(path=source_path,sha256=q.digest(b'{}'))])
        targetjob=dict(base,id=jobid,kind='bounded_experiment',caps=caps,dependencies=[dep],source_refs=[dict(path=approval_path,sha256=q.digest(approval)),dict(path=bind_path,sha256=q.digest(bind))])
        jr=q.encode(targetjob);sr=q.encode(sourcejob);local['job_sha256']=q.digest(jr);raw=q.encode(local);Path(ctx['local_claim_path']).write_bytes(raw);ctx['local_claim_sha256']=q.digest(raw)
        sc=dict(local,job_id=dep,job_sha256=q.digest(sr),deadline_unix=local['claimed_at_unix']+1800);scr=q.encode(sc)
        report=dict(schema=1,status='completed',start_unix=sc['claimed_at_unix'],deadline_unix=sc['deadline_unix'],finished_unix=sc['claimed_at_unix']+.1,metrics={},usage=dict(wall_seconds=.1,cpu_threads=None,worker_memory_mib=None,whole_memory_mib=None,fits=0,api_calls=0),first_error=None,secondary_errors=[])
        receipt=dict(schema=1,job_id=dep,job_sha256=q.digest(sr),dispatch_sha=dispatch,claim_sha=depoid,worker_id=worker,submitted_at_unix=sc['claimed_at_unix']+.2,nonce='fixture',report=report,artifacts_sha256={'summary.txt':q.digest(b'fixture')},verification='remote_reported_requires_independent_verification',promotion=False)
        packets={claimoid:{'claim.json':raw,'job.json':jr,'AGENT_PROMPT.txt':q.prompt(q.decode(jr)).encode()},depoid:{'claim.json':scr,'job.json':sr,'AGENT_PROMPT.txt':q.prompt(q.decode(sr)).encode()},resultoid:{'claim.json':scr,'job.json':sr,'result.json':q.encode(receipt),'artifacts/summary.txt':b'fixture'}}
        paths={q.JOB_DIR+'/'+jobid+'.json':jr,q.JOB_DIR+'/'+dep+'.json':sr,approval_path:approval,bind_path:bind,source_path:b'{}'};observed=[]
        class GitFixture:
            def fetch(_,ref):
                observed.append(ref)
                return {q.CLAIMS+jobid:claimoid,q.CLAIMS+dep:depoid,q.RESULTS+dep:resultoid}[ref]
            def files(_,oid):return packets[oid]
            def parent(_,oid):return depoid if oid==resultoid else dispatch
            def blob(_,oid,path,*args):return paths[path]
            def run(_, *args,**kwargs):
                observed.append(args[0])
                if args[0]=='ls-tree':return ('\n'.join(k for k in paths if k.startswith(q.JOB_DIR+'/'))+'\n').encode()
                if '--format=%H' in args:return (dispatch+'\n').encode()
                return b''
        fixture=GitFixture();clock=h.bootstrap_clock(ctx,initialize=True)
        fake_spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _:None))
        with mock.patch('importlib.util.spec_from_file_location',return_value=fake_spec),mock.patch('importlib.util.module_from_spec',return_value=q),mock.patch.object(h,'cooperative_git',return_value=fixture):
            actual=h.queue_admission('.',HERE/'refs/remote_queue.py',d.QUEUE_SHA,jobid,worker,claimoid,clock)
            self.assertEqual(actual[0],local);self.assertEqual(actual[1],targetjob);self.assertIn(q.RESULTS+dep,observed);self.assertIn('ls-tree',observed)
            changed=dict(local,nonce='different');packets[claimoid]['claim.json']=q.encode(changed)
            with self.assertRaisesRegex(h.Blocked,'remote_local_claim_mismatch'):h.queue_admission('.',HERE/'refs/remote_queue.py',d.QUEUE_SHA,jobid,worker,claimoid,clock)
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests);methods=[t._testMethodName for t in suite]
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output=dict(tests_run=result.testsRun,unique_methods=len(set(methods)),methods=methods,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),actual_unittest_subcases=0,passed=result.wasSuccessful(),command_observations=OBSERVATIONS,observed_adapter_commands=len(OBSERVATIONS),fits=0,api_calls=0)
    Path(sys.argv[1]).write_text(json.dumps(output,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
