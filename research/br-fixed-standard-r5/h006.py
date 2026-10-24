"""Stdlib source preparation only; does not import any guarded runtime."""
from pathlib import Path
import ast, difflib, hashlib, json

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
BASE=WORK/'run_lean_mvp_r2.py'
BASE_SHA='43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
SAMPLER=WORK/'verified-resource-sampling-next-dev/verified_sampling.py'
SAMPLER_SHA='d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
assert sha(BASE)==BASE_SHA and sha(SAMPLER)==SAMPLER_SHA
old=BASE.read_text('utf-8-sig')
changes=[]
def replace(before,after):
    global source
    assert source.count(before)==1,before
    source=source.replace(before,after)
    changes.append((before,after))
source=old
replace('WORK = Path(__file__).resolve().parent',
        "WORK = Path(__file__).resolve().parent.parent\nRESOURCE_SAMPLER = 'verified-resource-sampling-next-dev/verified_sampling.py'\nRESOURCE_SAMPLER_SHA = '"+SAMPLER_SHA+"'")
replace("    end = parent_start+parent_seconds\n    record = dict(status='starting'",
        "    end = parent_start+parent_seconds\n    def resource_checkpoint():\n        # Existing caller observation history/common/parent clocks, never reset.\n        state['_pulse'](); clock(deadline, unix)\n        need(time.monotonic() < end, 'parent_cap_exhausted')\n    record = dict(status='starting'")
replace("        frozen(end, 'parent_cap_exhausted'); clock(deadline, unix)\n        env = environment",
        "        frozen(end, 'parent_cap_exhausted'); clock(deadline, unix)\n        need(sha(local(RESOURCE_SAMPLER), resource_checkpoint) == RESOURCE_SAMPLER_SHA,\n             'verified_resource_sampler_source_changed')\n        sampling = imported('_verified_supervision_sampling', local(RESOURCE_SAMPLER))\n        resource_sampler = sampling.VerifiedResourceSampler()\n        me = psutil.Process(); self_identity = (me.pid, me.create_time())\n        bootstrap_identities = identities(bootstraps)\n        env = environment")
replace("                parents, memory, roles = {}, {}, {}\n                for identity, process in live.items():\n                    try:\n                        need(process.create_time() == identity[1], 'owned_identity_changed')\n                        memory[identity] = process.memory_info().rss\n                        parents[identity[0]] = process.ppid()\n                        argv = process.cmdline()  # Only exact owned processes; never saved.\n                        if any(Path(x).name in {'automl_worker.py', 'agent_worker.py'} for x in argv):\n                            job = Path(argv[-1]).resolve()\n                            need(job.is_relative_to(WORK), 'owned_worker_job_outside_work')\n                            roles[identity] = job\n                    except psutil.NoSuchProcess:\n                        continue",
        "                sample = resource_sampler.sample(set(live) | bootstrap_identities | {self_identity},\n                    required=[self_identity], checkpoint=resource_checkpoint)\n                stable_rss = {(row['pid'], row['create_time']): row['rss_bytes'] for row in sample['sampled']}\n                parents, memory, roles = {}, {i:stable_rss[i] for i in live if i in stable_rss}, {}\n                for identity, process in live.items():\n                    if identity not in stable_rss: continue  # Explicit freshly confirmed departed identity.\n                    try:\n                        resource_checkpoint()\n                        need(process.create_time() == identity[1], 'owned_identity_changed')\n                        parents[identity[0]] = process.ppid()\n                        argv = process.cmdline()  # Only exact owned processes; never saved.\n                        need(process.create_time() == identity[1], 'owned_identity_changed')\n                        resource_checkpoint()\n                        if any(Path(x).name in {'automl_worker.py', 'agent_worker.py'} for x in argv):\n                            job = Path(argv[-1]).resolve()\n                            need(job.is_relative_to(WORK), 'owned_worker_job_outside_work')\n                            roles[identity] = job\n                    except psutil.NoSuchProcess:\n                        resource_sampler.confirm_departed(identity, checkpoint=resource_checkpoint)\n                        # Keep already verified RSS/PPID conservatively, as the original loop did.\n                        continue\n                record['verified_resource_sample'] = sample\n                record['departed_known_resource_identities'] = list(resource_sampler.departed)")
replace("                total = psutil.Process().memory_info().rss+sum(memory.values())\n                for saved in bootstraps:\n                    try:\n                        p = psutil.Process(saved['pid'])\n                        if p.create_time() == saved['create_time']: total += p.memory_info().rss\n                    except psutil.NoSuchProcess:\n                        pass",
        "                # Preserve the original conservative self + tree + bootstrap sum,\n                # including any overlap; departed rows are provenance, never invented RSS0.\n                total = stable_rss[self_identity]+sum(memory.values())\n                for identity in bootstrap_identities:\n                    if identity in stable_rss: total += stable_rss[identity]")
compile(source,str(HERE/'coordinator.py'),'exec')
(HERE/'coordinator.py').write_text(source,encoding='utf-8',newline='\n')
inverse=source
for before,after in reversed(changes):
    assert inverse.count(after)==1
    inverse=inverse.replace(after,before)
