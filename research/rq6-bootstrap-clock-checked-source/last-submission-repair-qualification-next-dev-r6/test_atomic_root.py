"""Prepared synthetic ordering/clock/argv contracts; no actual closer/process."""
import argparse,ast,contextlib,copy,importlib.util,io,re
from pathlib import Path
import unittest,json,tempfile,types
from unittest.mock import Mock,patch

SOURCE=Path(__file__).with_name('run_root.py')
spec=importlib.util.spec_from_file_location('atomic_root_contract_source',SOURCE)
atomic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atomic)


class AtomicRootContracts(unittest.TestCase):
    def test_child_birth_cannot_reset_enclosing60_common600_or_existing_final(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=7000.,
            common_deadline_monotonic=6020.,final_deadline_monotonic=300.)
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
        for changed in [dict(state,absolute_deadline_unix=7001.),
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


    def test_real_child_script_argv_is_accepted_by_exact_closer_parser_without_starting_it(self):
        # Execute only the original argparse construction AST, never closer main.
        source=ast.parse(Path(__file__).with_name('close_controller.py').read_text('utf-8'))
        main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        body=[]
        for node in main.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='a' for t in node.targets):break
            body.append(copy.deepcopy(node))
        body.append(ast.Return(value=ast.Name(id='p',ctx=ast.Load())))
        factory=ast.FunctionDef(name='parser_factory',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
            body=body,decorator_list=[])
        namespace={'argparse':argparse,'__doc__':'synthetic cross-script parser'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[factory],type_ignores=[])),'<actual-closer-parser-only>','exec'),namespace)
        parser=namespace['parser_factory']()
        script=Path(__file__).with_name('close_child.ps1').read_text('utf-8')
        block=re.search(r"\$nativeArgs = @\((.*?)\)\r?\nif \(\$ActualSession",script,re.S).group(1)
        block=block.replace('.ToString([System.Globalization.CultureInfo]::InvariantCulture)','')
        tokens=list(re.finditer(r"'([^']*)'|\$([A-Za-z_][A-Za-z0-9_]*)",block))
        residue=re.sub(r"'([^']*)'|\$([A-Za-z_][A-Za-z0-9_]*)",'',block)
        self.assertFalse(residue.replace(',','').strip())
        values=dict(Closer=str(Path(__file__).with_name('close_controller.py')),Manifest='synthetic-private.json',
            ManifestSha='a'*64,CloserSha='b'*64,DriverSha='c'*64,CampaignSha='d'*64,ActualTool='actual-tool',ActualExit='0',PID='123',birthText='1000.25')
        argv=[m.group(1) if m.group(1) is not None else values[m.group(2)] for m in tokens]
        self.assertEqual(argv[:4],['-B','-X','utf8',values['Closer']])
        parsed=parser.parse_args(argv[4:])
        self.assertEqual(parsed.manifest,values['Manifest']);self.assertEqual(parsed.manifest_sha256,'a'*64)
        self.assertEqual(parsed.launch_parent_pid,123);self.assertEqual(parsed.launch_parent_create_time,1000.25)
        self.assertEqual(parsed.actual_exit_code,0);self.assertIsNone(parsed.actual_exec_session)
        self.assertIn("$nativeArgs += @('--actual-exec-session', $ActualSession)",script)
        self.assertEqual(parser.parse_args(argv[4:]+['--actual-exec-session','456']).actual_exec_session,456)
        old=[x.replace('--manifest','--private-manifest') if x.startswith('--manifest') else x for x in argv[4:]]
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as denied:parser.parse_args(old)
        self.assertEqual(denied.exception.code,2)


    def test_pinned_binder_siblings_enter_fresh_union_and_only_exact_current_shell_waits_posttool(self):
        def rows(*pids):return [dict(pid=p,create_time=float(p)+1000) for p in pids]
        base=types.SimpleNamespace(ids=lambda values:{(v['pid'],v['create_time']) for v in values})
        root=dict(owned_identities=rows(10),closure_preparer_identities=rows(20))
        cleanup=dict(owned_process_identities=rows(30));child=rows(30)[0]
        wrapper=rows(70,80,60);shell=rows(60)[0];chain=dict(verified=True,observed_shell=shell)
        actual=dict(session=None,exit_code=0,tool='actual-driver-tool')
        with tempfile.TemporaryDirectory() as directory,patch.object(atomic,'OUT',Path(directory)):
            path=Path(directory)/'atomic-binding-preparer-identity.json'
            original=dict(identities=rows(40,50,60),launch_parent_observation=dict(verified=True,observed_shell=shell),actual_driver=actual)
            def call(receipt=original,wrong_pin=False):
                path.write_text(json.dumps(receipt),encoding='utf-8');h=atomic.sha(path)
                binding=dict(binding_preparer_receipt=dict(path=str(path),sha256=h),immutable_files={str(path):'0'*64 if wrong_pin else h})
                return atomic.fresh_known_union(base,root,cleanup,child,binding,actual,wrapper,chain,lambda:None)
            known,partition=call()
            self.assertEqual(known,base.ids(rows(10,20,30,40,50)))
            self.assertEqual(base.ids(partition['binding_preparer_identities']),base.ids(rows(40,50,60)))
            self.assertEqual(partition['binding_preparer_current_observer_shell'],rows(60))
            self.assertEqual(base.ids(partition['binding_preparer_absence_identities']),base.ids(rows(40,50)))
            self.assertTrue(partition['shared_observer_shell_in_wrapper_preparers_requires_later_posttool_absence'])
            # Unchanged post helper adds all binder rows; same full union results.
            expected=known|base.ids(wrapper)
            self.assertEqual(expected,known|base.ids(wrapper)|base.ids(original['identities']))
            self.assertNotIn((60,1060.),known);self.assertIn((60,1060.),expected)
            cases=[dict(original,identities=rows(40,80,60)),dict(original,identities=rows(40,50,61)),
                dict(original,launch_parent_observation=dict(verified=False,observed_shell=shell)),
                dict(original,launch_parent_observation=dict(verified=True,observed_shell=rows(61)[0])),
                dict(original,actual_driver=dict(actual,tool='wrong-driver')),dict(original,schema='invented')]
            for index,receipt in enumerate(cases):
                with self.subTest(case=index),self.assertRaises(RuntimeError):call(receipt)
            with self.assertRaises(RuntimeError):call(wrong_pin=True)
            self.assertEqual(root,dict(owned_identities=rows(10),closure_preparer_identities=rows(20)))

if __name__=='__main__':unittest.main(verbosity=2)
