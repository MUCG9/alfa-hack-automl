"""Exact SOURCE-projected outer metadata validators; no candidate/outer module import."""
from pathlib import Path
import hashlib,importlib.util,json,sys
WORK=BASE=BASE_SHA=None

def need(value, code):
    if not value:
        raise RuntimeError(code)

def read(path):
    return json.loads(Path(path).read_text('utf-8'))

def sha(path, check=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check()
            block = stream.read(2 ** 20)
            if not block:
                break
            h.update(block)
    check()
    return h.hexdigest()

def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def qualified():
    need(sha(BASE) == BASE_SHA, 'qualified_C5_helper_changed')
    return imported('_q3h_qualified_C5', BASE)

def strong_authority(cfg, row, check=lambda: None):
    """Bind raw strong recipe to this qualified report, never deployment trees."""
    pins = cfg['immutable_files']
    ref = row['strong_authority']
    qualification = cfg['source_qualification']
    need(pins.get(ref['path']) == ref['sha256'] and sha(ref['path'], check) == ref['sha256'], 'strong_authority_changed')
    authority = read(ref['path'])
    root_ref = qualification['root']
    need(authority.get('schema') == 'qwen-three-hour-strong-recipe-authority-v1' and authority.get('qualified_root_sha256') == root_ref['sha256'] and (authority.get('kind') == row['task']['kind']) and (authority.get('metric') == row['task']['metric']), 'current_qualified_raw_recipe_authority_required')
    need(pins.get(root_ref['path']) == root_ref['sha256'] and sha(root_ref['path'], check) == root_ref['sha256'], 'source_qualification_root_changed')
    root = read(root_ref['path'])
    audit_ref = root['independent_audit']
    need(root.get('technical_procedure_passed') is True and pins.get(audit_ref['path']) == audit_ref['sha256'] and (sha(audit_ref['path'], check) == audit_ref['sha256']), 'actual_qualified_independent_artifact_map_required')
    audited = read(audit_ref['path'])
    report_ref = authority['source_report']
    actual = audited['actual_artifact_sha256']
    need(audited.get('artifact_procedure_passed') is True and audited.get('archive_sha256') == qualification['archive']['sha256'] and (actual.get(report_ref['path']) == pins.get(report_ref['path']) == report_ref['sha256']) and (sha(report_ref['path'], check) == report_ref['sha256']), 'strong_report_not_qualified_and_source_bound')
    report = read(report_ref['path'])
    recipe = report['selected_recipe'] if row['task']['kind'] == 'classification' else report['recipe']
    need(row['spec'] == report['spec'] and authority.get('recipe') == row['task']['strong_recipe'] == recipe, 'actual_selected_raw_recipe_and_strict_spec_required')

    def raw(value):
        if isinstance(value, dict):
            need('fit_iterations' not in value, 'historical_or_fullfit_tree_override_forbidden')
            for item in value.values():
                raw(item)
        elif isinstance(value, list):
            for item in value:
                raw(item)
    raw(recipe)
    need(all((actual.get(cut['path']) == pins.get(cut['path']) == cut['sha256'] for cut in row['task']['cuts'])), 'new_control_cuts_must_bind_actual_qualified_row_partitions')

def predecessor(cfg, check):
    c = qualified()
    pins = cfg['immutable_files']
    refs = cfg['source_qualification']
    for name in ('archive', 'root', 'confirmation', 'post_tool'):
        ref = refs[name]
        need(pins.get(ref['path']) == ref['sha256'] and sha(ref['path'], check) == ref['sha256'], 'actual_archive_qualification_ref_changed')
    root, fresh, post = (read(refs[k]['path']) for k in ('root', 'confirmation', 'post_tool'))
    actual = refs['driver_actual']
    wrapper = refs['wrapper_actual']
    post_actual = refs['post_tool_actual']
    need(set(actual) == {'session', 'exit_code', 'tool'} and actual['exit_code'] == 0 and actual['tool'] and (actual['session'] is None or (type(actual['session']) is int and actual['session'] > 0)) and (set(wrapper) == set(post_actual) == {'exit_code', 'tool'}) and (wrapper['exit_code'] == post_actual['exit_code'] == 0) and wrapper['tool'] and post_actual['tool'], 'actual_whole_archive_driver_and_wrapper_exits_required')
    need(root.get('schema') == 'standard-repair-qualification-root-closure-v1' and root.get('technical_procedure_passed') is True and all((root.get(k) is True for k in ('source_unchanged', 'cleanup_confirmed', 'temporary_cleanup_confirmed'))) and (root.get('actual_exec_session') == actual['session']) and (root.get('actual_exec_exit_code_observed_by_root') == 0) and (root.get('actual_tool_evidence') == actual['tool']) and (root.get('archive_sha256') == refs['archive']['sha256']) and (root.get('active_owned_processes') == root.get('uncertain_owned') == root.get('changed_source_or_core') == []), 'actual_both_task_archive_qualification_required')
    need(fresh.get('schema') == 'standard-repair-atomic-root-confirmation-v1' and fresh.get('root_sha256') == refs['root']['sha256'] and (fresh.get('actual_driver') == actual) and (fresh.get('actual_closer_exit') == 0) and all((fresh.get(k) is True for k in ('technical_procedure_passed', 'source_unchanged', 'current_temporary_absent', 'current_cleanup_confirmed', 'inside_actual_closer_birth60', 'inside_original6000', 'inside_existing_driver_final240'))) and (fresh.get('known_exact_live') == fresh.get('uncertain') == fresh.get('errors') == []), 'actual_archive_atomic_root_fresh_required')
    known = c.ids(fresh['known_identities']) | c.ids(fresh['wrapper_preparer_identities'])
    need(len(c.ids(fresh['known_identities'])) == fresh['known_count'] == len(fresh['known_identities']) and c.ids(root['owned_identities'] + root['closure_preparer_identities']) <= known, 'complete_archive_owned_and_preparer_scope')
    need(post.get('schema') == 'standard-repair-actual-wrapper-exit-confirmation-v1' and post.get('root_sha256') == refs['root']['sha256'] and (post.get('root_confirmation_sha256') == refs['confirmation']['sha256']) and (post.get('actual_driver') == actual) and (post.get('actual_wrapper') == wrapper) and (post.get('known_count') == len(known)) and (post.get('known_exact_live') == post.get('uncertain') == []) and (post.get('source_unchanged') is True) and (post.get('post_tool_confirmed') is True), 'actual_wrapper_tool_exit_and_full_known_fresh')
    known |= c.ids(post['post_tool_preparer_identities'])
    for ref in cfg.get('launch_preparer_receipts', []):
        need(set(ref) == {'path', 'sha256', 'actual_tool'} and ref['actual_tool']['exit_code'] == 0 and ref['actual_tool']['tool'] and (pins.get(ref['path']) == ref['sha256']) and (sha(ref['path'], check) == ref['sha256']), 'actual_later_preparer_binding')
        known |= c.ids(read(ref['path'])['identities'])
    return known
