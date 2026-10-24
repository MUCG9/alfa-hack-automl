"""Pure fixed-release objective authority, shared before numerical imports."""
from automl_task_understanding_metric_contract import resolve_metric_spec


def resolved_policy(text):
    """Only explicit supported objectives authorize a fixed family; no defaults."""
    candidates=[]
    for kind, name in [('regression','rmse'),('classification','macro_f1')]:
        metric=resolve_metric_spec(text,kind)
        if metric.status=='resolved' and metric.name==name:
            candidates.append((kind,metric))
    if len(candidates)!=1:
        raise ValueError('Unresolved, conflicting or unsupported fixed-release objective')
    return candidates[0]
