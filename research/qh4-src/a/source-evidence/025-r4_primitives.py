"""Exact selected R4 artifact primitives; excludes whole-agent/HPO/main predicates."""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            result.update(block)
    return result.hexdigest()


def close(a, b):
    return (not isinstance(b, bool) and isinstance(b, (int, float))
            and math.isfinite(b) and math.isclose(a, b, abs_tol=1e-10, rel_tol=1e-10))


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def index_sha(tr, va):
    return hashlib.sha256(tr.astype('<i8').tobytes()+va.astype('<i8').tobytes()).hexdigest()


def split(path, n):
    with np.load(path, allow_pickle=False) as saved:
        tr, va = saved['train'].copy(), saved['validation'].copy()
    for rows in [tr, va]:
        assert rows.ndim == 1 and rows.dtype.kind in 'iu' and len(rows)
        assert rows.min() >= 0 and rows.max() < n and len(np.unique(rows)) == len(rows)
    assert not np.intersect1d(tr, va).size
    return tr, va


def f1(truth, prediction, classes):
    mapping = {name: i for i, name in enumerate(classes)}
    assert set(truth) <= set(classes) and set(prediction) <= set(classes)
    counts = np.zeros((len(classes), len(classes)), dtype=np.int64)
    np.add.at(counts, ([mapping[v] for v in truth], [mapping[v] for v in prediction]), 1)
    return f1_counts(counts, classes)


def f1_counts(counts, classes):
    denominator = counts.sum(axis=0)+counts.sum(axis=1)
    values = np.divide(2*np.diag(counts), denominator,
        out=np.zeros(len(classes)), where=denominator > 0)
    return float(values.mean()), dict(zip(classes, map(float, values)))


def probability(path, positions, classes):
    with np.load(path, allow_pickle=False) as saved:
        order = saved['classes'].astype(str).tolist()
        values = saved['probabilities'].copy()
        if positions is not None:
            assert np.array_equal(saved['row_position'], positions)
    assert len(order) == len(set(order)) == len(classes) and set(order) == set(classes)
    assert values.ndim == 2 and values.shape[1] == len(classes) and np.isfinite(values).all()
    if positions is not None:
        assert len(values) == len(positions)
    assert (values >= 0).all() and (values <= 1).all()
    assert np.allclose(values.sum(axis=1), 1., rtol=1e-10, atol=1e-10)
    return values[:, [order.index(c) for c in classes]]


def child_feature_views(recipe, spec):
    plain = deepcopy(recipe)
    plain['params'].pop('feature_views')
    encoded = deepcopy(plain)
    categorical = [c for c in spec['features'] if c in set(spec['categorical_features'])][:3]
    encoded['params'].update(target_encoding=True,
        target_encoding_groups=[list(v) for v in combinations(categorical, 2)],
        target_encoding_smoothing=20.)
    plain['hypothesis'] = 'Fixed feature view: original categorical features'
    encoded['hypothesis'] = 'Fixed feature view: fitting-cross-fitted categorical statistics'
    return [plain, encoded]


def value_output_contract(spec, train, test, sample):
    """Canonical parser enum: one-column MacroF1/RMSE predictions use value."""
    assert spec['kind'] in {'classification', 'regression'}
    assert spec['metric'] == ('macro_f1' if spec['kind'] == 'classification' else 'rmse')
    assert spec.get('prediction_type') == 'value', 'Canonical prediction_type must be value'
    assert spec.get('output_columns') == [spec['target']]
    assert spec['target'] in train and spec['target'] not in test
    assert spec['target'] not in spec['features'] and spec.get('id') not in spec['features']
    assert len(spec['features']) == len(set(spec['features']))
    assert all(name in train and name in test for name in spec['features'])
    assert len(train) == spec['n_train'] and len(test) == spec['n_test'] == len(sample)
    assert not train[spec['target']].isna().any()
    assert list(sample) == ([spec['id']] if spec.get('id') is not None else []) + [spec['target']]
    positions = np.asarray(spec.get('sample_test_positions', np.arange(len(test))))
    assert positions.ndim == 1 and positions.dtype.kind in 'iu' and len(positions) == len(test)
    assert np.array_equal(np.sort(positions), np.arange(len(test))), 'Sample positions must be a permutation'
    if spec.get('id') is not None:
        assert spec['id'] in test and not test[spec['id']].isna().any() and not sample[spec['id']].isna().any()
        assert test[spec['id']].iloc[positions].reset_index(drop=True).equals(sample[spec['id']].reset_index(drop=True))
    if spec['kind'] == 'classification':
        classes = spec.get('classes')
        assert isinstance(classes, list) and classes and all(isinstance(c, str) for c in classes)
        assert classes == sorted(set(train[spec['target']].astype(str)))
    else:
        assert np.isfinite(pd.to_numeric(train[spec['target']], errors='raise').to_numpy(dtype=float)).all()
    return positions


