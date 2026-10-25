"""Optional current-epoch HPO identity producer. No lookup or fitted-model reuse.

Only the strict coordinator constructs TrialBankProducer. A serialized worker
claim is not parent cleanup/source authority; commit requires this object's
post-cleanup qualification of that exact returned result object.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
import os
import struct


class BankRejected(ValueError):
    """Bank ineligible only; does not redefine the original study objective."""


def need(value,code):
    if not value:raise BankRejected(code)


def canonical_digest(value):
    """Closed typed, length-delimited encoding; no repr/object coercion."""
    digest=hashlib.sha256();active=set()
    def chunk(tag,payload=b''):
        digest.update(tag);digest.update(struct.pack('>Q',len(payload)));digest.update(payload)
    def encode(item):
        if item is None:chunk(b'N')
        elif type(item) is bool:chunk(b'B',b'1' if item else b'0')
        elif type(item) is int:chunk(b'I',str(item).encode('ascii'))
        elif type(item) is float:
            need(math.isfinite(item),'nonfinite_identity_scalar');chunk(b'F',struct.pack('>d',item))
        elif type(item) is str:chunk(b'S',item.encode('utf-8'))
        elif type(item) is bytes:chunk(b'Y',item)
        elif type(item) in (list,tuple,dict):
            need(id(item) not in active,'cyclic_identity');active.add(id(item))
            try:
                chunk(b'L' if type(item) is list else b'T' if type(item) is tuple else b'D',str(len(item)).encode('ascii'))
                if type(item) is dict:
                    need(all(type(k) is str for k in item),'identity_dictionary_keys_must_be_strings')
                    for key in sorted(item):encode(key);encode(item[key])
                else:
                    for part in item:encode(part)
            finally:active.remove(id(item))
        else:raise BankRejected('unsupported_identity_type')
    encode(value);return digest.hexdigest()


def file_ref(path,checkpoint):
    path=Path(path);need(path.is_absolute() and path.is_file() and not path.is_symlink(),'absolute_regular_identity_file_required')
    size=path.stat().st_size;digest=hashlib.sha256();count=0
    with path.open('rb') as stream:
        while True:
            checkpoint();block=stream.read(2**20)
            if not block:break
            count+=len(block);need(count<=size,'identity_file_grew');digest.update(block)
    checkpoint();need(count==size and path.stat().st_size==size,'identity_file_changed_size')
    return dict(path=str(path),sha256=digest.hexdigest(),bytes=size)


def checked_refs(refs,checkpoint):
    need(type(refs) is dict and refs,'nonempty_exact_identity_file_map_required')
    for path,expected in refs.items():
        need(type(expected) is str and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),'typed_identity_SHA_required')
        need(file_ref(path,checkpoint)['sha256']==expected,'identity_file_bytes_changed')


def supported_recipe(recipe):
    if type(recipe) is not dict or recipe.get('engine')!='lightgbm':return False
    params=recipe.get('params',{})
    return type(params) is dict and not params.get('pair_refinement',False) and params.get('feature_views') in (None,'categorical_te_pair')


class FitIdentityRecorder:
    """Metadata for actual before/after estimator.fit calls, never a fit counter."""
    def __init__(self,job,checkpoint):
        self.request=deepcopy(job.get('_hpo_trial_bank'));self.checkpoint=checkpoint
        self.nodes=[];self.reason=None
        need(type(self.request) is dict and self.request.get('schema')=='hpo-trial-bank-worker-request-v1','typed_worker_identity_request_required')

    def reject(self,code):
        if self.reason is None:self.reason=code

    def skip_fit(self,scope,code):
        self.reject(code);self.nodes.append(dict(index=len(self.nodes),scope=scope,status='unqualified',reason=code))
        return len(self.nodes)-1

    def before_fit(self,*,scope,fit_x,targets,weights,parents,validation_x,validation_y,constructor,fit_settings,native):
        self.checkpoint()
        try:
            need(type(scope) is str and scope,'actual_fit_scope_required')
            need(type(native) is dict and set(native)=={'files','python','threads','environment'},'closed_native_identity_required')
            need(native['files']==self.request['native_refs'],'native_identity_epoch_mismatch')
            checked_refs(native['files'],self.checkpoint)
            need(type(constructor) is dict and constructor and type(fit_settings) is dict,'effective_constructor_fit_settings_required')
            value=deepcopy(dict(scope=scope,fit_x=fit_x,targets=targets,weights=weights,parents=parents,
                validation_x=validation_x,validation_y=validation_y,constructor=constructor,
                fit_settings=fit_settings,native=native))
            node=dict(index=len(self.nodes),status='pending',input_sha256=canonical_digest(value),identity=value,effective=None)
            self.nodes.append(node);return node['index']
        except BankRejected as exc:
            self.reject(str(exc));self.nodes.append(dict(index=len(self.nodes),status='unqualified',reason=str(exc)));return len(self.nodes)-1

    def after_fit(self,token,effective):
        self.checkpoint();need(type(token) is int and 0<=token<len(self.nodes),'actual_before_fit_token_required')
        node=self.nodes[token]
        if node['status']=='unqualified':return
        try:
            need(node['status']=='pending' and type(effective) is dict and effective,'complete_actual_effective_fit_settings_required')
            node.update(status='completed',effective=deepcopy(effective),effective_sha256=canonical_digest(effective))
        except BankRejected as exc:self.reject(str(exc));node.update(status='unqualified',reason=str(exc))

    def receipt(self):
        self.checkpoint();complete=self.reason is None and bool(self.nodes) and all(n['status']=='completed' for n in self.nodes)
        return dict(schema='hpo-fit-node-identities-v1',epoch_id=self.request['epoch_id'],
            complete=complete,nodes=deepcopy(self.nodes),reason=self.reason if not complete else None,
            leaf_path=deepcopy(self.request['leaf_path']),
            instrumented_fit_on_rows_calls=len(self.nodes),actual_recursive_learner_fits=None)


class TrialBankProducer:
    """One cold-study bank; records are not an authority for a future lookup."""
    def __init__(self,authority,checkpoint):
        required={'schema','manifest','source_refs','input_refs','native_refs','spec','bank_root'}
        need(type(authority) is dict and set(authority)==required and authority['schema']=='hpo-trial-bank-authority-v1','closed_actual_strict_authority_required')
        need(callable(checkpoint),'original_checkpoint_required')
        self.authority=deepcopy(authority);self.checkpoint=checkpoint;self.parents={};self.entries=[];self.bound=None
        self.root=Path(authority['bank_root']);need(self.root.is_absolute() and not self.root.exists(),'new_absolute_study_bank_required')
        self.epoch_id=canonical_digest({k:v for k,v in authority.items() if k!='bank_root'})
        self.actual_process_launches=None;self.actual_learner_fits=None;self.reuse_count=0;self.savings=None
        self.check_sources()

    def check_sources(self):
        self.checkpoint()
        for key in ('source_refs','input_refs','native_refs'):checked_refs(self.authority[key],self.checkpoint)

    def bind_study(self,spec,outer_rows_digest,split_ref,inner_rows_digest):
        self.check_sources();need(self.bound is None,'one_bank_one_study_only')
        need(spec==self.authority['spec'],'actual_study_spec_changed')
        need(type(outer_rows_digest) is str and len(outer_rows_digest)==64 and type(inner_rows_digest) is str and len(inner_rows_digest)==64,'ordered_partition_digests_required')
        need(file_ref(split_ref['path'],self.checkpoint)==split_ref,'actual_inner_split_ref_required')
        self.bound=dict(spec_sha256=canonical_digest(spec),outer_rows_sha256=outer_rows_digest,
            inner_rows_sha256=inner_rows_digest,split=deepcopy(split_ref))
        self.root.mkdir(parents=False,exist_ok=False)

    def worker_request(self,job,deadline):
        self.check_sources();need(self.bound is not None and job['spec']==self.authority['spec'],'actual_bound_study_required')
        need(type(deadline) in (int,float) and math.isfinite(deadline),'original_worker_deadline_required')
        return dict(schema='hpo-trial-bank-worker-request-v1',epoch_id=self.epoch_id,
            source_refs=deepcopy(self.authority['source_refs']),input_refs=deepcopy(self.authority['input_refs']),
            native_refs=deepcopy(self.authority['native_refs']),study=deepcopy(self.bound),
            original_worker_deadline_monotonic=deadline,leaf_path=[],supported=supported_recipe(job['recipe']),
            root_recipe_sha256=canonical_digest(job['recipe']),threads=job['threads'])

    def qualify_parent(self,result,*,job_path,split_path,process_identities,actual_exit_code,cleanup_confirmed,primary_exception_type,coordinator_killed):
        """Called only by the strict parent AFTER its existing cleanup succeeds."""
        self.check_sources()
        job=json.loads(Path(job_path).read_text('utf-8'));raw=json.loads(Path(job_path).with_name('result.json').read_text('utf-8'))
        need(job.get('spec')==self.authority['spec'] and not job.get('full_fit',False)
            and 'fit_iterations' not in job and job.get('_hpo_trial_bank',{}).get('epoch_id')==self.epoch_id
            and job.get('split_path')==self.bound['split']['path'],'actual_inner_job_binding_required')
        need(type(process_identities) is list and process_identities and all(type(v) is dict
            and type(v.get('pid')) is int and v['pid']>0 and type(v.get('create_time')) in (int,float)
            and math.isfinite(v['create_time']) and v['create_time']>0 for v in process_identities),'actual_parent_process_identities_required')
        need(type(raw) is dict and all(raw.get(k)==result.get(k) for k in ('status','metrics','fit_iterations','hpo_fit_identity')),
            'actual_saved_worker_result_binding_required')
        proof=dict(schema='hpo-trial-bank-parent-v1',epoch_id=self.epoch_id,
            actual_exit_code=actual_exit_code,cleanup_confirmed=cleanup_confirmed,
            primary_exception_type=primary_exception_type,coordinator_killed=coordinator_killed,
            process_identities=deepcopy(process_identities),job=file_ref(job_path,self.checkpoint),
            result=file_ref(Path(job_path).with_name('result.json'),self.checkpoint),
            split=file_ref(split_path,self.checkpoint),source_qualified=True,
            recipe_sha256=canonical_digest(job['recipe']),fit_identity_sha256=canonical_digest(raw.get('hpo_fit_identity')),
            metric_value=(raw.get('metrics') or {}).get(self.authority['spec']['metric']))
        # Object identity, not a worker-supplied boolean, authorizes commit.
        self.parents[id(result)]=(result,proof);result['_hpo_bank_parent']=deepcopy(proof);return result

    def commit_trial(self,*,number,sampling_phase,recipe,objective,result):
        answer=dict(number=number,sampling_phase=sampling_phase,status='not_qualified',objective=None,
            reuse_eligible=False,reuse_count=0,savings=None,reason=None)
        try:
            self.check_sources();need(type(number) is int and number>=0 and sampling_phase in {'anchor','startup','guided','random'},'actual_trial_identity_required')
            need(not any(e['number']==number for e in self.entries),'duplicate_bank_trial_number')
            need(type(objective) in (int,float) and math.isfinite(objective),'finite_nonbool_inner_objective_required')
            need(type(result) is dict and result.get('status')=='ok' and supported_recipe(recipe),'complete_supported_inner_trial_required')
            saved=self.parents.get(id(result));need(saved is not None and saved[0] is result,'actual_parent_qualification_required')
            proof=saved[1];need(proof['actual_exit_code']==0 and type(proof['actual_exit_code']) is int
                and proof['cleanup_confirmed'] is True and proof['primary_exception_type'] is None and proof['coordinator_killed'] is None,'clean_parent_exit_required')
            need(proof['recipe_sha256']==canonical_digest(recipe) and type(proof['metric_value']) in (int,float)
                and proof['metric_value']==objective,'actual_inner_recipe_and_metric_required')
            receipt=result.get('hpo_fit_identity');need(type(receipt) is dict and receipt.get('schema')=='hpo-fit-node-identities-v1'
                and receipt.get('complete') is True and receipt.get('epoch_id')==self.epoch_id
                and receipt.get('nodes') and all(n.get('status')=='completed' for n in receipt['nodes']),'all_actual_fit_nodes_required')
            need(canonical_digest(receipt)==proof['fit_identity_sha256'],'fit_identity_changed_after_parent_qualification')
            for node in receipt['nodes']:
                need(type(node) is dict and type(node.get('identity')) is dict
                    and node.get('input_sha256')==canonical_digest(node['identity'])
                    and type(node.get('effective')) is dict and node['effective']
                    and node.get('effective_sha256')==canonical_digest(node['effective']),'fit_node_identity_changed')
                native=node['identity'].get('native')
                need(type(native) is dict and native.get('files')==self.authority['native_refs'],'fit_node_native_epoch_changed')
                checked_refs(native['files'],self.checkpoint)
            for ref in (proof['job'],proof['result'],proof['split']):need(file_ref(ref['path'],self.checkpoint)==ref,'sealed_trial_artifact_changed')
            payload=dict(schema='hpo-trial-bank-entry-v1',state='sealed_candidate_pending_index',epoch_id=self.epoch_id,
                number=number,sampling_phase=sampling_phase,anchor=sampling_phase=='anchor',reuse_eligible=False,
                objective=objective,recipe=deepcopy(recipe),recipe_identity=canonical_digest(recipe),
                parent=deepcopy(proof),fit_identity=deepcopy(receipt),study=deepcopy(self.bound),
                fit_iterations=deepcopy(result.get('fit_iterations')),future_preworker_hit_validation=False)
            path=self.root/('trial-'+str(number)+'.json');self._exclusive(path,payload)
            answer.update(status='admitted',objective=objective,entry=file_ref(path,self.checkpoint),reason=None)
        except BankRejected as exc:answer['reason']=str(exc)
        self.entries.append(deepcopy(answer));return answer

    def _exclusive(self,path,value):
        self.checkpoint();raw=json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')
        need(len(raw)<=32*2**20,'bounded_bank_entry_required')
        temporary=path.with_name(path.name+'.pending');created=False;published=False;identity=None
        try:
            with temporary.open('xb') as stream:
                created=True;observed=os.fstat(stream.fileno());identity=(observed.st_dev,observed.st_ino)
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            self.checkpoint()
            # Exclusive publication: never replace any existing bank artifact.
            os.link(temporary,path);published=True;self.checkpoint()
        except BaseException as primary:
            if published:
                try:
                    observed=path.stat()
                    if (observed.st_dev,observed.st_ino)==identity:path.unlink()
                except BaseException as secondary:
                    try:primary.bank_cleanup_secondary_type=type(secondary).__name__
                    except BaseException:pass
            raise
        finally:
            if created:
                try:
                    observed=temporary.stat()
                    if (observed.st_dev,observed.st_ino)==identity:temporary.unlink()
                except FileNotFoundError:pass

    def finish(self,study_status):
        self.check_sources()
        for admission in self.entries:
            if admission['status']=='admitted':
                need(file_ref(admission['entry']['path'],self.checkpoint)==admission['entry'],'bank_entry_changed_before_index')
        value=dict(schema='hpo-trial-bank-index-v1',epoch_id=self.epoch_id,study_status=study_status,
            entries=deepcopy(self.entries),reuse_count=0,savings=None,consumer_implemented=False,
            actual_model_process_launches=None,actual_recursive_learner_fits=None,
            future_preworker_hit_validation=False,authority=deepcopy(self.authority),study=deepcopy(self.bound))
        self._exclusive(self.root/'bank.json',value);return value
