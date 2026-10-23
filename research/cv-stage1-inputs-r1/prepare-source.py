"""Freeze three existing grouped outer folds; no learners, API or scoring.

This writes only this new plan directory. It never launches the solver. Truth
files and original-row arrays are verifier inputs, not solver task inputs.
"""
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
import ast
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import sys
import time
import zipfile

sys.dont_write_bytecode = True
PLAN = Path(__file__).resolve().parent
WORK = PLAN.parent
REPO = WORK / 'alfa-hack-automl'
PROTOCOL = WORK / 'fullagent-fixed-half-plan-r2/protocol.json'
PROTOCOL_SHA = '5ae51e6e5981acfbd03ab670a33f70177163aed1a088eb3cf4407f5e5f113046'
SOURCE_TASK = WORK / 'evaluation/multiclass/task.md'
ARCHIVE = WORK / 'support-context-component-plan/evaluator-source.zip'
SEED, FOLDS = 83, 3
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS']:
    os.environ[key] = '1'
sys.path[:0] = [str(REPO / 'src')]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(WORK.resolve()).as_posix()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def deterministic_npz(path, arrays):
    import numpy as np
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, array in arrays.items():
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.asarray(array), allow_pickle=False)
            info = zipfile.ZipInfo(name + '.npy', date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, buffer.getvalue())


def function_tree(source, name):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise ValueError('Expected one frozen function ' + name)
    return ast.dump(nodes[0], include_attributes=False)


