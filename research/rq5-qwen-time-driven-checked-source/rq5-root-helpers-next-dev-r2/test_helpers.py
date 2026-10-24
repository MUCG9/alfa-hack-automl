"""Prepared pure/mock contracts. No candidate, process, provider or real clock."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_rq4_pure_policy', HERE/'helper_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class RootHelperContracts(unittest.TestCase):
    def test_posttool_schema_matches_exact_pinned_outer_consumer_without_importing_it(self):
        outer=HERE.parent/'qwen-three-hour-outer-next-dev-r2/run_campaign.py'
        self.assertEqual(hashlib.sha256(outer.read_bytes()).hexdigest(),
            '8b10b4c0f63952075b435b13cdeaa1e90c9d8b3d933716fce2060c41f5fc841b')
        tree=ast.parse(outer.read_text(encoding='utf-8-sig'))
        predecessor=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='predecessor')
        consumed=[]
        for node in ast.walk(predecessor):
            if (isinstance(node,ast.Compare) and len(node.ops)==len(node.comparators)==1
                and isinstance(node.ops[0],ast.Eq) and isinstance(node.left,ast.Call)
                and isinstance(node.left.func,ast.Attribute) and isinstance(node.left.func.value,ast.Name)
                and node.left.func.value.id=='post' and node.left.func.attr=='get'
                and len(node.left.args)==1 and isinstance(node.left.args[0],ast.Constant)
                and node.left.args[0].value=='schema' and isinstance(node.comparators[0],ast.Constant)):
                consumed.append(node.comparators[0].value)
        self.assertEqual(consumed,['standard-repair-actual-wrapper-exit-confirmation-v1'])
        produced=[]
        for node in ast.walk(ast.parse((HERE/'confirm_post_tool.py').read_text(encoding='utf-8'))):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
                produced.extend(kw.value.value for kw in node.keywords if kw.arg=='schema'
                    and isinstance(kw.value,ast.Constant) and isinstance(kw.value.value,str)
                    and kw.value.value.startswith('standard-repair-actual-wrapper-exit-'))
        self.assertEqual(produced,consumed*2)
        self.assertNotIn('standard-repair-actual-wrapper-exit-confirmed-v1',produced)

    def test_existing_pin_cannot_be_silently_replaced_after_initial_hash_scan(self):
        path = str((HERE/'synthetic-existing').resolve())
        pins = {path:'a'*64}; before = dict(pins)
        self.assertEqual(policy.bind_pin(pins,path,'a'*64,allowed_new={})['sha256'],'a'*64)
        with self.assertRaisesRegex(RuntimeError,'immutable_pin_collision'):
            policy.bind_pin(pins,path,'b'*64,allowed_new={path:'b'*64})
        self.assertEqual(pins,before)

    def test_new_pin_requires_exact_separate_allowlist_and_never_overrides_original(self):
        path = str((HERE/'synthetic-new').resolve()); pins = {}
        for permitted in ({},{path:'b'*64}):
            with self.assertRaisesRegex(RuntimeError,'unapproved_new_pin'):
                policy.bind_pin(pins,path,'a'*64,allowed_new=permitted)
            self.assertEqual(pins,{})
        self.assertEqual(policy.bind_pin(pins,path,'a'*64,allowed_new={path:'a'*64}),dict(path=path,sha256='a'*64))
        self.assertEqual(pins,{path:'a'*64})

    def test_posttool_union_rejects_missing_or_changed_original_pin(self):
        original={'source':'a'*64,'input':'b'*64}
        for later in ({'source':'a'*64},{'source':'c'*64,'input':'b'*64}):
            with self.assertRaisesRegex(RuntimeError,'original_frozen_pin'):
                policy.exact_union(original,later)
        later=dict(original,preparer='d'*64)
        self.assertEqual(policy.exact_union(original,later),later)
        self.assertIsNot(policy.exact_union(original,later),later)

    def test_original6000_final240_and_closer_birth60_never_rebase(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=7000.,
            common_deadline_monotonic=6020.,final_deadline_monotonic=5900.)
        before=dict(state); policy.window(state,6800.,5820.,reserve=60)
        self.assertEqual(state,before)
        for changed,wall,mono,kw in [(state,6830.,5850.,dict(reserve=60)),
            (dict(state,absolute_deadline_unix=7001.),6800.,5820.,{}),
            (state,6806.,5820.,{}),(state,6800.,5820.,dict(begin=5790.)),
            (state,6800.,5820.,dict(closer_birth=6740.))]:
            with self.subTest(kw=kw),self.assertRaises(RuntimeError):policy.window(changed,wall,mono,**kw)
        self.assertEqual(state,before)

    def test_late_failure_revokes_all_positive_role_flags_and_quality(self):
        value={key:True for key in policy.ROLE_FLAGS};value.update(metrics={'x':1},quality_metric={'x':1},qualified_ML_metrics={'x':1})
        untouched=copy.deepcopy(value);writes=[];calls=[0];primary=TimeoutError('synthetic late terminal failure')
        def check():
            calls[0]+=1
            if calls[0]==2:raise primary
        with self.assertRaises(TimeoutError) as caught:
            policy.publish_checked(value,lambda saved,exclusive:writes.append((copy.deepcopy(saved),exclusive)),check)
        self.assertIs(caught.exception,primary);self.assertEqual(value,untouched)
        self.assertEqual([exclusive for saved,exclusive in writes],[True,False])
        self.assertTrue(all(writes[-1][0][key] is False for key in policy.ROLE_FLAGS))
        self.assertTrue(all(writes[-1][0][key] is None for key in ('metrics','quality_metric','qualified_ML_metrics')))

    def test_late_metadata_failure_revokes_READY_without_changing_root_or_clock(self):
        root={'technical_procedure_passed':True};state={'start_monotonic':20.,'common_deadline_monotonic':6020.}
        before=copy.deepcopy((root,state));value=dict(readiness='READY_REVIEWED_FROZEN',missing_bindings=[],immutable_files={'old':'a'*64})
        answer=policy.revoked(value,OSError('synthetic'))
        self.assertEqual(answer['readiness'],'NOT_READY');self.assertIn('terminal_helper_failure',answer['missing_bindings'])
        self.assertEqual(answer['immutable_files'],value['immutable_files'])
        self.assertEqual((root,state),before)

    def test_failed_revocation_preserves_original_exception_and_safe_secondary_type(self):
        primary=TimeoutError('primary');calls=[0];writes=[0]
        def check():
            calls[0]+=1
            if calls[0]==2:raise primary
        def write(value,exclusive):
            writes[0]+=1
            if not exclusive:raise PermissionError('secondary')
        with self.assertRaises(TimeoutError) as caught:policy.publish_checked({'post_tool_confirmed':True},write,check)
        self.assertIs(caught.exception,primary)
        self.assertEqual(primary.helper_secondary_exception_type,'PermissionError');self.assertEqual(writes[0],2)

    def test_successful_publication_requires_pre_and_post_check_without_revocation(self):
        events=[];value={'post_tool_confirmed':True}
        policy.publish_checked(value,lambda result,exclusive:events.append(('write',exclusive,result.copy())),lambda:events.append('check'))
        self.assertEqual(events,['check',('write',True,value),'check'])

    def test_launcher_invokes_only_fixed_binder_and_frozen_atomic_without_private_flags(self):
        text=(HERE/'launch_atomic.ps1').read_text(encoding='utf-8')
        self.assertEqual(text.count('& $Python'),2)
        self.assertIn('$auth.refs.binder.path @common',text);self.assertIn('$auth.refs.atomic_source.path @atomicArgs',text)
        self.assertIn("'--binding'",text);self.assertNotIn("'--private-manifest'",text)
        self.assertIn('exit $actualWrapperExit',text);self.assertNotIn('Start-Process',text)
        self.assertNotIn('--wrapper-tool',text)  # Actual tool evidence is available only AFTER this command.

    def test_no_helper_assigns_a_replacement_campaign_origin_or_calls_candidate_main(self):
        for name in ('bind_atomic.py','confirm_post_tool.py'):
            tree=ast.parse((HERE/name).read_text(encoding='utf-8'))
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
            self.assertFalse(any(n.func.attr in {'run','Popen','main'} for n in calls))
            self.assertNotIn('start_monotonic =',(HERE/name).read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main(verbosity=2)
