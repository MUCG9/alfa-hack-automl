"""Strictly earlier-period regression statistics from the current fitting rows."""
import numpy as np
import pandas as pd

def validate_history_groups(train_x, test_x, time_column, groups):
    """Validate static feature contracts even when fitting support disables history."""
    if not isinstance(train_x, pd.DataFrame) or not isinstance(test_x, pd.DataFrame):
        raise ValueError('History features require training and test DataFrames')
    if not train_x.columns.is_unique or not test_x.columns.is_unique:
        raise ValueError('History features require unique input columns')
    if not isinstance(groups, list) or len(groups) > 3:
        raise ValueError('History features require at most three context groups')
    seen = set()
    for group in groups:
        if not isinstance(group, list) or not 1 <= len(group) <= 6 or any((not isinstance(column, str) for column in group)) or (len(set(group)) != len(group)) or (time_column in group):
            raise ValueError('History groups require 1..6 distinct non-time feature columns')
        key = frozenset(group)
        if key in seen:
            raise ValueError('History context groups must be distinct')
        seen.add(key)
    required = [time_column] + [column for group in groups for column in group]
    if any((column not in train_x or column not in test_x for column in required)):
        raise ValueError('History period and context columns must exist in both frames')
    names = [f'__history_{stat}_{number}' for number in range(len(groups)) for stat in ['last', 'trend']]
    if any((name in train_x or name in test_x for name in names)):
        raise ValueError('History feature collision')

def add_history_features(train_x, test_x, y, fit_rows, time_column, groups):
    """Append last context mean and its slope, using only fitting-period labels.

    ``fit_rows`` contains unique positional indices into ``train_x`` and ``y``.
    A Series target must have exactly the training frame's index; array-like
    targets are positional. Context selection belongs to the caller. Missing
    context values match other missing values, without a string sentinel. Query
    periods that cannot be represented as finite numbers have no history.

    A period mean is available only to queries with a strictly larger period.
    The trend at that period uses the two latest *distinct* fitting periods,
    divided by their actual period distance. Unrepresentable slopes remain NaN.
    No global prior fills absent data.
    """
    validate_history_groups(train_x, test_x, time_column, groups)
    rows = np.asarray(fit_rows)
    if rows.ndim != 1 or not len(rows) or (not np.issubdtype(rows.dtype, np.integer)) or np.any(rows < 0) or np.any(rows >= len(train_x)) or (len(np.unique(rows)) != len(rows)):
        raise ValueError('History fitting rows must be unique nonempty positional indices')
    if isinstance(y, pd.Series):
        if not y.index.equals(train_x.index):
            raise ValueError('History target index must match the training frame')
        fitting_targets = y.iloc[rows]
    else:
        if isinstance(y, pd.DataFrame) or len(y) != len(train_x):
            raise ValueError('History targets must align with the training frame')
        fitting_targets = [y[int(position)] for position in rows]
    try:
        targets = np.asarray(fitting_targets, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('History fitting targets must be finite numeric values') from exc
    if targets.ndim != 1 or len(targets) != len(rows) or (not np.isfinite(targets).all()):
        raise ValueError('History fitting targets must be finite numeric values')
    periods = np.concatenate([pd.to_numeric(frame[time_column], errors='coerce').to_numpy(dtype=float, na_value=np.nan) for frame in [train_x, test_x]])
    if not np.isfinite(periods[rows]).all():
        raise ValueError('History fitting periods must be finite numeric values')
    train_result = train_x.copy()
    test_result = test_x.copy()
    valid = np.flatnonzero(np.isfinite(periods))
    for number, group in enumerate(groups):
        contexts = pd.MultiIndex.from_frame(pd.concat([train_x[group], test_x[group]], ignore_index=True))
        codes = pd.factorize(contexts, sort=False)[0]
        history = pd.DataFrame({'context': codes[rows], 'period': periods[rows], 'last': targets})
        history = history.groupby(['context', 'period'], as_index=False, sort=True)['last'].mean()
        if not np.isfinite(history['last']).all():
            raise ValueError('History period means must be finite')
        previous = history.groupby('context', sort=False)[['period', 'last']].shift()
        with np.errstate(over='ignore', divide='ignore', invalid='ignore'):
            trend = (history['last'].to_numpy() - previous['last'].to_numpy()) / (history['period'].to_numpy() - previous['period'].to_numpy())
        history['trend'] = np.where(np.isfinite(trend), trend, np.nan)
        query = pd.DataFrame({'context': codes[valid], 'period': periods[valid], 'position': valid})
        matched = pd.merge_asof(query.sort_values('period'), history.sort_values('period'), on='period', by='context', direction='backward', allow_exact_matches=False)
        for stat in ['last', 'trend']:
            values = np.full(len(periods), np.nan)
            values[matched['position'].to_numpy(dtype=int)] = matched[stat].to_numpy()
            name = f'__history_{stat}_{number}'
            train_result[name] = values[:len(train_x)]
            test_result[name] = values[len(train_x):]
    return (train_result, test_result)
