"""RQ4 metadata-only binding. No driver/atomic invocation or new common clock."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
from helper_policy import bind_pin, need, publish_checked, save_json, window

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
PACKET = WORK / 'last-submission-repair-qualification-next-dev-r6'
OUT = WORK / 'rq6'
BASE = WORK / 'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA = 'd5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
PYTHON = WORK / 'venv/Scripts/python.exe'
PYTHON_SHA = 'd59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
PS_SHA = '362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authority(path, expected):
    path = Path(path)
    need(__debug__ and path.is_absolute() and sha(path) == expected, 'reviewed_authority_changed')
    value = read(path)
    need(value.get('schema') == 'rq4-root-helper-authority-v1'
         and value.get('readiness') == 'READY_REVIEWED_FROZEN' and value.get('missing_bindings') == [], 'NOT_READY')
    need(value['output'] == str(OUT) and value['packet'] == str(PACKET), 'fixed_RQ4_paths_required')
    refs = value['refs']
    fixed = dict(driver=PACKET/'run_controller.py', closer=PACKET/'close_controller.py',
                 atomic_source=PACKET/'run_root.py', atomic_template=PACKET/'atomic-binding.template.NOT_READY.json',
                 child_script=PACKET/'close_child.ps1', qualifier_handoff=PACKET/'source-handoff.json',
                 python=PYTHON, helper_policy=HERE/'helper_policy.py', binder=HERE/'bind_atomic.py',
                 post_tool=HERE/'confirm_post_tool.py', launch_script=HERE/'launch_atomic.ps1')
    for key, location in fixed.items():
        need(refs[key]['path'] == str(location), 'fixed_reviewed_helper_path_required')
    for ref in [value['manifest'], *refs.values()]:
        need(set(ref) == {'path', 'sha256'} and Path(ref['path']).is_absolute()
             and Path(ref['path']).resolve() == Path(ref['path'])
             and type(ref['sha256']) is str and len(ref['sha256']) == 64
             and sha(ref['path']) == ref['sha256'], 'actual_frozen_reference_required')
    need(refs['python']['sha256'] == PYTHON_SHA and refs['powershell']['sha256'] == PS_SHA,
         'pinned_interpreter_and_PowerShell_required')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('authority', 'authority-sha256', 'actual-tool'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--actual-exit-code', type=int, required=True)
    parser.add_argument('--actual-session', type=int)
    parser.add_argument('--launch-parent-pid', type=int, required=True)
    parser.add_argument('--launch-parent-create-time', type=float, required=True)
    args = parser.parse_args()
    auth = authority(args.authority, args.authority_sha256)
    need(args.actual_exit_code == 0 and bool(args.actual_tool), 'actual_driver_exit0_required')
    need(sha(BASE) == BASE_SHA, 'qualified_C5_changed')
    base = imported('_rq4_atomic_metadata_C5', BASE)
    import psutil
    preparers, chain = base.capture(psutil, args.launch_parent_pid, args.launch_parent_create_time)
    need(chain.get('verified') is True, 'atomic_metadata_launch_chain_unconfirmed')
    prep = OUT / 'atomic-binding-preparer-identity.json'
    save_json(prep, dict(identities=preparers, launch_parent_observation=chain,
        actual_driver=dict(session=args.actual_session, exit_code=args.actual_exit_code, tool=args.actual_tool)), True)
    manifest = Path(auth['manifest']['path']); cfg = read(manifest)
    need(cfg.get('schema') == 'standard-repair-qualification-private-v1'
         and cfg.get('readiness') == 'READY_REVIEWED_FROZEN' and cfg.get('missing_bindings') == []
         and cfg['output'] == str(OUT) and cfg['common_seconds'] == 6000, 'driver_NOT_READY')
    campaign = OUT / 'campaign.json'; state = read(campaign)
    need(state.get('status') == 'completed_pending_root' and not state.get('error_history')
         and all(state.get(k) is True for k in ('cleanup_confirmed', 'source_unchanged', 'temporary_cleanup_confirmed')),
         'actual_clean_terminal_required')
    check = lambda: window(state, time.time(), time.monotonic(), reserve=60)
    check(); pins = dict(cfg['immutable_files']); original = dict(pins)
    for path, expected in original.items():
        check(); need(sha(path) == expected, 'frozen_driver_source_or_input_changed')
    # Reviewed runtime/template/review/interpreter references MUST already exist.
    for key, ref in auth['refs'].items():
        if key not in {'binder', 'post_tool', 'helper_policy', 'launch_script'}:
            need(original.get(ref['path']) == ref['sha256'], 'reviewed_reference_not_in_original_pins')
    binding = read(auth['refs']['atomic_template']['path'])
    additions = {str(Path(args.authority)): args.authority_sha256,
                 str(manifest): auth['manifest']['sha256'], str(campaign): sha(campaign), str(prep): sha(prep)}
    additions.update({ref['path']: ref['sha256'] for key, ref in auth['refs'].items()
                      if key in {'binder', 'post_tool', 'helper_policy', 'launch_script'}})
    def ref(path):
        check()
        return bind_pin(pins, path, sha(path), allowed_new=additions)
    binding['output'] = str(OUT)
    for key in ('driver', 'closer', 'python', 'powershell', 'independent_source_review', 'qualification_source_review'):
        binding[key] = ref(auth['refs'][key]['path'])
    binding['manifest'] = ref(manifest); binding['campaign'] = ref(campaign)
    for item in auth['refs'].values():
        ref(item['path'])
    ref(args.authority); binding['binding_preparer_receipt'] = ref(prep)
    binding.update(immutable_files=pins, readiness='READY_REVIEWED_FROZEN', missing_bindings=[])
    destination = WORK / 'private/rq6-atomic-binding.ready-r1.json'
    def terminal():
        for path, expected in pins.items():
            check(); need(sha(path) == expected, 'terminal_frozen_pin_changed')
        check()
    publish_checked(binding, lambda value, exclusive: save_json(destination, value, exclusive), terminal)
    # Even stdout failure after publication must revoke this helper's metadata.
    try:
        print(json.dumps(dict(binding_sha256=sha(destination), immutable_pins=len(pins), metadata_preparers=len(preparers))))
        check()
    except BaseException as error:
        from helper_policy import revoked
        try:
            save_json(destination, revoked(binding, error), False)
        except BaseException as secondary:
            try:
                error.helper_secondary_exception_type = type(secondary).__name__
            except BaseException:
                pass
        raise
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(prepared=False, error_type=type(error).__name__,
            secondary_exception_type=getattr(error, 'helper_secondary_exception_type', None))))
        raise SystemExit(1)
