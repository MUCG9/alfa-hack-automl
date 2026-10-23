"""METH03-LINEAR: one preregistered90/10 validation-only component blend, zero fits.

Future launch only, after actual METH02b terminal proof and fresh owned absence.
The unit is SAME METH02b protected SINGLE plus SAME fixed no-text linear_text, never V16 ensemble.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import signal
import sys
import time

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
ROOT = WORK/'meth03l'
COMMON, SETUP, EVALUATOR, CHILD, FINAL = 720, 90, 570, 540, 60
BASE = ('m4packet/manifest.json','8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a')
COOR = ('run_lean_mvp_r2.py','43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818')
R4 = ('repaired-mvp-r1-dev/evaluator_r4.py','c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783')
REG = ('method-blend-linear-preregistration.json', '9aab605b11d8d7abf1f060f7af33eea66616a6683e486d5e47aa994733906ebd')
M2_SOURCE = ('method-linear-recovery-dev/run_components.py','f3feba874b5a00ae74f74d7540e6efe3e55178ef5409c94b98dfd4670c180372')
M2_AUDIT = ('method-linear-recovery-dev/audit_components.py','1c663e8ce9600d0679e9d6fbf761edd0d09e2d35a4a78029ef12f61a5d30ffce')
M2_FIXTURE = ('method-linear-recovery-dev/test_tabular_linear_contracts.py','827fcc5bab907ddeb71248456425a4ba8c31f7ff306cceebee69aa802fb9af34')
M2_CLOSER = ('method-linear-recovery-dev/close_linear_components.py','f75274ec4ca5023eb8a654f63466b1c75390943eb5a784375d639a8e117a8520')
FAILED_CAMPAIGN = ('meth02/campaign.json','fbc2844806b1ebda4912aa038f5b407931eff8c8a38c7fcf5f8722e11930e2f3')
HISTORY = [('cp1/terminal-root-closure.json','96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d'),
    ('m4packet/terminal-root-closure.json','d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc'),
    ('method-update-publication-closure-r1.json','93bd05d3ff741eadf9bfc8858c875e8c130ec2aadc216c77e9480283b2692030'),
    ('meth01/terminal-root-closure.json','2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283'),
    ('meth03/terminal-root-closure.json','901f3c928d95d992800aef808ff70f84768a456bc23235e0ae63fd539fe159bf'),
    ('meth02/terminal-root-closure.json','220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361')]
CUTS = [('regression',0),('regression',1),('regression',2),('classification',42),('classification',43)]
WEIGHTS = dict(strong_control=.9,new_component=.1)
METHOD_ROOT = 'meth02b/terminal-root-closure.json'
METHOD_PROOF = (METHOD_ROOT,'fe00067cb099fdd4fdcd036861f5c3d55cd1c9ee0ee75bcddf488cfc035fe7f7')
FAILURE = RuntimeError


def need(value, code):
    if not value: raise FAILURE(code)


def local(name):
    p=(WORK/name).resolve();need(not Path(name).is_absolute() and p.is_relative_to(WORK),'reference_outside_work');return p


def sha(path, check=None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            if check is not None:check()
            block=f.read(2**20)
            if not block:break
            h.update(block)
    if check is not None:check()
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def core(directory,check):
    hashes={}
    for parent,dirs,files in os.walk(directory):
        need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]),'sealed_component_symlink')
        for name in files:
            need(not name.endswith(('.pending','.tmp')),'unfinished_component_core')
            path=Path(parent)/name;hashes[path.relative_to(WORK).as_posix()]=sha(path,check)
    return hashes


def bound_method_audit(campaign,proof,check):
    """Bind saved audit to root-certified ref and its manifest/plan, not to the
    terminal campaign SHA: that audit legitimately saw a verifying snapshot.
    """
    ref,expected=campaign.get('independent_audit'),proof.get('independent_audit')
    need(bool(ref)==bool(expected),'method_root_and_campaign_audit_presence_differs')
    if not ref:return None
    need(all(ref.get(k)==expected.get(k) for k in ['path','sha256'])
         and sha(local(ref['path']),check)==ref['sha256'],'root_certified_method_audit_ref_changed')
    need(sha(WORK/'meth02b/manifest.json',check)==campaign['manifest_sha256']
         and sha(WORK/'meth02b/verification-plan.json',check)==campaign['verification_plan_sha256'],
         'actual_method_manifest_or_plan_changed')
    audit,plan=load(local(ref['path'])),load(WORK/'meth02b/verification-plan.json')
    need(audit['manifest_sha256']==campaign['manifest_sha256']
         and audit['verification_plan_sha256']==campaign['verification_plan_sha256']
         and audit['manual_metric_source_sha256']==R4[1]
         and plan['execution_manifest_sha256']==campaign['manifest_sha256']
         and plan['verifier_source_sha256']==M2_AUDIT[1]
         and plan['original_common_start_unix']==campaign['start_unix']
         and plan['original_absolute_deadline_unix']==campaign['absolute_deadline_unix'],
         'root_audit_actual_manifest_plan_clock_correspondence_failed')
    return audit


def original_failure_history(campaign,method,proof,check):
    ref=campaign['original_failed_attempt']
    need(ref==method['original_failed_attempt']==proof['original_failed_attempt']
         and ref['original_status']=='FAILED_preserved' and proof['original_attempt_status']=='FAILED_preserved'
         and (ref['campaign_path'],ref['campaign_sha256'])==FAILED_CAMPAIGN
         and ref['actual_exec_session'] is None and ref['actual_exec_exit_code_observed_by_root']==1,
         'original_failed_METH02_context_must_remain_preserved')
    need(sha(local(FAILED_CAMPAIGN[0]),check)==FAILED_CAMPAIGN[1],'original_failed_METH02_bytes_changed')
    failed=load(local(FAILED_CAMPAIGN[0]))
    need(failed['status']=='technical_failure' and failed['workers']==[],'only_original_prepublic_failure_context_expected')
    return dict(reference=ref,original_status=failed['status'],first_failure=failed.get('first_failure'),
        error_history=failed.get('error_history',[]),original_actual_exec_session=None,original_actual_exit_code=1)


def evaluate(args):
    """One no-fit child; all original component cores checked before labels."""
    manifest_path=local(args.manifest);manifest=load(manifest_path)
    need(sha(__file__)==args.self_sha256 and sha(manifest_path)==args.manifest_sha256,'blend_explicit_source_manifest_pin_failed')
    need(manifest['schema']=='METH03-LINEAR-fixed-component-blend-v1' and manifest['common_seconds']==720
         and manifest['weights']==WEIGHTS and manifest['model_fits']==0,'fixed_registered_blend_contract_changed')
    def clock():
        need(time.time()<manifest['absolute_deadline_unix'] and time.monotonic()<manifest['common_deadline_monotonic'],'original_blend_clock_exhausted')
    def frozen():
        need(sha(__file__,clock)==args.self_sha256 and sha(manifest_path,clock)==args.manifest_sha256,'blend_audit_authority_changed')
        for name,digest in manifest['immutable_files'].items():need(sha(local(name),clock)==digest,'blend_source_parent_core_or_input_changed')
    frozen()
    registration=load(local(REG[0]))
    need(registration['id']=='METH-03-LINEAR' and registration['fixed_weight']==WEIGHTS
         and registration['common_cap_seconds']==720 and registration['model_fits']==0,'preregistered_weight_changed')
    mroot=WORK/'meth02b';method=load(mroot/'manifest.json');campaign=load(mroot/'campaign.json')
    proof=load(local(manifest['method_terminal_exec']['root_closure']))
    original_audit=bound_method_audit(campaign,proof,clock)
    failure_history=original_failure_history(campaign,method,proof,clock)
    need(failure_history==manifest['original_failed_METH02_history'],'original_failure_history_binding_changed')
    saved_rows={r['key']:r for r in original_audit.get('rows',[])} if original_audit else {}
    need(not original_audit or len(saved_rows)==len(original_audit.get('rows',[])),'duplicate_independent_method_row')
    jobs={j['key']:j for j in method['jobs']};entries={r['key']:r for r in campaign.get('workers',[])}
    schema=imported('_fixed_METH02b_schema',local(M2_AUDIT[0]))
    need([j['key'] for j in method['jobs']]==schema.ORDER and len(jobs)==10 and len(entries)==len(campaign.get('workers',[])),
         'exact_five_pair_component_plan_required')
    need(method['archive_sha256']=='16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0','unchanged_component_archive_required')
    eligible={}
    # These checks hash bytes only. No training/validation labels are parsed yet.
    for kind,meta in method['tasks'].items():
        original=next(t for t in load(local(BASE[0]))['tasks'] if t['kind']==kind)
        need(meta['files']==original['files'] and meta['control_recipe']==original['control_recipe']
             and meta['component_control']==load(local(meta['control_recipe']['path']))['components'][0],
             'same_pristine_inputs_and_exact_first_SINGLE_required')
        for name,digest in meta['files'].items():
            need(sha(mroot/meta['code']/name,clock)==sha(local(meta['source'])/name,clock)==digest,'pristine_original_and_component_copy_changed')
    for key,job in jobs.items():
        eligible[key]=False
        need(key==f"{job['kind']}{job['cut']}-{job['arm']}" and job['arm'] in {'control','candidate'},'component_key_kind_cut_arm_mismatch')
        expected_cut=schema.CUT_SHA[(job['kind'],job['cut'])]
        need(sha(local(job['split_path']),clock)==job['split_sha256']==expected_cut
             and sha(local(job['job_path']),clock)==job['job_sha256'],'exact_original_component_job_split_changed')
        recipe=copy.deepcopy(method['tasks'][job['kind']]['component_control'] if job['arm']=='control' else schema.FIXED)
        if job['arm']=='candidate' and job['kind']=='classification':recipe['params'].update(text_classifier='logistic',text_C=1,class_weight_power=.5)
        need(recipe==job['recipe'],'same_METH02b_protected_SINGLE_and_fixed_linear_required')
        entry=entries.get(key)
        if entry is None:continue
        need(sha(local(entry['supervisor_path']),clock)==entry['supervisor_sha256'],'original_component_supervisor_changed')
        terminal=load(local(entry['supervisor_path']))
        for field in ['status','exit_code','cleanup_confirmed','solver_budget_seconds','parent_cap_seconds','child_cap_seconds',
                      'owned_root','owned_process_identities','cleanup_observation','kind','first_failure','error_history']:
            need(terminal.get(field)==entry.get(field),'original_saved_supervisor_differs_from_entry:'+field)
        need(terminal['cleanup_confirmed'] is True and terminal['cleanup_observation']['unresolved']==[],'original_component_cleanup_unknown')
        need(sha(local(entry['seal']['path']),clock)==entry['seal']['sha256'],'original_component_seal_changed')
        seal=load(local(entry['seal']['path']))
        need(seal['key']==key and seal['cleanup_confirmed'] is True and seal['source_unchanged'] is True
             and seal['sealed_before_independent_label_scoring'] is True
             and core(local(job['output_dir']),clock)==seal['files_sha256'],'original_component_core_inventory_changed')
        prior=saved_rows.get(key,{})
        eligible[key]=(terminal['status']=='ok' and terminal.get('exit_code')==0 and prior.get('integrity_passed') is True
            and prior.get('measurement_status')=='independent_component_metric')
    # Frozen R4 imports only NumPy/Pandas, never a learner or a fullagent main.
    r4=imported('_frozen_R4_blend_metrics',local(R4[0]));verifiers={}
    for kind,meta in method['tasks'].items():
        directory=mroot/meta['code'];spec=load(local(meta['spec_path']))
        need(sha(local(meta['spec_path']),clock)==meta['spec_sha256'],'original_rebound_spec_changed')
        train,test,sample=[r4.pd.read_csv(directory/name) for name in ['train.csv','test.csv','sample_submission.csv']]
        verifiers[kind]=r4.TaskVerifier(directory,dict(spec=spec,experiments=[],confirmations=[]),train,test,sample)
    rows=[];created={};quality_errors=[]
    for kind,cut in CUTS:
        clock();key=f'{kind}{cut}';parents=[key+'-control',key+'-candidate']
        row=dict(kind=kind,cut=cut,status='missing_or_failed_parent_cache',control_metric=None,blend_metric=None,
            delta_blend_minus_control=None,control_diagnostics=None,blend_diagnostics=None,
            registered_gate_passed=False,failed_metric_zero_imputed=False,validation_only=True,
            input_parent_keys=parents,weights=WEIGHTS,artifacts_sha256={})
        if not all(eligible.get(p,False) for p in parents):
            row['missing_or_unqualified_parents']=[p for p in parents if not eligible.get(p,False)];rows.append(row);continue
        folder=ROOT/key
        try:
            a,b=[jobs[p] for p in parents]
            need(a['split_path']==b['split_path'] and a['split_sha256']==b['split_sha256'],'same_ordered_partition_required')
            partition=local(a['split_path']);verifier=verifiers[kind];checked=[];diagnostics=[]
            for parent_key,job in zip(parents,[a,b]):
                record=dict(load(local(job['output_dir'])/'result.json'),output_dir=str(local(job['output_dir'])))
                checked.append(verifier.verify(record,partition,parent_key,False,job['recipe']))
                diagnostics.append(r4.diagnostics(verifier,record,partition,parent_key))
                need(r4.close(checked[-1]['value'],saved_rows[parent_key]['metric']),'independent_METH02b_metric_reproduction_failed')
            need(diagnostics[0]['positions_sha256']==diagnostics[1]['positions_sha256'],'aligned_component_rows_required')
            tr,va=r4.split(partition,len(verifier.train));truth=verifier.train[verifier.spec['target']].iloc[va].to_numpy()
            blended=.9*checked[0]['validation']+.1*checked[1]['validation']
            need(r4.np.isfinite(blended).all(),'nonfinite_blend_values');folder.mkdir()
            if kind=='classification':
                classes=verifier.classes
                need(blended.shape==(len(va),len(classes)) and (blended>=0).all() and (blended<=1).all()
                     and r4.np.allclose(blended.sum(axis=1),1.,rtol=1e-10,atol=1e-10),'blended_probability_contract_failed')
                path=folder/'validation_probabilities.npz'
                r4.np.savez_compressed(path,classes=r4.np.asarray(classes),probabilities=blended,row_position=va)
                actual=r4.probability(path,va,classes);prediction=r4.np.asarray(classes)[actual.argmax(axis=1)]
                value,per_class=r4.f1(truth.astype(str),prediction,classes)
            else:
                prediction=blended;per_class=None
            csv=folder/'validation_predictions.csv'
            r4.pd.DataFrame(dict(row_position=va,y_true=truth,y_pred=prediction)).to_csv(csv,index=False,float_format='%.17g')
            roundtrip=r4.pd.read_csv(csv,float_precision='round_trip')
            need(r4.np.array_equal(roundtrip.row_position,va),'blend_CSV_row_roundtrip_failed')
            if kind=='classification':
                need(r4.np.array_equal(roundtrip.y_true.astype(str),truth.astype(str))
                     and r4.np.array_equal(roundtrip.y_pred.astype(str),prediction),'blend_class_CSV_roundtrip_failed')
            else:
                values=roundtrip.y_pred.to_numpy(dtype=float)
                need(r4.np.isfinite(values).all() and r4.np.array_equal(values,blended)
                     and r4.np.allclose(roundtrip.y_true.to_numpy(dtype=float),truth.astype(float),rtol=0,atol=1e-12),
                     'blend_regression_CSV_roundtrip_failed')
                value=float(r4.np.sqrt(r4.np.mean((truth.astype(float)-values)**2)))
            diagnostic=copy.deepcopy(diagnostics[0]);diagnostic.update(value=value,prediction_sha256=sha(csv,clock),
                phase=key+'-fixed_blend',mixture_children=2)
            if kind=='classification':
                rarest=diagnostic['rarest_fitting_class'];diagnostic.update(per_class_f1=per_class,
                    ex_rarest_macro_f1=float(r4.np.mean([v for c,v in per_class.items() if c!=rarest])))
            hashes=core(folder,clock);created.update(hashes)
            row.update(status='independently_recomputed_fixed_validation_blend',control_metric=diagnostics[0]['value'],
                blend_metric=value,delta_blend_minus_control=value-diagnostics[0]['value'],
                control_diagnostics=diagnostics[0],blend_diagnostics=diagnostic,artifacts_sha256=hashes)
        except Exception as exc:
            reason=str(exc);trace=exc.__traceback__
            while trace is not None and trace.tb_next is not None:trace=trace.tb_next
            row.update(status='blend_artifact_unqualified',exception_type=type(exc).__name__,
                contract_reason=reason if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',reason) else None,
                errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),
                failure_source_basename=Path(trace.tb_frame.f_code.co_filename).name if trace else None,
                failure_source_line=trace.tb_lineno if trace else None)
            quality_errors.append(key)
        finally:
            if folder.exists():
                hashes=core(folder,clock);created.update(hashes);row['artifacts_sha256']=hashes
        rows.append(row)
    reg=[r for r in rows if r['kind']=='regression']
    for row in reg:row['registered_gate_passed']=row['blend_metric'] is not None and row['blend_metric']<row['control_metric']
    classes=[r for r in rows if r['kind']=='classification'];class_gates=dict(cuts=[],each_cut_MacroF1_improves=False,
        each_cut_supported_class_and_ex_rarest_gates_passed=False)
    if all(r['blend_diagnostics'] is not None for r in classes):
        mapped={42:'primary',43:'confirmation'}
        actual={mapped[r['cut']]:r['blend_diagnostics'] for r in classes};reference={mapped[r['cut']]:r['control_diagnostics'] for r in classes}
        matched=r4.matched_control_comparison(actual,reference,'classification')
        class_gates.update(cuts=[dict(c,cut=42 if c['phase']=='primary' else 43,
            cut_alias='group_seed_42' if c['phase']=='primary' else 'group_seed_43') for c in matched['cuts']],
            each_cut_MacroF1_improves=matched['each_cut_primary_gate_passed'],
            each_cut_supported_class_and_ex_rarest_gates_passed=matched['class_each_cut_gate_passed'])
        for row,gate in zip(classes,class_gates['cuts']):row['registered_gate_passed']=gate['all_class_gates_passed']
    else:
        class_gates['cuts']=[dict(cut=r['cut'],primary_improves=False,all_class_gates_passed=False,
            reason='missing_or_unqualified_fixed_blend_cut') for r in classes]
    complete=all(r['blend_metric'] is not None for r in rows)
    passed=complete and all(r['registered_gate_passed'] for r in rows)
    quality={}
    for kind,required in [('regression',3),('classification',2)]:
        group=[r for r in rows if r['kind']==kind];all_present=all(r['blend_metric'] is not None for r in group)
        quality[kind]=dict(required_cuts=required,complete=all_present,
            control_mean=sum(r['control_metric'] for r in group)/required if all_present else None,
            fixed_90_10_blend_mean=sum(r['blend_metric'] for r in group)/required if all_present else None)
    frozen()
    for name,digest in created.items():need(sha(local(name),clock)==digest,'late_generated_validation_artifact_changed')
    result=dict(status='fixed_component_blend_artifacts_verified_pending_parent_terminal' if not quality_errors else 'fixed_component_blend_partial_unqualified_pending_parent_terminal',
        rows=rows,quality_metric=quality,all_five_cuts_complete=complete,component_quality_gates_passed=passed,
        candidate_gates=dict(regression_all_three_strict_RMSE_improvement=len(reg)==3 and all(r['registered_gate_passed'] for r in reg),
            regression_cuts=[dict(cut=r['cut'],strict_RMSE_improvement=r['registered_gate_passed']) for r in reg],classification=class_gates),
        artifact_integrity_checks_passed=not quality_errors,audit_within_original_common_clock=True,
        generated_validation_artifacts_sha256=created,manifest_sha256=args.manifest_sha256,
        parent_exec_terminal_qualification_required=True,actual_common_deadline_satisfied=None,
        parent_METH02b_actual_exec=manifest['method_terminal_exec'],original_failed_METH02_history=failure_history,
        original_failed_METH02_preserved=True,weights=WEIGHTS,blend_unit='same_METH02b_protected_SINGLE_component_plus_fixed_linear_text',
        validation_only=True,full_refit=False,test_submission_generated=False,model_fits=0,API_calls=0,tests_run=0,
        failed_metrics_zero_imputed=False,promotion=False,submit=False,official_score=None,
        scope='One preregistered validation-cache mixture on five reused public cuts; no weight search, whole V16 ensemble, new full refit or official claim')
    out=ROOT/'independent-audit.json'
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    clock();print(json.dumps({k:result[k] for k in ['status','all_five_cuts_complete','component_quality_gates_passed']}))


def launch(args):
    global FAILURE
    need(not ROOT.exists() and __debug__,'new_nonoptimized_blend_run_required_no_resume')
    need((args.method_root_closure,args.method_root_closure_sha256)==METHOD_PROOF and args.method_exec_session==38041
         and args.method_exit_code==0 and local(METHOD_ROOT).is_file(),
         'explicit_existing_actual_METH02b_root_pin_required_before_any_new_clock')
    start_unix,start_mono=time.time(),time.monotonic();unix,deadline=start_unix+COMMON,start_mono+COMMON;ROOT.mkdir()
    import psutil
    state=dict(status='starting',common_seconds=COMMON,start_unix=start_unix,start_monotonic=start_mono,
        absolute_deadline_unix=unix,common_deadline_monotonic=deadline,weights=WEIGHTS,model_fits=0,API_calls=0,
        owned_root=dict(pid=os.getpid(),create_time=psutil.Process().create_time()),coordinator_bootstrap_identities=[],
        owned_process_identities=[],supervisors=[],active_supervisor=None,error_history=[],
        cleanup_confirmed=False,source_unchanged=False,component_procedure_passed=False,component_quality_gates_passed=None,quality_metric=None,
        independent_audit=None,root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        validation_only=True,full_refit=False,promotion=False,submit=False,official_score=None)
    coor=owner=awake=None;pins={};known=set();finished=set();final_end=None
    def persist():
        data={k:v for k,v in state.items() if not k.startswith('_')}
        if coor is None:
            with (ROOT/'campaign.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
        else:coor.save(ROOT/'campaign.json',data)
    def error(exc,phase):
        reason=str(exc);row=dict(code=reason if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',reason)
            else 'blend_'+type(exc).__name__,phase=phase,exception_type=type(exc).__name__,unix=time.time(),monotonic=time.monotonic(),
            errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure',row);state['error_history'].append(row)
        state.update(status='technical_failure',component_procedure_passed=False,component_quality_gates_passed=None,quality_metric=None)
    def checkpoint(end=None,code='blend_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:coor.cooperative_checkpoint(awake,deadline,unix,end,code)
        else:
            need(time.time()<unix and time.monotonic()<deadline,'blend_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time()))<=5,'wall_monotonic_clock_disagreement')
            if end is not None:need(time.monotonic()<end,code)
            if awake is not None and awake.record.get('last_heartbeat'):
                last=awake.record['last_heartbeat'];need(max(time.time()-last['unix'],time.monotonic()-last['monotonic'])<=10,'terminal_host_heartbeat_gap_over10s')
        rss=psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                p=psutil.Process(saved['pid'])
                if p.create_time()==saved['create_time']:rss+=p.memory_info().rss
            except psutil.NoSuchProcess:pass
        need(rss<=2*2**30,'blend_parent_bootstrap_memory_limit')
    def merge(name,digest):
        local(name);need(re.fullmatch('[0-9a-f]{64}',digest) and (name not in pins or pins[name]==digest),'conflicting_or_invalid_source_pin');pins[name]=digest
    def frozen(end=None,code='blend_parent_cap_exhausted'):
        check=lambda:checkpoint(end,code)
        for name,digest in pins.items():need(sha(local(name),check)==digest,'blend_frozen_source_parent_core_input_changed')
        check()
    def absence():
        known.update(coor.identities(coor.predecessor(owner,finished,base.get('extra_predecessor_receipts',[]),base['terminal_predecessor_receipts'])))
        observer=owner.StrictOwnedObserver();observer.remember(known|finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],'blend_predecessor_or_own_auditor_live_or_denied')
        state['fresh_predecessor_identity_count']=len(observer.seen)
    try:
        setup_end=start_mono+SETUP;check=lambda:checkpoint(setup_end,'blend_setup_over90')
        for name,digest in [BASE,COOR,R4,REG,M2_SOURCE,M2_AUDIT,M2_FIXTURE,M2_CLOSER,FAILED_CAMPAIGN,
            (Path(__file__).resolve().relative_to(WORK).as_posix(),args.self_sha256)]:
            need(sha(local(name),check)==digest,'explicit_blend_source_pin_failed');merge(name,digest)
        coor=imported('_blend_proven_coordinator',local(COOR[0]));FAILURE=coor.TechnicalFailure;base=load(local(BASE[0]))
        for name,digest in base['immutable_files'].items():merge(name,digest)
        need((args.method_root_closure,args.method_root_closure_sha256)==METHOD_PROOF and args.method_exec_session==38041
             and args.method_exit_code==0,'actual_METH02b_terminal_arguments_required')
        refs=[(args.method_root_closure,args.method_root_closure_sha256),*HISTORY]
        refs += [tuple(v.rsplit('=',1)) for v in args.extra_terminal_receipt]
        for index,(name,digest) in enumerate(refs):
            need(sha(local(name),check)==digest,'terminal_root_proof_changed');proof=load(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True and not proof.get('active_owned_processes',[])
                 and not proof.get('uncertain_owned',[]) and proof.get('owned_identities') and proof.get('closure_preparer_identities'),'actual_terminal_cleanup_source_unknown')
            if index==0:
                method_proof=proof
                need(proof['actual_exec_session']==38041 and proof['actual_exec_exit_code_observed_by_root']==args.method_exit_code
                     and proof['original_common_seconds']==10800,'actual_METH02b_root_exec_binding_failed')
            known.update(coor.identities(proof['owned_identities']));known.update(coor.identities(proof['closure_preparer_identities']));merge(name,digest)
        method_root=WORK/'meth02b';campaign=load(method_root/'campaign.json')
        need(campaign.get('finished_unix') is not None and campaign.get('finished_monotonic') is not None
             and campaign['status'] not in {'starting','running','verifying'} and campaign['common_seconds']==10800
             and campaign['start_unix']==method_proof['original_start_unix']
             and campaign['absolute_deadline_unix']==method_proof['original_deadline_unix'],'closed_original_METH02b_clock_required')
        for name,digest in [('meth02b/campaign.json',sha(method_root/'campaign.json',check)),
            ('meth02b/manifest.json',campaign['manifest_sha256']),('meth02b/verification-plan.json',campaign['verification_plan_sha256'])]:merge(name,digest)
        method=load(method_root/'manifest.json')
        bound_method_audit(campaign,method_proof,check)
        state['original_failed_METH02_history']=original_failure_history(campaign,method,method_proof,check)
        for name,digest in [*method['immutable_files'].items(),*method['setup_deployment_sha256'].items()]:merge(name,digest)
        if campaign.get('independent_audit'):merge(campaign['independent_audit']['path'],campaign['independent_audit']['sha256'])
        for entry in campaign.get('workers',[]):
            merge(entry['supervisor_path'],entry['supervisor_sha256']);merge(entry['seal']['path'],entry['seal']['sha256'])
            for name,digest in load(local(entry['seal']['path']))['files_sha256'].items():merge(name,digest)
        frozen(setup_end,'blend_setup_over90')
        owner=imported('_blend_owner',local(coor.LIBS['owner']));processes=imported('_blend_processes',local(coor.LIBS['processes']))
        locker=imported('_blend_lock',local(coor.LIBS['lock']));awake=imported('_blend_awake',local(coor.AWAKE)).PowerRequestGuard('Alfa METH03-LINEAR pid'+str(os.getpid()),10)
        parent=psutil.Process().parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if not v.startswith('-')):break
            need(parent.create_time()==birth,'bootstrap_identity_changed');state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        state.update(_manifest=base,_pulse=lambda:checkpoint(),awake_guard=awake.record,
            original_METH02b_actual_exec=dict(session=38041,exit_code=args.method_exit_code,root_closure=args.method_root_closure,root_closure_sha256=args.method_root_closure_sha256))
        with awake:
            absence();frozen(setup_end,'blend_setup_over90')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root']);absence();frozen(setup_end,'blend_setup_over90')
                manifest=dict(schema='METH03-LINEAR-fixed-component-blend-v1',immutable_files=dict(pins),common_seconds=COMMON,
                    start_unix=start_unix,absolute_deadline_unix=unix,start_monotonic=start_mono,common_deadline_monotonic=deadline,
                    weights=WEIGHTS,model_fits=0,method_terminal_exec=state['original_METH02b_actual_exec'],
                    original_failed_METH02_history=state['original_failed_METH02_history'],
                    allocations_seconds=dict(setup=SETUP,evaluator_parent=EVALUATOR,evaluator_child=CHILD,final=FINAL),
                    threads=1,whole_tree_gib=2,validation_only=True,full_refit=False)
                path=ROOT/'manifest.json';coor.save(path,manifest,True);state['manifest_sha256']=sha(path,check);merge('meth03l/manifest.json',state['manifest_sha256'])
                checkpoint(setup_end,'blend_setup_over90');state['setup_seconds']=time.monotonic()-start_mono
                previous={s:signal.signal(s,lambda n,f:(_ for _ in ()).throw(SystemExit(128+n))) for s in [signal.SIGINT,signal.SIGTERM]}
                persist()
                try:
                    tick=time.monotonic();need(deadline-tick>=EVALUATOR+FINAL,'full_blend_audit_final_reserve_unavailable');absence();frozen()
                    state['status']='evaluating';persist()
                    command=[sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--evaluate-child',
                        '--self-sha256',args.self_sha256,'--manifest','meth03l/manifest.json','--manifest-sha256',state['manifest_sha256']]
                    sup=coor.supervise(command,WORK,ROOT/'evaluator-supervisor.json','fixed-no-fit-blend',tick,EVALUATOR,CHILD,
                        deadline,unix,EVALUATOR+FINAL,state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'],solver_seconds=None)
                    coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'blend_evaluator_process_failed')
                    audit=load(ROOT/'independent-audit.json');state['independent_audit']=dict(path='meth03l/independent-audit.json',sha256=sha(ROOT/'independent-audit.json'),raw_result=audit)
                    merge('meth03l/independent-audit.json',state['independent_audit']['sha256'])
                    need(audit.get('artifact_integrity_checks_passed') is True and audit.get('audit_within_original_common_clock') is True
                         and audit.get('model_fits')==0,'blend_saved_artifact_audit_unqualified')
                    for name,digest in audit['generated_validation_artifacts_sha256'].items():merge(name,digest)
                    state.update(status='completed_fixed_blend_pending_root_exec_and_closure',quality_metric=audit['quality_metric'],
                        component_procedure_passed=audit['all_five_cuts_complete'],component_quality_gates_passed=audit['component_quality_gates_passed'],
                        all_five_cuts_complete=audit['all_five_cuts_complete'])
                except BaseException as exc:error(exc,'blend_evaluation')
                finally:
                    final_end=min(deadline-10,time.monotonic()+FINAL)
                    try:
                        frozen(final_end,'blend_final_over60');absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']),'blend_prior_cleanup_unknown');state.update(cleanup_confirmed=True,source_unchanged=True)
                    except BaseException as exc:error(exc,'blend_terminal');state.update(cleanup_confirmed=False,source_unchanged=False)
                    for sig,handler in previous.items():signal.signal(sig,handler)
        need(awake.record.get('release_API_verified') is True,'power_release_unverified');frozen(final_end,'blend_power_terminal_over_cap')
    except BaseException as exc:error(exc,'blend_setup_or_power_terminal')
    finally:
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=p,create_time=c) for p,c in sorted(finished)])
        try:checkpoint(final_end,'blend_terminal_export_over_cap')
        except BaseException as exc:error(exc,'blend_export')
        persist()
        try:checkpoint(final_end,'blend_terminal_receipt_over_cap')
        except BaseException as exc:error(exc,'blend_receipt');persist()
    print(json.dumps({k:state[k] for k in ['status','component_quality_gates_passed','cleanup_confirmed','source_unchanged','elapsed_common_seconds']}))
    raise SystemExit(0 if state['status']=='completed_fixed_blend_pending_root_exec_and_closure'
        and state['component_procedure_passed'] and state['cleanup_confirmed'] and state['source_unchanged'] and not state['error_history'] else 1)


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--launch',action='store_true');mode.add_argument('--evaluate-child',action='store_true')
    p.add_argument('--self-sha256',required=True);p.add_argument('--manifest');p.add_argument('--manifest-sha256')
    p.add_argument('--method-root-closure');p.add_argument('--method-root-closure-sha256')
    p.add_argument('--method-exec-session',type=int);p.add_argument('--method-exit-code',type=int)
    p.add_argument('--extra-terminal-receipt',action='append',default=[],metavar='WORK_REL_PATH=SHA256')
    args=p.parse_args();need(__debug__,'nonoptimized_python_required')
    if args.evaluate_child:
        need(args.manifest=='meth03l/manifest.json' and bool(args.manifest_sha256),'explicit_blend_manifest_required');evaluate(args)
    else:launch(args)


if __name__=='__main__':main()
