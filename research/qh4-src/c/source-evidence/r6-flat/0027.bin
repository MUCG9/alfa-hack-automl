"""Metadata-only producer receipt revision; no candidate/test execution."""
from pathlib import Path
import ast
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
OLD=WORK/'qwen-three-hour-autoresearch-next-dev-r3'
OLD_SHA='6cfa6b3f8cb213054a4723d2dbeb733f50b4505d158cfd67c1fa4121a6f8a414'
PEER=WORK/'qwen-three-hour-autoresearch-independent-review-r3.json'
PEER_SHA='e58b07429294ddfa0605bedffba6bca70090b5bd9680d868ff5d65f1c4be3fa9'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(node):return ast.dump(node,include_attributes=False)
def save(name,value):(HERE/name).write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))


HELPER='''def canonical_metadata(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def persist_parent_callback(result,folder,index,phase,cut,*,task_manifest,source_union,spec,recipe,check):
    """Save the exact returned parent record, separate from child result.json."""
    need(type(result) is dict and type(index) is int and index>0
         and type(phase) is str and phase,'typed_actual_parent_callback_required')
    folder=Path(folder).resolve();need(folder.is_absolute(),'absolute_callback_folder_required')
    def actual_ref(path):
        check()
        return dict(path=str(path),sha256=sha(path,check)) if path.is_file() else None
    record=dict(schema='qwen-three-hour-parent-result-v1',callback_index=index,phase=phase,
        task_manifest=dict(task_manifest),cut=dict(cut),
        source_union_canonical_sha256=canonical_metadata(source_union),
        spec_canonical_sha256=canonical_metadata(spec),recipe_canonical_sha256=canonical_metadata(recipe),
        raw_job=actual_ref(folder/'job.json'),raw_result=actual_ref(folder/'result.json'),result=result)
    target=folder/'parent-result.json';check();save(target,record);check()
    return dict(path=str(target),sha256=sha(target,check))


'''


