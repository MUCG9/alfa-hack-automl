"""Artifact integrity and end-to-end diagnostics; never trains a model."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.artifacts import load, Guard, AnalysisLimit
from error_analysis_fixture import PassportFixture, ref, sha


class ErrorAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def loaded(self, fixture):
        return load(fixture.request, Guard(fixture.request.budget))

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
