"""Fixed tabular representation contracts; no model/data-frame imports."""
from dataclasses import dataclass,asdict


@dataclass(frozen=True)
class RepresentationProfile:
    representation_profile:str
    transform:str
    components:int|None
    gamma_rule:str|None
    seed:int=42
    ridge_alpha:float=10.
    logistic_C:float=1.
    class_weight_power:float=.5
    matrix_limit_bytes:int=128_000_000
    maximum_rows:int=200_000
    maximum_columns:int=64
    maximum_prepared_columns:int=4096
    maximum_categories:int=64
    maximum_fitting_category_levels:int=4096
    prediction_batch_rows:int=512
    def to_dict(self):return asdict(self)


REPRESENTATION_PROFILES=(
    RepresentationProfile('tabular_linear_bounded_v1','identity',None,None),
    RepresentationProfile('tabular_rbf128_invdim_v1','rbf',128,'1/prepared_fitting_dimension'),
)


def representation_catalog():
    """Separate opt-in backend catalog. Ordinary planner capabilities stay fixed."""
    return tuple(profile.to_dict() for profile in REPRESENTATION_PROFILES)


def resolve_representation_profile(engine,params):
    if 'representation_profile' not in params:return None
    requested=params['representation_profile']
    if type(requested) is not str:raise ValueError('representation_profile must be a fixed string ID')
    matches=[p for p in REPRESENTATION_PROFILES if p.representation_profile==requested]
    if not matches:raise ValueError('Unknown representation_profile')
    if engine!='linear_text':raise ValueError('Representation profiles require linear_text engine')
    allowed={'representation_profile','generic_features','early_metric','nested_stopping',
             'min_iterations','seed','class_weight_power'}
    if set(params)-allowed:raise ValueError('Fixed representation profile received unsupported parameters')
    for name,expected in [('generic_features','none'),('early_metric','primary'),('nested_stopping',False),
                          ('min_iterations',100),('seed',42),('class_weight_power',.5)]:
        if name in params and ((type(expected) is bool and type(params[name]) is not bool)
                               or (type(params[name]) is bool and type(expected) is not bool) or params[name]!=expected):
            raise ValueError('Fixed representation profile conflicts with '+name)
    return matches[0]


def validate_representation_recipe(recipe,spec=None):
    if 'representation_profile' in recipe:raise ValueError('representation_profile belongs in params')
    profile=resolve_representation_profile(recipe.get('engine'),recipe.get('params',{}))
    if profile is not None:
        if recipe.get('feature_code',''):raise ValueError('Fixed representation requires unchanged raw features')
        from automl.contracts.messages import DataPolicy
        if not DataPolicy.parse(recipe.get('data_policy')).is_noop:
            raise ValueError('Fixed representation requires noop data policy')
        if spec is not None:
            if (spec.get('kind'),spec.get('metric')) not in {('regression','rmse'),('classification','macro_f1')}:
                raise ValueError('Representation profiles require original RMSE or MacroF1')
            if spec.get('text_features') or spec.get('task_family')=='pointwise_ranking':
                raise ValueError('Representation profiles require nontext tabular tasks')
    if recipe.get('engine')=='ensemble':
        for child in recipe.get('components',[]):validate_representation_recipe(child,spec)
    return profile
