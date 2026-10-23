"""Process-boundary and evidence integrity checks; no data loading or model fits."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from automl.contracts.messages import DatasetRef, PredictionBundle, TaskSpec
from automl.error_analysis.api import (
    PROFILE_SECTIONS, AnalysisArtifactRef, AnalysisBudget, ModelPredictionRef,
    ErrorAnalysisRequest, ErrorProfileSection, ErrorFinding, ErrorProfile,
)


def artifact(name='protocol.json', digest='a'):
    return AnalysisArtifactRef('/unavailable/' + name, digest * 64)


def prediction(model='control', fold='0', classification=True, probabilities=True):
    classes = ('negative', 'positive') if classification else ()
    return ModelPredictionRef(
        model, fold, 'b' * 64, 'c' * 64,
        PredictionBundle('/unavailable/validation.csv', 10,
                         ('row_position', 'y_true', 'y_pred'), classes, 'd' * 64),
        'e' * 64, 'f' * 64, artifact('split.npz'),
        artifact('probabilities.npz') if probabilities and classification else None,
        'decision_adjusted' if probabilities and classification else 'none',
    )


def request(classification=True):
    return ErrorAnalysisRequest(
        'err-01', TaskSpec('classification' if classification else 'regression',
                           'answer', 'record', ('signal', 'category'),
                           'macro_f1' if classification else 'rmse', classification),
        DatasetRef('/unavailable/train.csv', 'a' * 64, 100),
        'control', 'ERR-01', artifact(), 'search',
        (prediction(classification=classification),), '/unavailable/reports', AnalysisBudget(),
    )


def profile(value=None):
    value = value or request()
    return ErrorProfile(
        value, value.sha256, '1' * 64, 'complete',
        tuple(ErrorProfileSection(name, 'complete', artifact(name + '.json')) for name in PROFILE_SECTIONS),
        ('Reused public diagnostics; not private-score evidence.',),
        (ErrorFinding('shared-errors', 'Measured paired errors.', ('models', 'comparisons')),),
    )


class ErrorAnalysisContractTests(unittest.TestCase):
    def test_request_json_roundtrip_keeps_nested_types_and_digest(self):
        original = replace(request(), predictions=(prediction(), prediction(fold='1'), prediction('candidate')),
                           prediction_scope='oof', groups=DatasetRef('/groups.csv', 'b' * 64, 100),
                           observation_time=DatasetRef('/time.csv', 'c' * 64, 100))
        restored = ErrorAnalysisRequest.from_json(original.to_json())
        self.assertEqual(restored, original)
        self.assertIsInstance(restored.dataset, DatasetRef)
        self.assertIsInstance(restored.predictions[0].predictions, PredictionBundle)
        self.assertEqual(restored.sha256, original.sha256)

    def test_regression_and_label_only_classification_are_supported(self):
        self.assertEqual(ErrorAnalysisRequest.from_dict(request(False).to_dict()), request(False))
        value = replace(request(), predictions=(prediction(probabilities=False),))
        self.assertEqual(value.predictions[0].probability_kind, 'none')

    def test_unknown_fields_are_rejected_at_every_boundary(self):
        for path in ((), ('task',), ('dataset',), ('budget',), ('protocol',), ('predictions', 0),
                     ('predictions', 0, 'predictions'), ('predictions', 0, 'split')):
            with self.subTest(path=path):
                value = request().to_dict()
                target = value
                for part in path:
                    target = target[part]
                target['train_model'] = True
                with self.assertRaises(ValueError):
                    ErrorAnalysisRequest.from_dict(value)

    def test_unknown_versions_are_rejected_including_legacy_references(self):
        old = request().to_dict()
        old['schema_version'] = '1.0'
        with self.assertRaisesRegex(ValueError, 'schema version'):
            ErrorAnalysisRequest.from_dict(old)
        for path in ((), ('task',), ('dataset',), ('budget',), ('protocol',), ('predictions', 0),
                     ('predictions', 0, 'predictions'), ('predictions', 0, 'split')):
            with self.subTest(path=path):
                value = request().to_dict()
                target = value
                for part in path:
                    target = target[part]
                target['schema_version'] = '99.0'
                with self.assertRaises(ValueError):
                    ErrorAnalysisRequest.from_dict(value)

    def test_duplicate_json_fields_and_nonfinite_numbers_are_rejected(self):
        for text in ('{"request_id":"a","request_id":"b"}', '{"budget":{"threads":1,"threads":2}}',
                     '{"budget":{"max_seconds":NaN}}', '{"budget":{"max_seconds":Infinity}}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ErrorAnalysisRequest.from_json(text)

    def test_missing_fields_and_wrong_json_types_are_rejected(self):
        for key, value in [('budget', {'threads': True}), ('budget', {'max_seconds': 10**400}), ('predictions', {}), ('task', None),
                           ('schema_version', 1), ('request_id', 9)]:
            payload = request().to_dict()
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ErrorAnalysisRequest.from_dict(payload)
        value = request().to_dict()
        del value['dataset']
        with self.assertRaises(ValueError):
            ErrorAnalysisRequest.from_dict(value)

    def test_references_validate_metadata_without_accessing_files(self):
        with patch('builtins.open', side_effect=AssertionError('Unexpected I/O')), \
             patch.object(Path, 'open', side_effect=AssertionError('Unexpected I/O')):
            value = profile()
            self.assertEqual(ErrorProfile.from_json(value.to_json()), value)
        for name in ('', '  ', '/bad\x00path'):
            with self.assertRaises(ValueError):
                AnalysisArtifactRef(name, 'a' * 64)
        for digest in ('short', 'G' * 64, 'a' * 63):
            with self.assertRaises(ValueError):
                AnalysisArtifactRef('/path', digest)

    def test_budget_rejects_boolean_unbounded_and_nonfinite_values(self):
        for kwargs in ({'threads': True}, {'threads': 9}, {'max_memory_mb': 0},
                       {'max_memory_mb': 32769}, {'max_seconds': 0}, {'max_seconds': 10801},
                       {'max_seconds': float('inf')}, {'max_seconds': float('nan')}, {'max_seconds': True}, {'max_seconds': 10**400}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AnalysisBudget(**kwargs)
        self.assertEqual(AnalysisBudget(max_seconds=60), AnalysisBudget.from_json(AnalysisBudget().to_json()))

    def test_test_and_full_fit_predictions_cannot_be_declared_diagnostics(self):
        for scope in ('test', 'full_fit', 'private', ''):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                replace(request(), prediction_scope=scope)

    def test_control_fold_uniqueness_and_model_identity_are_required(self):
        value = request()
        for predictions in ((), (prediction('candidate'),), (prediction(), prediction()),
                            (prediction(), replace(prediction(fold='1'), recipe_sha256='1' * 64)),
                            (prediction(), replace(prediction(fold='1'), source_sha256='2' * 64))):
            with self.subTest(predictions=predictions), self.assertRaises(ValueError):
                replace(value, predictions=predictions)

    def test_probability_artifacts_must_declare_semantics_and_class_order(self):
        for kwargs in ({'probability_kind': 'calibrated'}, {'probability_kind': 'none'}, {'probabilities': None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(prediction(), **kwargs)
        with self.assertRaises(ValueError):
            replace(prediction(), predictions=replace(prediction().predictions, classes=('positive', 'positive')))

    def test_legacy_shape_metadata_is_checked_without_changing_legacy_contracts(self):
        for bundle in (replace(prediction().predictions, rows=True),
                       replace(prediction().predictions, rows=0),
                       replace(prediction().predictions, columns=('x', 'x')),
                       replace(prediction().predictions, split_sha256='')):
            with self.subTest(bundle=bundle), self.assertRaises(ValueError):
                replace(prediction(), predictions=bundle)
        for kwargs in ({'predictions': (prediction(classification=False),)},
                       {'predictions': (replace(prediction(), predictions=replace(prediction().predictions, rows=101)),)},
                       {'dataset': DatasetRef('/train.csv', 'a' * 64, True)}):
            with self.assertRaises(ValueError):
                replace(request(), **kwargs)

    def test_task_roles_and_original_row_metadata_are_required(self):
        for task in (replace(request().task, features=('answer',)), replace(request().task, features=('record',)),
                     replace(request().task, features=('signal', 'signal')), replace(request().task, greater_is_better=1)):
            with self.assertRaises(ValueError):
                replace(request(), task=task)
        for name in ('groups', 'observation_time'):
            with self.assertRaises(ValueError):
                replace(request(), **{name: DatasetRef('/metadata.csv', 'a' * 64, 99)})

    def test_profile_json_roundtrip_retains_provenance_and_evidence(self):
        value = profile()
        self.assertEqual(ErrorProfile.from_json(value.to_json()), value)
        self.assertEqual(value.request_sha256, value.request.sha256)

    def test_profile_rejects_tampered_request_and_decision_authority(self):
        for kwargs in ({'request_sha256': '0' * 64}, {'analysis_source_sha256': ''}, {'diagnostic_only': False}, {'diagnostic_only': 1},
                       {'request': replace(request(), protocol_id='different-protocol')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(profile(), **kwargs)

    def test_missing_or_duplicate_sections_cannot_look_complete(self):
        value = profile()
        for sections in (value.sections[:-1], value.sections + (value.sections[0],)):
            with self.assertRaises(ValueError):
                replace(value, sections=sections)
        with self.assertRaises(ValueError):
            ErrorProfileSection('models', 'unavailable')
        with self.assertRaises(ValueError):
            ErrorProfileSection('models', 'failed', artifact(), 'Bad input')

    def test_partial_profile_requires_reason_and_consistent_overall_status(self):
        value = profile()
        sections = value.sections[:-1] + (ErrorProfileSection('uncertainty', 'unavailable', reason='Too few independent groups'),)
        with self.assertRaises(ValueError):
            replace(value, sections=sections)
        partial = replace(value, sections=sections, status='partial')
        self.assertEqual(ErrorProfile.from_json(partial.to_json()), partial)

    def test_alignment_failure_blocks_completed_diagnostics(self):
        value = profile()
        sections = (ErrorProfileSection('alignment', 'failed', reason='Incompatible rows'),) + value.sections[1:]
        with self.assertRaises(ValueError):
            replace(value, sections=sections, status='failed')
        sections = tuple(ErrorProfileSection(name, 'unavailable', reason='No validated artifacts') for name in PROFILE_SECTIONS)
        unavailable = replace(value, sections=sections, findings=(), status='failed')
        self.assertEqual(ErrorProfile.from_json(unavailable.to_json()), unavailable)
        failed = replace(unavailable, sections=(ErrorProfileSection('alignment', 'failed', reason='Incompatible rows'),) + sections[1:])
        self.assertEqual(ErrorProfile.from_json(failed.to_json()), failed)

    def test_findings_require_completed_evidence_and_limitations(self):
        value = profile()
        finding = ErrorFinding('uncertain', 'Uncertainty was measured.', ('uncertainty',))
        sections = value.sections[:-1] + (ErrorProfileSection('uncertainty', 'unavailable', reason='No intervals'),)
        with self.assertRaises(ValueError):
            replace(value, status='partial', sections=sections, findings=(finding,))
        with self.assertRaises(ValueError):
            replace(value, findings=value.findings * 2)
        with self.assertRaises(ValueError):
            replace(value, limitations=())

    def test_flat_transport_roundtrip_is_standalone_and_dependency_free(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        from build_submission import build_files
        with tempfile.TemporaryDirectory() as directory:
            for name, content in build_files().items():
                (Path(directory) / name).write_bytes(content)
            script = '''
import sys,json,importlib.abc
sys.path.insert(0,sys.argv[1])
class DenyDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy','pandas','openai','lightgbm','xgboost','catboost','sklearn'}:
            raise AssertionError('Unexpected dependency: '+fullname)
sys.meta_path.insert(0,DenyDependencies())
from automl_error_analysis_api import ErrorProfile
value=ErrorProfile.from_json(sys.stdin.read())
print(value.to_json())
'''
            original = profile()
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script, directory],
                                    input=original.to_json(), capture_output=True, text=True, timeout=15,
                                    cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(ErrorProfile.from_json(result.stdout), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
