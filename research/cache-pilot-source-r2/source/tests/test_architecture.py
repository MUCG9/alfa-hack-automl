"""Contracts and dependency direction. Not a substitute for the full benchmark."""
from pathlib import Path
import ast,importlib.util,sys,unittest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.messages import TaskSpec,SplitPlan,ExperimentRequest,EvaluationResult,SelectionPlan

class ArchitectureTests(unittest.TestCase):
    def test_domain_only_imports_public_neighbor_api(self):
        source=ROOT/'src/automl'
        for path in source.rglob('*.py'):
            own=path.relative_to(source).parts[0]
            if own=='compat': continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node,ast.ImportFrom) or not node.module or not node.module.startswith('automl.'): continue
                parts=node.module.split('.')
                if parts[1] in {'task_understanding','evaluation','search','execution','publishing','error_analysis'} and parts[1]!=own:
                    self.assertEqual(parts[-1],'api',f'{path}: private import {node.module}')
    def test_contracts_have_no_model_data_or_client_dependencies(self):
        for path in (ROOT/'src/automl/contracts').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                modules=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
                for module in modules:
                    self.assertTrue(module and (module.split('.')[0] in sys.stdlib_module_names or module.startswith('automl.contracts.')),
                                    f'{path}: non-contract dependency {module}')
    def test_split_rejects_overlap_duplicates_and_bounds(self):
        SplitPlan((0,1),(2,3)).validate(4)
        for plan in [SplitPlan((0,1),(1,2)),SplitPlan((0,0),(1,)),SplitPlan((0,),(4,))]:
            with self.assertRaises(ValueError): plan.validate(4)
    def test_task_rejects_target_as_feature(self):
        with self.assertRaises(ValueError): TaskSpec.from_legacy({'kind':'regression','target':'y','id':'id','features':['y'],'metric':'rmse','greater_is_better':False})
    def test_result_and_selection_validation(self):
        with self.assertRaises(ValueError): EvaluationResult('rmse',float('nan'),'sha',False)
        with self.assertRaises(ValueError): SelectionPlan(('sha',),(-1.,)).validate()
    def test_build_contains_only_flat_modules_and_original_requirements(self):
        spec=importlib.util.spec_from_file_location('flat_builder',ROOT/'tools/build_submission.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        files=module.build_files()
        self.assertIn('solution.py',files); self.assertIn('automl_worker.py',files)
        self.assertTrue(all('/' not in name and '\\' not in name for name in files))
        self.assertEqual(files['requirements.txt'],(ROOT/'requirements.txt').read_bytes())
        self.assertNotIn('module_map.json',files)
    def test_signature_ignores_unused_xgboost_parameter(self):
        sys.path.insert(0,str(ROOT)); from agent_policy import normalize,signature
        first=normalize({'engine':'xgboost','params':{'max_depth':6}})
        second=normalize({'engine':'xgboost','params':{'max_depth':6,'num_leaves':255}})
        self.assertEqual(signature(first),signature(second))

if __name__=='__main__': unittest.main(verbosity=2)
