"""Prospective bounded support packet. Standard library only; no metrics fit.
Saved primary metrics require explicit job/split/artifact lineage. These checks
do not independently recompute F1, establish entity independence or change the
all-class MacroF1 objective. No overflow is repaired by dropping packet fields.
"""
from itertools import zip_longest
from pathlib import Path
import hashlib
import json
import math
import re
import struct
import time

MAX_CLASSES=64
MAX_LABEL_BYTES=128
MAX_FITTING_ROWS=200000
MAX_PRIMARY_RECORDS=14
MAX_PACKET_BYTES=16384
MAX_MESSAGES_BYTES=65536
MAX_PREPARATION_SECONDS=5.
MAX_PREPARATION_IO_BYTES=64*2**20
MAX_METADATA_BYTES=2**20
MAX_JSON_NODES=65536
MAX_JSON_DEPTH=32


class ContextRejected(ValueError):
    def __init__(self,code,limit=None,observed=None):
        self.receipt=dict(status='context_rejected_before_API',code=code,limit=limit,
            observed=observed,metrics=None,API_calls=0,fields_dropped=False)
        super().__init__(code)


class PreparationBudget:
    def __init__(self):
        self.started=time.monotonic();self.io_bytes=0
    def check(self):
        if time.monotonic()-self.started>MAX_PREPARATION_SECONDS:
            raise ContextRejected('preparation_time_limit',MAX_PREPARATION_SECONDS,time.monotonic()-self.started)
    def charge(self,n):
        self.io_bytes+=n;self.check()
        if self.io_bytes>MAX_PREPARATION_IO_BYTES:
            raise ContextRejected('preparation_IO_limit',MAX_PREPARATION_IO_BYTES,self.io_bytes)
    def receipt(self):
        return dict(preparation_seconds=time.monotonic()-self.started,preparation_IO_bytes=self.io_bytes,
            charged_inside_existing_parent_deadline=True)


def _require(value,code):
    if not value:raise ValueError(code)


