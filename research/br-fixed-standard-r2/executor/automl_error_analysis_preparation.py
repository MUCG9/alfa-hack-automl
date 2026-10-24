"""Explicit cache relocation and portable baseline audit; no cache reconstruction."""
from dataclasses import replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import zipfile
import numpy as np
from automl_contracts_error_analysis import AnalysisArtifactRef, AnalysisBudget, DiagnosticBlend, ErrorAnalysisProtocol, ErrorAnalysisRequest, ModelPredictionRef
from automl_contracts_messages import DatasetRef, PredictionBundle, TaskSpec, canonical_hash
from automl_error_analysis_artifacts import Guard, npz, sha_rows, table
from automl_error_analysis_reporting import write_json

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def artifact(path):
    path = Path(path).resolve(strict=True)
    return AnalysisArtifactRef(str(path), sha(path))

def relocate_path(path, mapping):
    path = Path(path)
    for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if path.is_relative_to(Path(old)):
            return (Path(new) / path.relative_to(Path(old))).resolve()
    raise ValueError('No explicit root mapping for frozen artifact path')

def prepare_report_request(report_path, run_dir, dataset_path, source_manifest_path, workspace, scope='search', root_mapping=None):
    """Resolve only an explicitly supplied run directory, never old absolute paths."""
    if scope not in ('search', 'confirmation'):
        raise ValueError('Report preparation supports search or confirmation')
    report_path, run_dir = (Path(report_path).resolve(strict=True), Path(run_dir).resolve(strict=True))
    dataset_path = Path(dataset_path).resolve(strict=True)
    report = json.loads(report_path.read_text())
    if report.get('integrity_ok') is not True or report.get('final_fit_status') != 'ok':
        raise ValueError('Only completed integrity-passing reports are supported')
    spec = report['spec']
    task = TaskSpec.from_legacy(spec)
    frame = table(dataset_path.read_bytes(), target=task.target)
    if len(frame) != spec['n_train'] or set(task.features) - set(frame):
        raise ValueError('Relocated dataset schema/rows differ from frozen report')
    sources = artifact(source_manifest_path)
    manifest = json.loads(Path(sources.path).read_text())
    if not isinstance(manifest, dict) or not manifest or any((not isinstance(v, str) or len(v) != 64 or any((c not in '0123456789abcdef' for c in v)) for v in manifest.values())):
        raise ValueError('Expected source manifest with SHA256 values')
    provenance_path = run_dir / 'provenance.json'
    provenance = json.loads(provenance_path.read_text())['sha256']
    if provenance.get('input:train') != sha(dataset_path):
        raise ValueError('Relocated fitting dataset differs from original run provenance')
    frozen_sources = {Path(k[len('source:'):]).name: v for k, v in provenance.items() if k.startswith('source:')}
    if not frozen_sources or any((manifest.get(name) != digest for name, digest in frozen_sources.items())):
        raise ValueError('Run source provenance differs from frozen source manifest')
    workspace = Path(workspace).resolve()
    if workspace.exists():
        raise FileExistsError('Request workspace already exists')
    split_path = run_dir / ('split.npz' if scope == 'search' else 'confirmation_split.npz')
    split_ref = artifact(split_path)
    guard = Guard(AnalysisBudget(600, 1536, 1))
    with npz(guard.read(split_ref.path, split_ref.sha256), guard) as split:
        training = np.asarray(split['train'], dtype='<i8')
        rows = np.asarray(split['validation'], dtype='<i8')
    signature = hashlib.sha256(training.tobytes() + rows.tobytes()).hexdigest()
    records = list(report['experiments'] if scope == 'search' else report['confirmations'])
    ensemble = (report.get('ensemble') or {}).get('primary' if scope == 'search' else 'confirmation')
    if ensemble:
        records.append(ensemble)
    if not records:
        raise ValueError('No completed model records in requested scope')
    mapping = root_mapping or {str(Path(records[0]['output_dir']).parent): str(run_dir)}
    predictions = []
    recipe_models = {}
    seen = {}
    blends = []

    def adjusted(recipe):
        return bool(recipe.get('params', {}).get('calibrate')) or any((adjusted(child) for child in recipe.get('components', [])))

    def add(record, directory):
        directory = directory.resolve()
        if not directory.is_relative_to(run_dir):
            raise ValueError('Relocated artifact escapes the supplied run directory')
        directory = directory.resolve(strict=True)
        local = json.loads((directory / 'result.json').read_text())
        if local.get('recipe') != record['recipe'] or local.get('metrics') != record['metrics']:
            raise ValueError('Local result differs from the frozen portable report')
        recipe_hash = canonical_hash(record['recipe'])
        model = 'model-' + recipe_hash[:20]
        probabilities_path = directory / 'validation_probabilities.npz'
        probability_ref = artifact(probabilities_path) if task.kind == 'classification' and probabilities_path.is_file() else None
        classes = tuple(spec.get('classes') or [])
        if probability_ref:
            with npz(guard.read(probability_ref.path, probability_ref.sha256), guard) as stored:
                classes = tuple(stored['classes'].astype(str))
        prediction_path = directory / 'validation_predictions.csv'
        value = ModelPredictionRef(model, scope, recipe_hash, canonical_hash(manifest), PredictionBundle(str(prediction_path), len(rows), ('row_position', 'y_true', 'y_pred'), classes, signature), sha(prediction_path), sha_rows(rows), split_ref, probabilities=probability_ref, probability_kind='decision_adjusted' if probability_ref and adjusted(record['recipe']) else 'raw' if probability_ref else 'none', recorded_result=artifact(directory / 'result.json'))
        if model in seen:
            previous = seen[model]
            if previous.predictions_sha256 != value.predictions_sha256 or (previous.probabilities and value.probabilities and (previous.probabilities.sha256 != value.probabilities.sha256)):
                raise ValueError('Identical recipes have conflicting cached predictions')
        else:
            seen[model] = value
            predictions.append(value)
        recipe_models[recipe_hash] = model
        if record['recipe'].get('params', {}).get('feature_views'):
            children = []
            for i in range(2):
                child_dir = directory / ('component-' + str(i))
                child = json.loads((child_dir / 'result.json').read_text())
                children.append(add(child, child_dir))
            blend_name = 'views-' + recipe_hash[:20]
            if not any((b.name == blend_name for b in blends)):
                blends.append(DiagnosticBlend(blend_name, tuple(children), (0.5, 0.5)))
        return model
    for record in records:
        add(record, relocate_path(record['output_dir'], mapping))
    selected_hash = canonical_hash(report['selected_recipe'])
    if selected_hash not in recipe_models:
        raise ValueError('Selected model is not represented in the requested split caches')
    selected = report['selected_recipe']
    if selected.get('engine') == 'ensemble':
        components = [recipe_models.get(canonical_hash(c)) for c in selected['components']]
        if any((c is None for c in components)):
            raise ValueError('Selected ensemble component cache missing')
        blends.append(DiagnosticBlend('selected-fixed-ensemble', tuple(components), tuple(selected['weights'])))
    numeric = tuple((c for c in task.features if np.issubdtype(frame[c].dtype, np.number)))[:8]
    categorical = tuple((c for c in task.features if c in (spec.get('categorical_features') or [])))
    period = (spec.get('time_candidate') or {}).get('column')
    context_groups = []
    for record in records:
        if canonical_hash(record['recipe']) in {canonical_hash(c) for c in selected.get('components', [selected])}:
            for run in record.get('data_policy_runs', [])[-1:]:
                for group in run.get('target_encoding_groups', []):
                    if tuple(group) not in context_groups:
                        context_groups.append(tuple(group))
    protocol = ErrorAnalysisProtocol('ERR-01-frozen-report', numeric_features=numeric, categorical_features=categorical, context_groups=tuple(context_groups), period_column=period, blends=tuple(blends), evidence=(artifact(report_path), sources, artifact(provenance_path)), require_group_disjoint=spec.get('validation_strategy') != 'time')
    workspace.mkdir(parents=True, exist_ok=False)
    relocation_path = workspace / 'relocation.json'
    write_json(relocation_path, {'root_mapping': mapping, 'dataset_mapping': {str(spec.get('paths', {}).get('train', dataset_path)): str(dataset_path)}, 'run_dir': str(run_dir), 'original_evidence_rewritten': False})
    protocol = replace(protocol, evidence=protocol.evidence + (artifact(relocation_path),))
    protocol_path = workspace / 'protocol.json'
    write_json(protocol_path, protocol.to_dict())
    request = ErrorAnalysisRequest(workspace.name, task, DatasetRef(str(dataset_path), sha(dataset_path), len(frame)), recipe_models[selected_hash], protocol.protocol_id, artifact(protocol_path), 'forward' if spec.get('validation_strategy') == 'time' else scope, tuple(predictions), str(workspace / 'passport'), AnalysisBudget(600, 1536, 1))
    write_json(workspace / 'request.json', request.to_dict())
    return request

