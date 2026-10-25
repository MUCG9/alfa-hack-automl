"""Fixed metadata-only QH4 preflight caller; no campaign clock or runtime admission."""
import time
ENTRY_UNIX,ENTRY_MONOTONIC=time.time(),time.monotonic()
from pathlib import Path
import argparse,contextlib,hashlib,importlib.util,json,types

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;PRIVATE=WORK/'private'
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
UTILITY=WORK/'qwen-three-hour-metadata-preflight-next-dev-r2/preflight.py'
UTILITY_SHA='a830f4b24f655795ad30b73298eb469abdabdc724ff05f1a691d6b1a334161a0'
OUTER=WORK/'qwen-three-hour-outer-next-dev-r9/run_campaign.py'
OUTER_SHA='cf8057fe763ec9ca8f90972fd5e6e98f365453c4dc55f5a361f53a1ce5d0c95a'
KNOWN_SHA='7bd7cb265f740b78c095c722cd4184fdf366439b7f0084d4bd7a4a0862facd3f'
EARLY=PRIVATE/'qh4-metadata-preflight-early-preparers-r1.json'
PREPARERS=PRIVATE/'qh4-metadata-preflight-preparer-r1.json'
RESULT=PRIVATE/'qh4-metadata-preflight-result-r1.json'

def need(value,code):
    if not value:raise RuntimeError(code)

def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()

def read(path):return json.loads(Path(path).read_text('utf-8'))

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def identity_rows(identities):return [dict(pid=p,create_time=b) for p,b in sorted(identities)]