def _sha_string(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate_task(spec):
    if spec.get('kind')!='classification' or spec.get('metric')!='macro_f1':
        raise ContextRejected('only_classification_macro_f1_is_eligible')
    classes=spec.get('classes')
    if not isinstance(classes,(list,tuple)) or not 1<=len(classes)<=MAX_CLASSES:
        raise ContextRejected('class_count_limit',MAX_CLASSES,len(classes) if isinstance(classes,(list,tuple)) else None)
    for label in classes:
        if not isinstance(label,str):raise ContextRejected('class_label_must_be_string')
        # UTF8 has at least one byte per code point; reject before allocating
        # an encoding of an arbitrarily large existing label.
        if len(label)>MAX_LABEL_BYTES:raise ContextRejected('class_label_UTF8_limit',MAX_LABEL_BYTES,len(label))
        try:size=len(label.encode('utf-8'))
        except UnicodeEncodeError:raise ContextRejected('class_label_invalid_UTF8') from None
        if size>MAX_LABEL_BYTES:raise ContextRejected('class_label_UTF8_limit',MAX_LABEL_BYTES,size)
    if len(set(classes))!=len(classes):raise ContextRejected('duplicate_class_labels')
    return tuple(classes)


def validate_fitting_rows(count):
    if type(count) is not int or not 1<=count<=MAX_FITTING_ROWS:
        raise ContextRejected('fitting_row_limit',MAX_FITTING_ROWS,count if type(count) is int else None)


def _check_json_shape(value,limit,budget):
    # Never materialize an unbounded encoder string/chunk or call opaque __str__.
    # Saved generation contexts are standard JSON; unsupported values reject both arms.
    nodes=0;active=set()
    def walk(item,depth):
        nonlocal nodes
        nodes+=1;budget.check()
        if nodes>MAX_JSON_NODES or depth>MAX_JSON_DEPTH:
            raise ContextRejected('JSON_shape_limit',dict(nodes=MAX_JSON_NODES,depth=MAX_JSON_DEPTH),dict(nodes=nodes,depth=depth))
        if item is None or type(item) in (bool,int):return
        if type(item) is float:
            if not math.isfinite(item):raise ContextRejected('nonfinite_or_unserializable_input')
            return
        if isinstance(item,str):
            if len(item)>limit:raise ContextRejected('serialized_UTF8_limit',limit,len(item))
            try:size=len(item.encode('utf-8'))
            except UnicodeEncodeError:raise ContextRejected('nonfinite_or_unserializable_input') from None
            if size>limit:raise ContextRejected('serialized_UTF8_limit',limit,size)
            return
        if type(item) not in (dict,list,tuple):raise ContextRejected('standard_JSON_value_required')
        identity=id(item)
        if identity in active:raise ContextRejected('cyclic_JSON_input')
        active.add(identity)
        try:
            if type(item) is dict:
                for key,child in item.items():
                    if not isinstance(key,str):raise ContextRejected('string_JSON_keys_required')
                    walk(key,depth+1);walk(child,depth+1)
            else:
                for child in item:walk(child,depth+1)
        finally:active.remove(identity)
    walk(value,0)


def _json_text(value,limit,budget):
    _check_json_shape(value,limit,budget)
    pieces=[];size=0
    try:
        for piece in json.JSONEncoder(ensure_ascii=False,allow_nan=False).iterencode(value):
            budget.check();size+=len(piece.encode('utf-8'))
            if size>limit:raise ContextRejected('serialized_UTF8_limit',limit,size)
            pieces.append(piece)
    except (UnicodeEncodeError,TypeError,ValueError) as exc:
        if isinstance(exc,ContextRejected):raise
        raise ContextRejected('nonfinite_or_unserializable_input') from None
    return ''.join(pieces),size


def bounded_messages(system_prompt,context,budget=None):
    """Measure complete messages, matching the reviewed gateway's user JSON.
    The cap covers message JSON UTF8 bytes, not output tokens or provider tokens.
    No input truncation, tokenizer dependency or token-budget claim is made.
    """
    budget=budget or PreparationBudget()
    if not isinstance(system_prompt,str):raise ContextRejected('system_prompt_must_be_string')
    user,user_bytes=_json_text(context,MAX_MESSAGES_BYTES,budget)
    messages=[{'role':'system','content':system_prompt},{'role':'user','content':user}]
    text,size=_json_text(messages,MAX_MESSAGES_BYTES,budget)
    return dict(messages_UTF8_bytes=size,user_context_UTF8_bytes=user_bytes,
        messages_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
        hard_input_byte_limit=MAX_MESSAGES_BYTES,output_token_limit_is_not_input_bound=True,
        **budget.receipt())


def bounded_context_copy(value,budget=None):
    """Copy the exact bounded gateway JSON view, never a large opaque object."""
    budget=budget or PreparationBudget();text,_=_json_text(value,MAX_MESSAGES_BYTES,budget)
    return json.loads(text)


def fitting_class_support(spec,fitting_labels,original_feature_hashes,split_sha256,
                          expected_rows,diagnostic_support_threshold=100,budget=None):
    budget=budget or PreparationBudget();classes=validate_task(spec);validate_fitting_rows(expected_rows)
    if not _sha_string(split_sha256):raise ContextRejected('primary_split_SHA_required')
    if type(diagnostic_support_threshold) is not int or diagnostic_support_threshold<1:
        raise ContextRejected('positive_diagnostic_threshold_required')
    index={label:i for i,label in enumerate(classes)};rows={c:0 for c in classes};groups={c:0 for c in classes}
    masks={};shared=0;count=0;missing=object();hash_digest=hashlib.sha256()
    # One bounded uint64->64-bit class mask map. No N-sized list copies or
    # separate per-class sets; the caller checks N BEFORE pandas/NumPy indexing.
    for label,value in zip_longest(fitting_labels,original_feature_hashes,fillvalue=missing):
        count+=1
        if count>expected_rows or count>MAX_FITTING_ROWS:
            raise ContextRejected('fitting_row_count_overflow',expected_rows,count)
        if label is missing or value is missing or not isinstance(label,str) or label not in index:
            raise ContextRejected('aligned_known_fitting_labels_required')
        if type(value) is not int or not 0<=value<2**64:raise ContextRejected('original_uint64_hash_required')
        mask=1<<index[label];previous=masks.get(value,0);rows[label]+=1
        if not previous&mask:
            groups[label]+=1
            if previous and not previous&(previous-1):shared+=1
            masks[value]=previous|mask
        hash_digest.update(struct.pack('<Q',value))
        if count%1024==0:budget.check()
    if count!=expected_rows:raise ContextRejected('fitting_row_count_mismatch',expected_rows,count)
    packet=dict(scope='primary_fitting_rows_only_before_FE_or_resampling',split_sha256=split_sha256,
        raw_fitting_rows_per_class=rows,original_feature_hash_groups_per_class=groups,
        classes_absent_from_fitting=[c for c in classes if not rows[c]],
        rarest_fitting_class=min(classes,key=lambda c:(groups[c],c)),
        diagnostic_support_threshold=diagnostic_support_threshold,
        supported_classes=[c for c in classes if groups[c]>=diagnostic_support_threshold],
        cross_class_shared_hash_groups=shared,
        hash_interpretation='Original discover() feature-pattern uint64 hashes before FE/resampling; not verified independent entities. Hash collisions and conflicting labels are possible. Validation support is a different scope.')
    budget.check()
    return packet,dict(status='fitting_support_built',fitting_rows=count,distinct_hashes=len(masks),
        fitting_hash_sequence_sha256=hash_digest.hexdigest(),class_count=len(classes),
        maximum_fitting_rows=MAX_FITTING_ROWS,**budget.receipt())


def _file_sha(path,budget,maximum=MAX_PREPARATION_IO_BYTES):
    path=Path(path)
    if path.is_symlink():raise ValueError('artifact_symlink')
    size=path.stat().st_size
    if size>maximum:raise ContextRejected('lineage_file_size_limit',maximum,size)
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):budget.charge(len(block));digest.update(block)
    return digest.hexdigest()


