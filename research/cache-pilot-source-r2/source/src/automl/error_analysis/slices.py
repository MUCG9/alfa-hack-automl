"""Predeclared slices; numeric cutpoints and support counts use fitting rows."""
import numpy as np
import pandas as pd

from automl.error_analysis.artifacts import score


def _keys(frame, columns):
    return pd.util.hash_pandas_object(frame[list(columns)], index=False).to_numpy()


def _counts(keys, groups):
    return pd.DataFrame({'key': keys, 'group': groups}).drop_duplicates().groupby('key').size()


def profiles(data, guard):
    result = []
    task = data.request.task
    for (model, fold), value in sorted(data.predictions.items()):
        guard.check()
        fit = data.dataset.iloc[value.training]
        held = data.dataset.iloc[value.rows]
        masks = []
        missing = held[list(task.features)].isna().sum(axis=1).to_numpy()
        for label, mask in [('0', missing == 0), ('1', missing == 1), ('2-4', (missing >= 2) & (missing <= 4)), ('5+', missing >= 5)]:
            masks.append(('missing_feature_count', label, mask, None))
        for feature in data.protocol.numeric_features:
            fitting = pd.to_numeric(fit[feature], errors='coerce').replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
            values = pd.to_numeric(held[feature], errors='coerce').to_numpy(dtype=float)
            edges = np.unique(np.quantile(fitting, np.linspace(0, 1, data.protocol.quantile_bins + 1)[1:-1])) if len(fitting) else np.array([])
            bins = np.searchsorted(edges, values, side='right')
            for i in range(len(edges) + 1):
                masks.append(('numeric:' + feature, str(i), (bins == i) & np.isfinite(values), {'fitting_cutpoints': edges.tolist()}))
            masks.append(('numeric:' + feature, 'missing', ~np.isfinite(values), {'fitting_cutpoints': edges.tolist()}))
        for feature in data.protocol.categorical_features:
            fitting_keys, held_keys = _keys(fit, (feature,)), _keys(held, (feature,))
            counts = _counts(fitting_keys, data.groups[value.training])
            support = pd.Series(held_keys).map(counts).fillna(0).to_numpy()
            for label, mask in [('unseen', support == 0), ('rare', (support > 0) & (support <= data.protocol.rare_max_groups)), ('supported', support > data.protocol.rare_max_groups)]:
                masks.append(('category_support:' + feature, label, mask, None))
            top = counts.sort_values(ascending=False, kind='stable').head(data.protocol.max_categories).index
            for i, key in enumerate(top):
                masks.append(('category:' + feature, 'fitting_top_' + str(i), held_keys == key, None))
            masks.append(('category:' + feature, 'other_or_unseen', ~np.isin(held_keys, top), None))
        for i, columns in enumerate(data.protocol.context_groups):
            fitting_keys, held_keys = _keys(fit, columns), _keys(held, columns)
            counts = _counts(fitting_keys, data.groups[value.training])
            support = pd.Series(held_keys).map(counts).fillna(0).to_numpy()
            for label, mask in [('unseen', support == 0), ('rare', (support > 0) & (support <= data.protocol.rare_max_groups)), ('supported', support > data.protocol.rare_max_groups)]:
                masks.append(('context_support:' + str(i), label, mask, {'columns': list(columns)}))
            if data.request.prediction_scope == 'forward' and data.times is not None:
                periods = pd.DataFrame({'key': fitting_keys, 'period': data.times[value.training]}).groupby('key').period.nunique()
                count = pd.Series(held_keys).map(periods).fillna(0).to_numpy()
                for label, mask in [('none', count == 0), ('1-2', (count > 0) & (count < 3)), ('3+', count >= 3)]:
                    masks.append(('earlier_context_periods:' + str(i), label, mask, {'columns': list(columns), 'interpretation': 'Fitting-only context coverage proxy, not engine-specific history eligibility.'}))
        if data.times is not None:
            # Validation period values are used only to describe evaluation slices.
            for period in np.unique(data.times[value.rows])[:50]:
                masks.append(('observation_period', str(period), data.times[value.rows] == period, None))
        if task.kind == 'regression':
            edges = np.unique(np.quantile(fit[task.target], [.25, .5, .75]))
            bins = np.searchsorted(edges, value.predicted, side='right')
            for i in range(len(edges) + 1):
                masks.append(('predicted_magnitude', str(i), bins == i, {'fitting_target_cutpoints': edges.tolist()}))
        entries = []
        total_sse = float(np.sum((value.predicted - value.truth) ** 2)) if task.kind == 'regression' else None
        for dimension, label, mask, definition in masks:
            guard.check()
            n = int(mask.sum())
            group_count = int(len(np.unique(data.groups[value.rows][mask])))
            item = {'dimension': dimension, 'slice': label, 'rows': n, 'independent_groups': group_count,
                    'low_support': group_count < data.protocol.min_slice_groups, 'definition': definition}
            if n:
                probabilities = value.probabilities[mask] if value.probabilities is not None else None
                item['metrics'] = score(task, value.truth[mask], value.predicted[mask], probabilities, value.classes)
                if total_sse is not None:
                    item['squared_error_share'] = float(np.sum((value.predicted[mask] - value.truth[mask]) ** 2) / total_sse) if total_sse else 0.
            else:
                item['metrics'] = None
            entries.append(item)
        result.append({'model': model, 'fold': fold, 'slices': entries})
    return {'models': result, 'boundaries_source': 'fitting rows only',
            'interpretation': 'Exploratory overlapping slices, not disjoint totals, routing rules or significance tests.'}
