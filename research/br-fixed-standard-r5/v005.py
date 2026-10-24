"""Stdlib source projection only. Never imports coordinator/sampler or scans PIDs."""
from pathlib import Path
import ast,difflib,hashlib,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parent;OLD=WORK/'verified-supervision-next-dev'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):
    (HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
assert sha(OLD/'source-handoff.json')=='ae471f6e6b17e8f7b462ee7bd6edce60f6888c98c3304904080918f2874fd645'
assert sha(OLD/'coordinator.py')=='52d1cf5154d845888392be60dcaa55a2e82bb7ada6dc08441efafce2278565ba'
before=(OLD/'coordinator.py').read_text('utf-8')
old="        state['_pulse'](); clock(deadline, unix)"
new="        state['_resource_checkpoint'](); clock(deadline, unix)"
assert before.count(old)==1
after=before.replace(old,new)
compile(after,str(HERE/'coordinator.py'),'exec')
(HERE/'coordinator.py').write_text(after,encoding='utf-8',newline='\n')
proof=json.loads((OLD/'source-proof.json').read_text('utf-8'))
inverse=after.replace(new,old)
assert inverse==before
for r in reversed(proof['replacements']):inverse=inverse.replace(r['after'],r['before'])
assert inverse==(WORK/'run_lean_mvp_r2.py').read_text('utf-8-sig')
write('source-proof.json',dict(schema='verified-supervision-clock-only-hook-proof-v2',
    previous_handoff_sha256=sha(OLD/'source-handoff.json'),previous_source_sha256=sha(OLD/'coordinator.py'),
    previous_SOURCE_ONLY_preserved=True,exact_delta=dict(before=old,after=new),
    inverse_equals_previous_whole_source=True,inverse_previous_replacements_equals_original43be=True,
    prior_finding='state._pulse was full resource guard, not the required clock-only callback',
    corrected_contract='state._resource_checkpoint is required clock-only original gap/rollback/common observation; existing _pulse remains full outer observation',
    no_clock_reset=True,compiled_source_only=True,actual_imports_tests_fits_API_PIDscans_clock=0))
(HERE/'R1-to-R2.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='frozen52d1',tofile='clock-only-hook')),encoding='utf-8')
(HERE/'README.txt').write_text('SOURCE ONLY; do not execute main/run.\n'
    'Same exact43be inverse as R1, plus resource_checkpoint now requires state["_resource_checkpoint"].\n'
    'Caller C5 must install its original clock-only gap/rollback/common checkpoint there.\n'
    'Existing state["_pulse"] still executes outside primitive resource operations.\n'
    'Original43be and frozen R1 remain unchanged. No clocks or tests have been run.\n',encoding='utf-8')
refs=json.loads((OLD/'source-handoff.json').read_text('utf-8'))['external_source_refs']
refs['preserved_R1_handoff']=dict(path='verified-supervision-next-dev/source-handoff.json',sha256=sha(OLD/'source-handoff.json'))
refs['preserved_R1_source']=dict(path='verified-supervision-next-dev/coordinator.py',sha256=sha(OLD/'coordinator.py'))
names=['coordinator.py','source-proof.json','R1-to-R2.patch','README.txt','prepare_source.py']
write('source-handoff.json',dict(schema='verified-supervision-source-handoff-v2',readiness='FROZEN_SOURCE_ONLY_PENDING_PEER',
    files_sha256={n:sha(HERE/n) for n in names},external_source_refs=refs,
    actual_imports_tests_fits_API_data_PIDscans_clock=0,qualification=None))
print(json.dumps(dict(coordinator_sha256=sha(HERE/'coordinator.py'),handoff_sha256=sha(HERE/'source-handoff.json'))))
