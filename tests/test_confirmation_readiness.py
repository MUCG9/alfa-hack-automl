"""No fitting: fail-closed readiness and output isolation on tiny file fixtures."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_selector_confirmation import long_run_ready, prepare


class ConfirmationReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def completed(self, index):
        task = self.root / f'task-{index:02d}'
        run = task / 'automl_runs/run-v2'
        run.mkdir(parents=True)
        (task / 'submission.csv').write_bytes(b'id,target\n0,1\n')
        digest = hashlib.sha256((task / 'submission.csv').read_bytes()).hexdigest()
        (task / 'assessment.json').write_text(json.dumps({'exit_code': 0, 'submission_sha256': digest}))
        (run / 'anytime_state.json').write_text(json.dumps({'phase': 'completed'}))
        (run / 'report.json').write_text(json.dumps({'version': 'long-01-anytime',
            'integrity_ok': True, 'exported_full_fit_ok': True, 'exported_mean': 1.,
            'final_fit_status': 'preserved_trained_baseline', 'submission_sha256': digest}))
        return task, run

    def change(self, path, **values):
        content = json.loads(path.read_text())
        content.update(values)
        path.write_text(json.dumps(content))

    def test_empty_or_half_completed_run_not_ready(self):
        self.assertFalse(long_run_ready(self.root))
        self.completed(0)
        self.assertFalse(long_run_ready(self.root))

    def test_both_actual_trained_fallback_exports_are_valid(self):
        self.completed(0)
        self.completed(1)
        self.assertTrue(long_run_ready(self.root))

    def test_running_state_does_not_allow_next_fit(self):
        self.completed(0)
        _, run = self.completed(1)
        self.change(run / 'anytime_state.json', phase='exploration')
        self.assertFalse(long_run_ready(self.root))

    def test_failure_requires_review_not_automatic_restart(self):
        task, _ = self.completed(0)
        self.change(task / 'assessment.json', exit_code=-9)
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_boolean_exit_code_is_not_a_real_zero(self):
        task, _ = self.completed(0)
        self.change(task / 'assessment.json', exit_code=False)
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_actual_csv_checksum_must_match(self):
        task, _ = self.completed(0)
        (task / 'submission.csv').write_bytes(b'corrupted')
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_success_flag_without_trained_export_rejected(self):
        _, run = self.completed(0)
        self.change(run / 'report.json', exported_full_fit_ok=False)
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_integrity_failure_rejected(self):
        _, run = self.completed(0)
        self.change(run / 'report.json', integrity_ok=False)
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_nonfinite_exported_metric_rejected(self):
        _, run = self.completed(0)
        self.change(run / 'report.json', exported_mean=float('nan'))
        with self.assertRaises(ValueError): long_run_ready(self.root)

    def test_plan_cannot_write_inside_active_run(self):
        with self.assertRaisesRegex(ValueError, 'active LONG-01'):
            prepare(self.root / 'absent', self.root / 'absent2', self.root / 'plan.json', self.root)

    def test_existing_plan_is_never_overwritten(self):
        target = self.root / 'plan.json'
        target.write_text('preserve')
        with self.assertRaises(FileExistsError):
            prepare(self.root / 'absent', self.root / 'absent2', target, self.root / 'separate-run')
        self.assertEqual(target.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main(verbosity=2)
