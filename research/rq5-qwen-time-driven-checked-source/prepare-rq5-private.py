"""Root-only key-aware preparation of the RQ5 metadata review draft."""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, time

WORK=Path(__file__).resolve().parent
PACKET=WORK/'last-submission-repair-qualification-next-dev-r5-r2'

def need(v, code):
    if not v: raise RuntimeError(code)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text('utf-8'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def absolute(v):
    p=Path(v)
    return str(p if p.is_absolute() else WORK/p)
def methods(p):
    t=ast.parse(Path(p).read_text('utf-8-sig'));result={}
    for cls in t.body:
        if isinstance(cls,ast.ClassDef):
            for n in cls.body:
                if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'):
                    result[cls.name+'.'+n.name]=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
    return result

def main():
    import psutil
    a=argparse.ArgumentParser();a.add_argument('--parent-pid',type=int,required=True);a.add_argument('--parent-birth',type=float,required=True)
    a.add_argument('--source-peer',required=True);a.add_argument('--publication',required=True);a.add_argument('--primary-tool',required=True);a.add_argument('--dispatch-tool',required=True)
    args=a.parse_args();start=time.monotonic()
    def check():need(time.monotonic()-start<30,'metadata30_expired')
    basepath=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
    need(sha(basepath)=='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d','qualified_capture_changed')
    spec=importlib.util.spec_from_file_location('_rq5_metadata_capture',basepath);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    preparers,chain=base.capture(psutil,args.parent_pid,args.parent_birth);need(chain.get('verified') is True,'metadata_launch_chain_unconfirmed')
    postpath=WORK/'rq4/current-negative-post-tool-confirmation.json'
    need(sha(postpath)=='a10de471d11466b5790dbc27ef723c93cfd63d0478efaa8c8d0b9b77a0c1cd47','exact_RQ4_current_post_changed')
    post=read(postpath);known=base.ids(post['known_identities'])|base.ids(post['observer_preparer_identities']);need(len(known)==7920,'complete7920_before_current_preparer')
    for pid,birth in known:
        check()
        try:
            p=psutil.Process(pid);observed=p.create_time()
        except psutil.NoSuchProcess:continue
        need(observed!=birth,'known_exact_process_still_alive')
    cfg=read(PACKET/'binding.template.NOT_READY.json');pins={}
    def pin(p,h=None):
        p=absolute(str(p));value=sha(p) if h is None else h
        need(sha(p)==value,'metadata_source_pin_changed')
        need(p not in pins or pins[p]==value,'metadata_immutable_pin_collision');pins[p]=value
    old=read(WORK/'private/rq4-manifest.ready-r1.json')
    for p,h in old['immutable_files'].items():pin(p,h)
    for folder,filename in [(PACKET,'source-handoff.json'),(WORK/'rq5-root-helpers-next-dev-r2','source-handoff.json')]:
        handoff=read(folder/filename);pin(folder/filename)
        for k,h in handoff['files_sha256'].items():pin(folder/k,h)
        for k,h in handoff['external_refs_sha256'].items():pin(WORK/k,h)
    cfg['output']=str(WORK/'rq5');cfg['python']=str(WORK/'venv/Scripts/python.exe');cfg['lock']=str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock')
    # These are operational fields, not arbitrary strings or ZIP/member names.
    direct=[('executor','test'),('executor','base_inventory'),('legacy_reg_contracts','test'),('legacy_reg_contracts','recipe_fixture'),('legacy_reg_contracts','base_inventory'),('cases_contracts','test'),('root_helper_contracts','test')]
    for top,key in direct:cfg[top][key]=absolute(cfg[top][key])
    for top in ['candidate_source_review','counts','technical_entry']:cfg[top]['path']=absolute(cfg[top]['path'])
    final_entry_hash=read(PACKET/'source-handoff.json')['files_sha256']['technical_entry.py']
    need(pins[cfg['technical_entry']['path']]==final_entry_hash,'exact_final_technical_entry_pin_required')
    cfg['technical_entry']['sha256']=final_entry_hash
    for top,key in [('executor','handoff'),('executor','archive'),('cases_contracts','handoff'),('cases_contracts','source_review'),('root_helper_contracts','handoff')]:cfg[top][key]['path']=absolute(cfg[top][key]['path'])
    for value in cfg['helpers'].values():value['path']=absolute(value['path'])
    old_tasks={value['kind']:value for value in old['tasks']}
    for value in cfg['tasks']:
        approved=old_tasks[value['kind']]
        need(set(approved['files'])=={'task.md','train.csv','test.csv','sample_submission.csv','data_dictionary.csv'},'exact_original_task_input_roles_required')
        value['source']=absolute(approved['source'])
        value['files']=dict(approved['files'])
    for top in ['uar10','lc1','rq1_previous','rq2_previous','rq3_previous','rq4_previous']:
        for value in cfg[top].values():
            if isinstance(value,dict) and 'path' in value:value['path']=absolute(value['path'])
    for top in ['additional_preparer_receipts','launch_preparer_receipts']:
        for value in cfg.get(top,[]):value['path']=absolute(value['path'])
    # Preserve WORK-relative historical split references and all task/member maps.
    peer=Path(args.source_peer).resolve();pin(peer);cfg['qualification_source_review']={'path':str(peer),'sha256':sha(peer)}
    cfg['source_publication']={'commit':args.publication,'primary_actual_tool':args.primary_tool,'dispatch_actual_tool':args.dispatch_tool,'private_operational_bindings_retained_locally':True}
    for name in ['rq5-metadata-preflight-r3.py','rq5-root-helpers-independent-source-review-r2.json']:
        pin(WORK/name)
    sidecar=WORK/'private/rq5-metadata-preparers-r1.json'
    save(sidecar,{'schema':'rq5-root-metadata-preparer-v1','identities':preparers,'launch_parent_observation':chain,'actual_tool_evidence_pending':True})
    pin(sidecar)
    cfg['launch_preparer_receipts'].append({'path':str(sidecar),'sha256':sha(sidecar),'actual_tool':{'exit_code':0,'tool':'PENDING_ACTUAL_METADATA_EXIT'}})
    cfg['immutable_files']=pins;cfg['readiness']='NOT_READY';cfg['missing_bindings']=['actual_metadata_preparer_exit','independent_private_binding_review']
    save(WORK/'private/rq5-manifest.draft-r1.json',cfg)
    fresh={'schema':'rq5-prelaunch-finite-current-fresh-v1','known_count':len(known),'known_identities':[{'pid':p,'create_time':b} for p,b in sorted(known)],'known_exact_live':[],'uncertain':[],'metadata_preparer_identities':preparers,'observed_seconds':time.monotonic()-start}
    save(WORK/'private/rq5-prelaunch-current-fresh-r1.json',fresh)
    print(json.dumps({'draft_written':True,'pins':len(pins),'known_absent':len(known),'metadata_preparers':len(preparers),'draft_sha256':sha(WORK/'private/rq5-manifest.draft-r1.json'),'runtime_admitted':False}))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'metadata_preparation_failed':True,'type':type(e).__name__}));raise SystemExit(1)