def identity_sha(identities):
    return hashlib.sha256(json.dumps(identity_rows(identities),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def recording_observer_class(original,seen):
    class RecordingObserver(original):
        def observe(self):
            try:return super().observe()
            finally:seen.update(self.seen)
    return RecordingObserver

@contextlib.contextmanager
def continuous_clock_checkpoints(utility,checkpoint,actual_monotonic):
    """Change only this trusted module's time reference, never global time."""
    original=utility.time
    def monotonic():
        checkpoint();return actual_monotonic()
    utility.time=types.SimpleNamespace(monotonic=monotonic)
    try:yield
    finally:utility.time=original

def save_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['manifest','manifest-sha256','self-sha256']:parser.add_argument('--'+key,required=True)
    parser.add_argument('--launch-parent-pid',type=int,required=True);parser.add_argument('--launch-parent-create-time',type=float,required=True)
    args=parser.parse_args()
    need(__debug__ and sha(BASE)==BASE_SHA,'qualified_C5_source_changed');base=imported('_qh4_metadata_C5',BASE)
    import psutil
    captured,chain=base.capture(psutil,args.launch_parent_pid,args.launch_parent_create_time)
    need(PRIVATE.is_dir() and PRIVATE.resolve()==PRIVATE and not PRIVATE.is_symlink()
         and not any(p.exists() for p in [EARLY,PREPARERS,RESULT]),'exclusive_fixed_private_metadata_outputs_required')
    save_new(EARLY,dict(identities=captured,launch_parent_observation=chain,actual_tool_evidence_pending=True))
    seen=base.ids(captured);stats={};result=None;error=None;secondary=[];lease=None
    pulse=lambda **kwargs:None;cfg=None;known=set();preflight=None
    try:
        need(chain.get('verified') is True and sha(__file__)==args.self_sha256,'actual_self_source_or_chain_unconfirmed')
        manifest=Path(args.manifest);need(manifest.is_absolute() and manifest.stat().st_size<=2**20
            and sha(manifest)==args.manifest_sha256,'exact_bounded_absolute_private_manifest_required')
        cfg=read(manifest);pins=cfg['immutable_files']
        need(type(pins) is dict and pins.get(str(Path(__file__).resolve()))==args.self_sha256
            and pins.get(str(BASE))==BASE_SHA and pins.get(str(UTILITY))==UTILITY_SHA
            and pins.get(str(OUTER))==OUTER_SHA,'preimport_caller_utility_C5_outer_pins_required')
        modules={}
        for name in ['owner','sampling','lock']:
            relative,h=base.HELPERS[name];path=WORK/relative
            need(pins.get(str(path))==h and sha(path)==h,'qualified_metadata_helper_changed')
            modules[name]=imported('_qh4_metadata_'+name,path)
        observer_owner=types.SimpleNamespace(StrictOwnedObserver=recording_observer_class(modules['owner'].StrictOwnedObserver,seen))
        original_pulse=base.guard(ENTRY_MONOTONIC,ENTRY_MONOTONIC+30,ENTRY_UNIX+30,
            observer_owner,captured,stats,sampling=modules['sampling'])
        def pulse(force=False):
            original_pulse(force=force)
            sample=stats.get('verified_resource_sample') or {}
            seen.update(base.ids(sample.get('sampled',[])+sample.get('departed',[])+stats.get('departed_known_resource_identities',[])))
        pulse(force=True)
        need(sha(UTILITY,pulse)==UTILITY_SHA and sha(OUTER,pulse)==OUTER_SHA,'metadata_source_changed')
        for ref in cfg['launch_preparer_receipts']:
            pulse();need(set(ref)=={'path','sha256','actual_tool'} and Path(ref['path']).is_absolute()
                and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],pulse)==ref['sha256']
                and ref['actual_tool']['exit_code']==0 and bool(ref['actual_tool']['tool']),'exact_actual_predecessor_identity_receipt_required')
            known|=base.ids(read(ref['path'])['identities'])
        need(len(known)==8469 and identity_sha(known)==KNOWN_SHA and not known&base.ids(captured),
            'exact_reviewed_candidate8469_predecessor_union_required')
        base.absent(modules['owner'],known,pulse)
        lock=WORK/'alfa-hack-automl/test-runs/.owned-research.lock'
        need(cfg['lock']==str(lock) and lock.is_absolute(),'fixed_qualified_ABS_lock_required')
        lease=modules['lock'].ResearchLock(lock);lease.__enter__();lease.write_identity(captured[0])
        base.absent(modules['owner'],known,pulse)
        preflight=imported('_qh4_exact_preflight_R2',UTILITY)
        with continuous_clock_checkpoints(preflight,pulse,time.monotonic):
            result=preflight.evaluate(str(OUTER),str(manifest),OUTER_SHA,args.manifest_sha256)
        need(result.get('exact_config_predicate_passed') is True and result.get('exact_predecessor_predicate_passed') is True
            and result.get('saved_known_identity_count')==len(known)==8469,'exact_metadata_predicates_and_known_scope_required')
        base.absent(modules['owner'],known,pulse)
        need(sha(manifest,pulse)==args.manifest_sha256 and sha(UTILITY,pulse)==UTILITY_SHA
            and sha(OUTER,pulse)==OUTER_SHA and sha(__file__,pulse)==args.self_sha256,'metadata_source_or_private_changed')
        pulse(force=True)
    except BaseException as exc:error=exc
    finally:
        if lease is not None:
            try:lease.__exit__(None,None,None);pulse(force=True)
            except BaseException as exc:
                if error is None:error=exc
                else:secondary.append(dict(phase='lease_release',type=type(exc).__name__))
    def records(passed):
        observation={k:v for k,v in stats.items() if not k.startswith('_')}
        shared=dict(schema='qh4-bounded-metadata-preflight-v1',exact_config_predicate_passed=passed,
            exact_predecessor_predicate_passed=passed,source_unchanged=passed,known_current_absence_confirmed=passed,
            identities=identity_rows(seen),captured_launch_chain_identities=captured,launch_parent_observation=chain,
            identities_scope='exact_capture_plus_ALL_guard_observer_seen_and_sampled_departed; resource-only_roles_UNKNOWN; no ownership/worker/signal authority',
            asserted_resource_process_roles=None,resource_only_identity_ownership_adopted=False,
            manifest=dict(path=args.manifest,sha256=args.manifest_sha256),controller=dict(path=str(OUTER),sha256=OUTER_SHA),
            utility=dict(path=str(UTILITY),sha256=UTILITY_SHA),known_count=len(known),known_exact_live=[] if passed else None,
            uncertain=[] if passed else None,resource_observation=observation,preflight_result=result,
            own_parent_seconds=30,metadata_start_unix=ENTRY_UNIX,metadata_start_monotonic=ENTRY_MONOTONIC,
            elapsed_seconds=time.monotonic()-ENTRY_MONOTONIC,inside_own30=passed,experiment_clock_created=False,
            actual_new_experiment_clock=None,actual_tool_evidence_pending=True,model_fits=0,API_calls=0,
            candidate_imports=0,array_decodes=0,runtime_admitted=False,
            error=None if error is None else dict(type=type(error).__name__,code=str(error) if isinstance(error,RuntimeError) else type(error).__name__),secondary_errors=secondary)
        return dict(shared),dict(shared,schema='qh4-bounded-metadata-preflight-preparer-v1')
    written=[]
    try:
        if error is not None:raise error
        pulse(force=True);published_seen=set(seen);summary,preparer=records(True)
        for path,value in [(PREPARERS,preparer),(RESULT,summary)]:
            pulse();save_new(path,value);written.append(path);pulse(force=True)
        print(json.dumps(dict(exact_metadata_preflight_passed=True,known_count=len(known),observed_preparers=len(seen),
            preparer_sha256=sha(PREPARERS,pulse),result_sha256=sha(RESULT,pulse),runtime_admitted=False)))
        pulse(force=True);need(seen==published_seen,'guard_identity_inventory_grew_during_final_publication');return 0
    except BaseException as exc:
        if error is None:error=exc
        elif exc is not error:secondary.append(dict(phase='publication',type=type(exc).__name__))
        summary,preparer=records(False)
        for path,value in [(PREPARERS,preparer),(RESULT,summary)]:
            try:
                if path in written:base.save(path,value)
                elif not path.exists():save_new(path,value)
            except BaseException as save_error:secondary.append(dict(phase='negative_receipt_save',type=type(save_error).__name__))
        print(json.dumps(dict(exact_metadata_preflight_passed=False,error=type(error).__name__,runtime_admitted=False)))
        return 1

if __name__=='__main__':raise SystemExit(main())
