"""Local input-view preparation with mocked audit; no real data/fits needed."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_baseline_preparer', ROOT / 'tools/prepare_local_error_baseline.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LocalPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.tasks, self.sources, manifest = {}, {}, {}
        for kind in ('classification', 'regression'):
            folder = self.root / 'original' / kind
            folder.mkdir(parents=True)
            self.tasks[kind] = folder / 'task.md'
            self.tasks[kind].write_text('fixture task')
            self.sources[kind] = {}
            files = {'task.md': hashlib.sha256(self.tasks[kind].read_bytes()).hexdigest()}
            for role in ('train', 'test', 'data_dictionary', 'sample_submission'):
                path = folder / (role + '.csv')
                path.write_text('x,y\n1,2\n')
                self.sources[kind][role] = str(path)
                files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest[kind] = {'sha256': files}
        (self.root / 'docs/handoff').mkdir(parents=True)
        (self.root / 'docs/handoff/public_inputs.json').write_text(json.dumps(manifest))
        (self.root / 'transfer/v11-v16-caches').mkdir(parents=True)
        (self.root / 'transfer/v11-v16-caches/manifest.json').write_text(json.dumps({'source_root': '/old/root'}))
        self.output = self.root / 'prepared'
        self.audit_value = {'independent_checks_complete': True, 'raw_prediction_analysis': 'prepared_not_run',
                            'cache_inventory': [{'requests': [0, 1]} for _ in range(4)]}

    def run_prepare(self):
        with patch.object(module, 'ROOT', self.root), patch.object(module, 'load_inputs',
                side_effect=lambda task: {'paths': self.sources[task.parent.name]}), \
                patch.object(module, 'audit_baseline', return_value=self.audit_value) as audit:
            result = module.prepare(self.tasks, self.output)
        return result, audit

    def test_prepares_ten_verified_links_without_running_passports(self):
        result, audit = self.run_prepare()
        self.assertEqual(result['input_files_verified'], 10)
        self.assertEqual(result['prepared_requests'], 8)
        self.assertFalse(result['baseline_complete'])
        self.assertEqual(result['new_model_fits'], 0)
        self.assertEqual(audit.call_count, 1)
        self.assertTrue((self.output / 'input-view/classification/train.csv').is_symlink())

    def test_original_bytes_and_mtime_are_preserved(self):
        path = Path(self.sources['classification']['train'])
        old = path.read_bytes(), path.stat().st_mtime_ns
        self.run_prepare()
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), old)

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError): self.run_prepare()

    def test_bad_input_hash_fails_before_output_creation(self):
        Path(self.sources['regression']['train']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'SHA mismatch'): self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_missing_original_file_fails_before_output_creation(self):
        self.sources['classification']['train'] = str(self.root / 'missing.csv')
        with self.assertRaises(FileNotFoundError): self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_unknown_input_role_is_rejected(self):
        self.sources['classification']['extra'] = self.sources['classification']['train']
        with self.assertRaisesRegex(ValueError, 'input roles'): self.run_prepare()

    def test_both_task_roles_are_required(self):
        self.tasks.pop('regression')
        with self.assertRaisesRegex(ValueError, 'Both public'): self.run_prepare()


if __name__ == '__main__':
    unittest.main(verbosity=2)