def median_iterations(first, second):
    if isinstance(first, list) or isinstance(second, list):
        assert isinstance(first, list) and isinstance(second, list) and len(first) == len(second)
        return [median_iterations(a, b) for a, b in zip(first, second)]
    assert type(first) is int and type(second) is int and 1 <= first <= 3000 and 1 <= second <= 3000
    return max(30, int(np.median([first, second])))


def matched_control_comparison(cuts, control, kind):
    rows = []
    for phase in ['primary', 'confirmation']:
        actual, reference = cuts[phase], control[phase]
        assert actual['positions_sha256'] == reference['positions_sha256']
        delta = actual['value'] - reference['value']
        row = {'phase': phase, 'current': actual['value'], 'protected_control': reference['value'],
               'delta_current_minus_control': delta,
               'primary_improves': delta > 0 if kind == 'classification' else delta < 0}
        if kind == 'classification':
            assert actual['independent_fitting_groups'] == reference['independent_fitting_groups']
            assert actual['rarest_fitting_class'] == reference['rarest_fitting_class']
            support, rarest = actual['independent_fitting_groups'], actual['rarest_fitting_class']
            deltas = {c: actual['per_class_f1'][c] - reference['per_class_f1'][c] for c in support}
            losses = {c: value for c, value in deltas.items() if support[c] >= 100 and value < -.01-1e-12}
            ex_rarest = float(np.mean([v for c, v in deltas.items() if c != rarest]))
            row.update(per_class_f1_delta=deltas, supported_class_losses_over_001=losses,
                       ex_rarest_macro_f1_delta=ex_rarest,
                       all_class_gates_passed=row['primary_improves'] and not losses and ex_rarest > 0)
        rows.append(row)
    return {'cuts': rows, 'each_cut_primary_gate_passed': all(r['primary_improves'] for r in rows),
            'class_each_cut_gate_passed': all(r.get('all_class_gates_passed', True) for r in rows),
            'matched_saved_primary_and_confirmation_independently_recomputed': True,
            'fresh_protected_control_full_refit': False,
            'scope': 'Exact preserved control recipe rerun on the same two fitting/validation partitions; final refit audited only for the selected procedure'}


