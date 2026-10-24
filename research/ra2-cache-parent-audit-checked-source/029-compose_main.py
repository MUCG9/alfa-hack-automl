"""SOURCE-only composition of the qualified CX2 lifecycle into the RA1 leaf."""
from pathlib import Path
import ast,hashlib,json
P=Path(__file__).resolve().parent;W=P.parent;B=W/'class-xgb-cx2-next-dev/run_audit.py'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf-8'))
assert sha(B)=='abf1cef2df47cddc021ffc1da1a5c2e2d30f9df5457161e9c70938d22e89d67a'
source=B.read_text('utf-8');tree=ast.parse(source)
nodes={n.name:ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
target=P/'run_audit.py';header=target.read_text('utf-8')
assert '\ndef main():' not in header
refs={key:(rel,sha(W/rel)) for key,rel in dict(manifest='private/rq6-manifest.ready-r1.json',campaign='rq6/campaign.json',
    root='rq6/terminal-root-closure.json',negative='rq6/current-negative-closure.json',post='rq6/current-negative-post-tool-confirmation.json',
    barrier='rq6/pretruth-barrier.json',regression_seal='rq6/regression-core-seal.json',classification_seal='rq6/classification-core-seal.json',
    old_auditor='last-submission-repair-qualification-next-dev-r6/artifact_audit.py').items()}
header=header.replace('ORIGINAL_REFS={}','ORIGINAL_REFS='+repr(refs))
main=nodes['main'].replace("schema='class-xgb-cache-campaign-v1'","schema='postfailure-standard-artifact-qualification-campaign-v1'")
main=main.replace('comparison_procedure_passed','artifact_procedure_passed').replace('quality_gate_passed','quality_metric').replace('qualified_comparison','qualified_artifacts')
main=main.replace("cfg=config(a.manifest,a.manifest_sha256,a.self_sha256)","""cfg=config(a.manifest,a.manifest_sha256,a.self_sha256);state['_manifest']=cfg
        original=read(cfg['rq6']['campaign']['path'])
        need(sha(cfg['rq6']['campaign']['path'])==cfg['rq6']['campaign']['sha256'],'original_RQ6_campaign_changed')
        need(original['absolute_deadline_unix']==original['start_unix']+6000
            and original['common_deadline_monotonic']==original['start_monotonic']+6000,'inherited_original6000_not_reset')
        state['inherited_original_clock']={k:original[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}
        end=min(end,original['common_deadline_monotonic']);wall=min(wall,original['absolute_deadline_unix'])
        state['effective_deadline_monotonic']=end;state['effective_deadline_unix']=wall""")
start=main.index("        check();frozen();docs=")
end=main.index('        base.absent(owner,known,check);lease=',start)
main=main[:start]+"""        check();known=predecessor(cfg,check)
        # Only immutable previously sealed inventories; no copy/unpack/fit.
        for role in ('regression_seal','classification_seal'):
            ref=cfg['rq6'][role];need(sha(ref['path'],check)==ref['sha256'],'saved_core_seal_changed')
            inventory=read(ref['path'])['files_sha256'];need(type(inventory) is dict and len(inventory)<=20000,'bounded_saved_core_inventory')
            for path,h in inventory.items():
                need(Path(path).is_absolute() and re.fullmatch('[0-9a-f]{64}',h),'typed_saved_core_hash')
                need(path not in cfg['immutable_files'] or cfg['immutable_files'][path]==h,'saved_core_source_pin_collision')
                need(path not in sealed or sealed[path]==h,'two_saved_core_pin_collision');sealed[path]=h
        frozen()
"""+main[end:]
main=main.replace("CLASS-XGB-CONTRIBUTION-01-cache-audit","RA1-saved-standard-artifact-audit")
main=main.replace("prefix='cx-'","prefix='ra-'")
start=main.index("        for name,path,expected in [")
end=main.index('        # A genuine admission timestamp',start)
main=main[:start]+"""        for index,contract in enumerate(cfg['contracts']):
            name=('auditor-contracts','caller-contracts','atomic-root-contracts')[index];path=contract['path'];expected=contract['count']
            check(setup_end);need(setup_end-time.monotonic()>=60,'full_changed_contract_slot_required')
            ref=run([cfg['python'],'-B','-X','utf8',path,'-v'],Path(path).parent,name,60,45,420+60)
            need(counter.counts(Path(ref['path']).with_suffix('.log').read_text('utf-8'),expected),'exact_changed_contract_count_no_skip_required')
            state['contracts'].append(dict(name=name,expected=expected,supervisor=ref));persist();check(setup_end)
"""+main[end:]
start=main.index("        payload=copy.deepcopy(cfg['audit_payload'])")
end=main.index("    except BaseException as exc:fail",start)
main=main[:start]+"""        payload=copy.deepcopy(cfg['repair_payload']);payload['clock']=audit_clock(start,begin,admission_unix,admission_mono)
        need(payload['clock']['audit_deadline_monotonic']+300<=end
            and payload['clock']['audit_deadline_unix']+300<=wall,'full_audit_and_final_inside_both_commons')
        context=OUT/'repair-context.json';save(context,payload);sealed[str(context)]=sha(context,check)
        output=OUT/'independent-artifact-audit.json';state['status']='auditing';state['audit_binding']=dict(path=str(context),sha256=sealed[str(context)]);persist()
        original_manifest=cfg['rq6']['manifest']
        ref=run(audit_command(cfg['python'],original_manifest['path'],original_manifest['sha256'],str(context),sealed[str(context)],str(output)),WORK,
            'saved-standard-artifact-audit',120,90,420,parent_start=admission_mono)
        result=read(output);need(result_qualified(result,original_manifest['sha256'],sealed[str(context)]),
            'saved_standard_artifact_audit_unqualified')
        sealed[str(output)]=sha(output,check);state.update(status='completed_pending_root',artifact_procedure_passed=True,
            independent_audit=dict(path=str(output),sha256=sealed[str(output)],supervisor=ref),quality_metric=result['quality_metric'],qualified_artifacts=result['tasks'])
"""+main[end:]
main=main.replace("'original600_exhausted'","'new600_or_inherited_original6000_exhausted'")
main=main.replace("'research_audit'","'saved_artifact_audit'")
main=main.replace("'_cx_","'_ra1_")
fence=nodes['temporary_fence'].replace("directory.name.startswith('cx-')","directory.name.startswith('ra-')")
result=header+'\n\n'+nodes['capture']+'\n\n'+fence+'\n\n'+main+"\n\nif __name__=='__main__':raise SystemExit(main())\n"
compile(result,str(target),'exec');target.write_text(result,encoding='utf-8',newline='\n')
print(json.dumps(dict(source_written=True,main_sha256=sha(target),runtime_executed=False)))
