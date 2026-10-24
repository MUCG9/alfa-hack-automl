"""Label-preserving missingness robustness hypothesis, not unconditional augmentation."""
import numpy as np
import pandas as pd

def add_copies(x, y, weights, parents, reference, policy, rng, engine, max_rows):
    if engine not in {'lightgbm', 'xgboost', 'catboost'}:
        raise ValueError('Masking requires native missing-value support')
    rates = reference.isna().mean()
    columns = [c for c in reference if pd.api.types.is_numeric_dtype(reference[c]) and 0.01 < rates[c] < 0.85 and (reference[c].nunique() > 10)]
    if not columns:
        return (x, y, weights, parents, {'synthetic_rows': 0, 'skipped': 'No eligible partially missing continuous fitting feature'})
    count = min(int(len(reference) * policy.copy_fraction), max(0, max_rows - len(x)))
    chosen = rng.choice(len(x), count, replace=False)
    copies = x.iloc[chosen].copy()
    for column in columns:
        mask = (rng.random(count) < policy.mask_probability) & copies[column].notna().to_numpy()
        copies.loc[mask, column] = np.nan
    return (pd.concat([x, copies], ignore_index=True), pd.concat([y, y.iloc[chosen]], ignore_index=True), np.r_[weights, weights[chosen] * policy.synthetic_weight], np.r_[parents, parents[chosen]], {'synthetic_rows': count, 'masked_columns': columns})
