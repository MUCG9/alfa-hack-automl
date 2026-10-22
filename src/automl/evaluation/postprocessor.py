"""Positive, bounded Macro F1 decision tuning; not probability calibration."""
import numbers
import numpy as np

from automl.evaluation.callbacks import tune_class_factors,adjusted_probabilities


def validate_decision_optimizer(recipe, spec=None):
    params=recipe.get('params',{})
    if 'decision_optimizer' not in params:
        return 'coordinate'
    method=params['decision_optimizer']
    if not isinstance(method,str) or method not in {'coordinate','nelder_mead'}:
        raise ValueError('Unsupported Macro F1 decision optimizer')
    if recipe.get('engine') not in {'lightgbm','xgboost','catboost','extra_trees'} or params.get('calibrate') is not True:
        raise ValueError('Decision optimizer requires a calibrated tree learner')
    if method=='nelder_mead' and (params.get('calibration_folds',1)!=1 or params.get('feature_views')):
        raise ValueError('Experimental refinement requires one ordinary inner-holdout learner')
    if spec is not None and (spec.get('kind')!='classification' or spec.get('metric')!='macro_f1'):
        raise ValueError('Decision optimizer requires Macro F1 classification')
    return method


class MacroF1ThresholdOptimizer:
    """Fit on fitting-only held-out/OOF probabilities, then evaluate elsewhere.

    The caller owns isolation: this class cannot certify where probabilities
    came from. ``fit`` never receives test/outer-validation labels in the worker.
    ``predict`` returns channel indices, ``predict_labels`` preserves class order.
    Optional Nelder–Mead only refines the existing conservative coordinate rule.
    """
    def __init__(self,n_classes,method='coordinate'):
        if isinstance(n_classes,bool) or not isinstance(n_classes,numbers.Integral) or n_classes<2:
            raise ValueError('n_classes must be an integer >=2')
        if not isinstance(method,str) or method not in {'coordinate','nelder_mead'}:
            raise ValueError('Unsupported decision optimizer')
        self.n_classes=int(n_classes)
        self.method=method
        self.weights=np.ones(self.n_classes)
        self.fitted_=False

    def _probabilities(self,values):
        values=np.asarray(values,dtype=float)
        if values.ndim!=2 or values.shape[1]!=self.n_classes or not len(values):
            raise ValueError('Probability matrix has an invalid shape')
        if not np.isfinite(values).all() or (values<0).any() or (values>1).any():
            raise ValueError('Probabilities must be finite and in[0,1]')
        if not np.allclose(values.sum(axis=1),1.,rtol=1e-6,atol=1e-8):
            raise ValueError('Probability rows must sum to one')
        return values

    def fit(self,oof_probs,y_true,classes=None):
        probabilities=self._probabilities(oof_probs)
        labels=np.asarray(np.arange(self.n_classes) if classes is None else classes,dtype=str)
        truth=np.asarray(y_true,dtype=str)
        if labels.shape!=(self.n_classes,) or len(np.unique(labels))!=self.n_classes:
            raise ValueError('Class channels must be distinct and match n_classes')
        if truth.shape!=(len(probabilities),) or not set(truth)<=set(labels):
            raise ValueError('Labels must align with probability rows and channels')
        self.classes_=labels
        lookup={c:i for i,c in enumerate(labels)}
        encoded=np.asarray([lookup[c] for c in truth],dtype=int)
        support=np.bincount(encoded,minlength=self.n_classes)
        initial_factors=tune_class_factors(truth,probabilities,labels)
        self.weights=np.asarray([initial_factors[c] for c in labels])
        # Macro F1 exactly matches sklearn's explicit full-class macro definition.
        def objective(weights):
            predicted=np.argmax(probabilities*weights,axis=1)
            counts=np.bincount(predicted,minlength=self.n_classes)
            correct=np.bincount(encoded[predicted==encoded],minlength=self.n_classes)
            denominator=support+counts
            f1=np.divide(2.*correct,denominator,out=np.zeros(self.n_classes),where=denominator>0).mean()
            return float(f1-.004*np.square(np.log(weights)).mean())
        initial=objective(self.weights)
        self.diagnostics_={'method':self.method,'status':'coordinate_warm_start',
            'initial_objective':initial,'final_objective':initial,'optimizer_nfev':0,
            'max_function_evaluations':400 if self.method=='nelder_mead' else 0}
        if self.method=='nelder_mead':
            self._refine(objective)
        self.factors_={str(c):float(w) for c,w in zip(self.classes_,self.weights)}
        self.fitted_=True
        return self

    def _refine(self,objective):
        from scipy.optimize import minimize
        low,high=np.log(.4),np.log(2.5)
        initial=self.weights.copy();best=objective(initial)
        logs=np.log(initial)
        simplex=np.tile(logs,(self.n_classes+1,1))
        for i in range(self.n_classes):
            simplex[i+1,i]+= .15 if logs[i]+.15<=high else -.15
        try:
            result=minimize(lambda x:-objective(np.exp(x)),logs,method='Nelder-Mead',
                bounds=[(low,high)]*self.n_classes,
                options={'initial_simplex':simplex,'maxiter':400,'maxfev':400,'adaptive':True})
            candidate=np.exp(np.asarray(result.x,dtype=float))
            valid=(candidate.shape==initial.shape and np.isfinite(candidate).all()
                and (candidate>=.4-1e-12).all() and (candidate<=2.5+1e-12).all())
            self.diagnostics_['optimizer_nfev']=int(result.nfev)
            self.diagnostics_['optimizer_converged']=bool(result.success)
            if valid and objective(candidate)>best+1e-12:
                self.weights=np.clip(candidate,.4,2.5)
                self.diagnostics_.update(status='refined' if result.success else 'refined_budget_exhausted',
                    final_objective=objective(self.weights))
            else:
                self.diagnostics_['status']='preserved_coordinate_warm_start'
        except Exception as exc:
            self.diagnostics_.update(status='preserved_coordinate_on_optimizer_error',exception_type=type(exc).__name__)

    def predict_proba(self,probabilities):
        if not self.fitted_:
            raise ValueError('Fit the decision optimizer before prediction')
        values=self._probabilities(probabilities)
        return adjusted_probabilities(values,self.classes_,self.factors_)

    def predict(self,probabilities):
        return self.predict_proba(probabilities).argmax(axis=1)

    def predict_labels(self,probabilities):
        return self.classes_[self.predict(probabilities)]


def calibrate_class_factors(y,probabilities,classes,method='coordinate'):
    # Keep the default function call byte-for-byte numerically equivalent.
    if method=='coordinate':
        return tune_class_factors(y,probabilities,classes),{'method':'coordinate','status':'legacy'}
    fitted=MacroF1ThresholdOptimizer(len(classes),method).fit(probabilities,y,classes)
    return fitted.factors_,fitted.diagnostics_
