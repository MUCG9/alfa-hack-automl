"""Prepared vertical contracts: tiny CSV I/O plus mocked solver/resources only."""
from contextlib import ExitStack,contextmanager
from pathlib import Path
from types import SimpleNamespace
import csv,json,sys,tempfile,unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.search import runner
from automl.task_understanding import service
from automl.task_understanding.early_declaration import bootstrap_early_declaration
from automl.task_understanding.early_output import prepare_early_output
from automl.contracts.metrics import MetricSpec,UnresolvedMetricError
from automl.infrastructure.processes import ProcessObservationError


def rows(path,values):
    with path.open('w',encoding='utf-8',newline='') as stream: csv.writer(stream).writerows(values)


@contextmanager
def case(*,metric='MAE',kind='regression',identifier=True,labels=None,
         ids=('a','b'),sample_ids=None,matrix=False,dictionary=False,extra_text='',placeholder='0'):
    with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
        root=Path(directory); ticks=[0.]
        train_name,test_name,sample_name='renamed-fit.csv','renamed-eval.csv','answer-layout.csv'
        labels=labels if labels is not None else ['1','2','30']
        columns=['entity','measurement','outcome'] if identifier else ['measurement','outcome']
        train=[[f't{i}',str(i+1),label] if identifier else [str(i+1),label] for i,label in enumerate(labels)]
        rows(root/train_name,[columns]+train)
        rows(root/test_name,([['entity','measurement']]+[[label,str(i+10)] for i,label in enumerate(ids)])
             if identifier else [['measurement'],['10'],['20']])
        output_columns=['zeta','alpha'] if matrix else ['outcome']
        template_columns=(['entity'] if identifier else [])+output_columns
        chosen=list(sample_ids or ids)
        template=[([label] if identifier else [])+[placeholder]*len(output_columns) for label in chosen]
        rows(root/sample_name,[template_columns]+template)
        text=[f'Train file: {train_name}',f'Test file: {test_name}',f'Output template: {sample_name}',
              f'Target: outcome',f'Task kind: {kind}',
              'ID column: entity' if identifier else 'ID policy: none',
              'Output kind: probability_matrix' if matrix else 'Output kind: value']
        if metric is not None:text.append('Primary metric: '+metric)
        if dictionary:
            rows(root/'explicit-role-map.csv',[['feature','role','dtype'],['outcome','target','numeric' if kind=='regression' else 'category'],['entity','id','string'],['measurement','feature','numeric']])
            text.append('Data dictionary: explicit-role-map.csv')
        text.append(extra_text)
        task=root/'task.md';task.write_text('\n'.join(text),encoding='utf-8')
        trace=root/'budget'/'report.json';trace.parent.mkdir()
        budget=SimpleNamespace(clock=lambda:ticks[0],deadline=60.,trace=trace,calls_started=0)
        resources=Mock();resources.inspect.return_value=(None,1,2)
        stack.enter_context(patch.object(runner,'ResourceBudget',return_value=resources))
        stack.enter_context(patch.object(runner,'source_files',return_value=[]))
        for name in ['request_json','run_worker','evaluate','choose_validation','llm_plan']:
            stack.enter_context(patch.object(runner,name,side_effect=AssertionError('Measured/API boundary must not run: '+name)))
        solve=stack.enter_context(patch.object(runner,'solve_single',return_value={'status':'mock_solver_received_valid_contract'}))
        token=runner._STRICT_TASK_CONTRACT.set(True);stack.callback(runner._STRICT_TASK_CONTRACT.reset,token)
        args=SimpleNamespace(task=task,time_budget=60,run_name='strict-unit')
        yield SimpleNamespace(root=root,task=task,args=args,budget=budget,ticks=ticks,resources=resources,
            solve=solve,call=lambda:runner._strict_task_flow(args,budget),
            report=lambda:json.loads((trace.parent/'task-contract.json').read_text(encoding='utf-8')))


