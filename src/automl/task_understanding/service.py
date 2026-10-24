from pathlib import Path
import re,json,hashlib
import numpy as np
import pandas as pd
from automl.task_understanding.metrics import metric_from_text,LOWER_IS_BETTER
from automl.task_understanding.inputs import find_input,resolve_inputs
from automl.infrastructure.tables import read_input_table
from automl.infrastructure.observation_time import observation_values
from automl.task_understanding.probabilities import infer_positive_class


def infer_static_numeric(dictionary,train,features):
    """Schema-described construction attributes can refine recurring contexts."""
    result=[]
    for row in dictionary.to_dict(orient='records'):
        column=row.get('feature')
        description=' '.join(str(row.get(k,'')) for k in ['feature','description','description_ru']).lower()
        if column in features and pd.api.types.is_numeric_dtype(train[column]) and re.search(r'built|construction|построй',description):
            result.append(column)
    return result


def infer_time_candidate(dictionary,train,test,features):
    """Conservative observation-period detection, without dataset-specific names."""
    candidates=[]
    for row in dictionary.to_dict(orient='records'):
        column=row.get('feature')
        if column not in features: continue
        description=' '.join(str(row.get(k,'')) for k in ['feature','role','dtype','description_ru','description']).lower()
        if not re.search(r'year|period|timestamp|date|период|год.*наблюд|времен',description): continue
        if re.search(r'built|construction|построй|возраст|\bage\b|birth|duration|длитель',description): continue
        if not len(test): continue
        try:
            a,representation=observation_values(train[column]); b,test_representation=observation_values(test[column])
        except ValueError: continue
        if representation!=test_representation: continue
        if a.nunique()>=3 and b.min()>a.max():
            candidates.append({'column':column,'reason':'Documented observation period; entire test range follows training range',
                               'representation':representation,'split_mode':'chronological_block' if representation=='datetime' or a.nunique()>100 else 'period',
                               'train_min':float(a.min()),'train_max':float(a.max()),'test_min':float(b.min()),'test_max':float(b.max())})
    return candidates[0] if len(candidates)==1 else None
class MultipleTargets(ValueError):
    def __init__(self,targets):
        self.targets=tuple(targets)
        super().__init__('Expected one target, got '+repr(list(targets)))


class StrictTaskContractError(ValueError):
    """Explicit opt-in handoff failed; retain the already validated fallback."""


def _strict_objective(resolved_metric,task_kind,output_contract):
    from automl.contracts.metrics import MetricSpec
    if type(resolved_metric) is not MetricSpec:
        raise StrictTaskContractError('typed_resolved_metric_required')
    resolved_metric.require_resolved()
    allowed={'regression':{'rmse','mae','mse','mape','rmsle','r2'},
             'classification':{'macro_f1','weighted_f1','accuracy','balanced_accuracy','roc_auc','log_loss'}}
    if task_kind not in allowed or resolved_metric.name not in allowed[task_kind]:
        raise StrictTaskContractError('objective_not_implemented_for_declared_kind')
    if (type(output_contract) is not dict or output_contract.get('kind')!=task_kind
            or output_contract.get('metric')!=resolved_metric.name
            or output_contract.get('greater_is_better')!=(resolved_metric.direction=='maximize')):
        raise StrictTaskContractError('objective_output_contract_conflict')
    return resolved_metric