def _read_json(path,budget):
    path=Path(path)
    if path.is_symlink():raise ValueError('metadata_symlink')
    size=path.stat().st_size
    if size>MAX_METADATA_BYTES:raise ContextRejected('lineage_metadata_size_limit',MAX_METADATA_BYTES,size)
    with path.open('rb') as stream:raw=stream.read(MAX_METADATA_BYTES+1)
    budget.charge(len(raw))
    if len(raw)>MAX_METADATA_BYTES:raise ContextRejected('lineage_metadata_size_limit',MAX_METADATA_BYTES,len(raw))
    return json.loads(raw.decode('utf-8')),hashlib.sha256(raw).hexdigest()


def _canonical(value,budget):
    text,_=_json_text(value,MAX_MESSAGES_BYTES,budget)
    # Stable source/spec equality; this is separate from policy.signature().
    canonical=json.dumps(json.loads(text),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def capture_primary_bindings(spec,records,split_path,split_info_path,protected_artifact,
                             protected_signature,signature_fn,budget=None):
    """Pin an already completed primary snapshot before generation, never fit.
    Future matched screens must freeze/publish this descriptor before either arm.
    Missing artifacts remain explicit null entries; overflow rejects the context.
    """
    budget=budget or PreparationBudget();validate_task(spec)
    if not isinstance(records,list) or len(records)>MAX_PRIMARY_RECORDS:
        raise ContextRejected('primary_record_count_limit',MAX_PRIMARY_RECORDS,len(records) if isinstance(records,list) else None)
    split=Path(split_path).resolve();info=Path(split_info_path).resolve();meta,info_sha=_read_json(info,budget)
    _require(split.name=='split.npz' and info.parent==split.parent and info.name=='split.json','primary_split_path_required')
    binding=dict(split_path=str(split),split_file_sha256=_file_sha(split,budget),split_info_path=str(info),
        split_info_sha256=info_sha,split_sha256=meta.get('split_sha256'),spec_sha256=_canonical(spec,budget),
        protected_signature=protected_signature,protected_artifact=None,records={})
    if protected_artifact is not None:
        artifact=Path(protected_artifact['path']).resolve();recipe,recipe_sha=_read_json(artifact,budget)
        _require(recipe_sha==protected_artifact['sha256'] and signature_fn(recipe)==protected_signature,'protected_artifact_or_signature_changed')
        binding['protected_artifact']=dict(path=str(artifact),sha256=recipe_sha)
    for record in records:
        name=str(Path(record.get('output_dir','')).resolve());directory=Path(name)
        binding['records'][name]=None
        if record.get('status')!='ok' or directory.parent!=split.parent or re.fullmatch('experiment-[0-9]{2}',directory.name) is None:continue
        try:
            binding['records'][name]={n:_file_sha(directory/n,budget,MAX_METADATA_BYTES if n.endswith('.json') else MAX_PREPARATION_IO_BYTES)
                for n in ['job.json','result.json','validation_predictions.csv','validation_probabilities.npz']}
        except (OSError,ValueError) as exc:
            if isinstance(exc,ContextRejected):raise
    return binding


def _common_lineage(binding,support,signature_fn,budget):
    _require(binding is not None and binding.get('split_sha256')==support['split_sha256'],'primary_binding_missing')
    _require(_file_sha(binding['split_path'],budget)==binding['split_file_sha256'],'primary_split_file_changed')
    info,h=_read_json(binding['split_info_path'],budget)
    _require(h==binding['split_info_sha256'] and info.get('split_sha256')==support['split_sha256'],'primary_split_info_changed')
    ref=binding.get('protected_artifact');_require(ref is not None,'protected_artifact_missing')
    recipe,h=_read_json(ref['path'],budget)
    _require(h==ref['sha256'] and signature_fn(recipe)==binding['protected_signature'],'protected_artifact_changed')


def _record_metrics(record,support,binding,signature_fn,budget):
    _require(record is not None and record.get('status')=='ok','record_not_successful')
    directory=Path(record['output_dir']).resolve();expected=binding['records'].get(str(directory))
    _require(expected is not None and directory.parent==Path(binding['split_path']).parent
        and re.fullmatch('experiment-[0-9]{2}',directory.name) is not None,'not_bound_outer_primary_record')
    _require(record.get('experiment_index')==int(directory.name.split('-')[1]),'record_index_mismatch')
    job,jh=_read_json(directory/'job.json',budget);result,rh=_read_json(directory/'result.json',budget)
    _require(jh==expected['job.json'] and rh==expected['result.json'],'record_metadata_changed')
    _require(Path(job['split_path']).resolve()==Path(binding['split_path']) and job.get('full_fit') is False
        and result.get('full_fit') is False and result.get('status')=='ok','not_same_primary_job')
    _require(Path(job['output_dir']).resolve()==directory and _canonical(job['spec'],budget)==binding['spec_sha256'],'job_output_or_spec_mismatch')
    _require(signature_fn(record['recipe'])==signature_fn(job['recipe'])==signature_fn(result['recipe']),'recipe_lineage_mismatch')
    _require(record.get('metrics')==result.get('metrics'),'record_result_metrics_mismatch')
    for name in ['validation_predictions.csv','validation_probabilities.npz']:
        _require(_file_sha(directory/name,budget)==expected[name],'primary_prediction_artifact_changed')
    metrics=result['metrics'];values=metrics.get('per_class_f1');classes=list(support['raw_fitting_rows_per_class'])
    _require(isinstance(values,dict) and set(values)==set(classes),'complete_per_class_F1_required')
    _require(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in values.values()),'invalid_per_class_F1')
    macro=metrics.get('macro_f1')
    _require(type(macro) in (int,float) and math.isfinite(macro)
        and math.isclose(macro,sum(values.values())/len(classes),rel_tol=1e-10,abs_tol=1e-10),'all_class_macro_F1_mismatch')
    return values


