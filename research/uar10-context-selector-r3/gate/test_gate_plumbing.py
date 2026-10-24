"""Prepared synthetic ordering/clock/argv contracts; no actual closer/process."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).with_name('run_root.py')
spec=importlib.util.spec_from_file_location('atomic_root_contract_source',SOURCE)
atomic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atomic)


class AtomicRootContracts(unittest.TestCase):
    def test_child_birth_cannot_reset_enclosing60_common1200_or_existing_final(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=2200.,
            common_deadline_monotonic=1220.,final_deadline_monotonic=300.)
        before=state.copy()
        initial=atomic.bounds(state,1100.,120.)
        late_child=atomic.bounds(state,1100.,120.,1115.)
        self.assertEqual(initial,(1160.,180.))
        self.assertEqual(late_child,initial)
        self.assertLessEqual(late_child[0],1115.+60)
        self.assertLessEqual(late_child[1],state['start_monotonic']+1115.-state['start_unix']+60)
        self.assertEqual(state,before)
        final=dict(state,final_deadline_monotonic=150.)
        self.assertEqual(atomic.bounds(final,1100.,120.,1115.),(1130.,150.))
        for changed in [dict(state,absolute_deadline_unix=2201.),
                        dict(state,common_deadline_monotonic=float('nan'))]:
            with self.assertRaises(RuntimeError):atomic.bounds(changed,1100.,120.)
        with self.assertRaises(RuntimeError):atomic.bounds(state,1100.,120.,1099.)

    def test_actual_exit_is_saved_before_fresh_and_late_or_failed_exit_never_qualifies(self):
        order=[]
        save=lambda:order.append('actual_exit_saved')
        fresh=lambda:(order.append('fresh'),{'qualified':True})[1]
        check=lambda:order.append('check')
        self.assertEqual(atomic.postexit(0,0,save,fresh,check),{'qualified':True})
        self.assertEqual(order,['actual_exit_saved','check','fresh','check'])
        for shell,native in [(1,1),(0,1),(1,0),(None,0)]:
            order.clear()
            with self.assertRaises(RuntimeError):atomic.postexit(shell,native,save,fresh,check)
            self.assertEqual(order,['actual_exit_saved','check'])
        order.clear()
        def expired():
            order.append('expired')
            raise TimeoutError('same-original-window')
        with self.assertRaises(TimeoutError):atomic.postexit(0,0,save,fresh,expired)
        self.assertEqual(order,['actual_exit_saved','expired'])

    def test_fixed_child_shell_argv_has_no_payload_and_requires_absolute_typed_evidence(self):
        root=SOURCE.parent.resolve()
        cfg={k:{'path':str(root/(k+'.fixed')),'sha256':'a'*64}
             for k in ['powershell','python','closer','manifest','driver','campaign']}
        actual=dict(session=123,exit_code=0,tool='actual-tool')
        argv=atomic.child_command(cfg,actual,root/'native-exit.json')
        self.assertIn('-File',argv)
        self.assertEqual(argv[argv.index('-File')+1],str(atomic.PACKET/'close_child.ps1'))
        self.assertNotIn('-Command',argv)
        self.assertNotIn('-ExecutionPolicy',argv)
        self.assertIn('-ActualSession',argv)
        self.assertEqual(argv[argv.index('-ActualExit')+1],'0')
        self.assertNotIn('-LaunchParentPid',argv)  # Child script observes its own actual shell.
        actual_shell={'pid':123,'create_time':100.0000004}
        declared={'pid':123,'create_time':100.}
        early={'launch_parent_observation':{'verified':True,'observed_shell':actual_shell,'declared':declared}}
        atomic.native_shell_verified({'shell':declared},early,actual_shell)
        for wrong in [{'pid':124,'create_time':100.}, {'pid':123,'create_time':100.0000008}]:
            with self.assertRaises(RuntimeError):atomic.native_shell_verified({'shell':wrong},early,actual_shell)
        with self.assertRaises(RuntimeError):
            atomic.native_shell_verified({'shell':declared},early,dict(actual_shell,create_time=100.))

        with self.assertRaises(RuntimeError):
            atomic.child_command(dict(cfg,closer={'path':'relative.py','sha256':'a'*64}),actual,root/'exit.json')
        with self.assertRaises(RuntimeError):
            atomic.child_command(cfg,dict(actual,tool='x; arbitrary-command'),root/'exit.json')




import ast
from copy import deepcopy
import inspect
import json
import tempfile
from types import SimpleNamespace


def module_source(name):
    spec=importlib.util.spec_from_file_location('_uar10_contract_'+name,SOURCE.with_name(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


G=module_source('run_gate');C=module_source('contracts')


def actual_technical_scope():
    """Execute only the unchanged copied nested plumbing definitions in mocks.

    The full gate itself remains the execution proof of the actual process path.
    This synthetic scope never loads config, observes a PID or creates a clock.
    """
    tree=ast.parse(inspect.getsource(G.main)).body[0]
    definitions=[deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'resource_clock','pulse'}]
    assert [n.name for n in definitions]==['resource_clock','pulse']
    parameters=['parent_pulse','parent_clock','sampler','suite_ob','coor','cfg','state','root','children','clock','mono']
    prefix=ast.parse("last_technical_sample=mono\npulse_maximum_gap=0.\npulse_sticky_error=None\nrequired=(root['pid'],root['create_time'])\n").body
    suffix=ast.parse("state['_resource_checkpoint']=resource_clock\nreturn pulse,resource_clock,lambda:(last_technical_sample,pulse_sticky_error)\n").body
    function=ast.FunctionDef(name='factory',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=n) for n in parameters],
        kwonlyargs=[],kw_defaults=[],defaults=[]),body=prefix+definitions+suffix,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    tick=SimpleNamespace(value=0.)
    namespace=dict(G.__dict__,time=SimpleNamespace(monotonic=lambda:tick.value))
    exec(compile(module,'<exact-UAR10-nested-plumbing>','exec'),namespace)
    state={};root=dict(pid=1,create_time=2.);namespace['preparers']=[root]
    children=set();parent=Mock();parent_clock=Mock();clock=Mock()
    observer=SimpleNamespace(seen={(3,4.)},denials=[],observe=lambda:{})
    coor=SimpleNamespace(identities=lambda rows:{(r['pid'],r['create_time']) for r in rows})
    result={'sampled':[dict(pid=1,create_time=2.,rss_bytes=10),dict(pid=3,create_time=4.,rss_bytes=20)],'departed':[]}
    calls=[]
    def sample(known,*,required,checkpoint):
        calls.append((known,required));checkpoint();checkpoint();return result
    sampler=SimpleNamespace(sample=sample)
    pulse,hook,peek=namespace['factory'](parent,parent_clock,sampler,observer,coor,{'work_root':'not-read'},state,root,children,clock,0.)
    return SimpleNamespace(pulse=pulse,hook=hook,peek=peek,tick=tick,parent=parent,parent_clock=parent_clock,
        result=result,calls=calls,state=state,children=children)


class UAR10PlumbingContracts(unittest.TestCase):
    def test_exported_original_clock_hook_never_samples_or_resets_resource_history(self):
        s=actual_technical_scope();s.tick.value=.5;s.hook()
        self.assertEqual(s.calls,[]);s.parent.assert_not_called();s.parent_clock.assert_called_once()
        self.assertEqual(s.peek(),(0.,None));self.assertIs(s.state['_resource_checkpoint'],s.hook)
        s.tick.value=10.001
        with self.assertRaisesRegex(RuntimeError,'technical_observation_gap10'):s.hook()
        s.tick.value=1.
        with self.assertRaises(RuntimeError):s.pulse(force=True)
        self.assertEqual(s.calls,[]);self.assertEqual(s.peek()[0],0.)

    def test_full_round_requires_actual_self_and_all_caps_before_advancing(self):
        s=actual_technical_scope();s.tick.value=.5;s.pulse(force=True)
        self.assertEqual(s.calls,[({(1,2.),(3,4.)},[(1,2.)])])
        self.assertEqual(s.peek(),(.5,None));self.assertEqual(s.children,{(3,4.)})
        self.assertIs(s.state['verified_technical_resource_sample'],s.result)
        s.result['sampled'][1]['rss_bytes']=1536*2**20+1;s.tick.value=.75
        with self.assertRaisesRegex(RuntimeError,'technical_child_tree_memory_limit'):s.pulse(force=True)
        self.assertEqual(s.peek()[0],.5)
        s.result['sampled'][1]['rss_bytes']=1
        with self.assertRaises(RuntimeError):s.pulse(force=True)

    def test_unrun_fixture_projection_uses_real_flat_import_and_replaces_src_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'tools').mkdir();(root/'src/automl').mkdir(parents=True)
            (root/'tools/module_map.json').write_text(json.dumps({'automl.search.runner':'automl_runner'}))
            fixture=root/'fixture.py';fixture.write_text("from pathlib import Path\nimport sys\nimport unittest\nROOT=Path(__file__).resolve().parents[1]\nsys.path.insert(0,str(ROOT/'src'))\nfrom automl.search import runner as R\ndef fixture(): return R\nclass F(unittest.TestCase):\n    def test_unrun(self): self.assertTrue(True)\n")
            raw=C.adapted_fixture({'canonical_root':str(root)},{'test':str(fixture)})
            tree=ast.parse(raw)
            self.assertIn('import automl_runner as R',raw.decode())
            self.assertFalse(any(isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('automl.') for n in ast.walk(tree)))
            self.assertFalse(any(isinstance(n,ast.BinOp) and isinstance(n.left,ast.Name) and n.left.id=='ROOT'
                and isinstance(n.right,ast.Constant) and n.right.value=='src' for n in ast.walk(tree)))


if __name__=='__main__':unittest.main(verbosity=2)
