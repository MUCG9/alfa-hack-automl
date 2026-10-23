"""SOURCE PROTOTYPE ONLY: no driver/launch authorization or actual data here.
Future bounded materializer may call these functions after T7 terminal proof.
Numerical/application dependencies import ONLY inside explicitly called methods.
Raw lexical CSV rows are copied, then the ACTUAL runtime reader must prove exact
dtype/value/original-feature-hash parity. Any drift aborts; no coercion/reseed.
Scope is trusted algorithm-facing source/I/O flow, not an OS/ACL sandbox claim.
"""
from pathlib import Path
import csv,hashlib,json,math,time

MAX_ROWS=1000000
MAX_SOURCE_BYTES=512*2**20
MAX_COLUMNS=512
MAX_CELL_BYTES=65536
MAX_CLASSES=64

class ContractFailure(ValueError):
    pass

def need(value,code):
    if not value:raise ContractFailure(code)

def schema_roles(spec,test_columns):
    features=spec.get('features');target=spec.get('target');identifier=spec.get('id')
    need(type(features) is list and 0<len(features)<=MAX_COLUMNS,'invalid_feature_schema')
    need(all(type(c) is str and c for c in features) and len(set(features))==len(features),'invalid_feature_columns')
    targets=spec.get('all_targets',[target])
    need(type(targets) is list and 0<len(targets)<=MAX_COLUMNS and all(type(c) is str and c for c in targets)
         and target in targets and len(set(targets))==len(targets),'invalid_target_schema')
    need(type(identifier) is str and identifier and identifier not in targets,'invalid_identifier_schema')
    need(not set(features)&(set(targets)|{identifier}),'feature_role_violation')
    need(type(test_columns) is list and 0<len(test_columns)<=MAX_COLUMNS
         and all(type(c) is str and c for c in test_columns) and len(set(test_columns))==len(test_columns)
         and set(test_columns)==set(features)|{identifier} and not set(test_columns)&set(targets),'test_has_target_or_wrong_schema')
    return target,identifier

def sha(path,checkpoint):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):checkpoint();digest.update(block)
    checkpoint();return digest.hexdigest()

def partition_positions(train_positions,validation_positions,n_rows):
    """Actual outer split is exhaustive, disjoint, sorted and never repaired."""
    need(type(n_rows) is int and 1<n_rows<=MAX_ROWS,'outer_row_bound')
    rows=[]
    for name,values in [('train',train_positions),('validation',validation_positions)]:
        need(isinstance(values,(list,tuple)) and 0<len(values)<n_rows,'outer_positions_sequence_required:'+name)
        need(all(type(p) is int and 0<=p<n_rows for p in values),'invalid_outer_position:'+name)
        need(all(a<b for a,b in zip(values,values[1:])),'outer_positions_not_strictly_sorted:'+name)
        rows.append(values)
    fit,held=map(set,rows)
    need(not fit&held and len(fit)+len(held)==n_rows,'outer_partition_not_exact_once')
    digest=hashlib.sha256()
    for values in rows:
        for p in values:digest.update(p.to_bytes(8,'little',signed=True))
    return dict(rows=n_rows,fitting_rows=len(fit),validation_rows=len(held),positions_sha256=digest.hexdigest())

def derive_outer_indices(original_spec,original_train,observation_transform=None,checkpoint=lambda:None):
    """Future splitter: full ORIGINAL typed frame/features before any CSV rewrite.
    No folds reduction/fallback: exactly SGKF(5,shuffle=True,seed1009), fold0.
    Regression uses latest original observation period, all strictly earlier fit.
    Source/version of Pandas/sklearn/observation_transform must be pinned outside.
    """
    import numpy as np
    import pandas as pd
    from sklearn.model_selection import StratifiedGroupKFold
    spec=original_spec;target=spec['target'];features=spec['features'];n=len(original_train)
    need(1<n<=MAX_ROWS and 0<len(features)<=MAX_COLUMNS,'original_shape_bound')
    need(target not in features and spec['id'] not in features and len(set(features))==len(features),'feature_role_violation')
    need(not original_train[target].isna().any(),'missing_original_target')
    hashes=pd.util.hash_pandas_object(original_train[features],index=False).to_numpy(dtype='uint64')
    y=original_train[target];positions=np.arange(n);checkpoint()
    if spec['kind']=='regression':
        column=spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
        need(column in features and callable(observation_transform),'pinned_observation_transform_required')
        values,representation=observation_transform(original_train[column]);need(not values.isna().any(),'missing_observation_period')
        latest=values.max();tr=np.flatnonzero((values<latest).to_numpy());va=np.flatnonzero((values==latest).to_numpy())
        need(len(tr)>0 and len(va)>0 and values.iloc[tr].max()<values.iloc[va].min(),'nonforward_outer_partition')
        private=dict(method='latest_original_observation_period',column=column,representation=representation,latest=str(latest))
    else:
        need(spec['kind']=='classification' and spec['metric']=='macro_f1','only_declared_task_kinds')
        classes=list(spec['classes']);need(1<len(classes)<=MAX_CLASSES and len(set(classes))==len(classes),'class_schema_bound')
        labels=y.astype(str);need(set(labels)==set(classes),'original_class_schema_mismatch')
        counts=pd.DataFrame({'y':labels.to_numpy(),'g':hashes}).groupby('y')['g'].nunique()
        need(set(counts.index)==set(classes) and int(counts.min())>=5,'SGKF5_original_group_support_infeasible')
        tr,va=next(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=1009).split(positions,labels,groups=hashes))
        need(not set(hashes[tr])&set(hashes[va]),'original_feature_hash_group_overlap')
        need(set(labels.iloc[tr])==set(classes)==set(labels.iloc[va]),'outer_fold0_missing_class_no_reseed')
        private=dict(method='StratifiedGroupKFold',n_splits=5,shuffle=True,seed=1009,fold=0,
            original_per_class_feature_hash_groups={str(c):int(v) for c,v in counts.items()},
            heldout_class_counts={str(c):int(v) for c,v in labels.iloc[va].value_counts().items()})
    tr=[int(v) for v in tr];va=[int(v) for v in va];proof=partition_positions(tr,va,n)
    proof.update(original_feature_columns=list(features),original_feature_hash_dtype='<u8',
        original_feature_hash_vector_sha256=hashlib.sha256(np.asarray(hashes,dtype='<u8').tobytes()).hexdigest(),
        hash_scope='Original typed discover() feature columns; target/ID excluded, before subset/FE/resampling. Pattern proxy, not verified independent entity.')
    checkpoint();return tr,va,hashes,proof,private

