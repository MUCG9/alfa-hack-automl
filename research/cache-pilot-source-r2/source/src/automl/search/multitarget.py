"""Independent-target orchestration with one shared wall-clock and planner budget."""
from pathlib import Path
import copy,hashlib,time
from automl.task_understanding.api import discover,load_inputs
from automl.publishing.api import save_submission,dummy_predictions,publish_targets,checkpoint
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.runtime import source_files
from automl.infrastructure.run_budget import constrain_deadline,budget_metadata
from automl.infrastructure.processes import ProcessCleanupError


def fingerprints(paths):
    values={}
    for name,path in paths.items():
        digest=hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda:stream.read(2**20),b''): digest.update(block)
        values[name]=digest.hexdigest()
    return values


def solve_many(args,targets,solve_single,loaded=None):
    started=time.monotonic(); deadline=constrain_deadline(started+args.time_budget)
    if not 2<=len(targets)<=16 or len(set(targets))!=len(targets):
        raise ValueError('Independent multi-target mode supports 2..16 distinct targets')
    loaded=load_inputs(args.task) if loaded is None else loaded
    if loaded['task_path']!=args.task.resolve(): raise ValueError('Cached multi-target inputs belong to another task')
    root=Path(loaded['root'])
    runs=root/'automl_runs'/('multi-target-'+str(time.time_ns())); runs.mkdir(parents=True)
    output=root/'submission.csv'; sample=loaded['sample']; tasks=[]; parts=[]
    paths={'task':args.task.resolve(),**loaded['paths'],**{'source:'+str(p):p for p in source_files()}}
    before=fingerprints(paths)
    atomic_json(runs/'provenance.json',{'source_and_input_sha256':before,'targets':list(targets)})
    # Every target gets a valid baseline before any long model search begins.
    for index,target in enumerate(targets):
        task_data=discover(args.task,target_override=target,loaded=loaded)
        spec,_,train,test,projected_sample,*_=task_data
        directory=runs/f'target-{index:02d}'; directory.mkdir()
        if spec['output_columns']!=[target]: raise ValueError('Per-target class probability matrices are not implemented')
        baseline=directory/'baseline.csv'
        save_submission(spec,projected_sample,test,dummy_predictions(spec,train,len(test)),baseline)
        child_output=directory/'submission.csv'; checkpoint({'submission':baseline},child_output)
        parts.append((spec,child_output)); tasks.append((task_data,directory,baseline))
    allowed=set(targets)|{s['id'] for s,_ in parts if s['id'] is not None}
    if set(sample)-allowed: raise ValueError('Unmapped multi-target sample columns')
    publish_targets(parts,sample,output)
    children=[]; remaining_calls=max(0,min(8,args.max_planner_calls))
    for index,(task_data,directory,baseline) in enumerate(tasks):
        remaining=deadline-time.monotonic(); count=len(tasks)-index
        child_args=copy.copy(args)
        child_args.time_budget=max(1,int((remaining-10)/count))
        child_args.max_planner_calls=remaining_calls//count
        remaining_calls-=child_args.max_planner_calls
        record={'target':targets[index],'budget_seconds':child_args.time_budget,
                'planner_call_budget':child_args.max_planner_calls,'output_root':str(directory)}
        if child_args.time_budget<90:
            record.update(status='budget_skipped_baseline',trained=False)
        else:
            try:
                report=solve_single(child_args,task_data=task_data,output_root=directory)
                record.update(status='completed',trained=report['best_validation'] is not None,
                    final_fit_status=report['final_fit_status'],best_validation=report['best_validation'],
                    report=report,score_scope='per-target reused local folds; no aggregate official score is inferred')
            except ProcessCleanupError as exc:
                record.update(status='cleanup_unconfirmed',exception_type=type(exc).__name__,cleanup=exc.receipt)
                children.append(record); atomic_json(runs/'progress.json',{'children':children})
                raise
            except Exception as exc:
                record.update(status='error_preserve_checkpoint',exception_type=type(exc).__name__)
        try: publish_targets(parts,sample,output)
        except (ValueError,OSError):
            checkpoint({'submission':baseline},directory/'submission.csv')
            record['publication_reverted_to_baseline']=True
            record.update(status='invalid_publication_baseline',trained=False)
            publish_targets(parts,sample,output)
        children.append(record); atomic_json(runs/'progress.json',{'children':children})
    integrity=fingerprints(paths)==before
    report={'version':'independent-multi-target-v1','targets':list(targets),'children':children,
            'elapsed_seconds':round(time.monotonic()-started,3),'wall_budget_seconds':args.time_budget,
            'integrity_ok':integrity,'submission':str(output),
            'submission_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'score_scope':'Independent per-target models; no joint model, shared-target features, or aggregate private estimate',**budget_metadata()}
    atomic_json(runs/'report.json',report)
    if not integrity: raise RuntimeError('Multi-target input/source files changed during execution')
    return report
