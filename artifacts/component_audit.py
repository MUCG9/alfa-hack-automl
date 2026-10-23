"""Thin opt-in component audit using the two exact approved independent libraries.

Not a whole-agent, refit, process-supervision or official-score qualification.
No CLI; caller must supply primary-pinned authority and fresh terminal core seals.
"""
from pathlib import Path
import importlib.util, json
from portable_harness import need, sha, canonical, inventory, check_inventory, native_split, load

LIBRARIES={
 'evaluator.py':'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783',
 'audit_components.py':'a7528e969cd2f58ef4562c34ab344852acdfde535f223d9fedcf3877fa9cdcdb'}
def libraries(root, tick=lambda:None):
    need(__debug__,'nonoptimized_python_required');modules=[]
    for name,expected in LIBRARIES.items():
        path=Path(root)/name;need(sha(path,tick)==expected,'audit_library_pin')
        spec=importlib.util.spec_from_file_location('_independent_'+name.replace('.','_'),path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module);tick()
    return modules

def native_roles(spec, mapping):
    need(set(mapping)=={'train','test','sample_submission','data_dictionary'},'explicit_native_roles')
    for role,path in mapping.items():
        need(Path(path).is_absolute() and '\\' not in str(path),'native_not_windows_path')
        need(Path(spec['paths'][role]).resolve()==Path(path).resolve(),'native_role_binding')

def iterations(folder, recipe, expected=None):
    record=load(Path(folder)/'result.json');value=record['fit_iterations']
    if expected is not None:need(value==expected,'recursive_iterations_binding')
    if recipe['engine']=='ensemble':children=recipe['components']
    elif recipe.get('params',{}).get('feature_views'):
        # R4 checks exact expanded feature-view recipes separately.
        children=[None,None]
    else:children=[]
    if children:
        need(isinstance(value,list) and len(value)==len(children),'recursive_iterations_shape')
        for i,child in enumerate(children):
            path=Path(folder)/('component-'+str(i));saved=load(path/'result.json')
            if child is None:child=saved['recipe']
            need(saved['recipe']==child,'recursive_recipe_binding');iterations(path,child,value[i])
    else:need(type(value) is int and 1<=value<=3000,'leaf_iteration_bounds')

def closed_core(folder, expected_recipe, spec, split_path, expected_inventory, terminal, clock):
    """Every recursive byte bound BEFORE any label-bearing CSV is loaded."""
    check_inventory(folder,expected_inventory,clock.tick)
    need(terminal['status']=='completed' and terminal['exit_code']==0 and terminal['cleanup_confirmed'] is True,'terminal_component_required')
    need(terminal['original_deadline']==clock.wall_deadline and terminal['finished_unix']<clock.wall_deadline,'terminal_clock_binding')
    need(terminal['peak_worker_subtree_rss_mib']<=1536 and terminal['peak_whole_owned_rss_mib']<=2048,'terminal_resources')
    job=load(Path(folder)/'job.json')
    need(job['spec']==spec and job['recipe']==expected_recipe and job['threads']==2 and job['full_fit'] is False,'component_job_binding')
    need(Path(job['output_dir']).resolve()==Path(folder).resolve() and Path(job['split_path']).resolve()==Path(split_path).resolve(),'component_paths')
    iterations(folder,expected_recipe)

def audit(root, authority, authority_sha, libroot, clock):
    """authority_sha must come from the separately primary-pinned execution plan.

    Core SHA inventories and terminal-receipt hashes are sealed by the owned
    parent before this separate audit process starts. No learned code is loaded.
    """
    import numpy as np
    import pandas as pd
    need(__debug__,'nonoptimized_python_required');clock.tick()
    need(canonical(authority)==authority_sha,'external_authority_pin')
    root=Path(root).resolve();spec=authority['spec'];roles=authority['roles'];native_roles(spec,roles)
    source=authority['source_manifest']
    need(source['source_archive_sha256']=='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c'
         and len(source['flat_files_sha256'])==70,'approved_original_source')
    need(authority['source_inventories'][authority['algorithm_relative']]==source['flat_files_sha256'],'complete_original_source_inventory')
    need(set(authority['input_sha256'])==set(roles),'all_pristine_roles_required')
    def frozen():
        clock.tick()
        for name,expected in LIBRARIES.items():need(sha(Path(libroot)/name,clock.tick)==expected,'audit_library_changed')
        for role,path in roles.items():need(sha(path,clock.tick)==authority['input_sha256'][role],'pristine_input_changed')
        for prefix,seals in authority['source_inventories'].items():check_inventory(root/prefix,seals,clock.tick)
        for item in authority['components']:
            folder=root/item['output_relative'];need(folder.is_relative_to(root),'component_escape')
            check_inventory(folder,item['core_sha256'],clock.tick)
            need(sha(root/item['split_relative'],clock.tick)==item['native_cut']['native_profiles']['Linux']['raw_npz_sha256'],'native_split_seal')
            need(sha(root/item['terminal_relative'],clock.tick)==item['terminal_sha256'],'terminal_seal')
    frozen()
    for item in authority['components']:
        closed_core(root/item['output_relative'],item['recipe'],spec,root/item['split_relative'],item['core_sha256'],load(root/item['terminal_relative']),clock)
    r4,kern=libraries(libroot,clock.tick)
    # Only after ALL terminal cores, jobs, specs, sources, inputs and splits seal.
    train,test,sample=[pd.read_csv(roles[r]) for r in ('train','test','sample_submission')];clock.tick()
    verifier=r4.TaskVerifier(root,{'spec':spec,'experiments':[],'confirmations':[]},train,test,sample)
    found={};representations={}
    for item in authority['components']:
        clock.tick();path=root/item['split_relative'];kind=item['native_cut']['kind']
        groups=verifier.hashes if kind=='classification' else None
        times=train[spec['time_column']].to_numpy() if kind=='regression' else None
        native_split(path,item['native_cut'],len(train),groups,times)
        folder=root/item['output_relative'];record=dict(load(folder/'result.json'),output_dir=str(folder))
        r4.TaskVerifier.verify(verifier,record,path,item['key'],full=False,expected_recipe=item['recipe'])
        found[item['key']]=r4.diagnostics(verifier,record,path,item['key'])
        if item['arm'] in ('linear','rbf'):
            representations[item['key']]=kern.representation_receipt(r4,verifier,record,dict(item,_absolute_split=str(path),kind=kind))
        frozen()
    comparisons={}
    for arm,pair in authority['comparisons'].items():
        actual={phase:found[key] for phase,key in pair['candidate'].items()}
        control={phase:found[key] for phase,key in pair['control'].items()}
        comparisons[arm]=r4.matched_control_comparison(actual,control,spec['kind'])
    frozen();clock.tick()
    return dict(status='component_audit_only',diagnostics=found,comparisons=comparisons,
                representations=representations,source_unchanged=True,full_refit=False,promotion=False)
