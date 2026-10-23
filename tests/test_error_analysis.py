"""Artifact integrity and end-to-end diagnostics; never trains a model."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.artifacts import load, Guard, AnalysisLimit
from error_analysis_fixture import PassportFixture, ref, sha
from automl.error_analysis.api import analyze, summarize, ErrorProfile
from automl.error_analysis.reporting import read_section, write_json


class ErrorAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def loaded(self, fixture):
        return load(fixture.request, Guard(fixture.request.budget))

    def test_json_artifact_hash_matches_exact_utf8_lf_bytes(self):
        value = {'label': '\u0414\u0430\u043d\u043d\u044b\u0435 \U0001f3af', 'escaped_lines': 'first\r\nsecond\n'}
        path = self.root / '\u043e\u0442\u0447\u0451\u0442.json'
        artifact = write_json(path, value)
        content = path.read_bytes()
        expected = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
        self.assertEqual(content, expected)
        self.assertNotIn(b'\r\n', content)
        self.assertEqual(json.loads(content.decode('utf-8')), value)
        self.assertEqual(artifact.sha256, sha(path))
        with self.assertRaises(FileExistsError):
            write_json(path, {'overwritten': True})

    def test_literal_labels_and_original_truth_are_preserved(self):
        data = self.loaded(PassportFixture(self.root))
        self.assertEqual(set(data.predictions[('control', '0')].truth), {'001', 'NA'})
        self.assertTrue(data.alignment['recorded_metrics_verified'])

    def test_full_oof_requires_exactly_once_coverage(self):
        fixture = PassportFixture(self.root, oof=True)
        data = self.loaded(fixture)
        self.assertEqual(data.alignment['oof_coverage'], 'exactly_once')
        fixture.request = replace(fixture.request, predictions=fixture.request.predictions[:2])
        with self.assertRaisesRegex(ValueError, 'exactly-once'):
            self.loaded(fixture)

    def test_overlapping_holdouts_are_not_pooled(self):
        fixture = PassportFixture(self.root)
        fixture.request = replace(fixture.request, predictions=fixture.request.predictions + tuple(replace(p, fold_id='1') for p in fixture.request.predictions))
        data = self.loaded(fixture)
        self.assertEqual(data.alignment['repeated_validation_rows'], 12)
        self.assertEqual(data.alignment['oof_coverage'], 'not_oof')

    def test_changed_input_bytes_are_rejected(self):
        fixture = PassportFixture(self.root)
        fixture.dataset.write_text(fixture.dataset.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.loaded(fixture)

    def test_changed_prediction_truth_is_rejected_even_with_updated_hash(self):
        fixture = PassportFixture(self.root)
        p = fixture.request.predictions[0]
        frame = pd.read_csv(p.predictions.path, dtype=str, keep_default_na=False)
        frame.loc[0, 'y_true'] = 'NA'
        frame.to_csv(p.predictions.path, index=False)
        fixture.request = replace(fixture.request, predictions=(replace(p, predictions_sha256=sha(p.predictions.path)),) + fixture.request.predictions[1:])
        with self.assertRaisesRegex(ValueError, 'truth'):
            self.loaded(fixture)

    def test_changed_row_order_is_rejected(self):
        fixture = PassportFixture(self.root)
        p = fixture.request.predictions[0]
        frame = pd.read_csv(p.predictions.path, dtype=str, keep_default_na=False).iloc[::-1]
        frame.to_csv(p.predictions.path, index=False)
        fixture.request = replace(fixture.request, predictions=(replace(p, predictions_sha256=sha(p.predictions.path)),) + fixture.request.predictions[1:])
        with self.assertRaisesRegex(ValueError, 'order'):
            self.loaded(fixture)

    def test_full_fit_result_cannot_be_validation_evidence(self):
        fixture = PassportFixture(self.root)
        fixture.change_result(full_fit=True)
        with self.assertRaisesRegex(ValueError, 'full-fit'):
            self.loaded(fixture)

    def test_recorded_recipe_and_metric_must_match(self):
        fixture = PassportFixture(self.root)
        fixture.change_result(metrics={'macro_f1': .99})
        with self.assertRaisesRegex(ValueError, 'metric'):
            self.loaded(fixture)
        fixture.change_result(recipe={'engine': 'tampered'})
        with self.assertRaisesRegex(ValueError, 'recipe'):
            self.loaded(fixture)

    def test_missing_result_is_not_treated_as_verified(self):
        fixture = PassportFixture(self.root)
        fixture.request = replace(fixture.request, predictions=(replace(fixture.request.predictions[0], recorded_result=None),) + fixture.request.predictions[1:])
        with self.assertRaisesRegex(ValueError, 'recorded result'):
            self.loaded(fixture)

    def test_nonunit_probability_mass_is_rejected(self):
        fixture = PassportFixture(self.root)
        p = fixture.request.predictions[0]
        with np.load(p.probabilities.path) as stored:
            content = dict(stored)
        content['probabilities'][0] = [.8, .8]
        np.savez(p.probabilities.path, **content)
        fixture.request = replace(fixture.request, predictions=(replace(p, probabilities=ref(p.probabilities.path)),) + fixture.request.predictions[1:])
        with self.assertRaisesRegex(ValueError, 'mass'):
            self.loaded(fixture)

    def test_probability_decisions_must_match_csv(self):
        fixture = PassportFixture(self.root)
        p = fixture.request.predictions[0]
        with np.load(p.probabilities.path) as stored:
            content = dict(stored)
        content['probabilities'][0] = content['probabilities'][0][::-1]
        np.savez(p.probabilities.path, **content)
        fixture.request = replace(fixture.request, predictions=(replace(p, probabilities=ref(p.probabilities.path)),) + fixture.request.predictions[1:])
        with self.assertRaisesRegex(ValueError, 'decisions'):
            self.loaded(fixture)

    def test_forward_split_must_be_strictly_earlier(self):
        fixture = PassportFixture(self.root, kind='regression')
        fixture.request = replace(fixture.request, prediction_scope='forward')
        with self.assertRaisesRegex(ValueError, 'future'):
            self.loaded(fixture)

    def test_forward_without_time_is_rejected(self):
        fixture = PassportFixture(self.root, kind='regression')
        fixture.set_protocol(period_column=None)
        fixture.request = replace(fixture.request, prediction_scope='forward')
        with self.assertRaisesRegex(ValueError, 'observation time'):
            self.loaded(fixture)

    def test_slice_columns_cannot_include_target(self):
        fixture = PassportFixture(self.root)
        fixture.set_protocol(numeric_features=('answer',))
        with self.assertRaisesRegex(ValueError, 'declared input'):
            self.loaded(fixture)

    def test_missing_control_fold_is_rejected(self):
        fixture = PassportFixture(self.root, oof=True)
        fixture.request = replace(fixture.request, predictions=tuple(p for p in fixture.request.predictions if (p.model_id, p.fold_id) != ('control', '1')))
        with self.assertRaisesRegex(ValueError, 'Control missing'):
            self.loaded(fixture)

    def test_different_candidate_fold_set_is_rejected(self):
        fixture = PassportFixture(self.root, oof=True)
        fixture.request = replace(fixture.request, predictions=tuple(p for p in fixture.request.predictions if (p.model_id, p.fold_id) != ('candidate', '1')))
        with self.assertRaisesRegex(ValueError, 'same fitting'):
            self.loaded(fixture)

    def test_budget_is_checked_before_input_reads(self):
        fixture = PassportFixture(self.root)
        guard = Guard(replace(fixture.request.budget, max_memory_mb=1))
        with self.assertRaises(AnalysisLimit):
            load(fixture.request, guard)

    def test_input_mutation_after_loading_is_detected(self):
        fixture = PassportFixture(self.root)
        guard = Guard(fixture.request.budget)
        load(fixture.request, guard)
        fixture.dataset.write_text(fixture.dataset.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            guard.verify_unchanged()

    def test_group_overlap_is_checked_on_original_rows(self):
        fixture = PassportFixture(self.root)
        path = self.root / 'groups.csv'
        pd.DataFrame({'row_position': np.arange(24), 'value': ['same'] * 24}).to_csv(path, index=False)
        from automl.contracts.messages import DatasetRef
        fixture.request = replace(fixture.request, groups=DatasetRef(str(path), sha(path), 24))
        with self.assertRaisesRegex(ValueError, 'groups overlap'):
            self.loaded(fixture)

    def test_unknown_protocol_fields_are_rejected(self):
        fixture = PassportFixture(self.root)
        payload = json.loads(fixture.protocol_path.read_text())
        payload['optimize_weights'] = True
        fixture.protocol_path.write_text(json.dumps(payload))
        fixture.request = replace(fixture.request, protocol=ref(fixture.protocol_path))
        with self.assertRaisesRegex(ValueError, 'unknown fields'):
            self.loaded(fixture)

    def test_complete_classification_passport_and_bounded_summary(self):
        fixture = PassportFixture(self.root, oof=True)
        profile = analyze(fixture.request)
        self.assertEqual(profile.status, 'complete', [(s.name, s.reason) for s in profile.sections])
        self.assertEqual(ErrorProfile.from_json((self.root / 'reports/error_profile.json').read_text()), profile)
        self.assertTrue((self.root / 'reports/error_profile.md').is_file())
        summary = summarize(profile)
        self.assertLess(len(json.dumps(summary).encode()), 8192)
        self.assertNotIn('row_position', json.dumps(summary))
        self.assertNotIn('y_true', json.dumps(summary))

    def test_regression_bias_variance_and_tail_statistics(self):
        fixture = PassportFixture(self.root, kind='regression')
        profile = analyze(fixture.request)
        result = read_section(profile, 'models')['models']['control']['folds']['0']
        self.assertAlmostEqual(result['mse'], result['bias_squared'] + result['residual_variance'])
        self.assertAlmostEqual(result['metrics']['rmse'], np.sqrt(8 / 3))
        self.assertGreaterEqual(result['largest_error_concentration']['0.05']['squared_error_share'],
                                result['largest_error_concentration']['0.01']['squared_error_share'])

    def test_regression_pairwise_mse_identity_and_fixed_blend(self):
        fixture = PassportFixture(self.root, kind='regression')
        profile = analyze(fixture.request)
        pair = read_section(profile, 'comparisons')['pairs'][0]['folds']['0']
        expected = .25 * pair['control']**2 + .25 * pair['candidate']**2 + .5 * pair['residuals']['mean_product']
        self.assertAlmostEqual(pair['fixed_half_blend']**2, expected)
        self.assertAlmostEqual(pair['residuals']['pearson'], 1)

    def test_declared_blend_ablation_renormalizes_without_refit(self):
        fixture = PassportFixture(self.root, kind='regression')
        profile = analyze(fixture.request)
        comparisons = read_section(profile, 'comparisons')
        blend = comparisons['declared_blends'][0]
        self.assertFalse(blend['weights_fitted'])
        pair = comparisons['pairs'][0]['folds']['0']
        without_control = next(v for v in blend['folds']['0']['ablations'] if v['removed'] == 'control')
        self.assertAlmostEqual(without_control['metrics']['rmse'], pair['candidate'])

    def test_fitting_quantile_boundaries_ignore_validation_feature_values(self):
        fixture = PassportFixture(self.root, kind='regression')
        loaded = self.loaded(fixture)
        from automl.error_analysis.slices import profiles
        first = profiles(loaded, Guard(fixture.request.budget))
        loaded.dataset.loc[12:, 'signal'] = 1e9
        second = profiles(loaded, Guard(fixture.request.budget))
        boundaries = lambda report: [s['definition'] for m in report['models'] for s in m['slices'] if s['dimension'] == 'numeric:signal']
        self.assertEqual(boundaries(first), boundaries(second))

    def test_too_few_groups_produces_partial_profile_with_reason(self):
        fixture = PassportFixture(self.root)
        fixture.set_protocol(min_bootstrap_groups=100)
        profile = analyze(fixture.request)
        self.assertEqual(profile.status, 'partial')
        uncertainty = next(s for s in profile.sections if s.name == 'uncertainty')
        self.assertEqual(uncertainty.status, 'unavailable')
        self.assertIn('enough independent', uncertainty.reason)

    def test_bootstrap_seed_is_reproducible_and_identical_predictions_have_zero_delta(self):
        fixture = PassportFixture(self.root)
        data = self.loaded(fixture)
        from automl.error_analysis.uncertainty import paired_bootstrap
        value = data.predictions[('control', '0')]
        a = paired_bootstrap(data.request.task, value, value, data.groups[value.rows], data.protocol, Guard(fixture.request.budget))
        b = paired_bootstrap(data.request.task, value, value, data.groups[value.rows], data.protocol, Guard(fixture.request.budget))
        self.assertEqual(a, b)
        self.assertEqual(a['paired_percentile_95'], [0, 0])

    def test_bootstrap_uses_declared_groups_instead_of_row_count(self):
        fixture = PassportFixture(self.root)
        path = self.root / 'groups.csv'
        pd.DataFrame({'row_position': np.arange(24), 'value': np.repeat(np.arange(4), 6)}).to_csv(path, index=False)
        from automl.contracts.messages import DatasetRef
        fixture.request = replace(fixture.request, groups=DatasetRef(str(path), sha(path), 24))
        profile = analyze(fixture.request)
        result = read_section(profile, 'uncertainty')
        self.assertEqual(result['unit'], 'declared_group')
        self.assertEqual(result['comparisons'][0]['units'], 2)

    def test_forward_single_period_never_gets_row_bootstrap_interval(self):
        fixture = PassportFixture(self.root, kind='regression')
        fixture.frame['period'] = np.repeat([1, 2], 12)
        fixture.frame.to_csv(fixture.dataset, index=False)
        fixture.request = replace(fixture.request, dataset=replace(fixture.request.dataset, sha256=sha(fixture.dataset)), prediction_scope='forward')
        profile = analyze(fixture.request)
        self.assertEqual(profile.status, 'partial')
        self.assertIsNone(read_section(profile, 'uncertainty'))
        self.assertEqual(read_section(profile, 'alignment')['oof_coverage'], 'not_oof')

    def test_invalid_input_returns_failed_manifest_without_completed_sections(self):
        fixture = PassportFixture(self.root)
        fixture.dataset.write_text(fixture.dataset.read_text() + '\n')
        profile = analyze(fixture.request)
        self.assertEqual(profile.status, 'failed')
        self.assertFalse(any(s.status == 'complete' for s in profile.sections))
        self.assertEqual(summarize(profile)['models'], [])

    def test_mutated_input_during_analysis_invalidates_all_downstream_sections(self):
        fixture = PassportFixture(self.root)
        from automl.error_analysis import service
        original = service.model_profiles
        def mutate(data, guard):
            result = original(data, guard)
            fixture.dataset.write_text(fixture.dataset.read_text() + '\n')
            return result
        with patch.object(service, 'model_profiles', side_effect=mutate):
            profile = analyze(fixture.request)
        self.assertEqual(profile.status, 'failed')
        self.assertFalse(any(s.status == 'complete' for s in profile.sections))

    def test_existing_output_and_input_directory_are_never_overwritten(self):
        fixture = PassportFixture(self.root)
        original = fixture.dataset.read_bytes()
        with self.assertRaises(FileExistsError):
            analyze(replace(fixture.request, output_dir=str(self.root.parent)))
        analyze(fixture.request)
        with self.assertRaises(FileExistsError):
            analyze(fixture.request)
        self.assertEqual(fixture.dataset.read_bytes(), original)

    def test_tampered_aggregate_is_rejected_by_summary(self):
        fixture = PassportFixture(self.root)
        profile = analyze(fixture.request)
        path = self.root / 'reports/models.json'
        original = path.read_bytes()
        path.write_bytes(original + b'\n')
        self.assertEqual(path.stat().st_size, len(original) + 1)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            summarize(profile)

    def test_constant_residual_correlation_is_explicitly_undefined(self):
        from automl.error_analysis.comparisons import correlation
        self.assertIsNone(correlation(np.ones(10), np.arange(10)))
        self.assertIsNone(correlation(np.arange(10), np.ones(10)))

    def test_bootstrap_scorer_matches_weighted_multiclass_f1_with_absent_classes(self):
        from types import SimpleNamespace
        from sklearn.metrics import f1_score
        from automl.error_analysis.uncertainty import _scorer
        value = SimpleNamespace(classes=('a', 'b', 'c'), truth=np.array(['a', 'b', 'a', 'c']),
                                predicted=np.array(['b', 'b', 'a', 'a']))
        task = PassportFixture(self.root).task
        weights = np.array([2., 3., 1., 0.])
        self.assertAlmostEqual(_scorer(task, value)(weights),
            f1_score(value.truth, value.predicted, labels=value.classes, average='macro', sample_weight=weights, zero_division=0))

    def test_section_request_identity_is_checked_even_with_updated_content_hash(self):
        fixture = PassportFixture(self.root)
        profile = analyze(fixture.request)
        path = self.root / 'reports/models.json'
        payload = json.loads(path.read_text())
        payload['request_sha256'] = '0' * 64
        path.write_text(json.dumps(payload))
        profile = replace(profile, sections=tuple(replace(s, result=ref(path)) if s.name == 'models' else s for s in profile.sections))
        with self.assertRaisesRegex(ValueError, 'identity'):
            summarize(profile)

    def test_probability_columns_are_aligned_across_models(self):
        fixture = PassportFixture(self.root)
        first, candidate = fixture.request.predictions
        with np.load(candidate.probabilities.path) as stored:
            content = dict(stored)
        expected = content['probabilities'].copy()
        content['classes'] = content['classes'][::-1]
        content['probabilities'] = content['probabilities'][:, ::-1]
        np.savez(candidate.probabilities.path, **content)
        candidate = replace(candidate, probabilities=ref(candidate.probabilities.path),
                            predictions=replace(candidate.predictions, classes=candidate.predictions.classes[::-1]))
        fixture.request = replace(fixture.request, predictions=(first, candidate))
        data = self.loaded(fixture)
        self.assertTrue(np.array_equal(data.predictions[('candidate', '0')].probabilities, expected))

    def test_compiled_backend_analyzes_without_checkout_imports(self):
        import subprocess
        sys.path.insert(0, str(ROOT / 'tools'))
        from build_submission import build_files
        fixture_root = self.root / '\u0434\u0430\u043d\u043d\u044b\u0435'
        fixture_root.mkdir()
        fixture = PassportFixture(fixture_root)
        compiled = self.root / '\u043a\u043e\u043c\u043f\u0438\u043b\u044f\u0446\u0438\u044f'
        compiled.mkdir()
        for name, content in build_files().items():
            (compiled / name).write_bytes(content)
        script = "import sys;sys.path.insert(0,sys.argv[1]);from automl_error_analysis_api import ErrorAnalysisRequest,analyze; p=analyze(ErrorAnalysisRequest.from_json(sys.stdin.read()));print(p.status)"
        result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', '-c', script, str(compiled)], input=fixture.request.to_json(),
                                capture_output=True, text=True, encoding='utf-8', timeout=30, cwd=compiled)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'complete', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
