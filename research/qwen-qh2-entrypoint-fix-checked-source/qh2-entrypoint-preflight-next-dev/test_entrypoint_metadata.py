"""Two pure/source metadata contracts; not executed during authoring."""
from pathlib import Path
import ast
import copy
import unittest
import preflight as p


class EntrypointMetadataContracts(unittest.TestCase):
    def parent(self):
        constants={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(p.TASK.read_text('utf-8')).body
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
            and n.targets[0].id in {'COOR_SHA','OWNER_SHA','PROCESS_SHA'}}
        helpers={key:dict(path=str(p.WORK/('synthetic-'+key+'.py')),sha256=constants[name])
            for key,name in [('coordinator','COOR_SHA'),('owner','OWNER_SHA'),('processes','PROCESS_SHA')]}
        pins={value['path']:value['sha256'] for value in helpers.values()}
        pins.update({str(p.CANONICAL/'agent_worker.py'):p.WRAPPER_SHA,
            str(p.CANONICAL/'src/automl/infrastructure/processes.py'):'9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3',
            str(p.RUNTIME):p.RUNTIME_SHA})
        return dict(canonical_root=str(p.CANONICAL),immutable_files=pins,helpers=helpers,
            python='synthetic-python',output=str(p.WORK/'synthetic-qh2'),requested_model='synthetic',reasoning_effort='synthetic',
            tasks=[dict(task=dict(kind=kind),spec={}) for kind in ('regression','classification')])

    def test_missing_wrapper_rejects_even_when_current_and_historical_process_roles_are_correct(self):
        cfg=self.parent();cfg['immutable_files'].pop(str(p.CANONICAL/'agent_worker.py'))
        with self.assertRaisesRegex(RuntimeError,'candidate_current_processes_distinct_from_historical_guard'):
            p.validate(cfg)
        self.assertEqual(cfg['helpers']['processes']['sha256'],'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d')

    def test_exact_wrapper_is_accepted_and_parent_task_maps_are_distinct_complete_copies(self):
        cfg=self.parent();before=copy.deepcopy(cfg);result=p.validate(cfg)
        self.assertTrue(result['entrypoint_binding_passed']);self.assertTrue(result['parent_to_task_pin_propagation_passed'])
        self.assertFalse(result['runtime_admitted']);self.assertFalse(result['campaign_clock_assigned']);self.assertEqual(cfg,before)
        task=p.projected_task(cfg,cfg['tasks'][0],p.WORK/'synthetic-task')
        self.assertEqual(task['immutable_files'],cfg['immutable_files']);self.assertIsNot(task['immutable_files'],cfg['immutable_files'])
        task['immutable_files'].pop(str(p.CANONICAL/'agent_worker.py'))
        self.assertIn(str(p.CANONICAL/'agent_worker.py'),cfg['immutable_files'])
        with self.assertRaises(RuntimeError):p.projected_bindings(task)
        for mode in ('wrong_wrapper','swapped_helper','wrong_current'):
            bad=copy.deepcopy(cfg)
            if mode=='wrong_wrapper':bad['immutable_files'][str(p.CANONICAL/'agent_worker.py')]='0'*64
            elif mode=='swapped_helper':bad['helpers']['processes']['sha256']='9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3'
            else:bad['immutable_files'][str(p.CANONICAL/'src/automl/infrastructure/processes.py')]='fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):p.validate(bad)


if __name__=='__main__':unittest.main(verbosity=2)