def primary_f1_feedback(candidate,control,support,binding,signature_fn,budget=None):
    """Return null on missing/invalid lineage; no truth bool grants provenance."""
    budget=budget or PreparationBudget()
    try:
        _common_lineage(binding,support,signature_fn,budget)
        first=_record_metrics(candidate,support,binding,signature_fn,budget)
        second=_record_metrics(control,support,binding,signature_fn,budget)
    except (OSError,KeyError,TypeError,ValueError) as exc:
        if isinstance(exc,ContextRejected):raise
        return None,dict(status='comparison_unavailable',reason=str(exc) if type(exc) is ValueError else type(exc).__name__,metrics=None)
    return _feedback_from_checked_values(first,second,support,binding)


def _feedback_from_checked_values(first,second,support,binding):
    # Internal only: callers above/below perform file checks in the same call;
    # no public boolean/availability flag can substitute for those checks.
    classes=list(support['raw_fitting_rows_per_class']);delta={c:float(first[c]-second[c]) for c in classes}
    rare=support['rarest_fitting_class'];others=[c for c in classes if c!=rare]
    feedback=dict(scope='measured_current_primary_search_cut_only',split_sha256=support['split_sha256'],
        per_class_f1_delta_from_protected_control=delta,supported_class_losses={c:delta[c] for c in support['supported_classes'] if delta[c]<0},
        rarest_fitting_class=rare,macro_f1_excluding_rarest=None if not others else dict(candidate=sum(first[c] for c in others)/len(others),
            protected_control=sum(second[c] for c in others)/len(others),delta=sum(delta[c] for c in others)/len(others)),
        macro_f1_all_class_delta=sum(delta.values())/len(classes),
        interpretation='All-class MacroF1 remains the objective. Ex-rarest omits one class F1, not rows. Threshold is diagnostic; reused primary metrics are not blind/private or independently recomputed metrics.')
    return feedback,dict(status='saved_primary_lineage_checked',independent_metric_recomputation=False,
        split_file_sha256=binding['split_file_sha256'],protected_artifact_sha256=binding['protected_artifact']['sha256'])


