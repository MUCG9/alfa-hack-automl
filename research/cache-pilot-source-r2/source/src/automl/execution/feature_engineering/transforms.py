import ast
import numpy as np
import pandas as pd
def feature_transform(code, train_x, test_x, forbidden_columns=()):
    if not code or not code.strip():
        return train_x.copy(),test_x.copy()
    tree=ast.parse(code)
    banned_names={'open','eval','exec','compile','__import__','getattr','setattr','globals','locals','vars','input','breakpoint'}
    banned_attrs={'to_csv','to_pickle','to_parquet','to_sql','to_json','read_csv','read_pickle','read_parquet','read_sql','load','save','system','popen'}
    numpy_functions={'abs','arctan2','clip','cos','deg2rad','e','exp','expm1','finfo','float32','float64','full','hypot',
        'int8','int16','int32','int64','isfinite','isnan','log','log1p','maximum','minimum','nan','nan_to_num',
        'pi','radians','select','sign','sin','sqrt','square','tanh','where','zeros','ones'}
    pandas_functions={'DataFrame','Series','to_numeric','isna','notna','NA','Timestamp','to_datetime','cut','qcut'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in forbidden_columns:
            raise ValueError('Feature code references an unavailable target/ID column; use params.log_target for regression target transformations')
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.ClassDef,ast.AsyncFunctionDef)):
            raise ValueError('Feature code may only define a synchronous transform function without imports')
        if isinstance(node,ast.Name) and (node.id in banned_names or node.id.startswith('__')):
            raise ValueError('Disallowed feature-code name')
        if isinstance(node,ast.Attribute):
            safe_pandas_conversion=isinstance(node.value,ast.Name) and node.value.id=='pd' and node.attr in pandas_functions
            if node.attr.startswith('_') or node.attr in banned_attrs|{'eval','query','fromfile','memmap','loadtxt','genfromtxt','savetxt','dump','dumps','write','writelines'} or node.attr.startswith('read_') or (node.attr.startswith('to_') and not safe_pandas_conversion):
                raise ValueError('Disallowed feature-code attribute')
            if isinstance(node.value,ast.Name) and node.value.id in {'np','pd'}:
                allowed=numpy_functions if node.value.id=='np' else pandas_functions
                if node.attr not in allowed: raise ValueError('Unsupported module function in feature code')
    scope={'pd':pd,'np':np,'__builtins__':{'len':len,'str':str,'float':float,'int':int,
           'list':list,'dict':dict,'range':range,'enumerate':enumerate,'zip':zip,
           'min':min,'max':max,'abs':abs,'isinstance':isinstance,'sum':sum,'sorted':sorted}}
    exec(compile(tree,'<qwen_feature_code>','exec'),scope)
    if not callable(scope.get('transform')):
        raise ValueError('Feature code must define transform(df)')
    transformed=[]
    for source in [train_x,test_x]:
        value=scope['transform'](source.copy())
        if not isinstance(value,pd.DataFrame) or len(value)!=len(source) or not value.index.equals(source.index):
            raise ValueError('Feature code changed row count/order/index')
        if value.columns.duplicated().any() or len(value.columns)>len(source.columns)+32:
            raise ValueError('Feature code created duplicate or too many columns')
        transformed.append(value)
    if list(transformed[0].columns)!=list(transformed[1].columns):
        raise ValueError('Feature schemas differ between train and test')
    # Reject transformations depending on validation/other-row statistics.
    if len(train_x)>8:
        subset=train_x.iloc[::2].copy()
        check=scope['transform'](subset)
        try:
            pd.testing.assert_frame_equal(check,transformed[0].loc[subset.index],check_dtype=False,check_exact=False,rtol=1e-6,atol=1e-8)
        except (AssertionError,TypeError,ValueError) as exc:
            raise ValueError('Feature code depends on other rows; fitting/statistics must stay inside training split') from exc
    return transformed


GENERIC_FEATURE_MODES = frozenset({'none', 'missing', 'skew', 'both', 'broad'})
BROAD_MAX_PRIMITIVES = 64
BROAD_MAX_INTERACTIONS = 64


def _feature_inputs(train_x, test_x, fit_rows):
    if not isinstance(train_x, pd.DataFrame) or not isinstance(test_x, pd.DataFrame):
        raise ValueError('Feature generation requires DataFrames')
    if (not train_x.columns.is_unique or not test_x.columns.is_unique
            or list(train_x.columns) != list(test_x.columns)):
        raise ValueError('Feature generation requires equal unique column schemas')
    rows = np.asarray(fit_rows)
    if (rows.ndim != 1 or not len(rows) or not np.issubdtype(rows.dtype, np.integer)
            or (rows < 0).any() or (rows >= len(train_x)).any()
            or len(np.unique(rows)) != len(rows)):
        raise ValueError('Fitting rows must be unique nonempty positional indices')
    return rows