def _load_declared_inputs(task_path,declared,checkpoint):
    """Explicit-role full load only; legacy table dtype rules are unchanged."""
    from automl.task_understanding.early_declaration import EarlyDeclaration
    if type(declared) is not EarlyDeclaration or not declared.ready_for_projection or not callable(checkpoint):
        raise StrictTaskContractError('typed_declaration_and_checkpoint_required')
    checkpoint(); task_path=Path(task_path).resolve(); root=task_path.parent
    paths={}
    roles=dict(declared.paths)
    dictionary=(declared.receipt or {}).get('dictionary_path')
    if dictionary is not None: roles['data_dictionary']=dictionary
    for role,value in roles.items():
        checkpoint(); raw=Path(value); path=root/raw
        if raw.is_absolute() or '..' in raw.parts or path.is_symlink():
            raise StrictTaskContractError('declared_role_path_drift')
        path=path.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise StrictTaskContractError('declared_role_path_drift')
        paths[role]=path
    if set(paths)-{'train','test','sample_submission','data_dictionary'} or not {'train','test','sample_submission'}<=set(paths):
        raise StrictTaskContractError('declared_role_set_drift')
    tables={}
    for role,key in [('train','train'),('test','test'),('sample_submission','sample')]:
        checkpoint(); tables[key]=read_input_table(paths[role]); checkpoint()
    checkpoint()
    tables['dictionary']=read_input_table(paths['data_dictionary']) if dictionary is not None else pd.DataFrame(columns=['feature','role'])
    checkpoint()
    return {'root':root,'task_path':task_path,'text':declared.task_text,'paths':paths,
            **tables,'file_role_resolution':{'method':'strict_explicit_declaration','semantic_API_calls':0}}


