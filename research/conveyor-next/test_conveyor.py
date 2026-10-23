"""Pure filesystem contracts; no models, API, services or campaign launches."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy,json,unittest
import conveyor as q

class QueueContracts(unittest.TestCase):
    def setUp(self):
        self.fixture_parent=Path(__file__).resolve().parents[1]/'queue-fixtures'
        self.fixture_parent.mkdir(exist_ok=True)
        self.temp=TemporaryDirectory(prefix='q-',dir=self.fixture_parent)
        self.root=Path(self.temp.name).resolve()
        assert self.root.is_relative_to(self.fixture_parent.resolve())
        q.init(self.root)
    def tearDown(self):
        assert self.root.is_relative_to(self.fixture_parent.resolve())
        self.temp.cleanup()
    def draft(self,identity='EXP-001',**overrides):
        value=dict(id=identity,schema_version=1,execution_ready=True,hypothesis='A measured hypothesis',
            factor='one representation',acceptance='all declared cuts beat the protected control',
            repair_policy='preserve original clocks and failed attempts',source_git_sha='1'*40,
            budget=dict(common_seconds=900,worker_seconds=600,memory_bytes=2**30,threads=1,api_calls=0),dependencies=[])
        value.update({key:'2'*64 for key in ('source_sha256','control_sha256','inputs_sha256','splits_sha256','evaluator_sha256')})
        value.update(overrides);p=self.root/'drafts'/identity;p.mkdir();q.write(p/'task.json',value)
        return p
    def terminal(self,identity='EXP-001',status='completed',cleanup=True):
        p=self.root/'running'/'PLUS-1'/identity
        proof=dict(cleanup_confirmed=cleanup,active_owned_processes=[])
        q.write(p/'closure.json',proof)
        q.write(p/'receipt.json',dict(status=status,actual_exec_observed_by_root=True,
            cleanup_confirmed=cleanup,task_sha256=q.digest(p/'task.json'),closure_sha256=q.digest(p/'closure.json')))
        q.write(p/'metrics.json',dict(control=1.0,candidate=None if status!='completed' else 1.1))
        (p/'summary.txt').write_text('negative or failed outcome preserved',encoding='utf-8')
        return p
    def test_full_negative_result_lifecycle_preserves_task(self):
        p=self.draft();before=(p/'task.json').read_bytes();q.promote(self.root,'EXP-001')
        self.assertEqual(q.claim(self.root,'PLUS-1'),'EXP-001');self.terminal()
        q.publish(self.root,'PLUS-1','EXP-001');q.review(self.root,'EXP-001','rejected')
        p=self.root/'reviewed/EXP-001'
        self.assertEqual((p/'task.json').read_bytes(),before)
        self.assertEqual(q.read(p/'review.json')['decision'],'rejected')
        self.assertFalse(q.read(p/'claim.json')['experiment_clock_assigned'])
    def test_only_one_owner_and_running_blocks_another_experiment(self):
        self.draft();self.draft('EXP-002');q.promote(self.root,'EXP-001');q.promote(self.root,'EXP-002')
        self.assertEqual(q.claim(self.root,'PLUS-1'),'EXP-001')
        self.assertIsNone(q.claim(self.root,'PLUS-2'))
        self.assertTrue((self.root/'pending/EXP-002').is_dir())
    def test_busy_lock_is_never_stolen(self):
        self.draft();q.promote(self.root,'EXP-001');(self.root/'.transition-lock').mkdir()
        with self.assertRaisesRegex(ValueError,'never auto-steal'):q.claim(self.root,'PLUS-1')
        self.assertTrue((self.root/'.transition-lock').is_dir())
    def test_unready_task_missing_pin_and_invalid_budget_stay_drafts(self):
        for i,change in enumerate([dict(execution_ready=False),dict(source_sha256='bad'),
                dict(budget=dict(common_seconds=5,worker_seconds=6,memory_bytes=1,threads=1,api_calls=0))]):
            identity='EXP-10'+str(i);self.draft(identity,**change)
            with self.assertRaises(ValueError):q.promote(self.root,identity)
            self.assertTrue((self.root/'drafts'/identity).exists())
    def test_dependencies_need_reviewed_acceptance(self):
        self.draft();self.draft('EXP-002',dependencies=[dict(id='EXP-001',review_decision='accepted')])
        with self.assertRaises(ValueError):q.promote(self.root,'EXP-002')
        q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1');self.terminal()
        q.publish(self.root,'PLUS-1','EXP-001');q.review(self.root,'EXP-001','rejected')
        with self.assertRaisesRegex(ValueError,'not accepted'):q.promote(self.root,'EXP-002')
    def test_claimed_task_mutation_blocks_publication(self):
        self.draft();q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1');p=self.terminal()
        value=q.read(p/'task.json');value['factor']='changed';(p/'task.json').write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'claimed task changed'):q.publish(self.root,'PLUS-1','EXP-001')
        self.assertFalse((self.root/'results/EXP-001').exists())
    def test_partial_or_unclean_result_never_visible_to_consumers(self):
        self.draft();q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1')
        with self.assertRaises(FileNotFoundError):q.publish(self.root,'PLUS-1','EXP-001')
        self.terminal(cleanup=False)
        with self.assertRaisesRegex(ValueError,'fresh owned cleanup'):q.publish(self.root,'PLUS-1','EXP-001')
        self.assertEqual(list((self.root/'results').iterdir()),[])
    def test_failure_keeps_null_metric_and_does_not_reset_clock(self):
        self.draft();q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1');self.terminal(status='timeout')
        q.publish(self.root,'PLUS-1','EXP-001');p=self.root/'results/EXP-001'
        self.assertIsNone(q.read(p/'metrics.json')['candidate'])
        self.assertEqual(q.read(p/'receipt.json')['status'],'timeout')
        self.assertFalse(q.read(p/'claim.json')['experiment_clock_assigned'])
    def test_published_task_mutation_blocks_dependency_review(self):
        self.draft();q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1');self.terminal()
        q.publish(self.root,'PLUS-1','EXP-001');p=self.root/'results/EXP-001'
        value=q.read(p/'task.json');value['factor']='changed';(p/'task.json').write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'terminal packet changed'):q.review(self.root,'EXP-001','accepted')
    def test_published_metrics_receipt_closure_and_summary_are_sealed(self):
        for i,name in enumerate(['metrics.json','receipt.json','closure.json','summary.txt']):
            identity='EXP-30'+str(i);self.draft(identity);q.promote(self.root,identity)
            q.claim(self.root,'PLUS-1');self.terminal(identity);q.publish(self.root,'PLUS-1',identity)
            p=self.root/'results'/identity;(p/name).write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'terminal packet changed'):q.review(self.root,identity,'accepted')
    def test_uncertain_ownership_cannot_close_a_task(self):
        self.draft();q.promote(self.root,'EXP-001');q.claim(self.root,'PLUS-1');p=self.terminal()
        proof=q.read(p/'closure.json');proof['uncertain_owned']=[dict(pid=1,create_time=1)]
        (p/'closure.json').write_text(json.dumps(proof),encoding='utf-8')
        receipt=q.read(p/'receipt.json');receipt['closure_sha256']=q.digest(p/'closure.json')
        (p/'receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'unresolved ownership'):q.publish(self.root,'PLUS-1','EXP-001')
    def test_identifiers_and_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):q.claim(self.root,'../PLUS-1')
        p=self.draft();(p/'task.json').write_text('{"id":"EXP-001","id":"EXP-002"}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'duplicate'):q.promote(self.root,'EXP-001')

if __name__=='__main__':unittest.main(verbosity=2)