def _numeric_values(series):
    return pd.to_numeric(series, errors='coerce').to_numpy(dtype='float64', na_value=np.nan)


def _check_feature_names(train_x, test_x, names):
    if len(names) != len(set(names)) or any(name in train_x or name in test_x for name in names):
        raise ValueError('Generated feature name collision; original columns must be preserved')


def _broad_plan(train_x, rows):
    """Learn only the bounded column choices, never statistics from query rows.

    At most 256 source columns are profiled; row missingness still covers all
    original columns. Numeric-looking objects are inferred from fitting values,
    so a malformed held-out value cannot switch a fitting column to categorical.
    """
    numeric = []
    missing = []
    texts = []
    for position, column in enumerate(train_x.columns[:256]):
        values = train_x[column].iloc[rows]
        rate = float(values.isna().mean())
        if rate > 0:
            missing.append((-rate, position, column, False))
        if pd.api.types.is_datetime64_any_dtype(values.dtype) or pd.api.types.is_complex_dtype(values.dtype):
            continue
        parsed = _numeric_values(values)
        finite = np.isfinite(parsed)
        observed = values.notna().to_numpy()
        native = pd.api.types.is_numeric_dtype(values.dtype)
        inferred_numeric = native or (finite.any() and finite.sum() / max(1, observed.sum()) >= .95)
        if inferred_numeric:
            valid = parsed[finite]
            unique = len(np.unique(valid))
            if unique >= 3:
                # Uniqueness and coverage avoid ranking by arbitrary units.
                numeric.append((-unique, -float(finite.mean()), position, column))
            missing = [item for item in missing if item[2] != column]
            if (~finite).any():
                missing.append((-float((~finite).mean()), position, column, True))
        elif not native and observed.any():
            strings = values.astype('string').fillna('')
            if float(strings.str.len().mean()) >= 12 or float(strings.str.contains(r'\s', regex=True).mean()) >= .1:
                texts.append((position, column))
    numeric.sort()
    missing.sort()
    columns = [item[3] for item in numeric]
    positions = {column: position for position, column in enumerate(train_x.columns)}
    plan = [('__broad_row_missing_count', 'row_missing_count', ()),
            ('__broad_row_missing_fraction', 'row_missing_fraction', ())]
    if columns:
        for operation in ['mean', 'std', 'min', 'max', 'abs_mean', 'zero_count', 'negative_count', 'finite_count']:
            plan.append((f'__broad_numeric_{operation}', 'row_' + operation, tuple(columns[:24])))
    for _, position, column, numeric_missing in missing[:16]:
        plan.append((f'__broad_missing_{position}', 'numeric_missing' if numeric_missing else 'missing', (column,)))
    for column in columns[:20]:
        plan.append((f'__broad_log_{positions[column]}', 'signed_log', (column,)))
    for column in columns[:10]:
        plan.append((f'__broad_sqrt_{positions[column]}', 'signed_sqrt', (column,)))
    for position, column in texts[:4]:
        plan.append((f'__broad_text_length_{position}', 'text_length', (column,)))
        plan.append((f'__broad_text_words_{position}', 'text_words', (column,)))
    plan = plan[:BROAD_MAX_PRIMITIVES]
    # Up to 16 unordered pairs, four expressions per pair. Eight source arrays
    # bound the query cache; there is no n-by-p-by-p interaction tensor.
    from itertools import combinations
    for left, right in list(combinations(columns[:8], 2))[:BROAD_MAX_INTERACTIONS // 4]:
        for operation in ['difference', 'product', 'ratio', 'log_ratio']:
            name = f'__broad_{operation}_{positions[left]}_{positions[right]}'
            plan.append((name, operation, (left, right)))
    return plan


def _broad_frame(frame, plan):
    """Apply a fixed plan row by row, preserving every original value and index."""
    additions = {}
    numeric_cache = {}
    row_cache = {}
    pair_columns = {c for _, operation, columns in plan
                    if operation in {'difference', 'product', 'ratio', 'log_ratio'} for c in columns}

    def numeric(column):
        if column in numeric_cache:
            return numeric_cache[column]
        values = _numeric_values(frame[column])
        if column in pair_columns:
            numeric_cache[column] = values
        return values

    for name, operation, columns in plan:
        if operation in {'row_missing_count', 'row_missing_fraction'}:
            if 'missing_count' not in row_cache:
                count = np.zeros(len(frame), dtype='float64')
                for column in frame:
                    count += frame[column].isna().to_numpy()
                row_cache['missing_count'] = count
            value = row_cache['missing_count']
            if operation.endswith('fraction'):
                value = value / max(1, len(frame.columns))
        elif operation.startswith('row_'):
            if 'finite_count' not in row_cache:
                count = np.zeros(len(frame), dtype='float64')
                total = count.copy(); squares = count.copy(); absolute = count.copy()
                zero = count.copy(); negative = count.copy()
                low = np.full(len(frame), np.inf); high = np.full(len(frame), -np.inf)
                for column in columns:
                    source = numeric(column)
                    valid = np.isfinite(source)
                    source = np.where(valid, np.clip(source, -1e15, 1e15), 0.)
                    count += valid; total += source; squares += source * source
                    absolute += np.abs(source); zero += valid & (source == 0); negative += valid & (source < 0)
                    low = np.minimum(low, np.where(valid, source, np.inf))
                    high = np.maximum(high, np.where(valid, source, -np.inf))
                mean = total / np.maximum(count, 1)
                row_cache.update(finite_count=count, mean=mean,
                                 std=np.sqrt(np.maximum(0., squares / np.maximum(count, 1) - mean * mean)),
                                 min=np.where(count, low, 0.), max=np.where(count, high, 0.),
                                 abs_mean=absolute / np.maximum(count, 1), zero_count=zero, negative_count=negative)
            value = row_cache[operation[4:]]
        elif operation.startswith('text_'):
            text = frame[columns[0]].astype('string').fillna('')
            value = (text.str.len() if operation == 'text_length' else text.str.count(r'\S+')).to_numpy(dtype=float)
        elif operation in {'missing', 'numeric_missing'}:
            source = frame[columns[0]]
            value = ~np.isfinite(numeric(columns[0])) if operation == 'numeric_missing' else source.isna().to_numpy()
        else:
            left = numeric(columns[0])
            left = np.where(np.isfinite(left), np.clip(left, -1e15, 1e15), 0.)
            if operation == 'signed_log':
                value = np.sign(left) * np.log1p(np.abs(left))
            elif operation == 'signed_sqrt':
                value = np.sign(left) * np.sqrt(np.abs(left))
            else:
                right = numeric(columns[1])
                right = np.where(np.isfinite(right), np.clip(right, -1e15, 1e15), 0.)
                if operation == 'difference': value = left - right
                elif operation == 'product': value = left * right
                elif operation == 'ratio': value = np.divide(left, right, out=np.zeros(len(frame)), where=np.abs(right) > 1e-8)
                else: value = np.log1p(np.abs(left)) - np.log1p(np.abs(right))
        # Raw values remain unchanged. Every derived numeric value is finite,
        # including absent/huge/invalid query values and zero denominators.
        additions[name] = np.clip(np.nan_to_num(value, nan=0., posinf=1e30, neginf=-1e30), -1e30, 1e30).astype('float32')
    return pd.concat([frame, pd.DataFrame(additions, index=frame.index, copy=False)], axis=1, copy=False)


def generic_features(train_x, test_x, fit_rows, mode):
    """Fit column choices on ``fit_rows`` and apply one schema to both frames.

    Modes: none/missing/skew/both/broad. Broad adds at most 64 primitive and
    64 interaction float32 columns. Its transforms use row-local information;
    raw columns and row order are preserved. No targets or IDs are accepted as
    a separate input; the worker must continue to exclude them from X.
    """
    if not isinstance(mode, str) or mode not in GENERIC_FEATURE_MODES:
        raise ValueError('Unsupported generic feature mode')
    if mode == 'none':
        return train_x, test_x
    rows = _feature_inputs(train_x, test_x, fit_rows)
    if mode == 'broad':
        plan = _broad_plan(train_x, rows)
        _check_feature_names(train_x, test_x, [name for name, _, _ in plan])
        return _broad_frame(train_x, plan), _broad_frame(test_x, plan)
    fit = train_x.iloc[rows]
    numeric = [c for c in fit if pd.api.types.is_numeric_dtype(fit[c])]
    plan = []
    if mode in {'missing', 'both'}:
        missing = sorted(numeric, key=lambda c: float(fit[c].isna().mean()), reverse=True)
        plan.extend((f'__missing_{column}', 'missing', column)
                    for column in [c for c in missing if .01 < float(fit[c].isna().mean()) < .99][:12])
    if mode in {'skew', 'both'}:
        skew = fit[numeric].skew().abs().sort_values(ascending=False)
        plan.extend((f'__signed_log_{column}', 'signed_log', column) for column in skew[skew > 2].head(12).index)
    _check_feature_names(train_x, test_x, [name for name, _, _ in plan])
    result = []
    for frame in [train_x, test_x]:
        transformed = frame.copy()
        for name, operation, column in plan:
            values = pd.to_numeric(frame[column], errors='coerce')
            transformed[name] = (frame[column].isna().astype('int8') if operation == 'missing'
                                 else np.sign(values) * np.log1p(np.abs(values)))
        result.append(transformed)
    return tuple(result)

