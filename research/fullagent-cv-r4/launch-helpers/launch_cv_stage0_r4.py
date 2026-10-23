"""Launch separately reviewed f4 once, with one new immutable3600s clock."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time
import psutil

W=Path(__file__).resolve().parent
R=W/'alfa-hack-automl'
P=W/'fullagent-cv-launch-r4'
TARGET=W/'fullagent-cv-stage0-launch-r4.json'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','safe.directory='+R.as_posix(),'-C',str(R),*args])
def encoded(x):
    return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def write(x,exclusive=False):
    if exclusive:
        with TARGET.open('xb') as out:out.write(encoded(x))
    else:
        t=TARGET.with_suffix('.json.pending');t.write_bytes(encoded(x));t.replace(TARGET)
args=argparse.ArgumentParser();args.add_argument('--publication-commit',required=True);args.add_argument('--root-review-sha256',required=True);args=args.parse_args()
assert not TARGET.exists() and not (W/'f4').exists()
assert sha(W/'fullagent_cv_coordinator_r4.py')=='b85d04ec335a6cccefd3ed5214d05ea196fc4a62b619a054644b568c6d05d627'
manifest_sha='a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
assert sha(P/'manifest.json')==manifest_sha and sha(P/'review.json')==args.root_review_sha256
m=json.loads((P/'manifest.json').read_text('utf-8'));review=json.loads((P/'review.json').read_text('utf-8'))
assert review['root_launch_reviewed'] is True and review['authorized_stage']=='stage0'
assert review['manifest_sha256']==manifest_sha and m['limits']['stage0']==3600
for n,v in m['immutable_files'].items():assert sha(W/n)==v,n
assert git('rev-parse','HEAD').decode().strip()==args.publication_commit
published=R/'research/fullagent-cv-r4/actual-stage0-preparation'
for p in published.iterdir():
    assert hashlib.sha256(git('show',args.publication_commit+':'+p.relative_to(R).as_posix())).hexdigest()==sha(p),p.name
publication={'status':'actual_R4_Stage0_preparation_published_and_verified',
    'source_commit':args.publication_commit,'remote_sha_verified':True,
    'remote_verification':'Root observed push_branch.py exact local/remote SHA equality; all8 preparation files matched Git tree.',
    'manifest_sha256':manifest_sha,'root_launch_review_sha256':sha(P/'review.json'),
    'recorded_epoch':time.time(),'clock_assigned':False,'promotion':False}
with (W/'fullagent-cv-stage0-publication-r4.json').open('xb') as out:out.write(encoded(publication))
start,tick=time.time(),time.monotonic();deadline=start+3600
old=json.loads((W/'f3/stage0.json').read_text('utf-8'))
assert start>old['end_unix'] and deadline!=old['absolute_deadline_unix']
receipt={'status':'launching_stage0','stage':'stage0','technical_attempt':'f4_after_preserved_failed_f3',
    'start_unix':start,'start_monotonic':tick,'absolute_deadline_unix':deadline,
    'deadline_monotonic':tick+3600,'common_seconds':3600,
    'manifest_sha256':manifest_sha,'source_sha256':sha(W/'fullagent_cv_coordinator_r4.py'),
    'wrapper_sha256':sha(Path(__file__)),'root_review_sha256':sha(P/'review.json'),
    'launcher_identity':{'pid':psutil.Process().pid,'create_time':psutil.Process().create_time()},
    'publication_commit':args.publication_commit,'remote_sha_verified':True,
    'available_RAM_MiB':psutil.virtual_memory().available/2**20,'free_disk_GiB':psutil.disk_usage(str(W)).free/2**30,
    'preserved_prior_failed_original_deadline_unix':old['absolute_deadline_unix'],
    'prior_failed_clock_reset_or_extended':False,'stage1_started':False,'promotion':False,'official_submission':False}
write(receipt,True)
command=[sys.executable,'-X','utf8','-u',str(W/'fullagent_cv_coordinator_r4.py'),
    '--work-root',str(W),'--packet','fullagent-cv-launch-r4','--launch','--stage','stage0',
    '--manifest-sha256',manifest_sha,'--deadline-unix',str(deadline)]
with (W/'fullagent-cv-stage0-launch-r4.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=W.parent,stdout=log,stderr=subprocess.STDOUT)
    receipt['coordinator_launcher_identity']={'pid':child.pid,'create_time':psutil.Process(child.pid).create_time()}
    receipt['status']='running_stage0';write(receipt);code=child.wait()
receipt.update(status='stage0_exec_completed',exec_exit_code=code,end_unix=time.time(),elapsed_seconds=time.monotonic()-tick)
write(receipt)
print(json.dumps({'stage':'stage0','technical_attempt':'f4','exit_code':code,'elapsed_seconds':receipt['elapsed_seconds']}))
raise SystemExit(code)
