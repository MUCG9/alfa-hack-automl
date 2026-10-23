"""Terminal tm1 ownership proof. Never launches fits or signals a process."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

W=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exec-exit-code',type=int)
    args=parser.parse_args()
    receipt_path=W/'true-mvp-completion-ownership.json'
    if receipt_path.exists():raise RuntimeError('Completion proof already exists; preserve its original bytes')
    root_path=W/'true_four_stage_mvp.py'
    if sha(root_path)!='4abc86b070c8f629cf60a77ffa7dcfe24b3a5369945759b3907f51f67d222205':
        raise RuntimeError('Frozen tm1 supervisor differs')
    helper=module('_close_true_mvp_frozen',root_path);helper.configure(W)
    campaign_path=helper.OUTPUT/'campaign.json'
    campaign=load(campaign_path)
    allowed={'completed_qualified_four_stage_mvp','completed_unqualified_four_stage_mvp','stopped'}
    if campaign.get('status') not in allowed or campaign.get('cleanup_confirmed') is not True:
        raise RuntimeError('tm1 must have terminal campaign and confirmed cleanup before ownership closure')
    if campaign.get('source_unchanged') is not True or not campaign.get('finished_unix'):
        raise RuntimeError('Terminal source/finish evidence is missing')
    launcher_path=W/'true-mvp-launch-receipt.json';launcher=load(launcher_path)
    if launcher.get('status') in {None,'launching','running','preparing'}:
        raise RuntimeError('Root launch receipt is still active or missing')
    if not (launcher.get('finished_unix') or launcher.get('end_unix')):
        raise RuntimeError('Root launch receipt has no terminal timestamp')
    launchers=launcher.get('launcher_identities',[])
    if len(launchers)!=2:raise RuntimeError('Both observed launcher identities are required')
    known=[*launchers,campaign['owned_root']]
    supervisors={}
    for short in ('r','c'):
        p=helper.OUTPUT/short/'supervisor.json';s=load(p)
        if s.get('status')=='running' or s.get('cleanup_confirmed') is not True:
            raise RuntimeError('A task supervisor has not completed exact owned cleanup')
        supervisors[short]={'sha256':sha(p),'status':s['status'],'kind':s['kind']}
        known.append(s['owned_root'])
        known.extend(s.get('owned_process_identities',[]))
        known.extend(s.get('observed_worker_roots',[]))
    manifest=load(helper.BUNDLE/'manifest.json');helper.guard(manifest)
    _,owner=helper.libraries()
    before=owner.predecessor_snapshot(known)
    if before['active'] or not before['cleanup_confirmed']:
        raise RuntimeError('Fresh owned launcher/worker/orphan remains active')
    lock_module=module('_close_true_mvp_lock',helper.REPO/'tools/research_lock.py')
    with lock_module.ResearchLock(helper.REPO/'test-runs/.owned-research.lock'):
        after=owner.predecessor_snapshot([*known,*before['tracked']])
        if after['active'] or not after['cleanup_confirmed']:
            raise RuntimeError('Owned process appeared before exclusive lock proof')
        helper.guard(manifest)
        receipt={'status':'completed','checked_epoch':time.time(),'cleanup_confirmed':True,
            'active_owned_processes':[],'launcher_identities':launchers,
            'tracked_identities':after['tracked'],'campaign_receipt_sha256':sha(campaign_path),
            'campaign_status':campaign['status'],'launcher_receipt_sha256':sha(launcher_path),
            'launcher_status':launcher['status'],'task_supervisors':supervisors,
            'absolute_deadline_unix':campaign['absolute_deadline_unix'],
            'actual_finished_unix':campaign['finished_unix'],
            'within_common_deadline':campaign['finished_unix']<=campaign['absolute_deadline_unix'],
            'exec_exit_code':args.exec_exit_code,'exec_result_verified':args.exec_exit_code is not None,
            'exclusive_training_lock_acquired':True,'source_input_packet_unchanged':True,
            'manifest_sha256':sha(helper.BUNDLE/'manifest.json'),'frozen_file_count':len(manifest['immutable_files']),
            'closure_source_sha256':sha(Path(__file__)),'new_fits':0,'new_api_calls':0,
            'no_process_was_signalled':True,'quality_or_stage_promotion_implied':False}
        helper.write(receipt_path,receipt,exclusive=True)
    print(json.dumps({'status':receipt['status'],'tracked_count':len(after['tracked']),
                      'campaign_status':campaign['status'],'lock_released_on_exit':True}))

if __name__=='__main__':main()