class TaskVerifier:
    def __init__(self, directory, report, train, test, sample):
        self.directory, self.report = directory, report
        self.spec, self.train, self.test, self.sample = report['spec'], train, test, sample
        self.classes, self.records = list(self.spec.get('classes') or []), {}
        self.sample_positions = value_output_contract(self.spec, train, test, sample)
        self.hashes = pd.util.hash_pandas_object(train[self.spec['features']], index=False).to_numpy(dtype='uint64')

    def folder(self, record):
        path = Path(record.get('output_dir') or Path(record['submission']).parent).resolve()
        assert path.is_relative_to(self.directory)
        return path

    def verify(self, record, partition, phase, full=False, expected_recipe=None):
        folder = self.folder(record)
        key = (str(folder), phase, full)
        if key in self.records:
            return self.records[key]
        recipe = record['recipe']
        if expected_recipe is not None:
            assert recipe == expected_recipe
        assert record['status'] == 'ok'
        stored = load(folder / 'result.json')
        assert stored['status'] == 'ok' and stored['recipe'] == recipe and stored['full_fit'] is full
        assert stored['fit_iterations'] == record['fit_iterations']
        job_path = folder / 'job.json'
        if job_path.exists():
            job = load(job_path)
            assert job['spec'] == self.spec and job['recipe'] == recipe and job['threads'] == 2
            assert job['full_fit'] is full and Path(job['output_dir']).resolve() == folder
            assert Path(job['split_path']).resolve() == partition.resolve()
            if full:
                assert job.get('fit_iterations') == stored['fit_iterations']
        elif stored.get('training_reused') is True:
            assert recipe['engine'] == 'ensemble' and not full
        else:
            # Recursive leaf calls write their result and probability files,
            # while the invoking top-level job carries the dispatch contract.
            assert expected_recipe is not None
        tr, va = split(partition, len(self.train))
        prediction = pd.read_csv(folder / 'submission.csv', converters={self.spec['id']: str})
        assert list(prediction) == list(self.sample) and len(prediction) == len(self.sample)
        assert not prediction.isna().any().any()
        if self.spec.get('id') is not None:
            assert prediction[self.spec['id']].equals(self.sample[self.spec['id']])
        output = self.spec['output_columns'][0]
        returned = {'folder': folder, 'recipe': recipe, 'test': None, 'validation': None,
            'value': None, 'per_class_f1': None}
        if self.spec['kind'] == 'classification':
            test_probability = probability(folder / 'test_probabilities.npz', None, self.classes)
            assert len(test_probability) == len(self.test)
            positions = self.sample_positions
            assert np.array_equal(prediction[output].astype(str),
                np.asarray(self.classes)[test_probability.argmax(axis=1)][positions])
            returned['test'] = test_probability
        else:
            returned['test'] = prediction[output].to_numpy(dtype=float)
            assert np.isfinite(returned['test']).all()
        if not full:
            frame = pd.read_csv(folder / 'validation_predictions.csv')
            assert frame.row_position.dtype.kind in 'iu' and np.array_equal(frame.row_position, va)
            truth = self.train[self.spec['target']].iloc[va].to_numpy()
            if self.spec['kind'] == 'classification':
                val_probability = probability(folder / 'validation_probabilities.npz', va, self.classes)
                predicted = np.asarray(self.classes)[val_probability.argmax(axis=1)]
                assert np.array_equal(frame.y_true.astype(str), truth.astype(str))
                assert np.array_equal(frame.y_pred.astype(str), predicted)
                value, per_class = f1(truth.astype(str), predicted, self.classes)
                returned.update(validation=val_probability, value=value, per_class_f1=per_class)
            else:
                values = frame.y_pred.to_numpy(dtype=float)
                assert np.isfinite(values).all()
                assert np.allclose(frame.y_true.to_numpy(dtype=float), truth.astype(float), atol=1e-12, rtol=0)
                value = float(np.sqrt(np.mean((truth.astype(float)-values)**2)))
                returned.update(validation=values, value=value)
            assert close(value, record['metrics'][self.spec['metric']])
            assert close(value, stored['metrics'][self.spec['metric']])
        children, weights = [], None
        if recipe['engine'] == 'ensemble':
            weights = np.asarray(recipe['weights'], dtype=float)
            assert len(weights) == len(recipe['components']) and np.isfinite(weights).all()
            assert (weights >= 0).all() and weights.sum() > 0
            weights = weights / weights.sum()
            for i, child_recipe in enumerate(recipe['components']):
                if job_path.exists():
                    child = load(folder / f'component-{i}/result.json')
                    child = dict(child, output_dir=str(folder / f'component-{i}'))
                else:
                    field = 'experiments' if phase == 'primary' else 'confirmations'
                    matches = [r for r in self.report[field] if r.get('status') == 'ok' and r['recipe'] == child_recipe]
                    assert len(matches) == 1
                    child = matches[0]
                children.append(self.verify(child, partition, phase, full, child_recipe))
        elif recipe.get('params', {}).get('feature_views'):
            assert recipe['params']['feature_views'] == 'categorical_te_pair'
            weights = np.asarray([.5, .5])
            for i, child_recipe in enumerate(child_feature_views(recipe, self.spec)):
                child = load(folder / f'component-{i}/result.json')
                children.append(self.verify(dict(child, output_dir=str(folder / f'component-{i}')),
                    partition, phase, full, child_recipe))
        if children:
            for field in ['test'] + ([] if full else ['validation']):
                expected = sum(weight*child[field] for weight, child in zip(weights, children))
                assert np.allclose(returned[field], expected, atol=1e-10, rtol=1e-10)
        returned['mixture_children'] = len(children)
        self.records[key] = returned
        return returned