def audit_baseline(repo_root, data_root, output_dir, cache_root=None, root_mapping=None):
    """Verify portable evidence; missing remote caches remain explicitly blocked."""
    root, data_root, output = (Path(repo_root).resolve(), Path(data_root).resolve(), Path(output_dir).resolve())
    if output.exists():
        raise FileExistsError('Baseline audit output already exists')
    input_manifest_path = root / 'docs/handoff/public_inputs.json'
    input_manifest = json.loads(input_manifest_path.read_text())
    inputs = {}
    for kind in ('classification', 'regression'):
        inputs[kind] = {}
        for name, expected in input_manifest[kind]['sha256'].items():
            path = data_root / kind / name
            actual = sha(path) if path.is_file() else None
            inputs[kind][name] = {'status': 'verified' if actual == expected else 'missing' if actual is None else 'mismatch', 'expected_sha256': expected, 'actual_sha256': actual}
    reports = {}
    evidence_paths = [input_manifest_path]
    for version in ('v11-featureviews1', 'v16-mean1'):
        directory = root / 'release' / version
        assessment = json.loads((directory / 'public-full.json').read_text())
        if len(assessment) != 2 or any((r.get('exit_code') != 0 or r.get('integrity_ok') is not True or r.get('final_fit_status') != 'ok' for r in assessment)):
            raise ValueError('Portable full-lifecycle evidence is incomplete')
        reports[version] = {'classification' if 'macro_f1' in a['best_validation'] else 'regression': a for a in assessment}
        evidence_paths.append(directory / 'public-full.json')
    parity = {}
    for kind in ('classification', 'regression'):
        a, b = (reports['v11-featureviews1'][kind], reports['v16-mean1'][kind])
        match = all((a[k] == b[k] for k in ('best_validation', 'selection', 'submission_sha256', 'integrity_ok', 'final_fit_status')))
        if not match:
            raise ValueError('V11/V16 portable assessment parity mismatch')
        parity[kind] = {'portable_assessments_match': True, 'declared_csv_sha256': a['submission_sha256'], 'actual_csv_bytes_verified': False}
    class_reports = [json.loads((root / 'release' / version / 'classification-report.json').read_text()) for version in ('v11-featureviews1', 'v16-mean1')]
    evidence_paths.extend((root / 'release' / version / 'classification-report.json' for version in ('v11-featureviews1', 'v16-mean1')))
    if len(class_reports[0]['experiments']) != 12 or len(class_reports[1]['experiments']) != 12:
        raise ValueError('Expected twelve completed classification search records')
    for a, b in zip(class_reports[0]['experiments'], class_reports[1]['experiments']):
        if any((a[k] != b[k] for k in ('recipe', 'metrics', 'fit_iterations', 'status'))):
            raise ValueError('V11/V16 classification search trace differs')
    if any((class_reports[0][k] != class_reports[1][k] for k in ('selected_recipe', 'final_fit_iterations', 'submission_sha256'))):
        raise ValueError('Selected classification recipe/iteration parity mismatch')
    archives = {}
    for version in ('v11-featureviews1', 'v16-mean1'):
        path = root / 'release' / ('solution-' + version + '.zip')
        manifest_path = path.with_suffix('.manifest.json')
        manifest = json.loads(manifest_path.read_text())
        if sha(path) != manifest['sha256']:
            raise ValueError('Historical archive SHA mismatch')
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())) or set(archive.namelist()) != set(manifest['files']):
                raise ValueError('Historical archive structure mismatch')
            for name, expected in manifest['files'].items():
                if '/' in name or not (name.endswith('.py') or name == 'requirements.txt') or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Historical archive member mismatch')
            if archive.read('requirements.txt') != (root / 'requirements.txt').read_bytes():
                raise ValueError('Historical requirements mismatch')
        archives[version] = {'sha256': manifest['sha256'], 'members_verified': len(manifest['files'])}
        evidence_paths.extend([path, manifest_path])
    expected_requirement = '9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'
    if sha(root / 'requirements.txt') != expected_requirement:
        raise ValueError('Original requirements changed')
    environment = {'python': sys.version, 'packages': {}, 'model_replay_environment_matches_recorded_python': sys.version.split()[0] == '3.12.14'}
    for name in ('numpy', 'pandas', 'scipy', 'scikit-learn', 'lightgbm', 'xgboost', 'catboost', 'torch', 'optuna', 'flaml', 'lightautoml', 'autogluon.tabular'):
        try:
            environment['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            environment['packages'][name] = None
    output.mkdir(parents=True, exist_ok=False)
    cache = []
    locations = [('v11-featureviews1', 'featureviews1-full', 0, 'classification'), ('v11-featureviews1', 'featureviews1-full', 1, 'regression'), ('v16-mean1', 'final-default-parity', 0, 'regression'), ('v16-mean1', 'final-default-parity', 1, 'classification')]
    for version, run, task, kind in locations:
        run_dir = Path(cache_root).resolve() / run / ('task-' + str(task).zfill(2)) / 'automl_runs/run-v2' if cache_root else None
        ready = run_dir is not None and (run_dir / 'report.json').is_file()
        cache.append({'version': version, 'kind': kind, 'relative_run_directory': run + '/task-' + str(task).zfill(2) + '/automl_runs/run-v2', 'run_dir': str(run_dir) if run_dir else None, 'status': 'available_unverified' if ready else 'blocked_missing_cache', 'reason': None if ready else 'Original prediction/split caches are on another laptop; no fallback or model refit.', 'requests': [], 'blocked_scopes': []})
        if ready:
            for scope in ('search', 'confirmation'):
                split_path = run_dir / ('split.npz' if scope == 'search' else 'confirmation_split.npz')
                if not split_path.is_file():
                    cache[-1]['blocked_scopes'].append({'scope': scope, 'missing_path': str(split_path), 'reason': 'Original split artifact is missing; no partition reconstruction or substitute.'})
                    continue
                request = prepare_report_request(run_dir / 'report.json', run_dir, data_root / kind / 'train.csv', root / 'release' / version / 'public-source-manifest.json', output / (version + '-' + kind + '-' + scope), scope, root_mapping)
                cache[-1]['requests'].append({'scope': scope, 'request_sha256': request.sha256, 'path': str(Path(request.output_dir).parent / 'request.json')})
            cache[-1]['status'] = 'partially_prepared_missing_split' if cache[-1]['blocked_scopes'] else 'requests_prepared_not_analyzed'
    receipt = {'schema_version': '1.0', 'scope': 'BASE-01 no training; portable evidence is not a new quality measurement', 'repo_root': str(root), 'data_root': str(data_root), 'inputs': inputs, 'portable_parity': parity, 'archives': archives, 'classification_12_trial_trace_and_iteration_parity': True, 'evidence_sha256': {str(p.relative_to(root)): sha(p) for p in evidence_paths}, 'environment': environment, 'cache_inventory': cache, 'independent_checks_complete': all((v['status'] == 'verified' for kind in inputs.values() for v in kind.values())), 'raw_prediction_analysis': 'blocked' if any((c['status'] == 'blocked_missing_cache' or c['blocked_scopes'] for c in cache)) else 'prepared_not_run', 'baseline_complete': all((v['status'] == 'verified' for kind in inputs.values() for v in kind.values())) and all((c['status'] == 'verified' for c in cache)), 'new_model_fits': 0, 'v10_used_as_v11': False}
    write_json(output / 'baseline_inventory.json', receipt)
    write_json(output / 'environment.json', environment)
    return receipt

def finalize_baseline(inventory_path):
    """Close BASE-01 only after actual passports and original final CSV verification."""
    from automl_contracts_error_analysis import ErrorProfile
    from automl_error_analysis_reporting import read_section
    inventory_path = Path(inventory_path).resolve()
    inventory = json.loads(inventory_path.read_text())
    root = Path(inventory['repo_root'])
    if not inventory['independent_checks_complete']:
        raise ValueError('Independent baseline checks have not passed')
    for name, expected in inventory['evidence_sha256'].items():
        if sha(root / name) != expected:
            raise ValueError('Portable baseline evidence changed')
    for kind, files in inventory['inputs'].items():
        for name, item in files.items():
            if sha(Path(inventory['data_root']) / kind / name) != item['expected_sha256']:
                raise ValueError('Baseline input changed')
    verified = []
    expected_runs = {(version, kind) for version in ('v11-featureviews1', 'v16-mean1') for kind in ('classification', 'regression')}
    if len(inventory['cache_inventory']) != 4 or {(r['version'], r['kind']) for r in inventory['cache_inventory']} != expected_runs:
        raise ValueError('All four original V11/V16 runs are required')
    for entry in inventory['cache_inventory']:
        if len(entry['requests']) != 2 or {r['scope'] for r in entry['requests']} != {'search', 'confirmation'}:
            raise ValueError('Original caches/request pair missing; baseline remains blocked')
        run_dir = Path(entry['run_dir'])
        report = json.loads((run_dir / 'report.json').read_text())
        scopes = []
        for descriptor in entry['requests']:
            request_path = Path(descriptor['path'])
            request = ErrorAnalysisRequest.from_json(request_path.read_text())
            protocol = ErrorAnalysisProtocol.from_json(Path(request.protocol.path).read_text())
            artifacts = [request.protocol, request.dataset] + list(protocol.evidence)
            for prediction in request.predictions:
                artifacts.extend([AnalysisArtifactRef(prediction.predictions.path, prediction.predictions_sha256), prediction.split])
                artifacts.extend((r for r in (prediction.probabilities, prediction.recorded_result) if r is not None))
            for reference in artifacts:
                if sha(reference.path) != reference.sha256:
                    raise ValueError('Original passport artifact changed before baseline closure')
            profile_path = Path(request.output_dir) / 'error_profile.json'
            profile = ErrorProfile.from_json(profile_path.read_text())
            if request.sha256 != descriptor['request_sha256'] or profile.request_sha256 != request.sha256:
                raise ValueError('Baseline passport request mismatch')
            required = {'alignment', 'models', 'comparisons', 'slices'}
            if any((s.status == 'failed' or (s.name in required and s.status != 'complete') for s in profile.sections)):
                raise ValueError('Baseline passport has failed/incomplete required sections')
            for section in profile.sections:
                if section.status == 'complete':
                    read_section(profile, section.name)
            value = read_section(profile, 'models')['models'][request.control_model_id]['fold_mean'][request.task.metric]
            role = 'primary' if descriptor['scope'] == 'search' else 'confirmation'
            selected = (report.get('ensemble') or {}).get(role)
            if selected is None:
                records = report['experiments' if descriptor['scope'] == 'search' else 'confirmations']
                selected = next((r for r in records if canonical_hash(r['recipe']) == canonical_hash(report['selected_recipe'])))
            if not np.isclose(value, selected['metrics'][request.task.metric], rtol=1e-08, atol=1e-10):
                raise ValueError('Selected-model passport score differs from original report')
            relocation = json.loads((request_path.parent / 'relocation.json').read_text())
            scopes.append({'scope': descriptor['scope'], 'metric': request.task.metric, 'value': value, 'profile_status': profile.status, 'profile_sha256': sha(profile_path), 'request_sha256': request.sha256, 'path': str(profile_path)})
        output = relocate_path(report['submission_path'], relocation['root_mapping'])
        actual = sha(output)
        expected = inventory['portable_parity'][entry['kind']]['declared_csv_sha256']
        if actual != expected or actual != report['submission_sha256']:
            raise ValueError('Actual final CSV differs from V11/V16 portable baseline')
        verified.append({'version': entry['version'], 'kind': entry['kind'], 'scopes': scopes, 'mean': float(np.mean([s['value'] for s in scopes])), 'actual_final_csv_sha256': actual, 'actual_csv_bytes_verified': True})
    result = {'schema_version': '1.0', 'inventory_sha256': sha(inventory_path), 'baseline_complete': True, 'original_runs': verified, 'new_model_fits': 0, 'v10_used_as_v11': False, 'scope': 'Recomputed diagnostics from original frozen predictions; not new independent model-quality evaluation.'}
    write_json(inventory_path.parent / 'baseline_verified.json', result)
    return result
