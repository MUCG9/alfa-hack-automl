"""Prepared source contracts for actual current caller hooks; no real child/fit."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from automl.search import runner


class SelectorCacheConsumerTests(unittest.TestCase):
    def invoke_actual_worker_path(self, root, *, strict, enabled, spec_extra=None,
                                 recipe_extra=None):
        output = root / ('strict' if strict else 'legacy')
        spec = dict(root=str(root), **(spec_extra or {}))
        recipe = dict(engine='lightgbm', **(recipe_extra or {}))
        process = Mock(pid=321, returncode=0)
        process.poll.return_value = 0
        tree = Mock()
        budget = Mock()
        budget.inspect_artifacts.return_value = 0

        def child(*args, **kwargs):
            # Run the real job constructor/writer; replace only the external
            # child and its terminal artifact with a synthetic successful leaf.
            (output / 'result.json').write_text(json.dumps({'status': 'ok'}))
            return process

        strict_token = runner._STRICT_RUNTIME.set(strict)
        cache_token = runner._SELECTOR_IMPORTANCE_CACHE.set(enabled)
        try:
            with patch.object(runner, 'ExperimentRequest'), \
                 patch.object(runner, 'worker_entrypoint', return_value=root / 'mock-worker.py'), \
                 patch.object(runner.subprocess, 'Popen', side_effect=child) as spawn, \
                 patch.object(runner, 'ProcessTree', return_value=tree), \
                 patch.object(runner, 'ResourceBudget', return_value=budget), \
                 patch.object(runner, '_strict_worker_cleanup'), \
                 patch.object(runner.time, 'monotonic', return_value=50.):
                result = runner.run_worker(spec, recipe, output, root / 'split.npz', 30)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(spawn.call_count, 1)
            return json.loads((output / 'job.json').read_text())
        finally:
            runner._SELECTOR_IMPORTANCE_CACHE.reset(cache_token)
            runner._STRICT_RUNTIME.reset(strict_token)

    def test_real_strict_and_legacy_jobs_forward_only_explicit_scope(self):
        for strict in [False, True]:
            for enabled in [False, True]:
                with self.subTest(strict=strict, enabled=enabled), tempfile.TemporaryDirectory() as directory:
                    job = self.invoke_actual_worker_path(Path(directory), strict=strict, enabled=enabled)
                    if enabled:
                        self.assertIs(job['selector_importance_cache'], True)
                    else:
                        self.assertNotIn('selector_importance_cache', job)
                    self.assertEqual(job['threads'], runner.THREADS)
                    self.assertFalse(job['full_fit'])
                    self.assertNotIn('fit_iterations', job)

    def test_plain_cli_defaults_off_and_explicit_cli_scope_restores_after_error(self):
        for enabled in [False, True]:
            for fail in [False, True]:
                argv = ['solution.py', 'declared-task.md', '--offline']
                if enabled:
                    argv.append('--selector-importance-cache')
                observed = []

                def solve(*args, **kwargs):
                    observed.append(runner._SELECTOR_IMPORTANCE_CACHE.get())
                    if fail:
                        raise RuntimeError('synthetic-solver-failure')
                    return 'synthetic-result'

                baseline = runner._SELECTOR_IMPORTANCE_CACHE.get()
                with self.subTest(enabled=enabled, fail=fail), \
                     patch.object(sys, 'argv', argv), \
                     patch.object(runner, 'RunBudget'), \
                     patch.object(runner, 'load_inputs', return_value=object()), \
                     patch.object(runner, 'discover', return_value=object()), \
                     patch.object(runner, 'solve_single', side_effect=solve):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, 'synthetic-solver-failure'):
                            runner._main()
                    else:
                        self.assertEqual(runner._main(), 'synthetic-result')
                self.assertEqual(observed, [enabled])
                self.assertIs(runner._SELECTOR_IMPORTANCE_CACHE.get(), baseline)

    def test_invalid_trusted_scope_fails_before_job_write_or_child_launch(self):
        for invalid in [None, 0, 1, 'true', [], {}]:
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                token = runner._SELECTOR_IMPORTANCE_CACHE.set(invalid)
                strict_token = runner._STRICT_RUNTIME.set(True)
                try:
                    with patch.object(runner, 'atomic_json') as write, \
                         patch.object(runner.subprocess, 'Popen') as spawn, \
                         self.assertRaisesRegex(ValueError, 'scope must be a boolean'):
                        runner.run_worker({'root': str(root)}, {'engine': 'lightgbm'},
                            root / 'leaf', root / 'split.npz', 30)
                    write.assert_not_called()
                    spawn.assert_not_called()
                finally:
                    runner._STRICT_RUNTIME.reset(strict_token)
                    runner._SELECTOR_IMPORTANCE_CACHE.reset(token)

    def test_default_off_ignores_recipe_spec_environment_lookalikes(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                {'AUTOML_SELECTOR_IMPORTANCE_CACHE': '1', 'selector_importance_cache': 'true'}):
            job = self.invoke_actual_worker_path(Path(directory), strict=True, enabled=False,
                spec_extra={'selector_importance_cache': True},
                recipe_extra={'selector_importance_cache': True,
                              'params': {'selector_importance_cache': True}})
        self.assertNotIn('selector_importance_cache', job)
        self.assertIs(job['spec']['selector_importance_cache'], True)
        self.assertIs(job['recipe']['params']['selector_importance_cache'], True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