class VerticalContractTests(unittest.TestCase):
    def test_legacy_OFF_does_not_enter_bootstrap_and_retains_runtime_scope(self):
        for runtime in (False,True):
            with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
                task=Path(directory)/'task.md';task.write_text('--strict-task-contract inside untrusted task text')
                calls=[]
                class Budget:
                    def __init__(self,*args):pass
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                stack.enter_context(patch.object(runner,'RunBudget',Budget))
                stack.enter_context(patch.object(runner,'_strict_task_flow',side_effect=AssertionError('OFF')))
                stack.enter_context(patch.object(runner,'load_inputs',side_effect=lambda *a,**k:calls.append(('load',k)) or 'loaded'))
                stack.enter_context(patch.object(runner,'discover',side_effect=lambda *a,**k:calls.append(('discover',k)) or 'data'))
                def solve(*args):
                    self.assertFalse(runner._STRICT_TASK_CONTRACT.get());self.assertEqual(runner._STRICT_RUNTIME.get(),runtime)
                    calls.append(('solve',args));return 'legacy'
                stack.enter_context(patch.object(runner,'solve_single',side_effect=solve))
                stack.enter_context(patch.object(sys,'argv',['solution.py',str(task)]+(['--strict-runtime'] if runtime else [])))
                self.assertEqual(runner._main(),'legacy')
                self.assertEqual([x[0] for x in calls],['load','discover','solve'])
                self.assertEqual(calls[0][1],{'allow_llm':True})

    def test_CLI_trusted_optin_enters_original_budget_and_restores_on_error(self):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            task=Path(directory)/'task.md';task.write_text('not consulted by mocked flow')
            active=[]
            class Budget:
                def __init__(self,*args):self.args=args
                def __enter__(self):active.append(self);return self
                def __exit__(self,*args):active.pop()
            stack.enter_context(patch.object(runner,'RunBudget',Budget))
            def flow(args,budget):
                self.assertIs(active[0],budget);self.assertTrue(runner._STRICT_TASK_CONTRACT.get())
                self.assertTrue(runner._STRICT_RUNTIME.get());raise RuntimeError('inert')
            stack.enter_context(patch.object(runner,'_strict_task_flow',side_effect=flow))
            stack.enter_context(patch.object(runner,'load_inputs',side_effect=AssertionError('legacy load')))
            stack.enter_context(patch.object(sys,'argv',['solution.py',str(task),'--strict-task-contract','--strict-runtime']))
            with self.assertRaisesRegex(RuntimeError,'inert'):runner._main()
            self.assertFalse(runner._STRICT_TASK_CONTRACT.get());self.assertFalse(runner._STRICT_RUNTIME.get());self.assertEqual(active,[])

    def test_atomic_metric_aware_fallback_exists_before_full_loader(self):
        with case(placeholder='') as c:
            original=runner.load_inputs
            def load(*args,**kwargs):
                with (c.root/'submission.csv').open(newline='') as stream:values=list(csv.DictReader(stream))
                self.assertEqual([r['outcome'] for r in values],['2.0','2.0'])
                self.assertEqual([r['entity'] for r in values],['a','b'])
                self.assertFalse(kwargs['allow_llm']);self.assertIn('declared',kwargs)
                return original(*args,**kwargs)
            with patch.object(runner,'load_inputs',side_effect=load):result=c.call()
            self.assertEqual(result['status'],'mock_solver_received_valid_contract')
            self.assertTrue(c.report()['full_input_provenance_verified'])
            self.assertEqual(c.solve.call_args.args[1][0]['metric'],'mae')

    def test_unknown_unsupported_and_ambiguous_metric_keep_fallback_and_never_load(self):
        for metric in (None,'custom_score','MAE and RMSE'):
            with self.subTest(metric=metric),case(metric=metric) as c,patch.object(runner,'load_inputs',side_effect=AssertionError('full load')):
                with self.assertRaises(UnresolvedMetricError):c.call()
                self.assertTrue((c.root/'submission.csv').is_file());self.assertFalse(c.solve.called)
                receipt=c.report();self.assertIsNone(receipt['metric_spec']['name']);self.assertIsNone(receipt['quality_metric'])
                self.assertEqual(receipt['status'],'format_only_metric_unresolved');self.assertEqual(receipt['model_planner_API_calls'],0)
        for changed in ['sample_header','task_metadata','dictionary_metadata']:
            with self.subTest(prepublication_drift=changed),case(metric=None,dictionary=True) as c,patch.object(runner,'load_inputs',side_effect=AssertionError('full load')):
                from automl.task_understanding import api as early_output
                original=early_output.prepare_early_output
                def drift(*args,**kwargs):
                    if changed=='sample_header':
                        rows(c.root/'answer-layout.csv',[['entity','other'],['a','0'],['b','0']])
                    else:
                        path=c.task if changed=='task_metadata' else c.root/'explicit-role-map.csv'
                        path.write_text(path.read_text()+'\n',encoding='utf-8')
                    return original(*args,**kwargs)
                with patch.object(early_output,'prepare_early_output',side_effect=drift):
                    with self.assertRaises(service.StrictTaskContractError):c.call()
                self.assertFalse((c.root/'submission.csv').exists());self.assertFalse(c.solve.called)
                self.assertFalse(c.report()['output_produced'])

    def test_unknown_format_and_multitarget_preserve_prior_bytes_without_fake_CSV(self):
        for text in ('The arbitrary prose says regression.','Targets: ["outcome", "other"]'):
            with case() as c,patch.object(runner,'load_inputs',side_effect=AssertionError('full load')):
                c.task.write_text(text if text.startswith('The') else c.task.read_text().replace('Target: outcome',text),encoding='utf-8')
                output=c.root/'submission.csv';output.write_bytes(b'last-good-unvalidated-prior')
                with self.assertRaises(service.StrictTaskContractError):c.call()
                self.assertEqual(output.read_bytes(),b'last-good-unvalidated-prior');self.assertFalse(c.report()['output_produced'])
                self.assertIn(c.report()['format_status'],['unknown','ambiguous','multitarget']);self.assertFalse(c.solve.called)
        for role,name in [('train','renamed-fit.csv'),('test','renamed-eval.csv'),
                          ('sample','answer-layout.csv'),('dictionary','explicit-role-map.csv'),('task','task.md')]:
            with self.subTest(overlap=role),case(dictionary=True) as c:
                output=c.root/'submission.csv';(c.root/name).rename(output)
                if role=='task':c.args.task=output
                else:c.task.write_text(c.task.read_text().replace(name,'submission.csv'),encoding='utf-8')
                protected=output.read_bytes()
                with self.assertRaisesRegex(service.StrictTaskContractError,'publication_overlaps_declared_source'):c.call()
                self.assertEqual(output.read_bytes(),protected);self.assertFalse(c.report()['output_produced']);self.assertFalse(c.solve.called)
        with case() as c,patch.object(runner.os.path,'samestat',return_value=True):
            output=c.root/'submission.csv';output.write_bytes(b'prior-output-distinct-path-same-filesystem-identity')
            with self.assertRaisesRegex(service.StrictTaskContractError,'publication_overlaps_declared_source'):c.call()
            self.assertEqual(output.read_bytes(),b'prior-output-distinct-path-same-filesystem-identity')
        with case() as c,patch.object(Path,'is_symlink',lambda path:path.name=='submission.csv'):
            with self.assertRaisesRegex(service.StrictTaskContractError,'publication_output_symlink'):c.call()
            self.assertFalse((c.root/'submission.csv').exists());self.assertFalse(c.solve.called)

    def test_resolved_hooks_bypass_legacy_kind_and_metric_guesses(self):
        with case(metric='RMSE',extra_text='classification is only a diagnostic word here') as c:
            with patch.object(service,'metric_from_text',side_effect=AssertionError('legacy metric guessing')):c.call()
            spec=c.solve.call_args.args[1][0]
            self.assertEqual((spec['kind'],spec['metric'],spec['greater_is_better']),('regression','rmse',False))
            self.assertEqual(spec['metric_spec']['status'],'resolved')

    def test_explicit_renamed_dictionary_roles_do_not_call_filename_or_LLM_resolution(self):
        with case(dictionary=True) as c,patch.object(service,'resolve_inputs',side_effect=AssertionError('role guessing')):
            c.call();spec=c.solve.call_args.args[1][0]
            self.assertEqual(Path(spec['paths']['data_dictionary']).name,'explicit-role-map.csv')
            provenance=json.loads((c.budget.trace.parent/'strict-input-provenance.json').read_text())
            self.assertIn('input:data_dictionary',provenance['sha256']);self.assertEqual(provenance['dictionary_path'],'explicit-role-map.csv')

    def test_lexical_test_ID_drift_stops_before_search_and_preserves_early_order(self):
        with case(ids=('001','1'),sample_ids=('1','001')) as c:
            with self.assertRaises(service.StrictTaskContractError):c.call()
            with (c.root/'submission.csv').open(newline='') as stream:values=list(csv.DictReader(stream))
            self.assertEqual([r['entity'] for r in values],['1','001']);self.assertFalse(c.solve.called)
            self.assertIn('lexical_drift',c.report()['reason'])

    def test_lexical_class_labels_lost_by_legacy_loader_are_not_silently_repaired(self):
        with case(metric='Macro F1',kind='classification',labels=['001','1','NA']) as c:
            with self.assertRaises(service.StrictTaskContractError):c.call()
            self.assertTrue(c.report()['output_produced']);self.assertFalse(c.solve.called)
            self.assertEqual(c.report()['metric_spec']['name'],'macro_f1')
            self.assertEqual(c.report()['status'],'blocked_full_input_contract')

    def test_probability_columns_class_order_and_sample_permutation_remain_authoritative(self):
        with case(metric='Log loss',kind='classification',labels=['zeta','alpha','zeta'],matrix=True,sample_ids=('b','a')) as c:
            c.call();spec=c.solve.call_args.args[1][0]
            self.assertEqual(spec['classes'],['alpha','zeta']);self.assertEqual(spec['output_columns'],['zeta','alpha'])
            self.assertEqual(spec['prediction_type'],'probability_matrix');self.assertEqual(spec['sample_test_positions'],[1,0])

    def test_full_input_or_task_change_after_publication_rejects_before_solver(self):
        for changed in ['renamed-fit.csv','task.md','explicit-role-map.csv']:
            with self.subTest(changed=changed),case(dictionary=True) as c:
                original=runner.load_inputs
                def load(*args,**kwargs):
                    result=original(*args,**kwargs)
                    path=c.root/changed;path.write_text(path.read_text()+'\n',encoding='utf-8');return result
                with patch.object(runner,'load_inputs',side_effect=load):
                    with self.assertRaises(service.StrictTaskContractError):c.call()
                self.assertTrue((c.root/'submission.csv').is_file());self.assertFalse(c.solve.called)
                self.assertEqual(c.report()['reason'],'protected_input_or_source_changed')

    def test_named_but_unsupported_strict_scope_stops_after_output_before_full_load(self):
        with case(metric='NDCG') as c,patch.object(runner,'load_inputs',side_effect=AssertionError('full load')):
            with self.assertRaises(service.StrictTaskContractError):c.call()
            self.assertTrue(c.report()['output_produced']);self.assertFalse(c.solve.called)
            self.assertEqual(c.report()['reason'],'objective_not_implemented_for_declared_kind')
        for metric,kind in [({'name':'rmse'},'regression'),(MetricSpec('rmse','minimize','value','resolved','test'),'classification')]:
            with self.assertRaises(service.StrictTaskContractError):service.discover(Path('unused'),resolved_metric=metric,task_kind=kind,output_contract={})

    def test_original_checkpoint_deadline_and_raw_denial_propagate_without_API(self):
        for failure in ('deadline','denial'):
            with case() as c:
                if failure=='deadline':
                    def late(*args):c.ticks[0]=61.;return None,1,2
                    c.resources.inspect.side_effect=late;expected=TimeoutError
                else:
                    c.resources.inspect.side_effect=runner.psutil.AccessDenied(123);expected=ProcessObservationError
                with self.assertRaises(expected):c.call()
                self.assertFalse(c.solve.called);self.assertFalse((c.root/'submission.csv').exists())
                self.assertEqual(c.budget.deadline,60.)

    def test_strict_candidate_checkpoint_validates_context_and_OFF_call_is_unchanged(self):
        with case() as c:
            declared=bootstrap_early_declaration(c.task,checkpoint=lambda:None)
            early=prepare_early_output(c.root,declared.paths,declared.declaration,declared.task_text,checkpoint=lambda:None)
            destination=c.root/'submission.csv';destination.write_bytes(b'last-good')
            bad=c.root/'bad.csv';rows(bad,[['entity','outcome'],['wrong','3'],['b','4']])
            with self.assertRaises(ValueError):runner._publish_task_checkpoint({'submission':str(bad)},destination,early.writer_spec,early.sample,early.test_ids)
            self.assertEqual(destination.read_bytes(),b'last-good')
            token=runner._STRICT_TASK_CONTRACT.set(False)
            try:
                with patch.object(runner,'checkpoint',return_value='legacy') as mocked:
                    self.assertEqual(runner._publish_task_checkpoint({'submission':'x'},destination,{},None,None),'legacy')
                    mocked.assert_called_once_with({'submission':'x'},destination)
            finally:runner._STRICT_TASK_CONTRACT.reset(token)


if __name__=='__main__':unittest.main()
