"""V16 CLASS policy, current strict worker/lexical authority, original deadline."""
from pathlib import Path
from types import SimpleNamespace
import time
from automl_fixed_release import load_fixed_inputs,validate_output_identity
from automl_release_authority import resolved_policy
from automl_release_runtime import ReleaseClock
from automl_infrastructure_run_budget import RunBudget
import automl_v16_class_runner as runner


def inherited_budget(authority,root):
    """Initialize the existing budget fields from observed origin, no new clock."""
    budget=RunBudget.__new__(RunBudget)
    budget.clock=time.monotonic
    budget.started=authority.start_monotonic
    budget.deadline=authority.deadline_monotonic
    budget.seconds=budget.deadline-budget.started
    budget.max_calls=0;budget.calls_started=0;budget.events=[]
    budget.trace_root=Path(root)/'automl_runs';budget.trace=None
    budget.status='running';budget.exception_type=None
    return budget


def execute_class(task,authority):
    authority.check()
    seconds=authority.deadline_monotonic-authority.start_monotonic
    clock=ReleaseClock(seconds,Path(task).parent,origin=(authority.start_unix,authority.start_monotonic))
    kind,metric=resolved_policy(Path(task).read_text(encoding='utf-8-sig'));clock.check()
    if kind!='classification':raise ValueError('delegated_class_kind_changed')
    loaded=load_fixed_inputs(task,kind,clock)
    task_data=runner.discover(task,loaded=loaded,allow_llm=False)
    spec=task_data[0]
    if (spec['kind']!=kind or spec['metric']!=metric.name
            or spec['target']!=loaded['declared_target'] or spec.get('id')!=loaded['declared_identifier']):
        raise ValueError('V16 class discovery differs from explicit objective/role authority')
    protected={**{'input:'+k:v for k,v in loaded['paths'].items()},'task':task,
        **{'source:'+p.name:p for p in runner.source_files()}}
    protected['requirements']=Path(__file__).with_name('requirements.txt')
    output=Path(task).parent/'submission.csv'
    validate_output_identity(output,protected)
    original_save,original_checkpoint=runner.save_submission,runner.checkpoint
    def safe_save(spec,sample,test,predictions,path):
        clock.check();validate_output_identity(path,protected)
        validate_output_identity(Path(path).with_suffix('.csv.tmp'),protected)
        result=original_save(spec,sample,test,predictions,path);clock.check();return result
    def safe_checkpoint(record,path):
        clock.check();validate_output_identity(path,protected)
        validate_output_identity(Path(path).with_suffix('.csv.tmp'),protected)
        result=original_checkpoint(record,path);clock.check();return result
    args=SimpleNamespace(task=task,time_budget=9900,max_experiments=12,max_planner_calls=4,
        max_llm_calls=0,offline=True,validation_strategy='auto',run_name='v16-class-release')
    token=runner._CLASS_RELEASE_CLOCK.set(clock)
    runner.save_submission=safe_save;runner.checkpoint=safe_checkpoint
    try:
        with inherited_budget(authority,Path(task).parent):
            clock.check(force=True)
            report=runner.solve_single(args,task_data)
            clock.check(force=True)
            if report.get('integrity_ok') is not True or report.get('final_fit_status')!='ok':
                raise RuntimeError('V16_class_requires_successful_fresh_full_refit')
            return dict(policy='V16_offline_portfolio_confirmation_blend',
                final_fit_status=report['final_fit_status'],integrity_ok=True,
                selected_recipe=report['selected_recipe'],
                final_fit_iterations=report['final_fit_iterations'],
                submission_sha256=report['submission_sha256'],
                original_clock=clock.receipt(),quality_metric=None,Qwen_calls=0,API_calls=0)
    finally:
        runner.save_submission=original_save;runner.checkpoint=original_checkpoint
        runner._CLASS_RELEASE_CLOCK.reset(token)
