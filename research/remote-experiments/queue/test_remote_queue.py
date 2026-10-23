"""Offline tests only. Never use the user's repo, network, models or credentials."""
from pathlib import Path
import copy,json,subprocess,tempfile,threading,time,unittest,uuid
from unittest.mock import patch
import remote_queue as q

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='queue-bare-test-');self.root=Path(self.tmp.name)
        self.remote=self.root/'remote.git';self.a=self.root/'a';self.b=self.root/'b'
        self.git(None,'init','--bare',str(self.remote))
        self.git(None,'clone',str(self.remote),str(self.a))
        self.git(self.a,'config','user.name','Queue Test');self.git(self.a,'config','user.email','test@local.invalid')
        self.git(self.a,'config','core.autocrlf','false')
        (self.a/'source.py').write_text('answer = 42\n',encoding='utf-8')
        self.job=dict(schema=1,id='remote-one',kind='source_only',readiness='ready',objective='Review pinned source only; no fits or API.',
            caps=dict(wall_seconds=900,cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048,max_fits=0,max_api_calls=0),
            source_refs=[dict(path='source.py',sha256=q.digest((self.a/'source.py').read_bytes()))],dependencies=[],expected_outputs=['changes.patch','notes.txt'])
        p=self.a/q.JOB_DIR/'remote-one.json';p.parent.mkdir(parents=True);p.write_bytes(q.encode(self.job))
        self.git(self.a,'add','.');self.git(self.a,'commit','-m','dispatch')
        self.git(self.a,'push','origin','HEAD:refs/heads/research/remote-dispatch')
        self.dispatch=self.git(self.a,'rev-parse','HEAD').decode().strip()
        self.git(None,'clone','--no-checkout',str(self.remote),str(self.b))
        self.ga,self.gb=q.Git(self.a),q.Git(self.b)
        self.art=self.root/'art';self.art.mkdir();(self.art/'changes.patch').write_text('--- a/source.py\n+++ b/source.py\n@@ -1 +1 @@\n-answer = 42\n+answer = 43\n',encoding='utf-8')
        (self.art/'notes.txt').write_text('Public source review only.\n',encoding='utf-8')
    def tearDown(self):self.tmp.cleanup()
    def git(self,repo,*args,data=None):
        cmd=['git']+(['-C',str(repo)] if repo else [])+list(args)
        r=subprocess.run(cmd,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        self.assertEqual(r.returncode,0,'offline_git_failed');return r.stdout
    def owned(self):
        return q.claim(self.ga,self.dispatch,'remote-one','worker-a')
    def report(self,c,status='completed'):
        r=dict(schema=1,status=status,start_unix=c['claimed_at_unix'],deadline_unix=c['deadline_unix'],finished_unix=time.time(),
            metrics={'rmse':None},usage=dict(wall_seconds=0,cpu_threads=1,worker_memory_mib=None,whole_memory_mib=None,fits=0,api_calls=0),
            first_error=None,secondary_errors=[])
        if status!='completed':r['first_error']=dict(code='bounded_timeout',detail='No metric was qualified.')
        return r
    def publish_bad(self,owned,change,artifact=None):
        _,c,_,cf=q.read_claim(self.ga,'remote-one')
        r=dict(schema=1,job_id='remote-one',job_sha256=c['job_sha256'],dispatch_sha=c['dispatch_sha'],claim_sha=owned['claim_sha'],
            worker_id='worker-a',submitted_at_unix=time.time(),nonce=uuid.uuid4().hex,report=self.report(c),artifacts_sha256={},
            verification='remote_reported_requires_independent_verification',promotion=False)
        change(r);files={'job.json':cf['job.json'],'claim.json':cf['claim.json'],'result.json':q.encode(r)}
        if artifact:files['artifacts/changes.patch']=artifact
        commit=self.ga.commit(owned['claim_sha'],files,'bad result fixture');self.ga.push_new(commit,q.RESULTS+'remote-one')
    def test_roundtrip_source_patch_is_remote_reported_only(self):
        o=self.owned();q.submit(self.ga,'remote-one','worker-a',o['claim_sha'],self.report(o['claim']),self.art)
        out=q.collect(self.gb,'remote-one',self.root/'collected')
        self.assertFalse(out['promotion']);self.assertFalse(out['independent_clock_verification'])
        self.assertEqual(out['verification'],'remote_reported_requires_independent_verification')
        self.assertEqual((self.root/'collected/artifacts/changes.patch').read_bytes(),(self.art/'changes.patch').read_bytes())
        self.assertEqual(self.git(self.a,'rev-parse','HEAD').decode().strip(),self.dispatch)
    def test_two_worker_atomic_claim_race_has_exactly_one_winner(self):
        barrier=threading.Barrier(2);original=q.Git.push_new;rows=[]
        def synchronized(g,commit,ref):barrier.wait(timeout=15);return original(g,commit,ref)
        def worker(g,name):
            try:rows.append(('won',q.claim(g,self.dispatch,'remote-one',name)['claim_sha']))
            except q.QueueError:rows.append(('lost',None))
        with patch.object(q.Git,'push_new',synchronized):
            a=threading.Thread(target=worker,args=(self.ga,'worker-a'));b=threading.Thread(target=worker,args=(self.gb,'worker-b'))
            a.start();b.start();a.join(30);b.join(30);self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(sorted(r[0] for r in rows),['lost','won'])
        self.assertEqual(self.ga.remote_oid(q.CLAIMS+'remote-one'),next(r[1] for r in rows if r[0]=='won'))
    def test_same_owner_resume_keeps_exact_original_clock(self):
        a=self.owned();b=q.claim(self.ga,self.dispatch,'remote-one','worker-a')
        self.assertEqual(a['claim_sha'],b['claim_sha']);self.assertEqual(a['claim'],b['claim'])
        another=dict(self.job,id='remote-two')
        with patch.object(q,'jobs',return_value={'remote-one':(self.job,q.encode(self.job)),'remote-two':(another,q.encode(another))}):
            with self.assertRaisesRegex(q.QueueError,'worker_has_unfinished_claim'):q.claim(self.ga,self.dispatch,'remote-two','worker-a')
    def test_other_owner_cannot_reclaim(self):
        self.owned()
        with self.assertRaises(q.QueueError):q.claim(self.gb,self.dispatch,'remote-one','worker-b')
    def test_changed_job_id_cannot_be_reused(self):
        self.job['objective']='Changed after dispatch.'
        (self.a/q.JOB_DIR/'remote-one.json').write_bytes(q.encode(self.job))
        self.git(self.a,'add','.');self.git(self.a,'commit','-m','bad mutation')
        self.git(self.a,'push','origin','HEAD:refs/heads/research/remote-dispatch')
        current=q.snapshot(self.gb,'research/remote-dispatch')
        with self.assertRaises(q.QueueError):q.jobs(self.gb,current)
        self.git(self.a,'rm',q.JOB_DIR+'/remote-one.json');self.git(self.a,'commit','-m','bad delete')
        self.git(self.a,'push','origin','HEAD:refs/heads/research/remote-dispatch')
        deleted=q.snapshot(self.gb,'research/remote-dispatch')
        with self.assertRaisesRegex(q.QueueError,'immutable_published_job_deleted'):q.jobs(self.gb,deleted)
    def test_wrong_claim_and_worker_cannot_submit(self):
        o=self.owned()
        for worker,sha in [('worker-b',o['claim_sha']),('worker-a','0'*40)]:
            with self.subTest(worker=worker,sha=sha):
                with self.assertRaises(q.QueueError):q.submit(self.ga,'remote-one',worker,sha,self.report(o['claim']),self.art)
        self.assertIsNone(self.ga.remote_oid(q.RESULTS+'remote-one'))
    def test_collect_rejects_wrong_job_binding(self):
        o=self.owned();self.publish_bad(o,lambda r:r.update(job_sha256='0'*64))
        with self.assertRaises(q.QueueError):q.collect(self.gb,'remote-one')
    def test_collect_rejects_wrong_artifact_hash(self):
        o=self.owned();self.publish_bad(o,lambda r:r.update(artifacts_sha256={'changes.patch':'0'*64}),b'public patch\n')
        with self.assertRaises(q.QueueError):q.collect(self.gb,'remote-one')
    def test_result_ref_is_write_once(self):
        o=self.owned();r=self.report(o['claim'])
        extra=self.art/'unexpected.json';extra.write_text('{}',encoding='utf-8')
        with self.assertRaises(q.QueueError):q.submit(self.ga,'remote-one','worker-a',o['claim_sha'],r,self.art)
        self.assertIsNone(self.ga.remote_oid(q.RESULTS+'remote-one'));extra.unlink()
        a=q.submit(self.ga,'remote-one','worker-a',o['claim_sha'],r,self.art)
        with self.assertRaises(q.QueueError):q.submit(self.ga,'remote-one','worker-a',o['claim_sha'],r,self.art)
        self.assertEqual(self.ga.remote_oid(q.RESULTS+'remote-one'),a['result_sha'])
    def test_null_timeout_and_original_deadline_contract(self):
        c=dict(claimed_at_unix=100.,deadline_unix=1000.);r=self.report(c,'timeout');r['finished_unix']=1001.
        q.validate_report(r,self.job,c)
        for mutate in [lambda x:x.update(start_unix=101.),lambda x:x.update(deadline_unix=1001.),
            lambda x:x.update(status='completed'),lambda x:x['metrics'].update(rmse=float('nan'))]:
            bad=copy.deepcopy(r);mutate(bad)
            with self.assertRaises(q.QueueError):q.validate_report(bad,self.job,c)
        bounded=copy.deepcopy(self.job);bounded['kind']='bounded_experiment';bounded['caps']['max_fits']=128
        good=self.report(c);good['finished_unix']=101.;good['metrics']={'rmse':1.};good['usage'].update(fits=18,worker_memory_mib=100,whole_memory_mib=200)
        q.validate_report(good,bounded,c);good['usage']['fits']=129
        with self.assertRaises(q.QueueError):q.validate_report(good,bounded,c)
    def test_secret_data_binary_private_path_and_cap_denials(self):
        bad=[('predictions.json',b'{}'),('weights.json',b'{}'),('.env',b'x'),('changes.patch',('g'+'hp_'+'a'*32).encode()),
            ('changes.patch',b'Bearer abcdefghijklmnop'),('notes.txt',b'C:\\Users\\private\\file'),
            ('notes.txt',b'/home/private/file'),('notes.txt',b'\xff'),('notes.txt',b'x'*(q.MAX_FILE+1)),('escape/notes.txt',b'x')]
        for name,data in bad:
            with self.subTest(name=name):
                with self.assertRaises(q.QueueError):q.artifact_bytes(name,data)
        with self.assertRaises(q.QueueError):q.decode(b'{"value":NaN}')
        with self.assertRaises(q.QueueError):q.public_path('../outside.py')
        badjob=copy.deepcopy(self.job);badjob['expected_outputs']=['Foo.py','foo.py']
        with self.assertRaises(q.QueueError):q.validate_job(badjob)
        for refs in [[7],[[{}]],[{'path':'source.py','sha256':7}]]:
            malformed=copy.deepcopy(self.job);malformed['source_refs']=refs
            with self.assertRaises(q.QueueError):q.validate_job(malformed)
    def test_git_symlink_mode_and_bounded_claim_fail_closed(self):
        blob=self.ga.run('hash-object','-w','--stdin',data=b'target').decode().strip()
        tree=self.ga.run('mktree',data=f'120000 blob {blob}\tlinked.py\n'.encode()).decode().strip()
        commit=self.ga.run('commit-tree',tree,'-p',self.dispatch,data=b'symlink fixture\n').decode().strip()
        with self.assertRaises(q.QueueError):self.ga.blob(commit,'linked.py')
        j=copy.deepcopy(self.job);j['kind']='bounded_experiment';j['caps']['max_fits']=18
        with patch.object(q,'jobs',return_value={'remote-one':(j,q.encode(j))}):
            with self.assertRaises(q.QueueError):q.claim(self.ga,self.dispatch,'remote-one','worker-a')
    def test_bounded_requires_exact_same_worker_primary_approval_and_caps(self):
        owned=self.owned()
        result=q.submit(self.ga,'remote-one','worker-a',owned['claim_sha'],self.report(owned['claim']),self.art)
        approval=dict(schema=1,job_id='remote-one',result_sha=result['result_sha'],worker_id='worker-a',
            approved_for_bounded_experiments=True,caps=dict(self.job['caps'],max_fits=128))
        apath='research/remote-experiments/reviews/remote-one.json'
        p=self.a/apath;p.parent.mkdir(parents=True);p.write_bytes(q.encode(approval))
        job=copy.deepcopy(self.job);job.update(id='remote-two',kind='bounded_experiment',dependencies=['remote-one'])
        job['caps']['max_fits']=18;job['source_refs'].append(dict(path=apath,sha256=q.digest(q.encode(approval))))
        (self.a/q.JOB_DIR/'remote-two.json').write_bytes(q.encode(job))
        self.git(self.a,'add','.');self.git(self.a,'commit','-m','primary approval and next job')
        self.git(self.a,'push','origin','HEAD:refs/heads/research/remote-dispatch')
        dispatch=q.snapshot(self.ga,'research/remote-dispatch')
        self.assertEqual(q.snapshot(self.gb,'research/remote-dispatch'),dispatch)
        with self.assertRaises(q.QueueError):q.claim(self.gb,dispatch,'remote-two','worker-b')
        original=self.ga.blob
        for fields in [dict(worker_id='worker-b'),dict(result_sha='0'*40)]:
            changed=dict(approval,**fields);badjob=copy.deepcopy(job)
            badjob['source_refs'][-1]['sha256']=q.digest(q.encode(changed))
            with patch.object(self.ga,'blob',side_effect=lambda commit,path,*args,entry=changed: q.encode(entry) if path==apath else original(commit,path,*args)):
                with self.assertRaises(q.QueueError):q.bounded_admission(self.ga,dispatch,badjob,'worker-a')
        over=copy.deepcopy(job);over['caps']['wall_seconds']=901
        with self.assertRaises(q.QueueError):q.bounded_admission(self.ga,dispatch,over,'worker-a')
        actual=q.claim(self.ga,dispatch,'remote-two','worker-a')
        self.assertEqual(actual['status'],'claimed');self.assertEqual(actual['claimed_job']['caps']['max_fits'],18)

if __name__=='__main__':unittest.main()
