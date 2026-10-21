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


def generic_features(train_x,test_x,fit_rows,mode):
    """Feature choices learned on fitting rows only; all transforms are row-wise."""
    if mode not in {'missing','skew','both'}:
        return train_x,test_x
    train_x=train_x.copy(); test_x=test_x.copy()
    fit=train_x.iloc[fit_rows]
    numeric=[c for c in fit if pd.api.types.is_numeric_dtype(fit[c])]
    missing=sorted(numeric,key=lambda c:float(fit[c].isna().mean()),reverse=True)
    if mode in {'missing','both'}:
        for column in [c for c in missing if .01<float(fit[c].isna().mean())<.99][:12]:
            for frame in [train_x,test_x]: frame[f'__missing_{column}']=frame[column].isna().astype('int8')
    if mode in {'skew','both'}:
        skew=fit[numeric].skew().abs().sort_values(ascending=False)
        for column in skew[skew>2].head(12).index:
            for frame in [train_x,test_x]:
                values=pd.to_numeric(frame[column],errors='coerce')
                frame[f'__signed_log_{column}']=np.sign(values)*np.log1p(np.abs(values))
    return train_x,test_x

