"""Single-level pinned LAMA with explicit inner holdout and fresh fixed refit."""
import time
import numpy as np
import pandas as pd
from automl.contracts.lama import LamaRequest,LamaResult


def fit_predict(request,train,test):
    if not isinstance(request,LamaRequest):raise ValueError('Typed LAMA request required')
    request.validate(len(train))
    from importlib.metadata import version
    pins={'lightautoml':'0.4.2','lightgbm':'4.6.0','numpy':'1.26.4','pandas':'2.2.3',
          'scikit-learn':'1.5.2','joblib':'1.4.2','threadpoolctl':'3.6.0'}
    if any(version(p)!=v for p,v in pins.items()):raise ValueError('Original LAMA/ML pins required')
    from lightautoml.automl.presets.tabular_presets import TabularAutoML
    from lightautoml.tasks import Task
    from lightautoml.dataset.roles import CategoryRole,NumericRole
    from sklearn.metrics import f1_score,mean_squared_error
    started=time.monotonic();deadline=started+request.seconds
    classification=request.task.kind=='classification';features=list(request.task.features)
    categorical=list(request.categorical_features);numeric=[c for c in features if c not in categorical]
    target_name='__lama_target__'
    if target_name in features:raise ValueError('Reserved internal target name')
    label_map={c:i for i,c in enumerate(request.classes)}

    def frame(data,rows=None,with_target=False):
        data=data if rows is None else data.iloc[list(rows)]
        value=data[features].copy().reset_index(drop=True)
        for c in categorical:value[c]=value[c].fillna('__missing__').astype(str)
        for c in numeric:value[c]=pd.to_numeric(value[c],errors='coerce').replace([np.inf,-np.inf],np.nan)
        if with_target:
            y=data[request.task.target]
            y=y.astype(str).map(label_map) if classification else pd.to_numeric(y,errors='raise')
            if y.isna().any() or not np.isfinite(y.to_numpy(dtype=float)).all():raise ValueError('Invalid fitting target')
            value[target_name]=y.to_numpy()
        return value

    def primary(y,p):
        return f1_score(y,np.asarray(p).argmax(axis=1),labels=np.arange(len(request.classes)),average='macro',zero_division=0) if classification else float(np.sqrt(mean_squared_error(y,np.asarray(p).ravel())))

    def preset(iterations,stop,remaining):
        if remaining<3:raise TimeoutError('LAMA deadline/refit reserve exhausted')
        task=Task('multiclass' if classification else 'reg',metric=primary,greater_is_better=classification)
        return TabularAutoML(task,timeout=max(1,int(remaining)),memory_limit=1,cpu_limit=request.threads,gpu_ids=None,
            general_params={'use_algos':[['lgb']],'nested_cv':False},selection_params={'mode':0},
            reader_params={'cv':False,'advanced_roles':False,'n_jobs':request.threads,'random_state':42},
            gbm_pipeline_params={'top_intersections':0,'max_intersection_depth':1,'use_groupby':False,'output_categories':False},
            lgb_params={'freeze_defaults':True,'default_params':{'num_trees':iterations,'early_stopping_rounds':stop,
                'learning_rate':.05,'num_leaves':63,'reg_lambda':8.,'bagging_fraction':1.,'bagging_freq':0,
                'feature_fraction':.9,'random_state':42,'verbose_eval':0}})

    roles={'target':target_name}
    if categorical:roles[CategoryRole(encoding_type='int')]=categorical
    if numeric:roles[NumericRole()]=numeric
    inner=frame(train,request.inner_training_rows,True)
    if classification and set(inner[target_name])!=set(range(len(request.classes))):raise ValueError('Inner training lacks class')
    stop=frame(train,request.inner_validation_rows,True)
    model=preset(request.iterations,min(30,request.iterations),request.seconds*.55)
    model.fit_predict(inner,roles=roles,valid_data=stop,verbose=0)
    if model.reader.cv is not False:raise ValueError('Unexpected random inner folds')
    algorithms=[a for level in model.levels for pipe in level for a in pipe.ml_algos]
    if len(algorithms)!=1 or len(algorithms[0].models)!=1:raise ValueError('Unexpected hidden LAMA ensemble')
    iterations=int(algorithms[0].models[0].current_iteration())
    if not 1<=iterations<=request.iterations:raise ValueError('Invalid frozen iterations')
    # New reader/encoders/learner, ALL fitting rows, fixed iterations and no stopping.
    refit=preset(iterations,0,deadline-time.monotonic())
    complete=frame(train,request.fitting_rows,True)
    refit.fit_predict(complete,roles=roles,verbose=0)
    learner=refit.levels[0][0].ml_algos[0]
    actual=int(learner.models[0].current_iteration())
    if actual!=iterations or refit.reader.cv is not False or len(learner.models)!=1:
        raise ValueError('Incomplete fixed-length full refit')
    if refit.reader.class_mapping is not None:raise ValueError('Unexpected class-order remapping')

    def predict(data):
        if time.monotonic()>=deadline:raise TimeoutError('LAMA export deadline')
        matrix=refit.predict(data).data
        if not np.isfinite(matrix).all():raise ValueError('Invalid LAMA prediction')
        if classification:
            if matrix.shape!=(len(data),len(request.classes)) or np.any(matrix<0) or not np.allclose(matrix.sum(axis=1),1,atol=1e-5):
                raise ValueError('Class probability alignment failed')
            return np.asarray(request.classes)[matrix.argmax(axis=1)],matrix
        return matrix.ravel(),None
    predicted,probabilities=predict(frame(train,request.evaluation_rows))
    test_prediction,test_probabilities=predict(frame(test))
    return LamaResult(predicted,probabilities,test_prediction,test_probabilities,request.classes,iterations,
        time.monotonic()-started,True,{'versions':pins,'learner':'lgb-only','inner_training_rows':len(inner),
        'inner_validation_rows':len(stop),'refit_rows':len(complete),'refit_iterations':actual,
        'stopping_source':'fitting-inner-only','refit_metric_is_in_sample_ignored':True,
        'random_folds':False,'target_encoding':False,'selection':False,'hpo':False,'pretrained':False})
