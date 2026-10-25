"""Finite QH5 predecessor projection only; no current process claim or launch."""
from pathlib import Path
import hashlib,json,math
WORK=Path(__file__).resolve().parent.parent
REFS={
'negative':('qh4/current-negative-closure.json','64df1f5f57c62bde768dc830b7c4ad1dc44a32ad5ecb26828d146ec5bd865ed4'),
'post':('qh4/current-negative-post-tool-confirmation.json','e5a92018e825e99b6a844eba3cd66ed30468b8a4492d9f081ca7616b37ed3b27'),
'supplement':('qh4-post-closure-observed-identity-supplement-r1.json','87f56428ef2b6bf328b8a03132d04b01d59bb640c3b66f78bcc6e00a67158da5'),
'actual':('private/qh4-current-negative-actual-tools-r1.json','51076479e474856df34e808de9fdc56d91184a937dffdfe665fdd7670da8bd24'),
'postexit':('private/qh4-current-negative-postexit-root-tool.json','ce7c99aa759866bab718d72a825d2be7fa165f0bfa28c0cb1bd97e49c3b00e45')}
OUT=WORK/'private/qh5-root-predecessor-identities-r1.json'
def need(value,code):
    if not value:raise RuntimeError(code)
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()
def read(ref):
    relative,expected=ref;path=WORK/relative
    need(path.resolve().is_relative_to(WORK) and not path.is_symlink() and path.stat().st_size<=16*2**20,'bounded_exact_local_metadata')
    need(digest(path)==expected,'source_metadata_changed')
    obj=json.loads(path.read_text('utf-8-sig'))
    need(digest(path)==expected,'source_metadata_changed_during_read')
    return obj
def identity(row):
    need(type(row)is dict and type(row.get('pid'))is int and row['pid']>0
         and type(row.get('create_time'))in(int,float) and math.isfinite(row['create_time']) and row['create_time']>0,'full_finite_process_identity_required')
    return row['pid'],row['create_time']
def main():
    records={key:read(ref)for key,ref in REFS.items()}
    negative,post,supplement,actual,postexit=(records[k]for k in ('negative','post','supplement','actual','postexit'))
    for row in (negative,post):
        need(row['technical_procedure_passed']is False and row['original_QH4_FAIL_preserved']is True
             and row['root60_requalified']is False and row['known_exact_live']==row['uncertain']==[]
             and all(row[k]is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent')),'prior_negative_proof_not_qualified_current_cleanup_required')
    need(post['negative_closure_sha256']==REFS['negative'][1] and post['post_tool_current_confirmation']is True,'exact_negative_post_link')
    for name,chunk in (('observer','e73c96'),('post','d151b3')):
        result=actual[name]['result']
        need(result['exit_code']==0 and result['chunk_id']==chunk and actual[name]['history'][-1]==result,'actual_terminal_tool_history_required')
    need(postexit['actual']['exit_code']==0 and postexit['actual']['chunk_id']=='62c651','actual_postexit_tool_required')
    known={identity(row)for row in post['known_identities']}
    need(len(known)==len(post['known_identities'])==post['known_count']==8536,'exact_post8536')
    observer={identity(row)for row in post['observer_preparer_identities']}
    need(len(observer)==3 and not known&observer,'exact_three_disjoint_observer_preparers')
    known|=observer
    need(supplement['prior_preparer_union']==8539 and supplement['complete_observed_next_union']==8541
         and supplement['technical_procedure_passed']is False and supplement['original_QH4_FAIL_preserved']is True
         and supplement['root60_requalified']is False and supplement['owned_worker_role_granted']is False
         and supplement['termination_authority_granted']is False,'append_only_nonqualifying_supplement')
    added=set()
    for witness in supplement['supplemental_guard_only_identities']:
        source=Path(witness['source'])
        if not source.is_absolute():source=WORK.parent/source
        need(source.resolve().is_relative_to(WORK),'witness_local_containment')
        matching=[key for key in ('negative','post')if (WORK/REFS[key][0]).resolve()==source.resolve() and REFS[key][1]==witness['source_sha256']]
        need(len(matching)==1,'exact_hashed_guard_source_required')
        obj=records[matching[0]]
        pointer=witness['json_pointer']
        need(type(pointer)is str and pointer.startswith('/'),'explicit_JSON_pointer')
        for component in pointer.split('/')[1:]:
            token=component.replace('~1','/').replace('~0','~')
            obj=obj[int(token)]if type(obj)is list else obj[token]
        value=identity(witness['identity'])
        need(identity(obj)==value and value not in known and value not in added
             and witness['read_only_absence_witness']is True
             and witness['original_absent_or_reused']is True and witness['uncertain']is None,'exact_pinned_prior_witness_NULL_not_coerced')
        added.add(value)
    need(len(added)==2,'exact_two_guard_only_witnesses')
    known|=added;need(len(known)==8541,'exact_complete_observed8541')
    rows=[dict(pid=p,create_time=b)for p,b in sorted(known)]
    value=dict(schema='qh5-finite-prior-identity-projection-v1',transformation='post8536_plus_observer3_plus_exact_guard_witness2',
        known_count=len(rows),identities=rows,identities_canonical_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        source_refs={key:dict(path=str(WORK/rel),sha256=h)for key,(rel,h)in REFS.items()},
        technical_procedure_passed=False,original_QH4_FAIL_preserved=True,root60_requalified=False,
        fresh_current_absence_performed=False,fresh_complete_absence_required_before_runtime=True,
        prior_supplement_uncertain_field=None,prior_supplement_NULL_not_coerced=True,
        ownership_or_worker_adoption=False,termination_authority_granted=False,actual_clock=None,actual_metrics=None,new_runtime_ready=False)
    need(not OUT.exists(),'exclusive_new_projection')
    with OUT.open('x',encoding='utf-8',newline='\n')as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(known_count=len(rows),identity_sha256=value['identities_canonical_sha256'],projection_sha256=digest(OUT),fresh_current_absence_performed=False,runtime_ready=False)))
if __name__=='__main__':main()