def validate_support_packet(spec,support,budget=None):
    """Bound external container shape before enumeration, then validate/copy.
    This accepts only native JSON containers. No public boolean certifies that
    a caller has already validated a packet or paid its earlier preparation.
    """
    budget=budget or PreparationBudget();classes_ordered=validate_task(spec);budget.check()
    expected=('scope','split_sha256','raw_fitting_rows_per_class','original_feature_hash_groups_per_class',
        'classes_absent_from_fitting','rarest_fitting_class','diagnostic_support_threshold',
        'supported_classes','cross_class_shared_hash_groups','hash_interpretation')
    # Exact types avoid invoking custom iteration/len methods. All following
    # key checks are at most ten lookups, not an enumeration of external keys.
    if type(support) is not dict or len(support)!=len(expected):
        raise ContextRejected('support_packet_schema_mismatch')
    for field in expected:
        if field not in support:raise ContextRejected('support_packet_schema_mismatch')
    for field in ('raw_fitting_rows_per_class','original_feature_hash_groups_per_class'):
        values=support[field]
        if type(values) is not dict or len(values)!=len(classes_ordered):
            raise ContextRejected('support_count_map_mismatch')
    for field in ('supported_classes','classes_absent_from_fitting'):
        values=support[field]
        if type(values) is not list or len(values)>len(classes_ordered):
            raise ContextRejected('support_packet_values_mismatch')
    # JSON shape/bytes, including strings and finite scalar values, are checked
    # before sum/set/any, semantic traversals or any copy of the external packet.
    text,_=_json_text(support,MAX_PACKET_BYTES,budget);support=json.loads(text)
    classes=set(classes_ordered)
    for field in ('raw_fitting_rows_per_class','original_feature_hash_groups_per_class'):
        values=support[field]
        if set(values)!=classes or any(type(v) is not int or not 0<=v<=MAX_FITTING_ROWS for v in values.values()):
            raise ContextRejected('support_count_map_mismatch')
    validate_fitting_rows(sum(support['raw_fitting_rows_per_class'].values()))
    if (any(not isinstance(c,str) for c in support['supported_classes'])
        or len(set(support['supported_classes']))!=len(support['supported_classes'])
        or type(support['diagnostic_support_threshold']) is not int or support['diagnostic_support_threshold']<1
        or type(support['cross_class_shared_hash_groups']) is not int
        or not 0<=support['cross_class_shared_hash_groups']<=sum(support['raw_fitting_rows_per_class'].values())
        or not _sha_string(support['split_sha256'])
        or support['scope']!='primary_fitting_rows_only_before_FE_or_resampling'
        or not isinstance(support['rarest_fitting_class'],str)
        or not isinstance(support['hash_interpretation'],str)
        or any(not isinstance(c,str) for c in support['classes_absent_from_fitting'])):
        raise ContextRejected('support_packet_values_mismatch')
    expected_absent=[c for c in classes_ordered if not support['raw_fitting_rows_per_class'][c]]
    expected_supported=[c for c in classes_ordered if support['original_feature_hash_groups_per_class'][c]>=support['diagnostic_support_threshold']]
    expected_rarest=min(classes_ordered,key=lambda c:(support['original_feature_hash_groups_per_class'][c],c))
    if (support['classes_absent_from_fitting']!=expected_absent or support['supported_classes']!=expected_supported
        or support['rarest_fitting_class']!=expected_rarest):raise ContextRejected('support_diagnostic_rule_mismatch')
    if (any(support['original_feature_hash_groups_per_class'][c]>support['raw_fitting_rows_per_class'][c] for c in classes)
        or support['rarest_fitting_class'] not in classes or len(support['supported_classes'])>len(classes)
        or not set(support['supported_classes'])<=classes):raise ContextRejected('support_group_or_class_mismatch')
    budget.check()
    return support