def write_outer_csv_tables(source_csv,agent_root,judge_vault,spec,test_columns,sample_columns,
                           train_positions,validation_positions,n_rows,source_sha256,checkpoint,*,
                           source_delimiter,expected_partition_sha256):
    """Partial table builder, future call only. No task text/source/manifest driver.
    Vault contains row mapping and true heldout targets; agent gets no vault ref.
    No original test rows are used as the outer evaluation sample.
    """
    source=Path(source_csv).resolve();agent=Path(agent_root).resolve();vault=Path(judge_vault).resolve()
    need(not vault.is_relative_to(agent) and not agent.is_relative_to(vault),'vault_and_agent_must_be_disjoint')
    need(not agent.exists() and not vault.exists(),'new_exclusive_materialization_required')
    need(source.stat().st_size<=MAX_SOURCE_BYTES,'source_CSV_size_bound')
    partition=partition_positions(train_positions,validation_positions,n_rows)
    need(partition['positions_sha256']==expected_partition_sha256,'declared_outer_positions_changed')
    need(type(source_delimiter) is str and source_delimiter in (',',';','\t','|'),'frozen_source_delimiter_required')
    target,identifier=schema_roles(spec,test_columns);classes=spec.get('classes',[])
    need(spec.get('prediction_type')=='value' and identifier is not None,'V1_current_value_output_contract_only')
    need(sample_columns==[identifier,spec['output_columns'][0]],'V1_two_column_sample_contract_required')
    placeholder=0.0 if spec['kind']=='regression' else classes[0]
    need(sha(source,checkpoint)==source_sha256,'original_source_changed')
    # Trusted driver must bind these canonical paths and every algorithm job's
    # derived-only input paths. No OS/ACL mechanism is assumed or requested here.
    agent.mkdir();vault.mkdir();fit=set(train_positions);held=set(validation_positions)
    seen_ids=set();n=0;written_train=written_test=0
    with source.open('r',encoding='utf-8-sig',newline='') as stream, (agent/'train.csv').open('x',encoding='utf-8',newline='') as af, (agent/'test.csv').open('x',encoding='utf-8',newline='') as at, (agent/'sample_submission.csv').open('x',encoding='utf-8',newline='') as sm, (vault/'outer-targets.jsonl').open('x',encoding='utf-8') as vf:
        reader=csv.reader(stream,delimiter=source_delimiter);header=next(reader)
        need(0<len(header)<=MAX_COLUMNS and len(set(header))==len(header),'duplicate_or_oversize_header')
        need(target in header and identifier in header and set(test_columns)<=set(header),'source_header_role_mismatch')
        target_i=header.index(target);id_i=header.index(identifier);test_indices=[header.index(c) for c in test_columns]
        train_writer=csv.writer(af,lineterminator='\n');test_writer=csv.writer(at,lineterminator='\n');sample_writer=csv.writer(sm,lineterminator='\n')
        train_writer.writerow(header);test_writer.writerow(test_columns);sample_writer.writerow(sample_columns)
        for position,row in enumerate(reader):
            checkpoint();n+=1;need(n<=n_rows and len(row)==len(header),'source_row_count_or_width_changed')
            need(all(len(cell)<=MAX_CELL_BYTES and len(cell.encode('utf-8'))<=MAX_CELL_BYTES for cell in row),'CSV_cell_size_bound')
            identifier_raw=row[id_i];need(identifier_raw and identifier_raw not in seen_ids,'duplicate_or_missing_lexical_ID')
            seen_ids.add(identifier_raw)
            if position in fit:train_writer.writerow(row);written_train+=1
            elif position in held:
                test_writer.writerow([row[i] for i in test_indices]);sample_writer.writerow([identifier_raw,placeholder])
                vf.write(json.dumps(dict(original_position=position,outer_test_position=written_test,
                    original_ID_lexical=identifier_raw,target_lexical=row[target_i]),ensure_ascii=False,allow_nan=False)+'\n')
                written_test+=1
            else:raise ContractFailure('unmapped_original_row')
    need(n==n_rows and written_train==len(fit) and written_test==len(held),'incomplete_outer_materialization')
    need(sha(source,checkpoint)==source_sha256,'late_original_source_changed')
    # Never put returned vault data/path/hash in agent-visible profile/context.
    return dict(partition=partition,agent_table_sha256={name:sha(agent/name,checkpoint) for name in ['train.csv','test.csv','sample_submission.csv']},
        judge_only=dict(targets_sha256=sha(vault/'outer-targets.jsonl',checkpoint),row_mapping_order='ascending original positions',dummy_target_artifact=False),
        sample_artifact_is_placeholder_not_true_target=True,actual_roundtrip_verified=False,packet_ready_for_agent=False)

