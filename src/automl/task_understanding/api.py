"""Public task-discovery boundary; v2 return ordering remains supported."""
from automl.task_understanding.service import discover,find_input,metric_from_text,load_inputs,MultipleTargets,StrictTaskContractError,validate_declared_inputs,_strict_objective as strict_objective
from automl.task_understanding.early_declaration import bootstrap_early_declaration,DeclarationLimits
from automl.task_understanding.early_output import prepare_early_output
