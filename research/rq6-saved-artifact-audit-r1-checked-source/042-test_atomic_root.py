"""Prepared synthetic ordering/clock/argv contracts; no actual closer/process."""
import argparse,ast,contextlib,copy,importlib.util,io,re
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).with_name('run_root.py')
spec=importlib.util.spec_from_file_location('atomic_root_contract_source',SOURCE)
atomic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atomic)


class AtomicRootContracts(unittest.TestCase):
    def test_child_birth_cannot_reset_enclosing60_common600_or_existing_final(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=1600.,
            common_deadline_monotonic=620.,final_deadline_monotonic=300.,inherited_original_clock=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=7000.,common_deadline_monotonic=6020.))
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
        for changed in [dict(state,absolute_deadline_unix=1601.),
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
        source=ast.parse(Path(__file__).with_name('close_audit.py').read_text('utf-8'))
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
        values=dict(Closer=str(Path(__file__).with_name('close_audit.py')),Manifest='synthetic-private.json',
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


class PostToolContracts(unittest.TestCase):
    def helper(self):
        spec=importlib.util.spec_from_file_location('synthetic_qh_post',Path(__file__).with_name('confirm_post_tool.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def test_actual_tool_original_windows_and_late_publication_revoke_all_positive_roles(self):
        post=self.helper();state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=1600.,
            common_deadline_monotonic=620.,final_deadline_monotonic=300.,inherited_original_clock=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=7000.,common_deadline_monotonic=6020.))
        before=copy.deepcopy(state);post.window(state,1100.,120.,begin=119.,closer_birth=1050.)
        self.assertEqual(post.actual_wrapper(0,'actual-wrapper'),dict(exit_code=0,tool='actual-wrapper'))
        for wall,mono,begin,birth in [(1110.,130.,129.,1050.),(1280.,300.,299.,1250.),(1100.,120.,90.,1050.)]:
            with self.subTest(wall=wall),self.assertRaises(RuntimeError):post.window(state,wall,mono,begin=begin,closer_birth=birth)
        for code,tool in [(1,'actual'),(None,'actual'),(0,''),(0,'PENDING_ACTUAL_EXIT')]:
            with self.assertRaises(RuntimeError):post.actual_wrapper(code,tool)
        with self.assertRaises(RuntimeError):post.window(dict(state,absolute_deadline_unix=1601.),1100.,120.)
        saved=[];calls=[];positive={k:True for k in post.ROLE_FLAGS}
        def write(value,exclusive):saved.append((copy.deepcopy(value),exclusive))
        def check():
            calls.append(1)
            if len(calls)==2:raise TimeoutError('same original root deadline')
        with self.assertRaises(TimeoutError):post.publish_checked(positive,write,check)
        self.assertEqual([exclusive for _,exclusive in saved],[True,False])
        self.assertTrue(saved[0][0]['post_tool_confirmed'])
        self.assertTrue(all(saved[-1][0][key] is False for key in post.ROLE_FLAGS))
        self.assertEqual(state,before)
        old_limited=dict(start_unix=10000.,start_monotonic=9020.,absolute_deadline_unix=10600.,common_deadline_monotonic=9620.,final_deadline_monotonic=9300.,
            inherited_original_clock=dict(start_unix=4100.,start_monotonic=3120.,absolute_deadline_unix=10100.,common_deadline_monotonic=9120.))
        with self.assertRaisesRegex(RuntimeError,'inherited_original_RQ6_common_expired'):post.window(old_limited,10100.,9120.)

    def test_full_known_union_keeps_wrapper_and_closer_preparers_and_denies_missing_or_live_scope(self):
        post=self.helper()
        def row(pid):return dict(pid=pid,create_time=100.+pid)
        def ids(rows):return {(v['pid'],v['create_time']) for v in rows}
        fresh=dict(known_identities=[row(1),row(2),row(3)],known_count=3,wrapper_preparer_identities=[row(4),row(5),row(6)])
        root=dict(owned_identities=[row(1),row(2)],closure_preparer_identities=[row(3)])
        before=copy.deepcopy((fresh,root));known=post.full_known_union(fresh,root,[row(9)],ids)
        self.assertEqual(known,ids([row(n) for n in range(1,7)]));self.assertEqual((fresh,root),before)
        for bad in [dict(fresh,known_count=4),dict(fresh,known_identities=[row(1),row(2),row(2)])]:
            with self.assertRaises(RuntimeError):post.full_known_union(bad,root,[row(9)],ids)
        with self.assertRaises(RuntimeError):post.full_known_union(fresh,dict(root,closure_preparer_identities=[row(7)]),[row(9)],ids)
        with self.assertRaises(RuntimeError):post.full_known_union(fresh,root,[row(4)],ids)
        # Execute ONLY the actual producer's pre-import guard AST with a mock
        # importer: changed bytes+ref cannot bypass the ORIGINAL frozen value.
        main=next(n for n in ast.parse(Path(post.__file__).read_text('utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        guarded=next(n for n in main.body if isinstance(n,ast.Try)).body
        first=next(i for i,n in enumerate(guarded) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='driver_ref' for t in n.targets))
        last=next(i for i,n in enumerate(guarded[first:],first) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='driver' for t in n.targets))
        only_guards=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(guarded[first:last+1]),type_ignores=[])),'<actual-post-preimport-guards>','exec')
        path=str(post.PACKET/'run_audit.py');actual='b'*64
        for frozen in (actual,'a'*64,None):
            importer=Mock(return_value=object())
            namespace=dict(binding={'driver':{'path':path,'sha256':actual}},pins={} if frozen is None else {path:frozen},
                sha=Mock(return_value=actual),need=post.need,Path=Path,PACKET=post.PACKET,imported=importer)
            if frozen==actual:
                exec(only_guards,namespace);importer.assert_called_once()
            else:
                with self.assertRaisesRegex(RuntimeError,'frozen_main_source_changed'):exec(only_guards,namespace)
                importer.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
