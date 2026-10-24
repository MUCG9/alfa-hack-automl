"""Prepared inert bootstrap contracts. Not registered and never executed by author.

Future execution extracts only named stdlib-only functions from reviewed source;
it never imports a coordinator, provider, worker, model or audit library.
"""
from pathlib import Path
import ast
import json
import math
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parent


def pure_functions(names,**supplied):
    tree=ast.parse((ROOT/'run_pair.py').read_text('utf-8'))
    selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Assign))
        and (getattr(n,'name',None) in names or isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id in supplied for t in n.targets))]
    # Assignments are supplied independently; no source module initialization.
    selected=[n for n in selected if isinstance(n,ast.FunctionDef)]
    scope=dict(FAILURE_TYPE=RuntimeError,math=math,sys=sys,**supplied)
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<isolated-bootstrap-functions>','exec'),scope)
    return types.SimpleNamespace(**scope)


class UQ3BootstrapTests(unittest.TestCase):
    def test_fresh_origin_has_no_UQ1_tuple_and_rejects_reset_or_short_setup(self):
        clock=types.SimpleNamespace(time=lambda:101.,monotonic=lambda:501.)
        f=pure_functions({'need','launch_origin'},COMMON=10800,SETUP=900,time=clock)
        args=types.SimpleNamespace(start_unix=100.,start_monotonic=500.,
            absolute_deadline_unix=10900.,common_deadline_monotonic=11300.)
        self.assertEqual(f.launch_origin(args),(100.,500.,10900.,11300.))
        args.common_deadline_monotonic+=1
        with self.assertRaisesRegex(RuntimeError,'exact_assigned'):f.launch_origin(args)
        args.common_deadline_monotonic=11300.
        clock.time=lambda:1000.
        with self.assertRaisesRegex(RuntimeError,'setup900'):f.launch_origin(args)

    def test_class_common_flag_is_before_B_suffix_REG_unchanged(self):
        caps={'regression':dict(hpo=300,solver=810),'classification':dict(hpo=900,solver=3510)}
        f=pure_functions({'solver_argv'},CAPS=caps)
        for kind in caps:
            a=f.solver_argv('A',kind,'a'*64);b=f.solver_argv('B',kind,'a'*64)
            self.assertEqual(b,a+['--strict-task-contract'])
            self.assertEqual(a.count('--hpo-fair-reserve'),int(kind=='classification'))
            self.assertIn('--strict-runtime',a)
            self.assertEqual(a[a.index('--hpo-budget')+1],str(caps[kind]['hpo']))

    def test_launcher_origin_precedes_source_publication_provider_and_runpy(self):
        tree=ast.parse((ROOT/'launcher.py').read_text('utf-8'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        clock=min(n.lineno for n in ast.walk(main) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Tuple) and any(isinstance(x,ast.Name) and x.id=='start_unix'
                for x in t.elts) for t in n.targets))
        publication=min(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute) and n.func.attr=='check_output')
        launch_provider=max(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name) and n.func.id=='provider_environment')
        self.assertLess(clock,publication);self.assertLess(clock,launch_provider)
        text=(ROOT/'launcher.py').read_text('utf-8')
        self.assertNotIn('RECOVERY_ORIGIN',text);self.assertNotIn('bootstrap_failure',text)
        self.assertIn("WORK/'uq3-cadence-hpo-next-dev/candidate'",text)

    def test_exact_historical_failure_is_evidence_only_no_false_flag_repair(self):
        f=pure_functions({'need','historical_failure_evidence'},HISTORICAL_FAILURES={'uq1/terminal-root-closure.json':'a'*64})
        proof=dict(technical_procedure_passed=False,cleanup_confirmed=False,source_unchanged=False,
            active_owned_processes=[],actual_exec_session=None,actual_exec_exit_code_observed_by_root=1,
            actual_tool_evidence='94cc24',first_failure=dict(code='conflicting_input_pin'),
            changed_source_or_core=['missing-pair-manifest'],
            uncertain_owned=[dict(scope='campaign',reason='saved_cleanup_not_confirmed')])
        before=json.dumps(proof,sort_keys=True)
        self.assertTrue(f.historical_failure_evidence('uq1/terminal-root-closure.json','a'*64,proof))
        self.assertEqual(before,json.dumps(proof,sort_keys=True))
        self.assertFalse(f.historical_failure_evidence('unrelated/terminal-root-closure.json','a'*64,proof))
        with self.assertRaisesRegex(RuntimeError,'exact_historical'):
            f.historical_failure_evidence('uq1/terminal-root-closure.json','b'*64,proof)
        proof['cleanup_confirmed']=True
        with self.assertRaises(RuntimeError):f.historical_failure_evidence('uq1/terminal-root-closure.json','a'*64,proof)

    def test_only_exact_historical_guard_projection_keeps_candidate_pin(self):
        source=(ROOT/'run_pair.py').read_text('utf-8')
        tree=ast.parse(source);main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        loop=next(n for n in ast.walk(main) if isinstance(n,ast.For)
            and ast.unparse(n.iter)=="base['immutable_files'].items()")
        segment=ast.get_source_segment(source,loop)
        scope=dict(base={'immutable_files':{'proc':'fac3','other':'unchanged'}},pins={'proc':'9f'},
            process_key='proc',historical_relative='history/proc',merge=lambda p,k,v:p.update({k:v}))
        exec(compile(segment,'<one-key-relocation>','exec'),scope)
        self.assertEqual(scope['pins'],{'proc':'9f','history/proc':'fac3','other':'unchanged'})
        self.assertIn("'conflicting_input_pin'",source)

    def test_template_cannot_grant_gate_or_clock_and_no_optional_8VALID_salvage(self):
        binding=json.loads((ROOT/'binding.template.json').read_text('utf-8'))
        self.assertEqual(binding['readiness'],'NOT_READY')
        self.assertEqual(binding['source_gate']['mode'],'full_gate_v1')
        for name in ['campaign','root_closure','root_confirmation','private_manifest']:
            self.assertEqual(binding['source_gate'][name],dict(path=None,sha256=None))
        self.assertEqual(binding['source_archive'],dict(path=None,sha256=None))
        self.assertFalse(binding['clock_assigned'])
        source=(ROOT/'audit_pair.py').read_text('utf-8')
        self.assertIn("policy.get('worker_callback_invocations')==8",source)
        self.assertIn("replay['completed_trials']>0",source)
        self.assertNotIn('optional_task_pair',source)


if __name__=='__main__':unittest.main()