def add_support_context(base,spec,support,records,binding,signature_fn,budget=None):
    budget=budget or PreparationBudget();validate_task(spec)
    if not isinstance(records,list) or len(records)>MAX_PRIMARY_RECORDS:
        raise ContextRejected('primary_record_count_limit',MAX_PRIMARY_RECORDS,len(records) if isinstance(records,list) else None)
    support=validate_support_packet(spec,support,budget)
    context=bounded_context_copy(base,budget);ledger=context['feedback_read_first'];tail=records[-12:]
    if len(ledger)!=len(tail) or any(row['recipe_sha256']!=signature_fn(record['recipe']) for row,record in zip(ledger,tail)):
        raise ContextRejected('baseline_ledger_primary_record_alignment_failed')
    protected=binding.get('protected_signature') if binding else None
    control=next((r for r in records if r.get('status')=='ok' and signature_fn(r['recipe'])==protected),None)
    checks=[];second=None;unavailable=None
    try:
        _common_lineage(binding,support,signature_fn,budget)
        second=_record_metrics(control,support,binding,signature_fn,budget)
    except (OSError,KeyError,TypeError,ValueError) as exc:
        if isinstance(exc,ContextRejected):raise
        unavailable=dict(status='comparison_unavailable',reason=str(exc) if type(exc) is ValueError else type(exc).__name__,metrics=None)
    for row,record in zip(ledger,tail):
        value=None;receipt=unavailable
        if second is not None:
            try:
                first=second if record is control else _record_metrics(record,support,binding,signature_fn,budget)
                value,receipt=_feedback_from_checked_values(first,second,support,binding)
            except (OSError,KeyError,TypeError,ValueError) as exc:
                if isinstance(exc,ContextRejected):raise
                receipt=dict(status='comparison_unavailable',reason=str(exc) if type(exc) is ValueError else type(exc).__name__,metrics=None)
        row['protected_control_comparison']=value;checks.append(receipt)
    context['class_support']=dict(support,protected_control_signature=protected,
        comparison_scope='Saved primary job/split/artifact lineage required; no independent metric certification.',
        proposal_guidance='Distinguish fitting rows from original feature-pattern proxies. Describe supported-class losses and rarest uncertainty; all-class MacroF1 and existing gates remain unchanged. Null means evidence unavailable.')
    packet={'class_support':context['class_support'],'protected_control_comparison':[r['protected_control_comparison'] for r in ledger]}
    _,size=_json_text(packet,MAX_PACKET_BYTES,budget)
    return context,dict(status='support_context_prepared',added_packet_UTF8_bytes=size,packet_limit=MAX_PACKET_BYTES,
        comparison_receipts=checks,independent_metric_recomputation=False,**budget.receipt())
