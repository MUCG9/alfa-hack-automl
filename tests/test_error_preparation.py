"""Relocation, supervisor and portable BASE-01 checks; no model fitting."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.api import audit_baseline, prepare_report_request, analyze, DiagnosticBlend, ErrorAnalysisProtocol
from error_analysis_fixture import PassportFixture, sha


class ErrorPreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def report_fixture(self):
        fixture = PassportFixture(self.root)
        shutil.copyfile(self.root / 'control-0/split.npz', self.root / 'split.npz')
        shutil.copyfile(self.root / 'control-0/split.npz', self.root / 'confirmation_split.npz')
        records = []
        for p in fixture.request.predictions:
            directory = Path(p.recorded_result.path).parent
            shutil.copyfile(directory / 'predictions.csv', directory / 'validation_predictions.csv')
            shutil.copyfile(directory / 'probabilities.npz', directory / 'validation_probabilities.npz')
            record = json.loads(Path(p.recorded_result.path).read_text())
            record['output_dir'] = '/unavailable-old-laptop/' + Path(p.recorded_result.path).parent.name
            records.append(record)
        spec = {'kind': fixture.kind, 'target': 'answer', 'id': None, 'features': list(fixture.task.features),
                'metric': 'macro_f1', 'greater_is_better': True, 'n_train': 24, 'classes': list(fixture.classes),
                'categorical_features': ['category'], 'validation_strategy': 'legacy'}
        report = {'spec': spec, 'integrity_ok': True, 'final_fit_status': 'ok', 'experiments': records,
                  'confirmations': records, 'selected_recipe': records[0]['recipe'], 'ensemble': None}
        path = self.root / 'report.json'
        path.write_text(json.dumps(report))
        sources = self.root / 'sources.json'
        sources.write_text(json.dumps({'fixture.py': 'a' * 64}))
        (self.root / 'provenance.json').write_text(json.dumps({'sha256': {'input:train': sha(fixture.dataset), 'source:/old/fixture.py': 'a' * 64}}))
        return fixture, path, sources

    def test_relocated_caches_use_explicit_root_not_original_absolute_paths(self):
        fixture, report, sources = self.report_fixture()
        request = prepare_report_request(report, self.root, fixture.dataset, sources, self.root / 'prepared')
        self.assertTrue(all(Path(p.predictions.path).is_relative_to(self.root) for p in request.predictions))
        profile = analyze(request)
        self.assertEqual(next(s for s in profile.sections if s.name == 'alignment').status, 'complete')

    def test_missing_cache_is_not_replaced_by_another_run(self):
        fixture, report, sources = self.report_fixture()
        shutil.rmtree(self.root / 'candidate-0')
        with self.assertRaises(FileNotFoundError):
            prepare_report_request(report, self.root, fixture.dataset, sources, self.root / 'prepared')
        self.assertFalse((self.root / 'prepared').exists())

    def test_selected_ensemble_is_control_and_its_fixed_components_are_retained(self):
        fixture, path, sources = self.report_fixture()
        report = json.loads(path.read_text())
        directory = self.root / 'ensemble-primary'
        directory.mkdir()
        with np.load(self.root / 'control-0/validation_probabilities.npz') as a, np.load(self.root / 'candidate-0/validation_probabilities.npz') as b:
            probabilities = .5 * a['probabilities'] + .5 * b['probabilities']
            rows, classes = a['row_position'], a['classes']
        predicted = classes[probabilities.argmax(axis=1)]
        np.savez(directory / 'validation_probabilities.npz', probabilities=probabilities, classes=classes, row_position=rows)
        pd.DataFrame({'row_position': rows, 'y_true': fixture.truth[rows], 'y_pred': predicted}).to_csv(directory / 'validation_predictions.csv', index=False)
        recipe = {'engine': 'ensemble', 'params': {}, 'components': [r['recipe'] for r in report['experiments']], 'weights': [.5, .5]}
        result = {'recipe': recipe, 'status': 'ok', 'full_fit': False,
                  'metrics': {'macro_f1': float(f1_score(fixture.truth[rows], predicted, labels=classes, average='macro'))}}
        (directory / 'result.json').write_text(json.dumps(result))
        report['selected_recipe'] = recipe
        report['ensemble'] = {'primary': dict(result, output_dir='/old/ensemble-primary')}
        path.write_text(json.dumps(report))
        request = prepare_report_request(path, self.root, fixture.dataset, sources, self.root / 'prepared')
        self.assertEqual(len(request.predictions), 3)
        profile = analyze(request)
        from automl.error_analysis.reporting import read_section
        models = read_section(profile, 'models')
        comparison = read_section(profile, 'comparisons')
        self.assertEqual(comparison['declared_blends'][0]['folds']['search']['metrics']['macro_f1'],
                         models['models'][request.control_model_id]['folds']['search']['metrics']['macro_f1'])

    def test_changed_report_recipe_is_not_matched_by_directory_name(self):
        fixture, path, sources = self.report_fixture()
        report = json.loads(path.read_text())
        report['experiments'][0]['recipe'] = {'engine': 'wrong'}
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'differs'):
            prepare_report_request(path, self.root, fixture.dataset, sources, self.root / 'prepared')

    def test_relocated_dataset_requires_original_content_fingerprint(self):
        fixture, report, sources = self.report_fixture()
        fixture.frame.loc[0, 'signal'] = -999
        fixture.frame.to_csv(fixture.dataset, index=False)
        with self.assertRaisesRegex(ValueError, 'original run provenance'):
            prepare_report_request(report, self.root, fixture.dataset, sources, self.root / 'prepared')

    def test_source_manifest_must_match_frozen_run(self):
        fixture, report, sources = self.report_fixture()
        sources.write_text(json.dumps({'fixture.py': 'b' * 64}))
        with self.assertRaisesRegex(ValueError, 'source provenance'):
            prepare_report_request(report, self.root, fixture.dataset, sources, self.root / 'prepared')

    def test_request_workspace_is_immutable(self):
        fixture, report, sources = self.report_fixture()
        workspace = self.root / 'prepared'
        workspace.mkdir()
        with self.assertRaises(FileExistsError):
            prepare_report_request(report, self.root, fixture.dataset, sources, workspace)

    def test_protocol_and_blend_roundtrip_and_bounds(self):
        protocol = ErrorAnalysisProtocol('test', blends=(DiagnosticBlend('fixed', ('a', 'b'), (3., 1.)),))
        self.assertEqual(ErrorAnalysisProtocol.from_json(protocol.to_json()), protocol)
        self.assertEqual(protocol.blends[0].weights, (.75, .25))
        for kwargs in ({'bootstrap_replicates': 10}, {'numeric_features': ['x']}, {'max_pairs': 0}, {'high_confidence': float('nan')}):
            with self.assertRaises(ValueError):
                ErrorAnalysisProtocol('test', **kwargs)
        with self.assertRaises(ValueError):
            DiagnosticBlend('bad', ('a', 'b'), (1., 0.))

    def test_guarded_cli_generates_passport_in_child_process(self):
        fixture = PassportFixture(self.root)
        request_path = self.root / 'request.json'
        request_path.write_text(fixture.request.to_json())
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/error_passport.py'), '--request', str(request_path)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'complete')

    def test_portable_baseline_audit_marks_remote_caches_blocked(self):
        # Real tracked evidence and input hashes, not new model measurements.
        if not (ROOT / 'public_tasks/classification/train.csv').is_file():
            self.skipTest('Public inputs are external to Git')
        result = audit_baseline(ROOT, ROOT / 'public_tasks', self.root / 'audit')
        self.assertTrue(result['independent_checks_complete'])
        self.assertEqual(result['raw_prediction_analysis'], 'blocked')
        self.assertFalse(result['baseline_complete'])
        self.assertFalse(result['v10_used_as_v11'])
        self.assertEqual(len(result['cache_inventory']), 4)
        self.assertTrue(all(c['status'] == 'blocked_missing_cache' for c in result['cache_inventory']))
        self.assertTrue(all(not p['actual_csv_bytes_verified'] for p in result['portable_parity'].values()))

    def test_portable_audit_refuses_to_overwrite(self):
        output = self.root / 'audit'
        output.mkdir()
        with self.assertRaises(FileExistsError):
            audit_baseline(ROOT, ROOT / 'public_tasks', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
