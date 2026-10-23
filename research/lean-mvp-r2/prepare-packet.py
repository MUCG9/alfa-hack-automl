"""Prospective T7 packet preparation; do not run before root source review.
Copy the EXACT existing m3 archive and manifest inputs. No application imports,
tests, fits, API or research clock. Does not build/rewrite the runtime archive.
Final coordinator must implement the declared new terminal predecessor schema.
"""
from pathlib import Path
import argparse,ast,copy,hashlib,json,shutil

BASE_SHA='4b987c652864179465dc754e90e3d1c8c9ed7c0a2144db5c3339e4c8a607d07e'
ARCHIVE_SHA='16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0'
AUDITOR_SHA='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
COORDINATOR_SHA='43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
TERMINAL=[dict(path='m3packet/terminal-root-closure.json',sha256='ca4796c602ac213a2c48a652fcbb8461ddceadd51b4aa0b8f661ad59931b344a',
    schema='campaign_root_closure',expected_exec_session=88656,expected_exec_exit_code=1,
    identity_fields=['owned_identities','closure_preparer_identities']),
    dict(path='t6-independent-classification-r1/root-closure.json',sha256='cdd587b0ab7f93f9af5cbc835267a15bd008d85b3241fb162032ced3a91168f4',
    schema='postfailure_audit_root_closure',expected_exec_session=43087,expected_exec_exit_code=0,
    identity_fields=['owned_identities','closure_preparer_identities']),
    dict(path='t7-predecessor-root-closure.json',sha256='1c7dea8a72738cee399597d5aef3afb34d220cd9719715fec4525c1dec48caae',
    schema='fresh_supervision_predecessor_closure',identity_fields=['owned_identities','closure_preparer_identities'])]
EVIDENCE={'m3packet/launch.json':'808913336453f9fd8c37b10b08c770599ed73163cce048103b10ab75c6f7a61a',
    't6/campaign.json':'d8004d3c0c5daf2c3f5e599bc7db849f603e6679e59a7559462d0d5bfc53a973',
    'run_t6_classification_audit_r1.py':'b2d6048b28c6a842502ef51ab5a6e5b589cddce19a914ada86c30c86945a3862',
    't6-independent-classification-r1/supervisor.json':'be14766f937eef7770b6015c88feb6cf2cc8b7e61aac5b8ac3882dd83a68ab12',
    't6-independent-classification-r1/audit.json':'831582b935dbfeabd5b6438d3133ab8fffcb8252708062f86057a5ac64d343b7',
    'supervision-contracts-r1/receipt.json':'ed74d1b51cf66c8ad21d547c4d9752c925a390085c38e146f1f72c84ac69e4b9',
    'supervision-contracts-r2/receipt.json':'6ae64fc67e621b49bd574a324393c648d1e516dfa50d0642f1c968e42dddd0eb'}

