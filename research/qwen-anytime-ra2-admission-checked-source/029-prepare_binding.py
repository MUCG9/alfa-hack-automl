"""Root-only metadata preparation after actual positive standard or separate RA1 saved-artifact qualification.

SOURCE ONLY until reviewed. Never starts the 10800 clock, a candidate, API or fit.
Only the qualified capture helper and the local stdlib metadata projections load.
"""
from pathlib import Path
import argparse, ast, csv, hashlib, importlib.util, json, re, sys, time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
QUALIFIER=WORK/'last-submission-repair-qualification-next-dev-r6'
C5=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
C5_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
ARCHIVE_SHA='eb85becbff8da0be93b97a8dafff108e426cdbed07476ed4f1dc0fb95e73c6fc'
KINDS=('regression','classification')
PRIVATE=WORK/'private'
SIDECAR=PRIVATE/'qh1-binding-metadata-preparers-r1.json'
DRAFT=PRIVATE/'qh1-manifest.draft-r1.json'
FRESH=PRIVATE/'qh1-binding-metadata-current-fresh-r1.json'


def need(value,code):
    if not value:raise RuntimeError(code)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    need(path.suffix=='.json' and path.stat().st_size<=32*2**20,'bounded_JSON_metadata_only')
    return json.loads(path.read_text('utf-8'))


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def absolute(value):
    path=Path(value)
    return str((path if path.is_absolute() else WORK/path).resolve())


def valid_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def exact_ref(value):
    need(type(value) is dict and set(value)=={'path','sha256'} and type(value['path']) is str
         and Path(value['path']).is_absolute() and valid_sha(value['sha256']),'absolute_typed_metadata_ref_required')
    need(str(Path(value['path']).resolve())==value['path'],'canonical_absolute_ref_required')
    return value


def checked_json(ref):
    exact_ref(ref);need(sha(ref['path'])==ref['sha256'],'metadata_ref_changed');return read(ref['path'])


def method_map(path):
    result={}
    for cls in ast.parse(Path(path).read_text('utf-8-sig')).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_contract_method')
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result


def raw_recipe(value):
    if isinstance(value,dict):
        need('fit_iterations' not in value,'deployment_iterations_must_never_enter_raw_recipe')
        for item in value.values():raw_recipe(item)
    elif isinstance(value,list):
        for item in value:raw_recipe(item)


def numeric_witness(path,features):
    """Read ONLY declared dictionary metadata; numeric is explicit, never not-cat."""
    path=Path(path);need(path.name=='data_dictionary.csv' and path.stat().st_size<=2**20,'bounded_declared_dictionary_required')
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);need({'feature','role','dtype'}<=set(reader.fieldnames or []),'explicit_dictionary_columns_required')
        rows=list(reader)
    need(len(rows)<=4096,'bounded_dictionary_rows_required')
    names=[row['feature'] for row in rows];need(len(names)==len(set(names)),'duplicate_dictionary_features')
    declared={row['feature']:row for row in rows}
    need(all(name in declared and declared[name]['role']=='feature' for name in features),'declared_predictor_role_required')
    numeric=[name for name in features if declared[name]['dtype']=='numeric']
    return numeric,dict(schema='explicit-dictionary-numeric-witness-v1',source=dict(path=str(path),sha256=sha(path)),
        rule='role exactly feature AND dtype exactly numeric; intersection in qualified spec.features order',
        numeric_features=numeric,unresolved_or_non_numeric=[name for name in features if name not in numeric])