assert inverse==old
old_ast=ast.parse(old);new_ast=ast.parse(source)
fn=lambda tree:{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
before_functions,after_functions=fn(old_ast),fn(new_ast)
assert set(before_functions)==set(after_functions)
assert [k for k in before_functions if before_functions[k]!=after_functions[k]]==['supervise']
(HERE/'base-to-copy.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),source.splitlines(True),fromfile='immutable43be',tofile='verified-copy')),encoding='utf-8')
save('source-proof.json',dict(schema='verified-supervision-source-proof-v1',base=dict(path='run_lean_mvp_r2.py',sha256=BASE_SHA),
    effective_WORK_unchanged=True,only_changed_existing_function='supervise',all_other_functions_and_classes_AST_equal=True,
    exact_whole_source_inverse=True,replacements=[dict(before=b,after=a) for b,a in changes],
    compiled_source_only=True,actual_runtime_imports_tests_fits_API_PIDscans_clock=0))
save('protocol.json',dict(schema='verified-supervision-consumer-protocol-v1',readiness='FROZEN_SOURCE_ONLY_NOT_EXECUTED',
    allowed_entrypoints=['supervise','child_errors','environment','sha','save','relative','identities'],
    forbidden_entrypoints=['main','run'],original43be_immutable=True,
    sampler=dict(path='verified-resource-sampling-next-dev/verified_sampling.py',sha256=SAMPLER_SHA),
    caps_changed=False,model_API_environment_changed=False,worker_roles_changed=False,known_only=True,
    RSS='Stable exact self + owned tree + captured bootstraps; original conservative overlap retained',
    NoSuch='Fresh same-birth-present/denial/unknown STOP; absent/new birth only recorded departed, never adopted or RSS0',
    clocks='Existing state._pulse history + original common/parent before/after primitive operations; no reset',
    new_clock=None,actual_runtime=None,metrics=None))
(HERE/'README.txt').write_text('Frozen source-only consumer of the reviewed verified resource sampler.\n'
    'Use only coordinator.supervise and unchanged helper functions; never main/run.\n'
    'Original43be remains byte-exact. The new nested file keeps effective WORK at work/.\n'
    'Only supervise RSS/role/bootstrap sampling changes; all other function/class ASTs equal.\n'
    'The sampler checkpoint uses the existing caller pulse plus common/parent bounds.\n'
    'No missing/denied resource observation is skipped. Fresh departure is recorded, not RSS0.\n'
    'No imports/tests/fits/PID observations/clocks were executed during preparation.\n',encoding='utf-8')
names=['coordinator.py','base-to-copy.patch','source-proof.json','protocol.json','README.txt','prepare_source.py']
history=HERE/'source-evidence/r1'
prior=json.loads((history/'source-handoff.json').read_text('utf-8'))
assert sha(history/'source-handoff.json')=='1776a8a82d33c4cd2e946b4f6b4cfe22101ea397be58dfb3ae343d4dc8555ebd'
assert all(sha(history/n)==h for n,h in prior['files_sha256'].items())
save('R1-preservation.json',dict(schema='verified-supervision-preparation-history-v1',status='SOURCE_ONLY_NOT_EXECUTED',
    handoff_sha256=sha(history/'source-handoff.json'),files_sha256={p.name:sha(p) for p in history.iterdir() if p.is_file()},
    corrected_before_peer='Keep already verified RSS and PPID conservatively when role NoSuch is freshly confirmed; do not discard an actual measured row.'))
names.append('R1-preservation.json')
save('source-handoff.json',dict(schema='verified-supervision-source-handoff-v1',readiness='FROZEN_SOURCE_ONLY_PENDING_PEER',
    files_sha256={n:sha(HERE/n) for n in names},external_source_refs={
    'immutable43be':dict(path='run_lean_mvp_r2.py',sha256=BASE_SHA),
    'sampler':dict(path='verified-resource-sampling-next-dev/verified_sampling.py',sha256=SAMPLER_SHA),
    'sampler_handoff':dict(path='verified-resource-sampling-next-dev/source-handoff.json',sha256='86859fe9596d672373e76edc56d6fc89c88c956952c2ed88ded15a6ea7e0076c'),
    'sampler_peer':dict(path='verified-resource-sampling-independent-review-r1.json',sha256='c61e4f028b7a06c0e6b17e02f8a567d08fd31804554e1a908e1dffb49bb418d6'),
    'root_scope':dict(path='brq2-verified-sampling-batch-root-scope-r1.json',sha256='a00ea96ff2455ad80d640f20f7da071288dffd7f18401058a6f14e35d4458f0e')},
    source_inverse_proof=True,actual_imports_tests_fits_API_data_PIDscans_clock=0,qualification=None))
print(json.dumps(dict(coordinator_sha256=sha(HERE/'coordinator.py'),handoff_sha256=sha(HERE/'source-handoff.json'),source_only=True)))