def need(value,code):
    if not value:raise RuntimeError(code)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-root',type=Path,required=True)
    ap.add_argument('--coordinator-sha256',required=True)
    ap.add_argument('--launcher-sha256',required=True)
    args=ap.parse_args();work=args.work_root.resolve();packet=work/'m4packet'
    def local(name):
        p=(work/name).resolve();need(not Path(name).is_absolute() and p.is_relative_to(work),'outside_work');return p
    need(not packet.exists() and not (work/'t7').exists(),'new_packet_and_output_required')
    base=local('m3packet/manifest.json');need(sha(base)==BASE_SHA,'exact_T6_base_manifest_required')
    old=load(base);need(old['source_root']=='m3dev' and len(old['immutable_files'])==718,'exact_m3_runtime_required')
    need(old['archive_sha256']==ARCHIVE_SHA and sha(local(old['archive']))==ARCHIVE_SHA,'exact_existing_archive_required')
    need(sum(old['registry'].values())==458 and len(old['gates'])==2,'unchanged458_registry_and_two_gates_required')
    for name,h in old['immutable_files'].items():need(sha(local(name))==h,'base_immutable_changed:'+name)
    coordinator='run_lean_mvp_r2.py';launcher='lean-supervision-next-dev/launch_lean_mvp_r2.py'
    need(args.coordinator_sha256==COORDINATOR_SHA and sha(local(coordinator))==COORDINATOR_SHA
         and sha(local(launcher))==args.launcher_sha256,'final_new_sources_required')
    text=local(coordinator).read_text(encoding='utf-8')
    constants={n.value for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    need('terminal_predecessor_receipts' in constants and 't7' in constants,'R2_T7_terminal_predecessor_contract_not_implemented')
    # Marker presence is a fail-closed typo guard, never a replacement for root's
    # source review of the actual predecessor code before+under the canonical lock.
    for ref in TERMINAL:need(sha(local(ref['path']))==ref['sha256'],'terminal_proof_changed')
    for name,h in EVIDENCE.items():need(sha(local(name))==h,'closed_evidence_changed:'+name)
    m=copy.deepcopy(old);m.update(status='prepared_not_launched_independent_T7',launcher=launcher,
        launcher_sha256=args.launcher_sha256,coordinator_sha256=args.coordinator_sha256,
        coordinator=coordinator,archive='m4packet/lean-source.zip',clock_assigned=False,
        original_common_start_unix=None,original_absolute_deadline_unix=None,
        terminal_predecessor_receipts=copy.deepcopy(TERMINAL),publication_prefix='research/lean-mvp-r2',
        output_root='t7',previous_T6_campaign_qualification='FAIL',previous_T6_exec_session=88656,
        previous_T6_exec_exit_code=1,previous_T6_clock_reset=False,
        procedure_scope='New supervision-only iteration; exact unchanged m3 ML runtime/archive/tasks/control/HPO/max9. Prior T6 FAIL and postfailure task evidence retained. Reused-public, no official score.')
    for gate in m['gates']:
        gate['result']=gate['result'].replace('t6/','t7/')
        gate['command']=[str(local(m['archive'])) if arg==str(local(old['archive'])) else arg for arg in gate['command']]
    cfg=m['final_audit'];cfg['command']=['t7' if a=='t6' else a.replace('t6/','t7/').replace('m3packet/lean-source.zip','m4packet/lean-source.zip') for a in cfg['command']]
    cfg['result']='t7/independent-audit.json'
    m['verification_plan_template']['execution_manifest_sha256']=None
    m['verification_plan_template']['original_absolute_deadline_unix']=None
    # Retain every old718 source/input reference as evidence; add new controller,
    # launcher/closure metadata. The manifest never pins itself or launch receipt.
    pins=m['immutable_files'];pins['m3packet/manifest.json']=BASE_SHA
    pins[coordinator]=args.coordinator_sha256;pins[launcher]=args.launcher_sha256
    pins[Path(__file__).resolve().relative_to(work).as_posix()]=sha(Path(__file__).resolve())
    pins.update(EVIDENCE);pins.update({r['path']:r['sha256'] for r in TERMINAL})
    need(m['verification_plan_template']['verifier_source_sha256']==AUDITOR_SHA,'frozen_R4_required')
    packet.mkdir();shutil.copyfile(local(old['archive']),packet/'lean-source.zip')
    need(sha(packet/'lean-source.zip')==ARCHIVE_SHA,'archive_copy_parity_failed')
    pins['m4packet/lean-source.zip']=ARCHIVE_SHA
    for name,h in pins.items():need(sha(local(name))==h,'pre_manifest_source_changed:'+name)
    save(packet/'manifest.json',m)
    save(packet/'preparation.json',dict(status='prepared_only_no_clock_or_jobs',base_manifest_sha256=BASE_SHA,
        manifest_sha256=sha(packet/'manifest.json'),archive_sha256=ARCHIVE_SHA,runtime_source_root='m3dev',
        immutable_refs=len(pins),source_expected_tests=458,exact_expected_tests=23,
        research_clock_assigned=False,actual_gates_run=0,fits=0,API_calls=0,
        root_source_review_of_coordinator_predecessor_contract_required=True))
    print(json.dumps(dict(status='prepared_only',manifest_sha256=sha(packet/'manifest.json'),immutable_refs=len(pins))))
if __name__=='__main__':main()
