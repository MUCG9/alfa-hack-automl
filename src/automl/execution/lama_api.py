"""Opt-in LAMA research API, not registered in the default worker/planner."""
def fit_predict_lama(request,train,test):
    from automl.execution.model_adapters.lama import fit_predict
    return fit_predict(request,train,test)
