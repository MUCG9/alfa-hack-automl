"""SOURCE-only RA1 literal/schema/inherited-bound projection of qualified closers."""
from pathlib import Path
import ast,hashlib,json
P=Path(__file__).resolve().parent;W=P.parent
CX=W/'class-xgb-cx2-next-dev';QH=W/'qwen-three-hour-outer-next-dev-r5'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf-8'))
def put(path,text):compile(text,str(path),'exec');path.write_text(text,encoding='utf-8',newline='\n')
assert sha(QH/'source-handoff.json')=='f19d42fbc9c641a7a055b085dafce66f9f089ca5d895f935f9128397bace8b69'
assert sha(CX/'close_audit.py')=='eb25324be971073a953a6691269a54963e091575fb179c66ea923c073e6dbbcb'
s=(CX/'close_audit.py').read_text('utf-8').replace("OUT=WORK/'cx2'","OUT=WORK/'ra1'")
s=s.replace("schema='class-xgb-cache-root-closure-v1'","schema='postfailure-standard-artifact-qualification-root-v1'")
s=s.replace("    need(own_mono+60<=end and own_unix+60<=wall,'whole_root60_original_reserve_required')", """    inherited=state['inherited_original_clock']
    need(inherited['absolute_deadline_unix']==inherited['start_unix']+6000
        and inherited['common_deadline_monotonic']==inherited['start_monotonic']+6000,'inherited_RQ6_original6000_not_reset')
    end=min(end,inherited['common_deadline_monotonic'],state['final_deadline_monotonic'])
    wall=min(wall,inherited['absolute_deadline_unix'],state['start_unix']+state['final_deadline_monotonic']-state['start_monotonic'])
    need(own_mono+60<=end and own_unix+60<=wall,'whole_root60_inside_both_commons_and_saved_final_required')""")
start=s.index("        check(True);docs=");end=s.index('        for item in state.get(',start)
s=s[:start]+"""        check(True);known=c.predecessor(cfg,check)
        known|=base.ids(state.get('owned_process_identities',[]))
        known|=base.ids([state['owned_root']]+state.get('coordinator_bootstrap_identities',[]))
        for role in ('regression_seal','classification_seal'):
            ref=cfg['rq6'][role];need(c.sha(ref['path'],check)==ref['sha256'],'original_saved_core_seal_changed')
            for path,h in c.read(ref['path'])['files_sha256'].items():
                need(path not in expected or expected[path]==h,'source_and_core_pin_collision');expected[path]=h
"""+s[end:]
s=s.replace("CLASS-XGB-CONTRIBUTION-01-root","RA1-saved-standard-artifact-root").replace("temp.name.startswith('cx-')","temp.name.startswith('ra-')")
s=s.replace("state.get('comparison_procedure_passed')","state.get('artifact_procedure_passed')")
s=s.replace("c.result_qualified(audit,state.get('audit_binding',{}).get('sha256'),cfg['audit_payload']['expected_inventory']['sha256'])", "c.result_qualified(audit,cfg['rq6']['manifest']['sha256'],state.get('audit_binding',{}).get('sha256'))")
s=s.replace("qualified_comparison=audit.get('comparison') if passed else None,\n        quality_gate_passed=audit.get('quality_gate_passed') if passed else None", "qualified_artifacts=audit.get('tasks') if passed else None,quality_metric=audit.get('quality_metric') if passed else None")
s=s.replace('qualified_comparison=None,quality_gate_passed=None','qualified_artifacts=None,quality_metric=None')
s=s.replace("quality_gate_passed=result['quality_gate_passed']","quality_metric=result['quality_metric']")
s=s.replace("original_deadline_unix=wall,original_end_monotonic=end", "original_deadline_unix=state['absolute_deadline_unix'],original_end_monotonic=state['common_deadline_monotonic'],inherited_original_clock=inherited,effective_deadline_unix=wall,effective_deadline_monotonic=end")
s=s.replace("archive_build_or_release_qualification=False,", "original_rq6=cfg['rq6'],original_failed_driver=dict(session=49569,exit_code=1,tool='dbc6a1'),\n        original_failed_frozen_closer=dict(exit_code=1,tool='fb3841'),original_RQ6_FAIL_preserved=True,original_RQ6_procedure_requalified=False,\n        archive_sha256=c.ARCHIVE_SHA,repair_context=state.get('audit_binding'),original_two_models_not_repeated=True,\n        inside_inherited_RQ6_common6000=not bad and time.monotonic()<inherited['common_deadline_monotonic'] and time.time()<inherited['absolute_deadline_unix'],")
put(P/'close_audit.py',s)