def class_cut_protection(diagnostic,classes,phase,split_sha256):
    """Copy only protection authority from the exact qualified same-cut audit."""
    need(type(classes) is list and len(classes)>1 and len(classes)==len(set(classes))
         and all(type(c) is str for c in classes),'qualified_canonical_CLASS_order_required')
    support=diagnostic.get('independent_fitting_groups');rarest=diagnostic.get('rarest_fitting_class')
    need(diagnostic.get('phase')==phase and phase in ('primary','confirmation')
         and diagnostic.get('metric')=='macro_f1' and diagnostic.get('split_file_sha256')==split_sha256
         and diagnostic.get('feature_groups_disjoint') is True
         and type(support) is dict and set(support)==set(classes)
         and all(type(support[c]) is int and support[c]>=0 for c in classes)
         and rarest==min(classes,key=lambda c:support[c]),'exact_qualified_CLASS_cut_protection_required')
    return dict(independent_fitting_groups=dict(support),rarest_fitting_class=rarest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','plan-sha256','self-sha256','source-handoff-sha256'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--launch-parent-pid',type=int,required=True)
    parser.add_argument('--launch-parent-create-time',type=float,required=True)
    args=parser.parse_args();begin=time.monotonic()
    def check():need(time.monotonic()-begin<30,'metadata_preparation30_expired')
    # Same single reviewed metadata capture pattern as prepare-rq6-private.py.
    import psutil
    need(sha(C5)==C5_SHA,'qualified_metadata_capture_changed')
    capture=imported('_qh1_binding_C5_capture',C5)
    preparers,chain=capture.capture(psutil,args.launch_parent_pid,args.launch_parent_create_time)
    save(SIDECAR,dict(schema='qh1-root-metadata-preparer-v1',identities=preparers,
        launch_parent_observation=chain,actual_tool_evidence_pending=True))
    need(chain.get('verified') is True,'metadata_launch_chain_unconfirmed')
    need(sha(__file__)==args.self_sha256 and Path(args.plan).is_absolute()
         and sha(args.plan)==args.plan_sha256,'exact_preparation_source_and_plan_required')
    need(sha(PACKET/'source-handoff.json')==args.source_handoff_sha256,'exact_reviewed_preparation_handoff_required')
    source=read(PACKET/'source-handoff.json');pins={}
    def pin(path,expected,verify=True):
        path=absolute(str(path));need(valid_sha(expected),'typed_immutable_SHA_required')
        need(path not in pins or pins[path]==expected,'immutable_pin_collision')
        if verify:check();need(sha(path)==expected,'metadata_or_source_bytes_changed')
        pins[path]=expected
    pin(__file__,args.self_sha256);pin(args.plan,args.plan_sha256)
    for rel,h in source['files_sha256'].items():pin(PACKET/rel,h)
    for rel,h in source['external_refs_sha256'].items():pin(WORK/rel,h)
    pin(PACKET/'source-handoff.json',sha(PACKET/'source-handoff.json'))
    plan=read(args.plan)
    need(plan.get('schema')=='qwen-three-hour-binding-input-v1' and plan.get('readiness') in {'ACTUAL_RQ6_METADATA_BOUND','ACTUAL_RA1_METADATA_BOUND'}
         and plan.get('missing_bindings')==[],'future_actual_RQ6_metadata_required')
    need(plan.get('actual_clock') is None and plan.get('actual_metrics') is None,'preparation_must_not_create_experiment_clock_or_metric')
    for name in ('requested_model','reasoning_effort'):
        need(type(plan.get(name)) is str and 0<len(plan[name])<=128 and '\n' not in plan[name],'bounded_nonsecret_requested_provider_values_required')
    outer_ref=exact_ref(plan['reviewed_outer']);outer_hand=checked_json(outer_ref)
    outer=Path(outer_ref['path']).parent
    review_ref=exact_ref(plan['outer_source_review']);review=checked_json(review_ref)
    need(review.get('result')=='NO_SCOPED_SOURCE_BLOCKER'
         and review.get('reviewed_handoff',{}).get('sha256')==outer_ref['sha256'],
         'actual_final_outer_independent_source_peer_required')
    pin(outer_ref['path'],outer_ref['sha256']);pin(review_ref['path'],review_ref['sha256'])
    need(outer_hand['files_sha256'].get('binding.template.NOT_READY.json')==sha(outer/'binding.template.NOT_READY.json'),
         'final_outer_template_must_match_reviewed_handoff')
    cfg=read(outer/'binding.template.NOT_READY.json')
    need(cfg['schema']=='qwen-three-hour-outer-private-v1' and cfg['common_seconds']==10800
         and cfg['caps']==dict(setup=300,regression=[4800,4770],classification=[4800,4770],audit=[600,570],final=240,root=60),
         'unchanged_original_equal_three_hour_caps_required')
    for key,value in dict(output=str(WORK/'qh1'),python=str(WORK/'venv/Scripts/python.exe'),
        canonical_root=str(WORK/'alfa-hack-automl'),lock=str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock')).items():cfg[key]=value
    refs=plan['source_qualification']
    ra1=refs.get('mode')=='postfailure_saved_standard_artifacts_v1'
    need(plan.get('readiness')==('ACTUAL_RA1_METADATA_BOUND' if ra1 else 'ACTUAL_RQ6_METADATA_BOUND'),'typed_actual_qualification_mode_required')
    roles={'archive','root','confirmation','post_tool','driver_actual','wrapper_actual','post_tool_actual'}
    need(set(refs)==(roles|{'mode','original_rq6','qualification_manifest'} if ra1 else roles),'exact_qualification_roles_required')
    for name in ('archive','root','confirmation','post_tool'):
        ref=exact_ref(refs[name]);pin(ref['path'],ref['sha256'])
    need(refs['archive']['sha256']==ARCHIVE_SHA,'exact_RQ6_candidate_archive_required')
    root,fresh,post=(checked_json(refs[key]) for key in ('root','confirmation','post_tool'))
    qualified_manifest=checked_json(plan['qualified_manifest']);campaign=checked_json(plan['campaign'])
    need(Path(plan['campaign']['path'])==WORK/'rq6/campaign.json','fixed_original_RQ6_campaign_required')
    if ra1:
        need(refs['original_rq6'].get('manifest')==plan['qualified_manifest']
             and refs['original_rq6'].get('campaign')==plan['campaign']
             and campaign.get('status')=='failed' and campaign.get('manifest_sha256')==plan['qualified_manifest']['sha256'],
             'RA1_uses_original_failed_campaign_without_relabel')
        qualification_manifest=checked_json(refs['qualification_manifest'])
        need(root.get('schema')=='postfailure-standard-artifact-qualification-root-v1'
             and root.get('manifest_sha256')==refs['qualification_manifest']['sha256']
             and qualification_manifest.get('readiness')=='READY_REVIEWED_FROZEN'
             and Path(qualification_manifest.get('output','')).is_absolute()
             and Path(qualification_manifest['output']).resolve()==Path(qualification_manifest['output'])
             and Path(qualification_manifest['output'])!=WORK and Path(qualification_manifest['output']).is_relative_to(WORK)
             and Path(refs['root']['path'])==Path(qualification_manifest['output'])/'terminal-root-closure.json'
             and Path(refs['confirmation']['path'])==Path(qualification_manifest['output'])/'root-confirmation.json'
             and Path(refs['post_tool']['path'])==Path(qualification_manifest['output'])/'actual-wrapper-exit-confirmation.json',
             'actual_RA1_private_root_binding_required')
        pin(refs['qualification_manifest']['path'],refs['qualification_manifest']['sha256'])
        for path,h in qualification_manifest['immutable_files'].items():pin(path,h,verify=False)
        for ref in refs['original_rq6'].values():
            exact_ref(ref);pin(ref['path'],ref['sha256'])
        for row in campaign['supervisors']:
            pin(absolute(row['path']),row['sha256'])
        context_ref=exact_ref(root['repair_context']);pin(context_ref['path'],context_ref['sha256'])
    else:
        need(Path(refs['root']['path'])==WORK/'rq6/terminal-root-closure.json'
             and campaign.get('manifest_sha256')==root.get('manifest_sha256')==plan['qualified_manifest']['sha256']
             and campaign.get('status')=='completed_pending_root' and campaign.get('error_history')==[],
             'actual_campaign_manifest_and_positive_terminal_required')
    for ref in (plan['qualified_manifest'],plan['campaign']):pin(ref['path'],ref['sha256'])
    need(qualified_manifest.get('readiness')=='READY_REVIEWED_FROZEN'
         and qualified_manifest.get('output')==str(WORK/'rq6')
         and qualified_manifest['executor']['archive']==refs['archive'],'actual_qualified_private_archive_binding_required')
    # Reuse prior QUALIFIED pin values; do not open datasets/NPZ/models/predictions.
    for path,h in qualified_manifest['immutable_files'].items():
        need(Path(path).is_absolute(),'qualified_pin_must_already_be_absolute');pin(path,h,verify=False)
    # Actual root.independent_audit also carries its supervisor; preserve that
    # producer schema and project only the existing path/SHA for a typed ref.
    audit_ref=exact_ref({key:root['independent_audit'][key] for key in ('path','sha256')})
    audit=checked_json(audit_ref);pin(audit_ref['path'],audit_ref['sha256'])
    need(audit.get('schema')==('postfailure-standard-artifact-audit-v1' if ra1 else 'standard-repair-artifact-audit-v1') and audit.get('artifact_procedure_passed') is True
         and audit.get('archive_sha256')==ARCHIVE_SHA and audit.get('manifest_sha256')==plan['qualified_manifest']['sha256']
         and audit.get('audit_within_original_common_clock') is True,'actual_independent_archive_artifact_qualification_required')
    if ra1:
        need(audit.get('repair_context_sha256')==root['repair_context']['sha256']
             and audit.get('audit_within_repair_clock') is True
             and audit.get('original_RQ6_procedure_requalified') is False and audit.get('original_failure_preserved') is True,
             'actual_new_RA1_audit_preserves_old_FAIL')
    actual=audit['actual_artifact_sha256'];need(type(actual) is dict,'actual_artifact_map_required')
    cfg['source_qualification']=refs
    # Exact copied outer predecessor/strong-authority functions; no outer import.
    validators=imported('_qh1_binding_metadata_validators',PACKET/'metadata_validators.py')
    validators.WORK=WORK;validators.BASE=C5;validators.BASE_SHA=C5_SHA
    cfg['immutable_files']=pins;cfg['launch_preparer_receipts']=[]
    known=validators.predecessor(cfg,check)
    for receipt in plan.get('additional_preparer_receipts',[]):
        need(set(receipt)=={'path','sha256','actual_tool'} and set(receipt['actual_tool'])=={'exit_code','tool'}
             and receipt['actual_tool']['exit_code']==0 and type(receipt['actual_tool']['tool']) is str
             and receipt['actual_tool']['tool'] and 'PENDING' not in receipt['actual_tool']['tool'],'actual_later_metadata_preparer_exit_required')
        pin(receipt['path'],receipt['sha256']);known|=capture.ids(read(receipt['path'])['identities'])
        cfg['launch_preparer_receipts'].append(receipt)
    for pid,birth in known:
        check()
        try:observed=psutil.Process(pid).create_time()
        except psutil.NoSuchProcess:continue
        need(observed!=birth,'known_exact_prior_process_still_alive')
    rows=campaign['tasks'];need(type(rows) is list and [r['kind'] for r in rows]==list(KINDS),'actual_two_ordered_task_rows_required')
    task_rows={row['kind']:row for row in rows};need(len(task_rows)==2,'duplicate_actual_task_kind')
    task_sources={row['kind']:row for row in qualified_manifest['tasks']}
    signer=imported('_qh1_stdlib_recipe_signature',PACKET/'metadata_signature.py')
    authorities=[]
    for index,kind in enumerate(KINDS):
        check();row=task_rows[kind];report_path=row['report']
        need(Path(report_path).is_absolute() and actual.get(report_path) is not None,'actual_taskrow_report_authority_required')
        report_ref=dict(path=report_path,sha256=actual[report_path]);report=checked_json(report_ref);pin(report_path,report_ref['sha256'])
        spec=report['spec'];recipe=report['recipe'] if kind=='regression' else report['selected_recipe'];raw_recipe(recipe)
        need(spec.get('kind')==kind and spec.get('metric')==('rmse' if kind=='regression' else 'macro_f1')
             and spec.get('greater_is_better')==(kind=='classification'),'strict_shared_metric_direction_required')
        features=spec['features'];need(type(features) is list and features and len(features)==len(set(features))
            and all(type(v) is str and v for v in features),'exact_declared_predictors_required')
        forbidden=list(dict.fromkeys(spec.get('all_targets',[spec['target']])+[spec.get('id')]))
        need(not set(features)&set(forbidden),'protected_target_ID_not_predictors')
        old=task_sources[kind];dictionary=Path(old['source'])/'data_dictionary.csv';dictionary_sha=old['files']['data_dictionary.csv']
        need(pins.get(str(dictionary))==dictionary_sha and sha(dictionary)==dictionary_sha
             and actual.get(str(Path(row['directory'])/'data_dictionary.csv'))==dictionary_sha,'qualified_dictionary_metadata_required')
        numeric,witness=numeric_witness(dictionary,features)
        authority_path=PRIVATE/('qh1-strong-'+kind+'-r1.json')
        authority=dict(schema='qwen-three-hour-strong-recipe-authority-v1',kind=kind,metric=spec['metric'],recipe=recipe,
            recipe_signature=signer.signature(recipe),qualified_root_sha256=refs['root']['sha256'],source_report=report_ref,
            numeric_feature_witness=witness,scope='Actual qualified raw selected recipe; deployment iteration trees never transferred.')
        cuts=[]
        for seed,name,phase in zip((42,43),('primary-split.npz','confirmation-split.npz') if kind=='regression' else ('split.npz','confirmation_split.npz'),('primary','confirmation')):
            path=str(Path(report_path).parent/name);h=actual.get(path);need(valid_sha(h),'actual_qualified_split_metadata_required')
            pin(path,h,verify=False);cut=dict(seed=seed,path=path,sha256=h)
            if kind=='classification':cut.update(class_cut_protection(audit['tasks'][kind]['cuts'][phase],spec['classes'],phase,h))
            cuts.append(cut)
        task=dict(kind=kind,metric=spec['metric'],greater_is_better=spec['greater_is_better'],features=list(features),
            numeric_features=numeric,forbidden_columns=forbidden,strong_recipe=recipe,cuts=cuts,
            source_unchanged=True,authority_resolved=True,context_flag=False,selector_cache_flag=False)
        if kind=='classification':
            need(type(spec.get('classes')) is list and spec['classes'] and all(type(c) is str for c in spec['classes'])
                 and len(spec['classes'])==len(set(spec['classes'])),'qualified_lexical_class_order_required');task['classes']=spec['classes']
        save(authority_path,authority);pin(authority_path,sha(authority_path));authorities.append(str(authority_path))
        cfg['tasks'][index]=dict(task=task,spec=spec,strong_authority=dict(path=str(authority_path),sha256=pins[str(authority_path)]),
            trusted_DSL_compiler=dict(path=str(WORK/'alfa-hack-automl/tools/propose_feature_dsl.py'),sha256=source['DSL_compiler_sha256']))
        validators.strong_authority(cfg,cfg['tasks'][index],check)
    def typed_refs(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and valid_sha(value.get('sha256')):
                value['path']=absolute(value['path']);pin(value['path'],value['sha256'],verify=Path(value['path']).suffix!='.npz')
            for key,item in value.items():
                if key not in ('immutable_files','spec','task'):typed_refs(item)
        elif isinstance(value,list):
            for item in value:typed_refs(item)
    typed_refs(cfg)
    for key in ('auditor_entry',):cfg[key]=absolute(cfg[key])
    for handoff_ref in (outer_ref,cfg['core_handoff'],cfg['auditor_handoff']):
        folder=Path(handoff_ref['path']).parent;filename=Path(handoff_ref['path']).name
        hand=read(folder/filename);pin(folder/filename,sha(folder/filename))
        for rel,h in hand['files_sha256'].items():pin(folder/rel,h)
        for rel,h in hand.get('external_refs_sha256',{}).items():pin(WORK/rel,h,verify=Path(rel).suffix.lower() not in {'.npz','.csv','.npy','.bin','.pkl','.joblib'})
    for contract in cfg['contracts']:
        need(contract['expected']==len(contract['methods']) and method_map(contract['path'])==contract['methods'],'exact_contract_AST_map_required')
    need(sum(row['expected'] for row in cfg['contracts'])==cfg['prepared_contract_executions']
         and len(cfg['contracts'])==9 and sum(row['parent'] for row in cfg['contracts'])==270,
         'actual_final_contract_AST_census_and_setup270')
    pin(SIDECAR,sha(SIDECAR))
    cfg['launch_preparer_receipts'].append(dict(path=str(SIDECAR),sha256=pins[str(SIDECAR)],
        actual_tool=dict(exit_code=0,tool='PENDING_ACTUAL_METADATA_EXIT')))
    cfg.update(immutable_files=pins,requested_model=plan['requested_model'],reasoning_effort=plan['reasoning_effort'],
        readiness='NOT_READY',missing_bindings=['actual_metadata_preparer_exit','independent_private_binding_review','root_publication_and_actual_launch_admission'],
        actual_clock=None,actual_metrics=None,promotion=False,submit=False)
    need(len(pins)<=4096 and not (WORK/'qh1').exists(),'outer_pin_capacity_and_exclusive_new_experience_required')
    check();save(FRESH,dict(schema='qh1-binding-metadata-current-fresh-v1',known_count=len(known),
        known_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],known_exact_live=[],uncertain=[],
        metadata_preparer_identities=preparers,experiment_clock_created=False))
    save(DRAFT,cfg);check()
    print(json.dumps(dict(draft=str(DRAFT),sha256=sha(DRAFT),immutable_pins=len(pins),strong_authorities=authorities,
        known_absent=len(known),actual_preparer_tool_pending=True,readiness='NOT_READY',experiment_started=False)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(metadata_preparation_failed=True,type=type(exc).__name__)));raise SystemExit(1)