def validate_declared_inputs(loaded,declared,early,*,checkpoint):
    """Check protected projections before profiling or changing any dtype.

    Numeric features keep the legacy loader. A protected lexical value lost by
    that loader is rejected rather than reconstructed. Only exact revalidated
    class/ID strings are then handed to the existing worker/publisher.
    """
    from automl.task_understanding.early_declaration import EarlyDeclaration
    from automl.task_understanding.early_output import EarlyOutputResult
    if (type(declared) is not EarlyDeclaration or type(early) is not EarlyOutputResult
            or not declared.ready_for_projection or not early.ready_for_publication or not callable(checkpoint)):
        raise StrictTaskContractError('typed_early_handoff_required')
    checkpoint(); writer=early.writer_spec; root=Path(loaded['root']).resolve()
    expected={r:(root/Path(v)).resolve() for r,v in declared.paths.items()}
    dictionary=(declared.receipt or {}).get('dictionary_path')
    if dictionary is not None: expected['data_dictionary']=(root/dictionary).resolve()
    if (loaded['paths']!=expected or loaded['text']!=declared.task_text
            or Path(loaded['task_path']).resolve().parent!=root):
        raise StrictTaskContractError('full_load_role_or_task_drift')
    train,test,sample=(loaded[k] for k in ['train','test','sample'])
    for role,frame in [('train',train),('test',test),('sample_submission',sample)]:
        checkpoint()
        actual=hashlib.sha256(json.dumps(list(frame.columns),ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
        if actual!=(declared.receipt or {}).get('header_sha256',{}).get(role) or frame.columns.duplicated().any():
            raise StrictTaskContractError('full_load_header_drift:'+role)
    counts=early.receipt['row_counts']
    if [len(train),len(test),len(sample)]!=[counts['train'],counts['test'],counts['sample']]:
        raise StrictTaskContractError('full_load_row_count_drift')
    target,identifier=writer['target'],writer['id']
    def exact_strings(left,right,label):
        checkpoint()
        if left.isna().any() or left.astype(str).tolist()!=right.astype(str).tolist():
            raise StrictTaskContractError('full_load_lexical_drift:'+label)
    if writer['kind']=='classification':
        exact_strings(train[target],early.target_frame[target],'target')
        if sorted(train[target].astype(str).unique().tolist())!=writer['classes'] or len(writer['classes'])<2:
            raise StrictTaskContractError('full_load_class_order_or_cardinality_drift')
    else:
        checkpoint()
        values=pd.to_numeric(train[target],errors='raise').to_numpy(dtype=float)
        expected_y=early.target_frame[target].to_numpy(dtype=float)
        if not np.isfinite(values).all() or not np.array_equal(values,expected_y):
            raise StrictTaskContractError('full_load_target_value_drift')
    if identifier is not None:
        exact_strings(test[identifier],early.test_ids[identifier],'test_ID')
        exact_strings(sample[identifier],early.sample[identifier],'sample_ID')
    # Placeholder cells are not objective evidence. Header, row count and
    # protected IDs are checked here; the caller separately binds whole input
    # bytes. Use the already validated lexical sample for later publication.
    train_features=[c for c in train if c not in {target,identifier}]
    test_features=[c for c in test if c!=identifier]
    if train_features!=test_features:
        raise StrictTaskContractError('undeclared_train_test_columns')
    dictionary_frame=loaded['dictionary']
    if len(dictionary_frame):
        if not {'feature','role'}<=set(dictionary_frame):
            raise StrictTaskContractError('full_load_dictionary_schema_drift')
        roles=dictionary_frame['role'].astype(str).str.strip().str.lower()
        for role,wanted in [('target',[target]),('id',[] if identifier is None else [identifier])]:
            actual=dictionary_frame.loc[roles.eq(role),'feature'].tolist()
            if actual and actual!=wanted:
                raise StrictTaskContractError('full_load_dictionary_role_drift:'+role)
    checkpoint()
    if writer['kind']=='classification': train[target]=early.target_frame[target].to_numpy(copy=True)
    if identifier is not None: test[identifier]=early.test_ids[identifier].to_numpy(copy=True)
    loaded['sample']=early.sample.copy()
    loaded['strict_handoff_validated']=True
    checkpoint(); return loaded


def _read_tables(paths):
    train = read_input_table(paths['train'])
    test = read_input_table(paths['test'])
    sample = read_input_table(paths['sample_submission'])
    dictionary = read_input_table(paths['data_dictionary']) if 'data_dictionary' in paths else pd.DataFrame(columns=['feature','role'])
    return {'train':train,'test':test,'sample':sample,'dictionary':dictionary}


def load_inputs(task_path:Path,allow_llm=False,*,declared=None,checkpoint=None):
    if declared is not None:
        return _load_declared_inputs(task_path,declared,checkpoint)
    root=task_path.resolve().parent; text=task_path.read_text(encoding='utf-8-sig')
    resolution={}; accepted={}
    def validate(paths):
        from automl.task_understanding.role_validation import validate_role_tables
        tables=_read_tables(paths)
        validate_role_tables(tables)
        accepted.update(tables)
    paths=resolve_inputs(root,text,allow_llm=allow_llm,resolution=resolution,validate=validate)
    tables=accepted or _read_tables(paths)
    return {'root':root,'task_path':task_path.resolve(),'text':text,'paths':paths,
            **tables,'file_role_resolution':resolution}


def discover(task_path: Path,target_override=None,loaded=None,allow_llm=False,*,resolved_metric=None,task_kind=None,output_contract=None):
    strict=any(v is not None for v in (resolved_metric,task_kind,output_contract))
    if strict:
        _strict_objective(resolved_metric,task_kind,output_contract)
        if loaded is None or loaded.get('strict_handoff_validated') is not True:
            raise StrictTaskContractError('validated_full_input_handoff_required')
    loaded=load_inputs(task_path,allow_llm=allow_llm) if loaded is None else loaded
    if loaded['task_path']!=task_path.resolve(): raise ValueError('Cached inputs belong to a different task')
    root,text,paths=(loaded[k] for k in ['root','text','paths'])
    train,test,sample,dictionary=(loaded[k] for k in ['train','test','sample','dictionary'])
    if train.columns.duplicated().any() or test.columns.duplicated().any():
        raise ValueError('Duplicate column names are unsupported')
    roles = dictionary['role'].astype(str).str.strip().str.lower() if 'role' in dictionary else pd.Series(dtype=str)
    groups=dictionary.loc[roles.isin(['group','group_id','validation_group','query','query_id']), 'feature'].tolist() if len(roles) else []
    groups=[c for c in groups if c in train and c in test]
    targets = dictionary.loc[roles.eq('target'), 'feature'].tolist() if len(roles) else []
    if strict: targets=[output_contract['target']]
    elif not targets or any(c not in train for c in targets):
        targets = [c for c in train if c not in test]
    if len(targets)>1 and target_override is None: raise MultipleTargets(targets)
    if target_override is not None:
        if target_override not in targets: raise ValueError('Requested target is not declared in training data')
        target=target_override
    elif len(targets)==1: target=targets[0]
    else: raise ValueError(f'Expected one target, got {targets}')
    all_ids = dictionary.loc[roles.eq('id'), 'feature'].tolist() if len(roles) else []
    if strict: all_ids=[] if output_contract['id'] is None else [output_contract['id']]
    ids = list(all_ids)
    ids = [c for c in ids if c in sample and c in test and c not in targets]
    if not ids and not strict:
        ids = [c for c in sample if c in test and c not in targets]
    if len(ids) > 1:
        raise ValueError('Ambiguous sample ID columns')
    identifier = ids[0] if ids else None
    if train[target].isna().any():
        raise ValueError('Training target contains missing values')
    if len(sample)!=len(test): raise ValueError('Sample/test row counts differ')
    sample_positions=None
    if identifier is not None:
        if test[identifier].isna().any() or test[identifier].duplicated().any():
            raise ValueError('Test IDs are missing or duplicated')
        if sample[identifier].isna().any() or sample[identifier].duplicated().any():
            raise ValueError('Sample IDs are missing or duplicated')
        positions=pd.Index(test[identifier]).get_indexer(sample[identifier])
        if (positions<0).any(): raise ValueError('Sample/test ID values differ')
        if not np.array_equal(positions,np.arange(len(test))): sample_positions=positions.tolist()
    if len(targets)>1:
        if target not in sample: raise ValueError('Multi-target output columns must match declared target names')
        sample=sample[[c for c in sample if c==identifier or c==target]].copy()
    features = [c for c in test if c not in set(all_ids+[identifier]+targets) and c in train]
    if not features:
        raise ValueError('No common features')
    ranking=bool(re.search(r'\bndcg\b|learning.to.rank|\branking\b|ранжирован',text.lower()))
    classification = bool(re.search(r'классификац|classification', text.lower()))
    regression = bool(re.search(r'регресси|regression', text.lower()))
    if strict:
        ranking=False; kind=task_kind
    elif ranking:
        kind='regression'
    elif regression and not classification:
        kind = 'regression'
    elif classification and not regression:
        kind = 'classification'
    elif not pd.api.types.is_numeric_dtype(train[target]):
        kind = 'classification'
    else:
        kind = 'classification' if train[target].nunique() <= min(20, max(2, len(train)//100)) else 'regression'
    metric = resolved_metric.name if strict else metric_from_text(text, kind)
    ranking_parameters={}
    if ranking:
        if metric!='ndcg': raise ValueError('Only NDCG score-output ranking is implemented')
        if len(targets)>1: raise ValueError('Multi-target ranking is not implemented')
        if len(groups)!=1: raise ValueError('Ranking requires one explicit query/group role in the dictionary')
        if not pd.api.types.is_numeric_dtype(train[target]) or (train[target]<0).any():
            raise ValueError('Ranking relevance must be numeric and non-negative')
        match=re.search(r'ndcg\s*@\s*(\d+)',text,re.I); cutoff=int(match.group(1)) if match else None
        if cutoff is not None and cutoff<1: raise ValueError('NDCG top-k must be positive')
        gain='exponential' if re.search(r'2\s*(?:\*\*|\^)\s*(?:relevance|label|rel|y)|exponential\s+gain|экспоненциальн',text,re.I) else 'linear'
        features=[c for c in features if c!=groups[0]]
        if not features: raise ValueError('Ranking has no non-query input features')
        ranking_parameters={'task_family':'pointwise_ranking','group_column':groups[0],
            'ranking_k':cutoff,'ranking_gain':gain,'ranking_metric_definition':'mean_query_ndcg_ties_averaged_'+gain,
            'ranking_training_objective':'pointwise regression surrogate, not LambdaRank'}
    classes=sorted(train[target].astype(str).unique().tolist()) if kind=='classification' else None
    output_columns=[c for c in sample if c!=identifier]
    if len(output_columns)>1:
        if kind!='classification' or set(map(str,output_columns))!=set(classes):
            raise ValueError('Multiple output columns require class-named probability columns')
        prediction_type='probability_matrix'
    elif len(output_columns)==1:
        prediction_type='probability' if kind=='classification' and metric in {'roc_auc','log_loss'} else 'value'
        if prediction_type=='probability' and len(classes)!=2:
            raise ValueError('Multiclass probabilities require one sample column per class')
    else:
        raise ValueError('No prediction columns in sample_submission')
    if strict:
        if classes!=output_contract['classes'] or output_columns!=output_contract['output_columns']:
            raise StrictTaskContractError('full_discovery_class_or_output_drift')
        prediction_type=output_contract['prediction_type']
    hashes = pd.util.hash_pandas_object(train[features], index=False).to_numpy(dtype='uint64')
    dup_rate = float(pd.Series(hashes).duplicated().mean())
    text_features=[c for c in features if not pd.api.types.is_numeric_dtype(train[c])
                   and float(train[c].dropna().astype(str).str.len().mean())>50
                   and train[c].nunique()>min(100,len(train)*.1)]
    spec = {
        'root': str(root), 'task_path': str(task_path.resolve()),
        'paths': {k: str(v) for k, v in paths.items()},
        'target': target, 'id': identifier, 'features': features,
        'kind': kind, 'metric': metric, 'greater_is_better': metric not in LOWER_IS_BETTER,
        'n_train': len(train), 'n_test': len(test), 'n_features': len(features),
        'duplicate_feature_rate': dup_rate,
        'text_features': text_features,
        'classes': classes, 'prediction_type':prediction_type,'output_columns':output_columns,
        'categorical_features': [str(row['feature']) for row in dictionary.to_dict(orient='records')
                                 if str(row.get('dtype','')).lower() in {'category','categorical'} and row['feature'] in features],
        'time_candidate':infer_time_candidate(dictionary,train,test,features),
        'static_numeric_features':infer_static_numeric(dictionary,train,features),
        'group_candidate':{'column':groups[0],'reason':'Explicit group role in the data dictionary'} if len(groups)==1 else None,
    }
    if sample_positions is not None: spec['sample_test_positions']=sample_positions
    spec.update(ranking_parameters)
    if loaded.get('file_role_resolution'): spec['file_role_resolution']=dict(loaded['file_role_resolution'])
    if prediction_type=='probability':
        if strict:
            spec['positive_class']=output_contract['positive_class']; spec['positive_class_source']='explicit_declaration'
        else:
            spec['positive_class'],spec['positive_class_source']=infer_positive_class(text,classes,pd.api.types.is_numeric_dtype(train[target]))
    if strict: spec['metric_spec']=resolved_metric.to_dict()
    if len(targets)>1:
        spec['sample_columns']=list(sample.columns); spec['all_targets']=list(targets)
    profile = {
        'kind': kind, 'metric': metric, 'rows': len(train), 'test_rows': len(test),
        'feature_count':len(features), 'features': [
            {'name': c, 'dtype': str(train[c].dtype), 'unique': int(train[c].nunique()),
             'missing_rate': round(float(train[c].isna().mean()),4)} for c in features
        ],
        'target_summary': train[target].describe().astype(str).to_dict(),
        'class_counts': train[target].value_counts().to_dict() if kind=='classification' else None,
        'duplicate_feature_rate': dup_rate,
        'text_features': text_features,
        'dictionary': dictionary.to_dict(orient='records'),
    }
    return spec, profile, train, test, sample, text, hashes