s=(QH/'run_root.py').read_text('utf-8')
s=s.replace("OUT=WORK/'qh1'","OUT=WORK/'ra1'").replace('10800','600')
s=s.replace('qwen-three-hour','postfailure-standard-artifact').replace("root.get('schema')=='postfailure-standard-artifact-root-closure-v1'","root.get('schema')=='postfailure-standard-artifact-qualification-root-v1'")
s=s.replace("cfg.get('schema')=='postfailure-standard-artifact-atomic-root-private-v1'","cfg.get('schema')=='postfailure-standard-artifact-atomic-root-private-v1'")
anchor="    final=state['final_deadline_monotonic'];final_wall=start+(final-begin)"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+"""
    old=state['inherited_original_clock']
    need(old['absolute_deadline_unix']==old['start_unix']+6000
        and old['common_deadline_monotonic']==old['start_monotonic']+6000,'inherited_original_RQ6_assignment_required')""")
s=s.replace("limits[0]=min(limits[0],wall,final_wall)","limits[0]=min(limits[0],wall,final_wall,old['absolute_deadline_unix']);limits[1]=min(limits[1],old['common_deadline_monotonic'])")
s=s.replace("and entry_mono+60<=state['final_deadline_monotonic']", "and entry_mono+60<=state['final_deadline_monotonic'] and entry_mono+60<=end and entry_wall+60<=wall")
s=s.replace("inside_original600=True,inside_existing_driver_final240=True", "inside_original600=True,inside_inherited_RQ6_common6000=True,inside_existing_driver_final240=True")
put(P/'run_root.py',s)
ps=(QH/'close_child.ps1').read_text('utf-8').replace('qwen-three-hour','postfailure-standard-artifact')
(P/'close_child.ps1').write_text(ps,encoding='utf-8',newline='\n')

s=(QH/'confirm_post_tool.py').read_text('utf-8')
s=s.replace("OUT=WORK/'qh1'","OUT=WORK/'ra1'").replace('10800','600').replace('qwen-three-hour','postfailure-standard-artifact')
s=s.replace("root.get('schema')=='postfailure-standard-artifact-root-closure-v1'","root.get('schema')=='postfailure-standard-artifact-qualification-root-v1'")
s=s.replace("PACKET/'run_campaign.py'","PACKET/'run_audit.py'")
anchor="    start,initial,wall,end,final=values"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+"""
    old=state['inherited_original_clock']
    need(old['absolute_deadline_unix']==old['start_unix']+6000
        and old['common_deadline_monotonic']==old['start_monotonic']+6000,'inherited_original_RQ6_assignment_required')
    need(now_monotonic<old['common_deadline_monotonic'] and now_unix<old['absolute_deadline_unix'],'inherited_original_RQ6_common_expired')""")
s=s.replace("'inside_actual_closer_birth60','inside_original600','inside_existing_driver_final240'", "'inside_actual_closer_birth60','inside_original600','inside_existing_driver_final240','inside_inherited_RQ6_common6000'")
s=s.replace("'inside_saved_driver_final240','inside_actual_closer_birth60')", "'inside_saved_driver_final240','inside_actual_closer_birth60','inside_inherited_RQ6_common6000')")
s=s.replace("post_tool_confirmed=True,inside_original600=True,inside_saved_driver_final240=True", "post_tool_confirmed=True,inside_original600=True,inside_inherited_RQ6_common6000=True,inside_saved_driver_final240=True")
put(P/'confirm_post_tool.py',s)

tests=(QH/'test_atomic_root.py').read_text('utf-8')
tests=tests.replace('11800.','1600.').replace('10820.','620.').replace('11801.','1601.').replace("post.PACKET/'run_campaign.py'","post.PACKET/'run_audit.py'")
tests=tests.replace('final_deadline_monotonic=300.)',"final_deadline_monotonic=300.,inherited_original_clock=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=7000.,common_deadline_monotonic=6020.))")
anchor='        self.assertEqual(state,before)\n\n    def test_full_known_union'
assert tests.count(anchor)==1
extra='''        old_limited=dict(start_unix=10000.,start_monotonic=9020.,absolute_deadline_unix=10600.,common_deadline_monotonic=9620.,final_deadline_monotonic=9300.,
            inherited_original_clock=dict(start_unix=4100.,start_monotonic=3120.,absolute_deadline_unix=10100.,common_deadline_monotonic=9120.))
        with self.assertRaisesRegex(RuntimeError,'inherited_original_RQ6_common_expired'):post.window(old_limited,10100.,9120.)
'''
tests=tests.replace(anchor,'        self.assertEqual(state,before)\n'+extra+'\n    def test_full_known_union')
put(P/'test_atomic_root.py',tests)
print(json.dumps(dict(closure_sources_written=True,runtime_executed=False)))
