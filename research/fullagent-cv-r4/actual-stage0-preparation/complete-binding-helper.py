"""Bind observed publication and fresh predecessor absence; no prepare/fit/clock."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import time
import psutil

W=Path(__file__).resolve().parent
R=W/'alfa-hack-automl'
P=W/'fullagent-cv-supervisor-plan-r4'
COMMIT='d2449bb45a67331b1b3bb63ef78cf1fdf69c3561'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    return json.loads(p.read_text('utf-8'))
def encoded(x):
    return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
def git(*args):
    return subprocess.check_output(['git','-c','safe.directory='+R.as_posix(),'-C',str(R),*args])
assert git('rev-parse','HEAD').decode().strip()==COMMIT
assert sha(W/'fullagent_cv_coordinator_r4.py')=='b85d04ec335a6cccefd3ed5214d05ea196fc4a62b619a054644b568c6d05d627'
assert sha(W/'build_fullagent_cv_binding.py')=='84a519c3f6a916c82c568be1944f5c9e0fac6409b5ac50f8fbafac2a7398b5ff'
assert sha(P/'binding-draft-r4.json')=='05b506726dc66ce0a6bddc5e03d3472bc073515fd522103aa4e7164ecec1a44f'
published=R/'research/fullagent-cv-r4'
for p in published.rglob('*'):
    if p.is_file():
        assert hashlib.sha256(git('show',COMMIT+':'+p.relative_to(R).as_posix())).hexdigest()==sha(p),p.name
rootreview=load(published/'root-source-review.json')
assert rootreview['root_source_reviewed'] and rootreview['controller_narrow_mock_methods_passed']==12
publication={
    'status':'reviewed_R4_technical_repair_source_published_actual_gates_pending',
    'root_source_reviewed':True,'remote_sha_verified':True,'source_commit':COMMIT,
    'remote_verification':'Root observed push_branch.py exact local/remote equality; all26 publication files byte-checked against tree.',
    'coordinator_source_sha256':rootreview['coordinator_source_sha256'],
    'independent_verifier_sha256':rootreview['independent_verifier_sha256'],
    'mechanical_verifier_sha256':rootreview['mechanical_verifier_sha256'],
    'source_snapshot_manifest_sha256':rootreview['source_snapshot_manifest_sha256'],
    'archive_sha256':{'a':'88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0','b':'d5144685e682654bfed3a0e216ecec4f2ada4868b7df0e0d9779aba9f79d77bc'},
    'prior_failed_f3_preserved':True,'shared_metadata_files':9,
    'actual_gates_run':0,'actual_CV_arms':0,'deadline_assigned':False,'launch_authorized':False,'promotion':False,
}
publication_path=W/'fullagent-cv-coordinator-publication-r4.json'
assert not publication_path.exists() and not (W/'fullagent-cv-launch-binding-r4.json').exists()
cv=module('_root_R4_binding_cv',W/'fullagent_cv_coordinator_r4.py');cv.configure(W,'fullagent-cv-launch-r4')
builder=module('_root_R4_binding_builder',W/'build_fullagent_cv_binding.py')
owner=module('_root_R4_binding_owner',W/'fullagent-cv-launch-r1/ownership.py')
lockmod=module('_root_R4_binding_lock',W/'fullagent-cv-launch-r1/research_lock.py')
binding=load(P/'binding-draft-r4.json')
before=cv.predecessor_check(binding,owner)
builder.strict_orphan_check(owner,before['tracked'])
with lockmod.ResearchLock(R/'test-runs/.owned-research.lock') as lock:
    lock.write_identity({'pid':psutil.Process().pid,'create_time':psutil.Process().create_time()})
    fresh=cv.predecessor_check(binding,owner)
    tracked=builder.strict_orphan_check(owner,fresh['tracked'])
    for n,v in load(W/'fullagent-cv-launch-r1/manifest.json')['immutable_files'].items():
        assert sha(W/n)==v,n
    cv.gate_metadata(binding)
    for a in ['a','b']:
        for n,v in binding['arms'][a]['source_files_sha256'].items():
            assert sha(W/binding['arms'][a]['source_root']/n)==v,n
    with publication_path.open('xb') as out:
        out.write(encoded(publication))
    binding['coordinator_publication_receipt_sha256']=sha(publication_path)
    binding['status']='root_actual_R4_binding_ready_for_prepare_no_clock_or_launch'
    binding['required_before_prepare']=[]
    binding['binding_builder_proof']={
        'prior_binding_sha256':'ef4bbcaf1958f769c2c1254387710770c61a5f0313ed2549a816ee398b62e991',
        'draft_binding_sha256':sha(P/'binding-draft-r4.json'),
        'root_reviewed_exact_R4_source_publication':True,
        'recorded_epoch':time.time(),'fresh_absence_before_and_inside_canonical_lock':True,
        'strict_known_parent_orphan_scan':True,'fresh_tracked_count':len(tracked),
        'no_process_signalled':True,'helper_sha256':sha(Path(__file__)),
        'launch_authorized':False,'deadline_assigned':False,'fits':0,'API_calls':0,
    }
    assert builder.strict_orphan_check(owner,tracked)==tracked
    with (W/'fullagent-cv-launch-binding-r4.json').open('xb') as out:
        out.write(encoded(binding))
print(json.dumps({'status':binding['status'],'binding_sha256':sha(W/'fullagent-cv-launch-binding-r4.json'),
    'publication_sha256':sha(publication_path),'fresh_tracked_absent':len(tracked),'prepare_executed':False,'new_clock':False}))
