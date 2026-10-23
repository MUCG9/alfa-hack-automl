"""The ordinary platform invocation must activate the measured profile."""
from pathlib import Path
import os
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_submission import build_files, submission_entrypoint


class SubmissionProfileTests(unittest.TestCase):
    def dispatched(self, arguments, environment):
        observed = []
        runner = types.ModuleType('automl_runner')
        runner.THREADS = 2
        runner.llm_plan = runner.run_worker = None
        runner.main = lambda: observed.append((sys.argv[:], os.environ['AUTOML_THREADS']))
        with patch.dict(sys.modules, {'automl_runner': runner}), patch.object(sys, 'argv', ['solution.py', *arguments]), \
                patch.dict(os.environ, environment, clear=True):
            exec(compile(submission_entrypoint('incumbent_mix'), 'solution.py', 'exec'), {'__name__': '__main__'})
        self.assertEqual(len(observed), 1)
        return observed[0]

    def test_standard_command_activates_profile_without_disabling_role_discovery(self):
        argv, threads = self.dispatched(['task.md'], {})
        self.assertEqual(argv, ['solution.py', 'task.md', '--research-profile', 'incumbent_mix'])
        self.assertEqual(threads, '2')
        self.assertNotIn('--offline', argv)

    def test_explicit_arguments_and_thread_budget_are_preserved(self):
        for flag in [['--research-profile', 'incumbent_mix'], ['--research-profile=incumbent_mix']]:
            args = ['another-task.md', '--time-budget', '180', *flag]
            actual, threads = self.dispatched(args, {'AUTOML_THREADS': '1'})
            self.assertEqual(actual, ['solution.py', *args])
            self.assertEqual(threads, '1')

    def test_only_entrypoint_changes_and_unknown_profile_is_rejected(self):
        default = build_files(); deployed = build_files('incumbent_mix')
        self.assertEqual(set(default), set(deployed))
        self.assertEqual([name for name in default if default[name] != deployed[name]], ['solution.py'])
        self.assertEqual(deployed['requirements.txt'], (ROOT/'requirements.txt').read_bytes())
        with self.assertRaises(ValueError): build_files('unqualified-profile')


if __name__ == '__main__': unittest.main(verbosity=2)