def main():
    tick = time.monotonic()
    if digest(PROTOCOL) != PROTOCOL_SHA:
        raise ValueError('Approved protocol changed; do not infer new folds')
    protocol = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    cv = protocol['whole_selection_grouped_CV']
    if cv['fold_count'] != FOLDS or cv['seed'] != SEED:
        raise ValueError('Requested outer-fold assignment differs from approved protocol')
    if digest(ARCHIVE) != protocol['basis']['unchanged_current_runtime_archive_sha256']:
        raise ValueError('Frozen evaluator archive changed')
    paths = {role: SOURCE_TASK.parent / name for role, name in {
        'train': 'train.csv', 'test': 'test.csv',
        'sample_submission': 'sample_submission.csv',
        'data_dictionary': 'data_dictionary.csv'}.items()}
    source_hashes = {relative(p): digest(p) for p in [SOURCE_TASK, *paths.values()]}
    for p in paths.values():
        expected = protocol['frozen_component_and_control_files_sha256'][relative(p)]
        if digest(p) != expected:
            raise ValueError('Pristine input changed: ' + p.name)
    source_files = [REPO / 'src/automl/evaluation/service.py',
                    REPO / 'src/automl/task_understanding/service.py',
                    REPO / 'src/automl/task_understanding/inputs.py',
                    REPO / 'src/automl/infrastructure/tables.py',
                    REPO / 'src/automl/infrastructure/observation_time.py']
    code_hashes = {relative(p): digest(p) for p in source_files}
    with zipfile.ZipFile(ARCHIVE) as archive:
        frozen_evaluation = archive.read('automl_evaluation.py').decode('utf-8')
        frozen_task = archive.read('automl_task.py').decode('utf-8')
    for name, path, compiled in [
            ('make_folds', source_files[0], frozen_evaluation),
            ('discover', source_files[1], frozen_task)]:
        if function_tree(path.read_text(encoding='utf-8'), name) != function_tree(compiled, name):
            raise ValueError('Canonical function differs from frozen evaluator: ' + name)
    forbidden_network = {'attempts': 0}
    def no_network(*args, **kwargs):
        forbidden_network['attempts'] += 1
        raise AssertionError('Network forbidden during fold preparation')
    with ExitStack() as guards:
        guards.enter_context(patch.object(socket.socket, 'connect', side_effect=no_network))
        guards.enter_context(patch.object(socket, 'create_connection', side_effect=no_network))
        import numpy as np
        import pandas as pd
        import sklearn
        from automl.evaluation.api import make_folds
        from automl.task_understanding.api import discover
        spec, profile, train, original_test, original_sample, text, hashes = discover(
            SOURCE_TASK, allow_llm=False)
        if spec['kind'] != 'classification' or spec['metric'] != 'macro_f1':
            raise ValueError('Approved task is nontext MacroF1 classification')
        if spec.get('text_features') or spec.get('time_candidate') or spec.get('group_candidate'):
            raise ValueError('Unexpected task validation semantics; root review needed')
        if spec['target'] in spec['features'] or spec['id'] in spec['features']:
            raise ValueError('Target/ID entered raw feature hashing')
        direct_hashes = pd.util.hash_pandas_object(
            train[spec['features']], index=False).to_numpy(dtype='uint64')
        if not np.array_equal(direct_hashes, hashes):
            raise ValueError('Pristine raw feature hashing differs')
        if not pd.Series(hashes).duplicated().any():
            raise ValueError('Expected grouped public data; no silent row-fold fallback')
        assignments = make_folds(spec, train, hashes, FOLDS, SEED)
        if len(assignments) != FOLDS:
            raise ValueError('Existing splitter reduced requested fold count')
        n = len(train)
        coverage = np.zeros(n, dtype=np.int64)
        arrays, records = {}, []
        classes = list(spec['classes'])
        target, identifier = spec['target'], spec['id']
        if identifier is None or original_sample.columns.tolist() != [identifier, target]:
            raise ValueError('Unexpected output schema; do not invent ID mapping')
        class_series = train[target].astype(str)
        if train[identifier].isna().any() or train[identifier].duplicated().any():
            raise ValueError('Original training IDs cannot identify held-out predictions')
        tasks = PLAN / 'tasks'
        verifier = PLAN / 'verifier-only'
        tasks.mkdir()
        verifier.mkdir()
        for number, (fit, validation, info) in enumerate(assignments):
            fit, validation = np.asarray(fit, dtype='<i8'), np.asarray(validation, dtype='<i8')
            if info['method'] != 'StratifiedGroupKFold' or info['n_splits'] != FOLDS or info['seed'] != SEED:
                raise ValueError('Existing splitter unexpectedly changed algorithm')
            if any(len(a) == 0 or len(np.unique(a)) != len(a) or a.min() < 0 or a.max() >= n
                   or not np.array_equal(a, np.sort(a)) for a in [fit, validation]):
                raise ValueError('Invalid original-row partition')
            if len(fit) + len(validation) != n or np.intersect1d(fit, validation).size:
                raise ValueError('Outer partitions do not form one complete disjoint task')
            overlap = len(np.intersect1d(hashes[fit], hashes[validation]))
            if overlap:
                raise ValueError('Pristine feature group crosses outer boundary')
            if set(class_series.iloc[fit]) != set(classes):
                raise ValueError('An outer fitting task lost a class')
            coverage[validation] += 1
            arrays['fold%d_train' % number] = fit
            arrays['fold%d_validation' % number] = validation
            fold = tasks / ('f%d' % number)
            fold.mkdir()
            (fold / 'data_dictionary.csv').write_bytes(paths['data_dictionary'].read_bytes())
            placeholder = sorted(class_series.iloc[fit].unique().tolist())[0]
            fitting = np.zeros(n, dtype=bool)
            fitting[fit] = True
            file_paths = [fold / 'train.csv', fold / 'test.csv', fold / 'sample_submission.csv',
                          verifier / ('f%d-truth.csv' % number)]
            with ExitStack() as files:
                source = files.enter_context(paths['train'].open('r', encoding='utf-8-sig', newline=''))
                reader = csv.reader(source)
                header = next(reader)
                if header != train.columns.tolist():
                    raise ValueError('CSV lexical schema differs from loaded pristine schema')
                ti, ii = header.index(target), header.index(identifier)
                writers = [csv.writer(files.enter_context(p.open('x', encoding='utf-8', newline='')),
                                      lineterminator='\n') for p in file_paths]
                writers[0].writerow(header)
                writers[1].writerow([c for c in header if c != target])
                writers[2].writerow([identifier, target])
                writers[3].writerow(['original_row_position', identifier, target])
                count = 0
                for position, row in enumerate(reader):
                    if len(row) != len(header) or position >= n:
                        raise ValueError('Pristine lexical CSV shape changed')
                    if fitting[position]:
                        writers[0].writerow(row)
                    else:
                        writers[1].writerow([v for k, v in enumerate(row) if k != ti])
                        writers[2].writerow([row[ii], placeholder])
                        writers[3].writerow([position, row[ii], row[ti]])
                    count += 1
                if count != n:
                    raise ValueError('Pristine lexical CSV row count changed')
            task_text = re.sub(r'`[^`\n]*/(train\.csv|test\.csv|sample_submission\.csv|data_dictionary\.csv)`',
                               lambda m: '`' + m.group(1) + '`', text)
            for old_count, new_count in [(len(train), len(fit)), (len(original_test), len(validation))]:
                task_text = task_text.replace(format(old_count, ',').replace(',', ' '),
                                              format(new_count, ',').replace(',', ' '))
            task_text = re.sub(r'Test — stratified-выборка[^\n]*',
                               'Test — фиксированная отложенная выборка с теми же признаками, без целевой переменной.',
                               task_text)
            with (fold / 'task.md').open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(task_text)
            # Inspect the actual serialized task, not merely the in-memory slices.
            fold_spec, _, fit_read, test_read, sample_read, fold_text, fold_hashes = discover(
                fold / 'task.md', allow_llm=False)
            if fold_spec['features'] != spec['features'] or fold_spec['classes'] != classes:
                raise ValueError('Materialized fold changed schema/class order')
            if fold_spec['categorical_features'] != spec['categorical_features']:
                raise ValueError('Materialized fold changed categorical roles')
            if target in test_read or sample_read[target].astype(str).unique().tolist() != [placeholder]:
                raise ValueError('Hidden target leaked to solver test/sample')
            if not np.array_equal(fold_hashes, hashes[fit]):
                raise ValueError('Serialized fitting CSV changed pristine raw feature values')
            heldout_hashes = pd.util.hash_pandas_object(
                test_read[spec['features']], index=False).to_numpy(dtype='uint64')
            if not np.array_equal(heldout_hashes, hashes[validation]):
                raise ValueError('Serialized test CSV changed pristine raw feature values')
            if fit_read[target].astype(str).tolist() != class_series.iloc[fit].tolist():
                raise ValueError('Fitting label order differs from approved outer fitting rows')
            for actual, expected in [(fit_read[identifier], train[identifier].iloc[fit]),
                                     (test_read[identifier], train[identifier].iloc[validation]),
                                     (sample_read[identifier], train[identifier].iloc[validation])]:
                if actual.astype(str).tolist() != expected.astype(str).tolist():
                    raise ValueError('Original IDs/order changed during materialization')
            truth = pd.read_csv(file_paths[3])
            if truth['original_row_position'].tolist() != validation.tolist() or truth[target].astype(str).tolist() != class_series.iloc[validation].tolist():
                raise ValueError('Verifier truth mapping differs from frozen outer rows')
            counts = []
            for label in classes:
                fm = class_series.iloc[fit].to_numpy() == label
                vm = class_series.iloc[validation].to_numpy() == label
                independent = int(np.unique(hashes[fit][fm]).size)
                counts.append({'class': label, 'fitting_rows': int(fm.sum()),
                    'fitting_independent_raw_feature_groups': independent,
                    'validation_rows': int(vm.sum()),
                    'validation_independent_raw_feature_groups': int(np.unique(hashes[validation][vm]).size),
                    'supported_gate_applies': independent >= 100})
            rarest = min(counts, key=lambda c: (c['fitting_independent_raw_feature_groups'], c['class']))['class']
            forbidden_terms = ['verifier-only', 'f%d-truth.csv' % number, 'outer-folds.npz', str(PLAN.resolve())]
            if any(term in fold_text for term in forbidden_terms):
                raise ValueError('Verifier-only path entered the solver task text')
            inputs = {p.name: digest(p) for p in sorted(fold.iterdir()) if p.is_file()}
            if set(inputs) != {'train.csv', 'test.csv', 'sample_submission.csv', 'data_dictionary.csv', 'task.md'}:
                raise ValueError('Unexpected solver-visible file')
            records.append({'fold': number, 'split_info': info,
                'arm_order': cv['arm_order_by_fold'][number],
                'solver_template': relative(fold / 'task.md'),
                'solver_inputs_sha256': inputs,
                'A_control_input_sha256': dict(inputs), 'B_candidate_input_sha256': dict(inputs),
                'A_B_input_bytes_identical_by_shared_frozen_template': True,
                'placeholder_rule': 'Lexicographically first class present in outer fitting targets, constant for every sample row; not an outer truth prediction',
                'placeholder_class': placeholder,
                'verifier_truth': relative(file_paths[3]), 'verifier_truth_sha256': digest(file_paths[3]),
                'fitting_independent_raw_feature_groups': int(np.unique(hashes[fit]).size),
                'validation_independent_raw_feature_groups': int(np.unique(hashes[validation]).size),
                'shared_raw_feature_groups': overlap, 'support': counts,
                'excluded_rarest_class_frozen_before_scoring': rarest,
                'rarest_tie_rule': 'Minimum fitting independent raw feature groups, lexicographic class order breaks ties',
                'serialized_raw_feature_hashes_equal_pristine': True,
                'serialized_target_ID_order_equal_pristine': True,
                'solver_does_not_receive_truth_support_or_original_position_paths': True})
        if not np.all(coverage == 1):
            raise ValueError('Outer held-out coverage must be exactly once')
        arrays['coverage'] = coverage
        arrays['raw_feature_hashes'] = np.asarray(hashes, dtype='<u8')
        deterministic_npz(verifier / 'outer-folds.npz', arrays)
        with np.load(verifier / 'outer-folds.npz', allow_pickle=False) as saved:
            for name, expected in arrays.items():
                if not np.array_equal(saved[name], expected):
                    raise ValueError('Serialized fold array changed')
        if any(digest(WORK / name) != value for name, value in source_hashes.items()):
            raise ValueError('Pristine inputs changed during preparation')
        if any(digest(WORK / name) != value for name, value in code_hashes.items()):
            raise ValueError('Splitter/task source changed during preparation')
        manifest = {'plan_id': 'fullagent-fixed-half-stage1-grouped-CV83-r1',
            'status': 'outer_folds_and_solver_task_templates_frozen_no_fit',
            'approved_protocol': relative(PROTOCOL), 'approved_protocol_sha256': PROTOCOL_SHA,
            'evaluator_archive_sha256': digest(ARCHIVE),
            'prepare_source_sha256': digest(__file__), 'pristine_input_sha256': source_hashes,
            'splitter_parser_source_sha256': code_hashes,
            'make_folds_and_discover_AST_equal_frozen_evaluator': True,
            'versions': {'python': sys.version.split()[0], 'numpy': np.__version__,
                         'pandas': pd.__version__, 'sklearn': sklearn.__version__},
            'method': 'make_folds(spec,train,pristine_raw_feature_hashes,3,83)',
            'fold_count': FOLDS, 'seed': SEED, 'row_count': n,
            'raw_feature_count': len(spec['features']), 'raw_feature_schema_order': spec['features'],
            'canonical_class_order': classes, 'target_column': target, 'id_column': identifier,
            'original_training_duplicate_feature_rate': spec['duplicate_feature_rate'],
            'raw_feature_hash_excludes_target_and_ID': True,
            'exactly_once_heldout_coverage': True, 'coverage_minimum': int(coverage.min()),
            'coverage_maximum': int(coverage.max()), 'total_heldout_rows': int(coverage.sum()),
            'outer_fold_arrays': relative(verifier / 'outer-folds.npz'),
            'outer_fold_arrays_sha256': digest(verifier / 'outer-folds.npz'),
            'outer_fold_arrays_keys': list(arrays), 'folds': records,
            'solver_argv_template': ['<same_python>', '-u', 'solution.py', 'task.md', '--offline'],
            'solver_deployment_allowlist': ['task.md', 'train.csv', 'test.csv', 'sample_submission.csv', 'data_dictionary.csv'],
            'label_boundary': 'Copy only each fold solver deployment allowlist into isolated solver task directory. Do not pass plan/manifest/truth/support/original-row arrays or pristine full-label files to the solver. Verification reads outer truth only after predictions/source/recipe are sealed.',
            'filesystem_security_sandbox_implemented': False,
            'security_boundary_limitation': 'This is a prepared data/argv separation, not an OS access-control claim. Future launcher must enforce operational deployment and review any stronger isolation requirement.',
            'whole_selection_required_not_fixed_recipe_CV': True,
            'internal_selection_splits': 'Fresh existing internal search/confirmation/selection/calibration/refit using outer-fitting task only; existing defaults remain unchanged',
            'solver_seconds_each': 9900, 'slots_each': 12, 'HPO_trials_each': 0,
            'API_calls_each': 0, 'arm_order_by_fold': cv['arm_order_by_fold'],
            'scores_computed': False, 'fits': 0, 'api_calls': 0,
            'forbidden_network_attempts': forbidden_network['attempts'],
            'source_or_input_edits': 0, 'canonical_edits': 0,
            'deadline_assigned': False, 'promotion': False,
            'current_execution_blockers': ['Candidate ordinary-default last-slot integration, source/release/path/parity gates and root publication/review',
                'Active trueMVP terminal ownership cleanup and released central ResearchLock',
                'Reviewed future sequential coordinator, operational truth separation and immutable stage clock/resources'],
            'adaptive_public_data_limit': cv['evidence_limit'],
            'elapsed_preparation_seconds': time.monotonic() - tick}
        save(PLAN / 'manifest.json', manifest)
        print(json.dumps({'status': manifest['status'], 'manifest_sha256': digest(PLAN / 'manifest.json'),
              'folds': [{'fold': r['fold'], 'fit': r['split_info']['train_rows'],
                         'heldout': r['split_info']['validation_rows'], 'shared_groups': r['shared_raw_feature_groups'],
                         'rarest': r['excluded_rarest_class_frozen_before_scoring']} for r in records],
              'array_sha256': manifest['outer_fold_arrays_sha256'], 'fits': 0, 'api_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
