"""New terminal closure with one reviewed, proven lifetime fence; never resume."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,time
import psutil
W=Path(__file__).resolve().parent;P=W/'fullagent-cv-launch-r4'
OUT=W/'fullagent-cv-stage1-terminal-ownership-fenced-r1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text('utf-8'))
def require(x,code):
    if not x:raise RuntimeError(code)
def path(n):
    p=(W/n).resolve();require(p.is_relative_to(W),'outside_work');return p
def mod(n,p):
    spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=str,required=True)
    parser.add_argument('--review-sha256',required=True);args=parser.parse_args()
    require(not OUT.exists(),'append_only_closure_exists')
    reviewpath=path(args.review);require(sha(reviewpath)==args.review_sha256,'root_review_changed')
    review=load(reviewpath)
    require(review.get('root_reviewed') is True and review.get('one_exact_identity_fence_accepted') is True
        and review.get('synthetic_contracts_root_reviewed') is True and review.get('new_fits_allowed') is False,
        'concrete_root_review_required')
    require(review['files_sha256'].get(Path(__file__).name)==sha(__file__),'root_must_pin_closure_source')
    require(review['files_sha256'].get('terminal_identity_fence_r1.py')=='f6f112fc9eedce4e402e87a306dfae30bfedd75b457458b5ac5431f2f67757c8','fence_not_reviewed')
    require(sha(P/'manifest.json')=='a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a','manifest_changed')
    require(sha(W/'build_fullagent_cv_binding.py')=='84a519c3f6a916c82c568be1944f5c9e0fac6409b5ac50f8fbafac2a7398b5ff','builder_changed')
    require(sha(P/'ownership.py')=='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8','owner_changed')
    require(sha(P/'research_lock.py')=='78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45','lock_changed')
    require(sha(W/'f4/stage1.json')=='d2e5f64276e639fd6f20b315014701bb12352b2f2c65b3294ced04a9ccd7c456','terminal_stage_changed')
    manifest=load(P/'manifest.json');stage=load(W/'f4/stage1.json');launch=load(W/'fullagent-cv-stage1-launch-r4.json')
    require(stage['status']=='rejected_early_incomplete_CV' and stage['failure_code']=='unsupported_outer_output_contract','unexpected_terminal')
    require(launch['status']=='stage1_exec_completed' and launch['exec_exit_code']==1,'launcher_not_terminal1')
    require(stage['cleanup_confirmed'] and stage['source_unchanged'] and not stage['complete_CV'] and stage['pairs']==[],'terminal_scope_changed')
    require(stage['absolute_deadline_unix']==launch['absolute_deadline_unix']==1792801631.466951,'clock_changed')
    refs={p.relative_to(W).as_posix():sha(p) for p in sorted((W/'f4').glob('*.json'))}
    for n in ['fullagent-cv-stage0-launch-r4.json','fullagent-cv-stage1-launch-r4.json',
        'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json','fullagent-cv-stage1-review-r4/completion.json',
        'fullagent-cv-launch-r4/review-stage1-r4.json','fullagent-cv-terminal-closure-blocked-r4.json']:
        refs[n]=sha(W/n)
    owned_json_paths=list(refs)
    owned_json_paths.remove('fullagent-cv-terminal-closure-blocked-r4.json')
    for n in review.get('additional_owned_receipts',[]):
        require(n in review['files_sha256'] and Path(n).suffix=='.json','owned_receipt_not_pinned')
        owned_json_paths.append(n)
    refs.update(review['files_sha256']);refs[args.review]=args.review_sha256
    builder=mod('_fenced_terminal_builder',W/'build_fullagent_cv_binding.py')
    owner=mod('_fenced_terminal_owner',P/'ownership.py');lockmod=mod('_fenced_terminal_lock',P/'research_lock.py')
    fence=mod('_fenced_terminal_one_fence',W/'terminal_identity_fence_r1.py')
    known=set()
    # Analysis inventories contain expressly unowned processes. They are pinned
    # as evidence, but only real owner/supervisor receipts define ownership.
    for n in owned_json_paths:known|=builder.identities(load(W/n))
    def guard():
        require(len(manifest['immutable_files'])==430,'source_count')
        for n,h in manifest['immutable_files'].items():require(sha(W/n)==h,'immutable_changed:'+n)
        for n,h in refs.items():require(sha(W/n)==h,'evidence_changed:'+n)
    def fresh():return fence.strict_orphan_check_with_one_fence(owner,
        [{'pid':p,'create_time':c} for p,c in sorted(known)],W/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json')
    guard();before=fresh()
    with lockmod.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        me={'pid':os.getpid(),'create_time':psutil.Process().create_time()};lock.write_identity(me)
        guard();tracked=fresh()
        preparers=[me];parent=psutil.Process().parent()
        while parent is not None and parent.name().lower() in {'python.exe','pythonw.exe'}:
            if not any(Path(a).name==Path(__file__).name for a in parent.cmdline()):break
            preparers.append({'pid':parent.pid,'create_time':parent.create_time()});parent=parent.parent()
        launchers=sorted(builder.identities(launch))
        result={'status':'terminal_R4_Stage1_owned_absence_confirmed_with_one_proven_lifetime_fence',
            'recorded_epoch':time.time(),'stage_receipt_sha256':sha(W/'f4/stage1.json'),
            'manifest_sha256':sha(P/'manifest.json'),'closure_source_sha256':sha(__file__),
            'root_review':{'path':args.review,'sha256':args.review_sha256},
            'source_unchanged':True,'immutable_files_rehashed':430,'cleanup_confirmed':True,
            'fresh_absence_before_and_inside_canonical_lock':True,'strict_known_parent_orphan_scan':True,
            'strict_scan_revision':'One pinned exact parent lifetime fence; all other strict uncertainty checks retained.',
            'known_saved_identity_count':len(known),'tracked_identities':tracked['tracked_identities'],
            'excluded_impossible_parent_edges':tracked['excluded_impossible_parent_edges'],
            'fence':tracked['fence'],'active_owned_processes':[],'no_process_signalled':True,
            'closure_preparer_identities':preparers,'preparer_must_be_absent_before_next_launch':True,
            'launcher_identities':[{'pid':p,'create_time':c} for p,c in launchers],
            'exec_exit_code_observed_by_root':1,'root_observed_session':78130,'evidence_sha256':refs,
            'original_stage1_deadline_unix':stage['absolute_deadline_unix'],'original_attempt_resumed':False,
            'new_fits':0,'API_calls':0,'quality_metrics':None,'complete_CV':False,'OOF_complete':False,'promotion':False}
        # A disappearing impossible edge is harmless, but any newly unresolved
        # owned process still raises. Known tracked identities may not disappear
        # from the recorded union (absence is precisely the expected outcome).
        after=fresh();require(after['tracked_identities']==tracked['tracked_identities'],'known_union_changed')
        result['terminal_excluded_impossible_parent_edges']=after['excluded_impossible_parent_edges'];guard()
        with OUT.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'known_identities':len(known),'closure_sha256':sha(OUT),'new_fits':0}))
if __name__=='__main__':main()
