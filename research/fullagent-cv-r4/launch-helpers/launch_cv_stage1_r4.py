"""Launch the published Stage1 once after actual Stage0 and fresh owned cleanup."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import psutil

W=Path(__file__).resolve().parent;R=W/'alfa-hack-automl';P=W/'fullagent-cv-launch-r4'
B=W/'fullagent-cv-stage1-review-r4';TARGET=W/'fullagent-cv-stage1-launch-r4.json'
COMMIT='1d82bd004fb4a5940d2ec6c1935091b3222b7b0f'
SOURCE='b85d04ec335a6cccefd3ed5214d05ea196fc4a62b619a054644b568c6d05d627'
MANIFEST='a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
REVIEW='179f02f87cd59983de4e20d7de03eeb15c6c146ff85932d01a867dafe227e137'
OLD_REVIEW='f151c6013fb0e484885a41126cb5495ab987ab5e035a1e5ad42d814980eb42d4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text('utf-8'))
def enc(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+R.as_posix(),'-C',str(R),*args])
def write(x,exclusive=False):
    if exclusive:
        with TARGET.open('xb') as out:out.write(enc(x))
    else:
        t=TARGET.with_suffix('.json.pending');t.write_bytes(enc(x));t.replace(TARGET)
assert not TARGET.exists() and not (W/'f4/stage1.json').exists()
assert sha(W/'fullagent_cv_coordinator_r4.py')==SOURCE and sha(P/'manifest.json')==MANIFEST
assert sha(P/'review-stage1-r4.json')==REVIEW and sha(P/'review.json')==sha(P/'review-stage0-r4.json')==OLD_REVIEW
assert sha(B/'completion.json')=='bfe8bfcb7bf06fc13bf4292a1ba1adb7234677685f667cd231a13537b2b7e5c4'
assert sha(W/'build_fullagent_cv_binding.py')=='84a519c3f6a916c82c568be1944f5c9e0fac6409b5ac50f8fbafac2a7398b5ff'
assert sha(P/'ownership.py')=='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
assert sha(P/'research_lock.py')=='78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'
assert git('rev-parse','HEAD').decode().strip()==COMMIT
published=R/'research/fullagent-cv-r4/actual-stage1-preparation'
for p in published.iterdir():
    assert hashlib.sha256(git('show',COMMIT+':'+p.relative_to(R).as_posix())).hexdigest()==sha(p),p.name
completion=load(B/'completion.json')
for n,v in completion['files_sha256'].items():assert sha(B/n)==v,n
closure=load(B/'stage0-terminal-ownership.json');rootreview=load(P/'review-stage1-r4.json')
assert closure['cleanup_confirmed'] and closure['active_owned_processes']==[]
assert rootreview['authorized_stage']=='stage1' and rootreview['root_launch_reviewed'] is True
assert rootreview['manifest_sha256']==MANIFEST and rootreview['source_sha256']==SOURCE
assert rootreview['stage1_seconds']==64800 and rootreview['clock_assigned'] is False
for n,v in closure['evidence_sha256'].items():assert sha(W/n)==v,n
stage0=load(W/'f4/stage0.json');oldlaunch=load(W/'fullagent-cv-stage0-launch-r4.json')
assert stage0['status']=='completed_stage0_pass' and stage0['cleanup_confirmed'] and stage0['source_unchanged']
assert oldlaunch['exec_exit_code']==0 and stage0['manifest_sha256']==MANIFEST
cv=module('_root_stage1_launch_cv',W/'fullagent_cv_coordinator_r4.py');cv.configure(W,'fullagent-cv-launch-r4')
owner=module('_root_stage1_launch_owner',P/'ownership.py')
builder=module('_root_stage1_launch_builder',W/'build_fullagent_cv_binding.py')
locks=module('_root_stage1_launch_lock',P/'research_lock.py')
m=load(P/'manifest.json');cv.guard(m)
known=closure['tracked_identities']+closure['review_preparer_identities']
before=builder.strict_orphan_check(owner,known)
with locks.ResearchLock(R/'test-runs/.owned-research.lock') as lock:
    lock.write_identity({'pid':psutil.Process().pid,'create_time':psutil.Process().create_time()})
    cv.guard(m);cv.predecessor_check(m,owner)
    tracked=builder.strict_orphan_check(owner,before+known)
    for g in stage0['gates']:
        a,k=g['name'].split('_')
        if k=='source':p=cv.source_gate(g['supervisor'],m['arms'][a],W/'f4/gates'/g['name'])
        else:p=cv.exact_gate(g['supervisor'],m['arms'][a],W/'f4/gates'/(g['name']+'.json'))
        assert p==g['proof'] and p['passed']
    assert builder.strict_orphan_check(owner,tracked)==tracked
publication={'status':'actual_Stage0_proof_and_root_Stage1_decision_published_verified',
    'source_commit':COMMIT,'remote_sha_verified':True,'published_files_byte_verified':9,
    'remote_verification':'Root observed push_branch.py exact local/remote equality;9 Stage1 files matched Git tree.',
    'root_review_sha256':REVIEW,'manifest_sha256':MANIFEST,
    'fresh_stage0_and_review_preparer_identities_absent_before_inside_canonical_lock':True,
    'fresh_tracked_count':len(tracked),'no_predecessor_signalled':True,
    'recorded_epoch':time.time(),'clock_assigned':False,'promotion':False}
with (W/'fullagent-cv-stage1-publication-r4.json').open('xb') as out:out.write(enc(publication))
# Preserve the exact prior review under its published historical alias. Change
# only the unbound current-review pointer to the separately published Stage1.
t=P/'review.json.pending';t.write_bytes((P/'review-stage1-r4.json').read_bytes());t.replace(P/'review.json')
assert sha(P/'review.json')==REVIEW and sha(P/'review-stage0-r4.json')==OLD_REVIEW
for n,v in closure['evidence_sha256'].items():
    actual=P/'review-stage0-r4.json' if n=='fullagent-cv-launch-r4/review.json' else W/n
    assert sha(actual)==v,n
start,tick=time.time(),time.monotonic();deadline=start+64800
assert start>stage0['end_unix'] and deadline!=stage0['absolute_deadline_unix']
receipt={'status':'launching_stage1','stage':'stage1','publication_commit':COMMIT,
    'remote_sha_verified':True,'source_sha256':SOURCE,'manifest_sha256':MANIFEST,'root_review_sha256':REVIEW,
    'wrapper_sha256':sha(Path(__file__)),'start_unix':start,'start_monotonic':tick,
    'absolute_deadline_unix':deadline,'deadline_monotonic':tick+64800,'common_seconds':64800,
    'launcher_identity':{'pid':psutil.Process().pid,'create_time':psutil.Process().create_time()},
    'fresh_predecessor_identities_absent':len(tracked),'no_predecessor_signalled':True,
    'available_RAM_MiB':psutil.virtual_memory().available/2**20,'free_disk_GiB':psutil.disk_usage(str(W)).free/2**30,
    'Stage0_original_deadline_unix_preserved':stage0['absolute_deadline_unix'],
    'Stage0_clock_borrowed_reset_or_extended':False,'stage2_started':False,'promotion':False,'official_submission':False}
write(receipt,True)
command=[sys.executable,'-X','utf8','-u',str(W/'fullagent_cv_coordinator_r4.py'),
    '--work-root',str(W),'--packet','fullagent-cv-launch-r4','--launch','--stage','stage1',
    '--manifest-sha256',MANIFEST,'--deadline-unix',str(deadline)]
with (W/'fullagent-cv-stage1-launch-r4.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=W.parent,stdout=log,stderr=subprocess.STDOUT)
    receipt['coordinator_launcher_identity']={'pid':child.pid,'create_time':psutil.Process(child.pid).create_time()}
    receipt['status']='running_stage1';write(receipt);code=child.wait()
receipt.update(status='stage1_exec_completed',exec_exit_code=code,end_unix=time.time(),elapsed_seconds=time.monotonic()-tick)
write(receipt)
print(json.dumps({'stage':'stage1','exit_code':code,'elapsed_seconds':receipt['elapsed_seconds']}))
raise SystemExit(code)
