"""A single checked time representation for discovery and forward evaluation."""
import numpy as np
import pandas as pd


def observation_values(series):
    if not pd.api.types.is_datetime64_any_dtype(series):
        numeric=pd.to_numeric(series,errors='coerce')
        if numeric.notna().all() and np.isfinite(numeric.to_numpy(dtype=float)).all():
            return numeric,'numeric'
    parsed=pd.to_datetime(series,errors='coerce',utc=True,format='mixed')
    if parsed.isna().any(): raise ValueError('Observation times must be complete finite numbers or parseable dates')
    return parsed.astype('int64')/(86400.*10**9),'datetime'
