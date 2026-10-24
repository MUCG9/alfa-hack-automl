"""Stdlib SHA/AST/source materialization only; never imports a runtime module."""
from pathlib import Path
import ast,hashlib,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parent
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
AUD=WORK/'class-xgb-contribution-audit-next-dev'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def methods(path):
    result={}
    for c in ast.parse(path.read_text('utf-8-sig')).body:
        if isinstance(c,ast.ClassDef):
            for n in c.body:
                if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'):
                    key=c.name+'.'+n.name;assert key not in result
                    result[key]=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
    return result
assert sha(BASE)=='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
assert sha(AUD/'source-handoff.json')=='b1ac1930c19aca8e405a5ea361ca6ca0755f6a799194c577f3259f765d4026fd'
ah=read(AUD/'source-handoff.json')
assert all(sha(AUD/n)==h for n,h in ah['files_sha256'].items())
tree=ast.parse(BASE.read_text('utf-8-sig'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture')
capture=ast.get_source_segment(BASE.read_text('utf-8-sig'),node)
for name in ['run_audit.py','close_audit.py']:
    p=HERE/name;source=p.read_text('utf-8-sig')
    placeholder='# FROZEN_C5_CAPTURE_FUNCTION_INSERTED_BY_STDLIB_SOURCE_PREPARER'
    if placeholder in source:source=source.replace(placeholder,capture)
    actual=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='capture')
    assert ast.dump(actual,include_attributes=False)==ast.dump(node,include_attributes=False)
    if name=='run_audit.py':
        replacements={
            'AUDITOR_PATH=None':"AUDITOR_PATH='class-xgb-contribution-audit-next-dev/audit_cache.py'",
            'AUDITOR_SHA=None':'AUDITOR_SHA='+repr(sha(AUD/'audit_cache.py')),
            'AUDITOR_TEST_PATH=None':"AUDITOR_TEST_PATH='class-xgb-contribution-audit-next-dev/tests/test_audit_cache.py'",
            'AUDITOR_TEST_SHA=None':'AUDITOR_TEST_SHA='+repr(sha(AUD/'tests/test_audit_cache.py')),
            'AUDITOR_TEST_METHODS=None':'AUDITOR_TEST_METHODS='+repr(methods(AUD/'tests/test_audit_cache.py'))}
        for a,b in replacements.items():
            if a in source:source=source.replace(a,b)
    compile(source,str(p),'exec');p.write_text(source,encoding='utf-8',newline='\n')
caller=methods(HERE/'test_caller.py');auditor=methods(AUD/'tests/test_audit_cache.py')
assert len(caller)==4 and len(auditor)==12
compile((HERE/'test_caller.py').read_text('utf-8'),str(HERE/'test_caller.py'),'exec')
save('source-proof.json',dict(schema='class-xgb-cache-caller-source-proof-v1',capture_both_scripts_AST_equal_C5=True,
    reused_C5_guard_and_qualified_coordinator_R2_no_source_changes=True,setup180_contract_parent_slots=[60,60],
    audit_parent120_child90=True,final_driver240_root60_common600=True,clock_created_only_future_actual_main=True,
    source_AST_methods=dict(caller=caller,auditor=auditor),prepared_test_executions=len(caller)+len(auditor),
    missing_caches_STOP_no_fit_fallback=True,archive_build_release_promotion=False,actual_imports_tests_arrays_PIDs_fits_API_clock=0))
template=dict(schema='class-xgb-cache-caller-private-v1',readiness='NOT_READY',missing_bindings=['root_private_absolute_pin_binding',
    'independent_caller_review','independent_auditor_review','fresh_full7305_plus_new_preparers','root_publication_and_actual_launch'],
    output='cx1',python=None,common_seconds=600,caps=dict(setup=180,audit=[120,90],final=240,root=60),
    lock='alfa-hack-automl/test-runs/.owned-research.lock',immutable_files={},
    auditor=dict(path='class-xgb-contribution-audit-next-dev/audit_cache.py',sha256=sha(AUD/'audit_cache.py')),
    auditor_test=dict(path='class-xgb-contribution-audit-next-dev/tests/test_audit_cache.py',sha256=sha(AUD/'tests/test_audit_cache.py'),count=len(auditor),methods=auditor),
    caller_test=dict(path='class-xgb-contribution-caller-next-dev/test_caller.py',count=len(caller),methods=caller),
    counts=dict(path='uar-count-parser-next-dev/counts.py',sha256='bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3'),
    caller_source_review=dict(path=None,sha256=None),audit_payload=None,additional_preparer_receipts=[],
    brq3=dict(root=dict(path='brq3/terminal-root-closure.json',sha256='7578f3ea5f4d3b14e9925bec5705a3169ab17ae77de5a45cfc7583edeaedf42d'),
        fresh=dict(path='brq3/root-confirmation.json',sha256='85a00effb05fa5cb7218e1021c446855a84a508f1c9f68c01b6d83eee440fdd0'),
        timing=dict(path='brq3/root-fresh-timing-addendum.json',sha256='d2436badbad18f75b2f67feafede7b3ee5b91da840344b2aba4b4154c264b2c8')),
    actual_clock=None,actual_metrics=None,models=0,API=0,promotion=False,submit=False,release_or_archive_work=False)
save('binding.template.NOT_READY.json',template)
save('protocol.json',dict(schema='CLASS-XGB-CONTRIBUTION-01-caller-protocol-v1',readiness='SOURCE_ONLY_NOT_READY',
    only_hypothesis='Drop outerXGB; same retained twoLGBM fixed .5/.5; reproducefull3 control on BOTH42/43 first.',
    common600=dict(setup_contracts=180,audit_parent=120,audit_child=90,driver_final=240,root=60),
    newfits=0,API=0,missing_cache_STOP=True,strictserial=True,technicalthreads=1,worker_RSS_MiB=1536,whole_RSS_MiB=2048,
    inheritance='All7305 prior known identities plus pinned extra preparer receipts, fresh before/underlock and atclosure; unknownhistoricalPID not adopted.',
    original_clock_reset=False,actual_clock=None,actual_results=None,prepared_changed_contracts=dict(auditor=12,caller=4,total=16),
    quality_false_is_not_technical_failure=True,REG_and_deliveredarchive_unchanged=True,archive_release_qualification_DEFERRED=True,promotion=False,submit=False))
(HERE/'README.txt').write_text('SOURCE ONLY / NOT_READY. Fixed no-fit cache experiment, no archive or release action.\n'
    'One600 origin before materialization/import: setup/contracts180 + audit120(parent)/90(child) + driverfinal240 + root60.\n'
    'Changedsource tests only: auditor12+caller4, two fixed60/45 slots. No81-suite/model replay.\n'
    'Reuses frozen C5guard/clock-onlyhook+coorR2+owner/fac3/ResearchLock/PowerGuard/envfalse. Capture AST exactC5 in both scripts.\n'
    'Both controls reproduced before one candidate; missingcache STOP, no fallbackfit. Valid negativequality remains technicalsuccess.\n'
    'Root must instantiate exact absolute immutable inventory/template, reviewed-caller bindings and newpreparer union, independentlyreview/publish, then launch once.\n'
    'Forwarded manifest/output paths alwaysabsolute. Output work/cx1. Ownshallowtemp work/t/cx-* only; copyterminalreceipts before exactcleanup.\n'
    'NOT RUN: python -B -X utf8 run_audit.py --launch --manifest <ABS_READY> --manifest-sha256 <SHA> --self-sha256 <SHA> --launch-parent-pid <SHELL_PID> --launch-parent-create-time <ACTUAL_SHELL_UNIX_BIRTH>\n'
    'AfterACTUALwholeexit ONLY: python -B -X utf8 close_audit.py --manifest <ABS_READY> --manifest-sha256 <SHA> --self-sha256 <CLOSER_SHA> --driver-sha256 <DRIVER_SHA> --campaign-sha256 <ACTUAL_SHA> --actual-exit-code <ACTUAL> --actual-tool-evidence <ACTUAL_TOOL> [--actual-exec-session <ACTUAL_SESSION>] --launch-parent-pid <SHELL_PID> --launch-parent-create-time <ACTUAL_SHELL_UNIX_BIRTH>\n'
    'Actualcloserexit/freshcompletepreparerabsence mustfinishroot60/common600; oldBRQ3clockclosed, neverreopened.\n',encoding='utf-8')
files=['run_audit.py','close_audit.py','test_caller.py','prepare_source.py','source-proof.json','binding.template.NOT_READY.json','protocol.json','README.txt']
save('source-handoff.json',dict(schema='class-xgb-cache-caller-source-handoff-v1',readiness='FROZEN_SOURCE_ONLY_NOT_READY',
    files_sha256={n:sha(HERE/n) for n in files},external_refs=dict(
        auditor_handoff=dict(path='class-xgb-contribution-audit-next-dev/source-handoff.json',sha256=sha(AUD/'source-handoff.json')),
        base_C5=dict(path='br-standard-release-qualification-next-dev/controller-r5/run_controller.py',sha256=sha(BASE)),
        auditor_source=dict(path='class-xgb-contribution-audit-next-dev/audit_cache.py',sha256=sha(AUD/'audit_cache.py'))),
    prepared_changed_contracts=16,actual_imports_tests_arrays_PIDs_fits_API_clock=0,private_READY=None,actualclock=None,newresults=None,promotion=False,submit=False))
print(json.dumps(dict(handoff_sha256=sha(HERE/'source-handoff.json'),driver_sha256=sha(HERE/'run_audit.py'),
    closer_sha256=sha(HERE/'close_audit.py'),prepared_changed_contracts=16,NOT_READY=True)))
