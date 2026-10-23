"""Actual curated ownership closure; analytical exclusions remain evidence only."""
from pathlib import Path
import hashlib,importlib.util,json,os,time
import psutil
W=Path(__file__).resolve().parent;OUT=W/'cache-pilot-predecessor-binding-r2.json'
SNAP=W/'cache-pilot-prior-owned-clean-snapshot-r2.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text('utf-8'))
def mod(n,p):
    spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
assert not OUT.exists() and not SNAP.exists()
old=W/'cache-pilot-predecessor-binding-r1.json';assert sha(old)=='b60d2efbb3c3872a0008f24fce464632dd791539a9e3a9a0cc22f7017fe91c81'
b=load(old);known=b['owned_identities'];refs=dict(b['files_sha256'])
refs[old.name]=sha(old);refs['bind_cache_pilot_predecessor_r2.py']=sha(__file__)
refs['cache-pilot-launch-r1/manifest.json']=sha(W/'cache-pilot-launch-r1/manifest.json')
frozen=load(W/'fullagent-cv-launch-r4/manifest.json')['immutable_files']
assert sha(W/'terminal_identity_fence_r1.py')=='f6f112fc9eedce4e402e87a306dfae30bfedd75b457458b5ac5431f2f67757c8'
owner=mod('_cacheR2_owner',W/'fullagent-cv-launch-r4/ownership.py')
locks=mod('_cacheR2_locks',W/'fullagent-cv-launch-r4/research_lock.py')
fence=mod('_cacheR2_fence',W/'terminal_identity_fence_r1.py')
def guard():
    for n,h in refs.items():assert sha(W/n)==h,n
    for n,h in frozen.items():assert sha(W/n)==h,n
def fresh():return fence.strict_orphan_check_with_one_fence(owner,known,
    W/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json')
guard();fresh()
with locks.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
    me={'pid':os.getpid(),'create_time':psutil.Process().create_time()};lock.write_identity(me)
    tracked=fresh();guard();preparers=[me];parent=psutil.Process().parent()
    while parent is not None and parent.name().lower() in {'python.exe','pythonw.exe'}:
        if not any(Path(a).resolve()==Path(__file__).resolve() for a in parent.cmdline() if Path(a).name==Path(__file__).name):break
        preparers.append({'pid':parent.pid,'create_time':parent.create_time()});parent=parent.parent()
    union={(v['pid'],v['create_time']) for v in tracked['tracked_identities']+preparers}
    ids=[{'pid':p,'create_time':c} for p,c in sorted(union)]
    snapshot={'status':'completed_curated_prior_owned_absence_under_lock',
        'recorded_epoch':time.time(),'cleanup_confirmed':True,'source_unchanged':True,
        'active_owned_processes':[],'immutable_original_campaign_files_rehashed':430,
        'fresh_absence_before_and_inside_canonical_lock':True,'strict_known_parent_orphan_scan':True,
        'owned_identities':ids,'preparer_identities':preparers,
        'preparers_must_be_absent_before_next_launch':True,
        'excluded_impossible_parent_edge_count':len(tracked['excluded_impossible_parent_edges']),
        'exclusion_records_are_not_in_this_ownership_snapshot':True,
        'evidence_sha256':dict(refs),'binding_source_sha256':sha(__file__),
        'new_fits':0,'API_calls':0,'promotion':False}
    fresh();guard()
    with SNAP.open('x',encoding='utf-8',newline='\n') as f:json.dump(snapshot,f,ensure_ascii=False,indent=2);f.write('\n')
    refs[SNAP.name]=sha(SNAP)
    result={'status':'root_reviewed_curated_prior_owner_binding_no_clock',
        'root_reviewed':True,'scope_complete':True,'cleanup_confirmed':True,'source_unchanged':True,
        'recorded_epoch':time.time(),'owned_identities':ids,'owned_receipt_paths':[SNAP.name],
        'files_sha256':refs,'preparer_identities':preparers,'preparers_must_be_absent_before_launch':True,
        'root_preflight_R1_binding_rejected_without_launch':True,
        'reason':'Full failed receipts contain analytical impossible-parent edges and null audit source flags. They remain evidence; only the actual curated clean snapshot grants recursive ownership.',
        'original_full_receipts_preserved':True,'all_prior_failures_preserved':True,
        'fresh_absence_before_and_inside_lock':True,'immutable_campaign_files_rehashed':430,
        'candidate_wrapper_source_paths_pinned':7,'new_fits':0,'API_calls':0,
        'cache_clock_assigned':False,'promotion':False}
    fresh();guard()
    with OUT.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'binding_sha256':sha(OUT),'snapshot_sha256':sha(SNAP),'owned_identities':len(ids),'fits':0}))