def verify_actual_reader_roundtrip(original_train,original_spec,hashes,tr,va,loaded,checkpoint=lambda:None,*,
                                   expected_test_columns,expected_sample_columns):
    """Use tables read by the UNCHANGED actual runtime reader, not a custom dtype.
    Exact dtype/value/NaN/row/ID parity and original hashes are mandatory. This
    prototype intentionally cannot repair numeric-only object subsets or floats.
    """
    import numpy as np
    import pandas as pd
    spec=original_spec;features=spec['features'];identifier=spec['id'];target=spec['target']
    train,test,sample=(loaded[k] for k in ['train','test','sample'])
    schema_roles(spec,expected_test_columns)
    need(list(test.columns)==expected_test_columns and list(sample.columns)==expected_sample_columns
         and expected_sample_columns==[identifier,spec['output_columns'][0]],'declared_test_or_sample_column_order_changed')
    need(not set(spec.get('all_targets',[target]))&set(test.columns),'roundtrip_test_contains_target')
    expected_train=original_train.iloc[tr].reset_index(drop=True)
    expected_test=original_train.iloc[va][list(test.columns)].reset_index(drop=True)
    need(target not in test and list(train.columns)==list(original_train.columns),'roundtrip_schema_mismatch')
    pd.testing.assert_frame_equal(train.reset_index(drop=True),expected_train,check_dtype=True,check_exact=True)
    pd.testing.assert_frame_equal(test.reset_index(drop=True),expected_test,check_dtype=True,check_exact=True)
    for name,frame in [('train',train),('test',test)]:
        need(frame[identifier].notna().all() and frame[identifier].is_unique,'nonunique_or_missing_parsed_ID:'+name)
    need(not set(train[identifier])&set(test[identifier]),'parsed_ID_overlap')
    need(list(sample.columns)==[identifier,spec['output_columns'][0]] and sample[identifier].tolist()==test[identifier].tolist(),'sample_test_ID_mapping_changed')
    pd.testing.assert_series_equal(sample[identifier].reset_index(drop=True),test[identifier].reset_index(drop=True),
        check_dtype=True,check_exact=True,check_names=False)
    values=sample[spec['output_columns'][0]]
    if spec['kind']=='regression':
        numeric=pd.to_numeric(values,errors='raise').to_numpy(dtype=float)
        need(np.isfinite(numeric).all() and (numeric==0.0).all(),'sample_not_declared_constant_placeholder')
    else:
        need(type(spec.get('classes')) is list and spec['classes'],'classification_schema_missing')
        need(values.notna().all() and values.astype(str).eq(str(spec['classes'][0])).all(),'sample_not_declared_constant_placeholder')
    for frame,positions in [(train,tr),(test,va)]:
        actual=pd.util.hash_pandas_object(frame[features],index=False).to_numpy(dtype='uint64')
        need(np.array_equal(actual,hashes[positions]),'derived_reader_feature_hash_drift')
    if spec['kind']=='classification':need(set(train[target].astype(str))==set(spec['classes']),'derived_training_class_missing')
    checkpoint();return dict(status='actual_runtime_reader_exact_roundtrip_verified',check_dtype=True,check_exact=True,
        original_feature_hashes_preserved=True,unique_ID_bijection=True,placeholder_sample_only=True,
        dummy_placeholder_values_verified=True,declared_test_and_sample_column_order_verified=True)

if __name__=='__main__':
    raise SystemExit('SOURCE PROTOTYPE ONLY: bounded driver, algorithm-facing source/I/O and derived-inner auditor contracts are not implemented or tested; no materialization performed.')