def diagnostics(verifier, record, partition, phase):
    verified = verifier.verify(record, partition, phase)
    tr, va = split(partition, len(verifier.train))
    value = {'phase': phase, 'metric': verifier.spec['metric'], 'value': verified['value'],
        'fitting_rows': len(tr), 'validation_rows': len(va), 'positions_sha256': index_sha(tr, va),
        'training_rows_canonical_sha256': canonical(tr.tolist()),
        'split_file_sha256': digest(partition), 'prediction_sha256': digest(verified['folder'] / 'validation_predictions.csv'),
        'mixture_children': verified['mixture_children']}
    if verifier.spec['kind'] == 'classification':
        assert not np.intersect1d(verifier.hashes[tr], verifier.hashes[va]).size
        fitting_y = verifier.train[verifier.spec['target']].iloc[tr].astype(str).to_numpy()
        support = {c: len(np.unique(verifier.hashes[tr][fitting_y == c])) for c in verifier.classes}
        rarest = min(verifier.classes, key=lambda c: support[c])
        value.update(per_class_f1=verified['per_class_f1'], independent_fitting_groups=support,
            rarest_fitting_class=rarest, ex_rarest_macro_f1=float(np.mean([
                v for c, v in verified['per_class_f1'].items() if c != rarest])), feature_groups_disjoint=True)
    else:
        times = pd.to_numeric(verifier.train[verifier.spec['time_column']], errors='raise')
        assert times.iloc[tr].max() < times.iloc[va].min()
        value.update(forward_chronology_verified=True,
            validation_periods=sorted(map(float, times.iloc[va].unique())))
    return value


def verified_terminal(record):
    """Only the new exact-known departure variant needs this typed bridge.

    Original two statuses retain their existing predicate. The new branch is
    bound to parent-captured worker/self identities and completed strict cleanup.
    A departed old identity has unknown RSS, never a measured zero.
    """
    terminal=record.get('terminal_resource_observation',{})
    if terminal.get('status') in {'sampled_before_terminal_acceptance','root_absent_after_observed_exit'}:return True
    if terminal.get('status')!='fresh_known_root_departed_after_observed_exit':return False
    def identity(row):
        if (type(row) is not dict or type(row.get('pid')) is not int or row['pid']<=0
            or type(row.get('create_time')) not in (int,float) or not math.isfinite(row['create_time'])
            or row['create_time']<=0):return None
        return row['pid'],row['create_time']
    sample=record.get('verified_resource_sample');root=identity(record.get('worker_resource_root'));own=identity(record.get('worker_resource_self'))
    if (root is None or own is None or root==own or type(sample) is not dict
        or sample.get('schema')!='verified-known-resource-sample-v1'
        or type(sample.get('sampled')) is not list or type(sample.get('departed')) is not list
        or len(sample['sampled'])+len(sample['departed'])>30000
        or type(sample.get('required_count')) is not int or sample['required_count']!=1
        or type(sample.get('sampled_count')) is not int or sample['sampled_count']!=len(sample['sampled'])
        or type(sample.get('known_count')) is not int or sample['known_count']<len(sample['sampled'])+len(sample['departed'])
        or sample.get('scope')!='sampled_stable_known_RSS_not_OS_lifetime_peak'
        or record.get('parent_observed_worker_exit_code')!=0 or type(record.get('parent_observed_worker_exit_code')) is not int
        or record.get('cleanup_confirmed') is not True
        or terminal.get('worker_root_rss_bytes') is not None
        or terminal.get('remaining_owned_cleanup_still_required') is not True
        or terminal.get('departed')!=sample['departed']):return False
    sampled={};departed={}
    for row in sample['sampled']:
        key=identity(row)
        if key is None or key in sampled or type(row.get('rss_bytes')) is not int or row['rss_bytes']<0:return False
        sampled[key]=row['rss_bytes']
    for row in sample['departed']:
        key=identity(row)
        if key is None or key in departed or key in sampled or row.get('rss_bytes') is not None:return False
        replacement=row.get('replacement_create_time')
        if row.get('state')=='fresh_confirmed_absent':
            if replacement is not None:return False
        elif row.get('state')=='fresh_confirmed_reused':
            if type(replacement) not in (int,float) or not math.isfinite(replacement) or replacement<=0 or replacement==key[1]:return False
        else:return False
        departed[key]=row
    if root not in departed or root in sampled or own not in sampled:return False
    worker_rss=sum(value for key,value in sampled.items() if key!=own)
    return (type(terminal.get('sampled_known_worker_rss_bytes')) is int
        and terminal['sampled_known_worker_rss_bytes']==worker_rss
        and worker_rss<=1536*2**20 and worker_rss+sampled[own]<=2048*2**20)