def main():
    assert sha(OLD/'source-handoff.json')==OLD_SHA and sha(PEER)==PEER_SHA
    old=json.loads((OLD/'source-handoff.json').read_bytes())
    snapshot=HERE/'source-evidence/r3';snapshot.mkdir(parents=True,exist_ok=True)
    for rel,h in old['files_sha256'].items():
        assert sha(OLD/rel)==h
        target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes((OLD/rel).read_bytes())
        if not rel.startswith('source-evidence/') and rel!='prepare_r3.py':
            destination=HERE/rel;destination.parent.mkdir(parents=True,exist_ok=True);assert not destination.exists();destination.write_bytes((OLD/rel).read_bytes())
    (snapshot/'source-handoff.json').write_bytes((OLD/'source-handoff.json').read_bytes())
    (snapshot/'independent-review-r3.json').write_bytes(PEER.read_bytes())
    entry=(OLD/'task_entry.py').read_text('utf-8-sig')
    anchor='def run(a):\n';assert entry.count(anchor)==1;entry=entry.replace(anchor,HELPER+anchor,1)
    anchor="        result['split_sha256']=cut['sha256']\n        return result"
    replacement="""        result['split_sha256']=cut['sha256']
        result['parent_callback_receipt']=persist_parent_callback(result,output/('worker-'+str(worker_count)),
            worker_count,phase,cut,task_manifest=dict(path=str(manifest),sha256=a.manifest_sha256),
            source_union=pins,spec=cfg['spec'],recipe=recipe,check=view.check)
        return result"""
    assert entry.count(anchor)==1;entry=entry.replace(anchor,replacement,1)
    (HERE/'task_entry.py').write_bytes(entry.encode('utf-8'))
    loop=(OLD/'research_loop.py').read_text('utf-8-sig')
    anchor="        'full_refit':None,'quality_qualified':False,'promotion':False,'official_score_claim':False}"
    replacement="        'full_refit':None,'quality_qualified':False,'promotion':False,'official_score_claim':False,\n        'strong_control_cuts':None,'callback_ledger_refs':[]}"
    assert loop.count(anchor)==1;loop=loop.replace(anchor,replacement,1)
    anchor="        state['last_worker_final_status']=result.get('status')"
    addition="""        receipt=result.get('parent_callback_receipt')
        need(type(receipt) is dict and set(receipt)=={'path','sha256'}
             and type(receipt['path']) is str and receipt['path']
             and type(receipt['sha256']) is str and len(receipt['sha256'])==64
             and all(c in '0123456789abcdef' for c in receipt['sha256']),
             'actual_saved_parent_callback_receipt_required')
        state['callback_ledger_refs'].append(deepcopy(receipt))
"""
    assert loop.count(anchor)==1;loop=loop.replace(anchor,addition+anchor,1)
    anchor="        control=paired(incumbent,'control-');score_pair(control,task);best=control"
    replacement="        control=paired(incumbent,'control-');state['strong_control_cuts']=deepcopy(control)\n        score_pair(control,task);best=control"
    assert loop.count(anchor)==1;loop=loop.replace(anchor,replacement,1)
    (HERE/'research_loop.py').write_bytes(loop.encode('utf-8'))
    # Only the shared synthetic callback's return data changes, not any old test.
    test=(OLD/'test_research_loop.py').read_text('utf-8-sig')
    anchor="                    coordinator_killed=None,primary_exception_type=None,prior_result_status='ok'))"
    replacement="""                    coordinator_killed=None,primary_exception_type=None,prior_result_status='ok'),
                parent_callback_receipt=dict(path='synthetic-owned/worker-'+str(len(calls))+'/parent-result.json',
                    sha256=hashlib.sha256(str(len(calls)).encode()).hexdigest()))"""
    assert test.count(anchor)==1;test=test.replace(anchor,replacement,1)
    anchor="full_fit=phase=='full-refit',submission='owned/final.csv',"
    assert test.count(anchor)==1;test=test.replace(anchor,anchor+"recipe=deepcopy(recipe),",1)
    (HERE/'test_research_loop.py').write_bytes(test.encode('utf-8'))
    oldproof=json.loads((OLD/'source-proof.json').read_bytes());contracts={}
    for path in HERE.glob('test_*.py'):
        tree=ast.parse(path.read_bytes());methods={c.name+'.'+m.name:hashlib.sha256(dump(m).encode()).hexdigest()
            for c in tree.body if isinstance(c,ast.ClassDef) for m in c.body if isinstance(m,ast.FunctionDef) and m.name.startswith('test_')}
        contracts[path.name]=dict(sha256=sha(path),prepared_method_count=len(methods),methods_AST_sha256=methods,actual_executed=0)
    for name,row in oldproof['prepared_contracts'].items():assert contracts[name]['methods_AST_sha256']==row['methods_AST_sha256']
    assert sum(v['prepared_method_count'] for v in contracts.values())==24
    for name in ['provider_environment.py','r5_worker_runtime.py','r5_resources.py','verified_sampling.py','gateway_child.py']:
        assert (HERE/name).read_bytes()==(OLD/name).read_bytes()
    oldproof['prepared_contracts']=contracts
    oldproof['parent_callback_ledger_R4']=dict(previous_handoff_sha256=OLD_SHA,peer_sha256=PEER_SHA,
        strict_worker_process_caps_provider_bytes_exact=True,all22_old_method_and_assert_ASTs_exact=True,
        new_mock_methods=2,total_prepared_methods=24,actual_executed=0,
        exact_parent_record_saved_after_existing_source_and_cut_checks=True,
        raw_job_and_result_refs_are_actual_or_genuine_null=True,
        all_returned_callback_refs_and_strong_control_pair_persisted=True,
        no_learner_fit_count_inferred=True,all_outputs_require_outer_seals_before_truth=True)
    save('source-proof.json',oldproof)
    patches=[]
    for name in ['task_entry.py','research_loop.py','test_research_loop.py']:
        patches.extend(difflib.unified_diff((OLD/name).read_text('utf-8-sig').splitlines(True),(HERE/name).read_text('utf-8-sig').splitlines(True),fromfile='R3/'+name,tofile='R4/'+name))
    (HERE/'R4-parent-ledger-only.patch').write_bytes(''.join(patches).encode('utf-8'))
    protocol=json.loads((OLD/'protocol.json').read_bytes());protocol['parent_callback_ledger']='Every actually returned strict parent callback is saved separately in worker-N/parent-result.json with original manifest/source/spec/recipe/cut/raw-job/raw-result bindings; report retains full ledger refs and actual initial strong_control_cuts. No model/clock/process semantics change.';save('protocol.json',protocol)
    (HERE/'README.txt').write_bytes(((OLD/'README.txt').read_text('utf-8-sig')+'\nR4 adds only actual saved parent callback metadata and retained strong-control cut records. Child result.json is not a parent cleanup/resource receipt. Missing parent/cut/core/confirmation/source evidence STOPs independent audit; no reconstruction of absent facts. Raw job/result references may be genuinely NULL on failed callbacks, never fake success or learner-fit accounting. Existing22test method/assertion ASTs remain exact;2new source mocks,24prepared0run.\n').encode('utf-8'))
    for path in HERE.glob('*.py'):ast.parse(path.read_bytes())
    external=dict(old['external_refs_sha256']);external['qwen-three-hour-autoresearch-next-dev-r3/source-handoff.json']=OLD_SHA;external['qwen-three-hour-autoresearch-independent-review-r3.json']=PEER_SHA
    files={p.relative_to(HERE).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p!=HERE/'source-handoff.json'}
    result=dict(old);result.update(files_sha256=files,external_refs_sha256=external,prepared_contract_methods=24,
        previous_handoff_sha256=OLD_SHA,source_revision='R4_SAVED_PARENT_CALLBACK_AND_STRONG_CONTROL_ONLY')
    save('source-handoff.json',result)
    print(json.dumps(dict(handoff_sha256=sha(HERE/'source-handoff.json'),prepared=24,executed=0)))


if __name__=='__main__':main()
