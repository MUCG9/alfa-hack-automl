"""Synthetic frozen artifact fixtures; no models are fitted."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_squared_error

from automl.contracts.messages import DatasetRef, PredictionBundle, TaskSpec, canonical_hash
from automl.error_analysis.api import (
    AnalysisArtifactRef, AnalysisBudget, DiagnosticBlend, ErrorAnalysisProtocol,
    ErrorAnalysisRequest, ModelPredictionRef,
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return AnalysisArtifactRef(str(path), sha(path))


class PassportFixture:
    def __init__(self, root, kind='classification', oof=False):
        self.root = Path(root)
        self.kind = kind
        self.classes = ('001', 'NA') if kind == 'classification' else ()
        self.truth = np.asarray(['001', 'NA'] * 12) if self.classes else np.arange(24) * 1.25 + 2
        self.frame = pd.DataFrame({'signal': np.arange(24, dtype=float), 'category': ['x', 'y', 'z'] * 8,
                                   'period': np.repeat([1, 2, 3], 8), 'answer': self.truth})
        self.dataset = self.root / 'train.csv'
        self.frame.to_csv(self.dataset, index=False)
        self.task = TaskSpec(kind, 'answer', None, ('signal', 'category', 'period'),
                             'macro_f1' if self.classes else 'rmse', bool(self.classes))
        self.protocol = ErrorAnalysisProtocol('fixture', numeric_features=('signal',), categorical_features=('category',),
            period_column='period', context_groups=(('category',),), min_slice_groups=2,
            min_bootstrap_groups=2, bootstrap_replicates=100,
            blends=(DiagnosticBlend('declared', ('control', 'candidate'), (.75, .25)),))
        self.protocol_path = self.root / 'protocol.json'
        self.protocol_path.write_text(self.protocol.to_json())
        refs = []
        folds = [(np.arange(12), np.arange(12, 24))]
        if oof:
            folds.append((np.arange(12, 24), np.arange(12)))
        for fold, (training, rows) in enumerate(folds):
            for model in ('control', 'candidate'):
                directory = self.root / (model + '-' + str(fold))
                directory.mkdir()
                np.savez(directory / 'split.npz', train=training, validation=rows)
                predicted = self.truth[rows].copy()
                if self.classes:
                    wrong = np.arange(len(rows)) % (5 if model == 'control' else 7) == 0
                    predicted[wrong] = np.where(predicted[wrong] == '001', 'NA', '001')
                    probabilities = np.array([[.9, .1] if p == '001' else [.1, .9] for p in predicted])
                    np.savez(directory / 'probabilities.npz', row_position=rows, classes=self.classes, probabilities=probabilities)
                    metric = f1_score(self.truth[rows], predicted, labels=self.classes, average='macro')
                else:
                    predicted = predicted + (np.arange(len(rows)) % 3 - 1) * (2 if model == 'control' else 1)
                    metric = mean_squared_error(self.truth[rows], predicted) ** .5
                pd.DataFrame({'row_position': rows, 'y_true': self.truth[rows], 'y_pred': predicted}).to_csv(directory / 'predictions.csv', index=False)
                recipe = {'engine': 'fixture', 'params': {'model': model}}
                (directory / 'result.json').write_text(json.dumps({'status': 'ok', 'full_fit': False,
                    'recipe': recipe, 'metrics': {self.task.metric: float(metric)}}))
                signature = hashlib.sha256(training.astype('<i8').tobytes() + rows.astype('<i8').tobytes()).hexdigest()
                refs.append(ModelPredictionRef(model, str(fold), canonical_hash(recipe), 'c' * 64,
                    PredictionBundle(str(directory / 'predictions.csv'), len(rows), ('row_position', 'y_true', 'y_pred'), self.classes, signature),
                    sha(directory / 'predictions.csv'), hashlib.sha256(rows.astype('<i8').tobytes()).hexdigest(), ref(directory / 'split.npz'),
                    probabilities=ref(directory / 'probabilities.npz') if self.classes else None,
                    probability_kind='raw' if self.classes else 'none', recorded_result=ref(directory / 'result.json')))
        self.request = ErrorAnalysisRequest('fixture', self.task, DatasetRef(str(self.dataset), sha(self.dataset), len(self.frame)),
            'control', self.protocol.protocol_id, ref(self.protocol_path), 'oof' if oof else 'search', tuple(refs),
            str(self.root / 'reports'), AnalysisBudget(60, 1024, 1))

    def set_protocol(self, **kwargs):
        self.protocol = replace(self.protocol, **kwargs)
        self.protocol_path.write_text(self.protocol.to_json())
        self.request = replace(self.request, protocol=ref(self.protocol_path))

    def change_result(self, **kwargs):
        value = self.request.predictions[0]
        path = Path(value.recorded_result.path)
        result = json.loads(path.read_text())
        result.update(kwargs)
        path.write_text(json.dumps(result))
        self.request = replace(self.request, predictions=(replace(value, recorded_result=ref(path)),) + self.request.predictions[1:])
