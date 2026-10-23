"""Bounded held-out residual correction for an explicit log-target recipe."""
import numbers
import numpy as np
from automl.contracts.messages import DataPolicy


def validate_target_smearing(recipe,spec=None):
    params=recipe.get('params',{})
    requested=params.get('target_smearing',False)
    if type(requested) is not bool:raise ValueError('target_smearing must be boolean')
    if not requested:
        if 'target_smearing_method' in params:raise ValueError('Correction method requires target_smearing')
        return False
    method=params.get('target_smearing_method','duan')
    if not isinstance(method,str) or method not in {'duan','least_squares'}:
        raise ValueError('Unsupported target correction method')
    if recipe.get('engine') not in {'lightgbm','xgboost','catboost','extra_trees'} or params.get('log_target') is not True:
        raise ValueError('Target smearing requires a native log-target tree recipe')
    if not DataPolicy.parse(recipe.get('data_policy')).is_noop:
        raise ValueError('Target smearing requires noop data policy')
    if spec is not None and (spec.get('kind')!='regression' or spec.get('metric') not in {'rmse','mse'}
            or spec.get('text_features') or spec.get('task_family')=='pointwise_ranking'):
        raise ValueError('Target smearing requires nontext RMSE/MSE regression')
    return True


def fit_smearing(truth,prediction_log,method='duan'):
    if not isinstance(method,str) or method not in {'duan','least_squares'}:
        raise ValueError('Unsupported target correction method')
    truth=np.asarray(truth,dtype=float);predicted=np.asarray(prediction_log,dtype=float)
    if truth.ndim!=1 or truth.shape!=predicted.shape or not np.isfinite(truth).all() or not np.isfinite(predicted).all() or (truth<0).any():
        raise ValueError('Smearing requires aligned finite nonnegative held-out targets')
    result={'factor':1.,'calibration_rows':len(truth),'method':method}
    if len(truth)<20:return dict(result,status='skipped_insufficient_calibration_rows')
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        if method=='duan':
            raw=float(np.exp(np.log1p(truth)-predicted).mean())
        else:
            z=np.exp(predicted);target=truth+1.
            scale_z=float(z.max());scale_y=float(target.max())
            if not np.isfinite(z).all() or scale_z<=0:
                return dict(result,status='skipped_nonfinite_residual_moment')
            scaled_z=z/scale_z;scaled_y=target/scale_y
            raw=float((np.dot(scaled_z,scaled_y)/np.dot(scaled_z,scaled_z))*(scale_y/scale_z))
    if not np.isfinite(raw) or raw<=0:return dict(result,status='skipped_nonfinite_residual_moment')
    factor=float(np.clip(raw,.8,1.25))
    return dict(result,factor=factor,raw_factor=raw,status='fitted' if factor==raw else 'bounded')


def inverse_log_predictions(values,factor=1.):
    if isinstance(factor,bool) or not isinstance(factor,numbers.Real) or not np.isfinite(factor) or not .8<=factor<=1.25:
        raise ValueError('Invalid smearing factor')
    if factor==1.:return np.expm1(values)
    return np.expm1(np.asarray(values,dtype=float)+np.log(factor))