def need(value,code):
    if not value:raise AssertionError(code)


def loss_telemetry(record,recipe,verifier,r4,partition):
    """Same fixed LOSS backend proof extended only to full-refit fitting rows."""
    profile=recipe.get('params',{}).get('loss_profile_id')
    catalog={'lgbm_l2_v1':('regression',None),'lgbm_l1_v1':('regression_l1',None),'lgbm_huber_a09_v1':('huber',.9)}
    need(profile in catalog and verifier.spec['kind']=='regression','known_regression_loss_only')
    objective,alpha=catalog[profile];full=record.get('full_fit') is True
    tr,_=r4.split(partition,len(verifier.train))
    if full:parents=[r4.np.arange(len(verifier.train),dtype=r4.np.int64)];scopes=['full_refit'];stops=[False]
    else:
        need(record.get('early_stopping_source')=='inner_training_holdout' and record.get('inner_split_error') is None,'nested_loss_stopping_required')
        spec=verifier.spec;column=spec['time_column'];need(spec.get('validation_strategy')=='time'
            and (spec.get('time_candidate') or {}).get('split_mode')=='period','same_period_scope_required')
        values=r4.pd.to_numeric(verifier.train[column],errors='raise').to_numpy(dtype=float);local=values[tr]
        latest=r4.np.unique(local)[-1];inner=tr[r4.np.flatnonzero(local<latest)]
        parents=[inner,tr];scopes=['inner_fitting','outer_fitting'];stops=[True,False]
    rows=record.get('data_policy_runs');need(type(rows) is list and len(rows)==len(parents),'actual_loss_fit_receipts_required')
    proofs=[]
    for index,(row,parent,scope,stopping) in enumerate(zip(rows,parents,scopes,stops),1):
        proof=row.get('loss_profile');target=verifier.train[verifier.spec['target']].iloc[parent].to_numpy(dtype=float)
        scale='log1p' if recipe['params'].get('log_target',False) and target.min()>=0 else 'original'
        need(row.get('source_rows')==len(parent) and row.get('output_rows')==len(parent)
            and row.get('source_parent_sha256')==r4.canonical(parent.tolist()) and row.get('synthetic_rows')==0,
            'loss_fitting_parent_lineage_changed')
        need(isinstance(proof,dict) and proof.get('loss_profile_id')==profile and proof.get('requested_objective')==objective
            and proof.get('effective_objective')==objective and proof.get('requested_alpha')==alpha
            and (alpha is None or proof.get('effective_alpha')==alpha) and proof.get('requested_metric')=='None'
            and proof.get('verified') is True and proof.get('evidence_source')=='fitted_booster.params'
            and proof.get('library')=='lightgbm' and proof.get('library_version')=='4.6.0' and proof.get('fit_index')==index
            and proof.get('model_scope')==scope and proof.get('validation_used_for_stopping') is stopping
            and proof.get('primary_metric')=='rmse' and proof.get('target_scale')==scale,'actual_booster_loss_proof_changed')
        metric=proof.get('effective_metric');metric=[metric] if isinstance(metric,str) else metric
        need(type(metric) is list and metric and all(type(v) is str and v.lower() in {'none','na','null','custom'} for v in metric),
             'actual_default_loss_metric_not_disabled')
        proofs.append(proof)
    need(record.get('loss_profile_id')==profile and record.get('effective_loss_profile')==proofs[-1],'effective_loss_receipt_mismatch')
    return dict(profile_id=profile,actual_postfit_receipts=proofs,full_fit=full)
