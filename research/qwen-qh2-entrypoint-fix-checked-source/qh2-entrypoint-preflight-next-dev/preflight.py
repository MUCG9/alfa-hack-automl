"""Only entrypoint/helper-pin metadata preflight; never a task admission.

Execute under the existing bounded root metadata caller. No campaign clock,
candidate import, filesystem mutation, process observation or model is created.
"""
from pathlib import Path
import ast
import hashlib
import json
import sys

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
CANONICAL=WORK/'alfa-hack-automl'
TASK=WORK/'qwen-three-hour-autoresearch-next-dev-r7/task_entry.py'
TASK_SHA='4660711d1e7b8b45d972ed35ce7d361530c612dd6f4e73f26b83858c38cce312'
RUNTIME=CANONICAL/'src/automl/infrastructure/runtime.py'
RUNTIME_SHA='c450ef040bd04e55c295c51ff1037147b938afb8e239617cb936bcfc2a9047d8'
OUTER=WORK/'qwen-three-hour-outer-next-dev-r6/run_campaign.py'
OUTER_SHA='714c83160cc0bdb625b6f294f4b76a4f40cc91cc0d4b9683b71ec9d20431823e'
WRAPPER_SHA='d4cde2ce88ed3ac44da5fe17010079690d5c2eff02305902b9b62046d7b529f3'


def need(value,code):
    if not value:raise RuntimeError(code)


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            block=stream.read(2**20)
            if not block:break
            value.update(block)
    return value.hexdigest()


def source(path,expected):
    need(Path(path).suffix=='.py' and Path(path).stat().st_size<=2**20
         and sha(path)==expected,'exact_frozen_metadata_source_required')
    return ast.parse(Path(path).read_text('utf-8-sig'))


def projected_bindings(cfg):
    """Execute unchanged helper loop + conjunction, then exact entry selector."""
    root=Path(cfg['canonical_root']);pins=cfg['immutable_files']
    need(root==CANONICAL and root.is_absolute(),'exact_current_canonical_root_required')
    tree=source(TASK,TASK_SHA)
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    def contains(node,text):
        return any(isinstance(n,ast.Constant) and n.value==text for n in ast.walk(node))
    loops=[n for n in run.body if isinstance(n,ast.For) and contains(n,'exact_qualified_helper_required')]
    guards=[n for n in run.body if isinstance(n,ast.Expr) and contains(n,'candidate_current_processes_distinct_from_historical_guard')]
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1
        and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'COOR_SHA','OWNER_SHA','PROCESS_SHA'}]
    original_need=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='need']
    need(len(loops)==len(guards)==len(original_need)==1 and len(constants)==3,'exact_entry_metadata_nodes_required')
    scope={'Path':Path,'cfg':cfg,'root':root,'pins':pins}
    exec(compile(ast.Module(body=original_need+constants+loops+guards,type_ignores=[]),str(TASK),'exec'),scope)
    runtime=source(RUNTIME,RUNTIME_SHA)
    functions=[n for n in runtime.body if isinstance(n,ast.FunctionDef) and n.name=='worker_entrypoint']
    need(len(functions)==1,'exact_worker_entrypoint_node_required')
    worker={'project_root':lambda:root}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(RUNTIME),'exec'),worker)
    selected=worker['worker_entrypoint']()
    need(selected==root/'agent_worker.py' and pins.get(str(selected))==WRAPPER_SHA
         and sha(selected)==WRAPPER_SHA and pins.get(str(RUNTIME))==RUNTIME_SHA,
         'exact_actual_worker_entrypoint_bytes_required')
    return selected


def projected_task(parent,row,output):
    """Copy the exact frozen outer assignment; timing remains an empty witness."""
    tree=source(OUTER,OUTER_SHA)
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1
        and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='task_cfg']
    need(len(assignments)==1,'exact_parent_task_assignment_required')
    scope={'cfg':parent,'row':row,'output':Path(output),'pins':dict(parent['immutable_files']),'timing':{}}
    exec(compile(ast.Module(body=assignments,type_ignores=[]),str(OUTER),'exec'),scope)
    task=scope['task_cfg']
    need(task['immutable_files']==parent['immutable_files']
         and task['immutable_files'] is not parent['immutable_files'],'exact_parent_to_task_pin_copy_required')
    return task


def validate(parent):
    selected=projected_bindings(parent)
    need([row['task']['kind'] for row in parent['tasks']]==['regression','classification'],'two_task_metadata_rows_required')
    for index,row in enumerate(parent['tasks']):
        task=projected_task(parent,row,Path(parent['output'])/('r' if index==0 else 'c'))
        need(projected_bindings(task)==selected,'same_actual_entrypoint_in_every_task_required')
    return dict(entrypoint_binding_passed=True,parent_to_task_pin_propagation_passed=True,
        wrapper_sha256=WRAPPER_SHA,task_predicate_sha256=TASK_SHA,runtime_selector_sha256=RUNTIME_SHA,
        outer_assignment_source_sha256=OUTER_SHA,task_count=2,candidate_imports=0,models=0,API=0,
        process_observations=0,campaign_clock_assigned=False,runtime_admitted=False)


if __name__=='__main__':
    need(len(sys.argv)==3,'exact_manifest_and_SHA_arguments_required')
    path=Path(sys.argv[1]);need(path.is_absolute() and path.suffix=='.json'
        and path.stat().st_size<=2**20 and sha(path)==sys.argv[2],'exact_private_metadata_required')
    print(json.dumps(validate(json.loads(path.read_text('utf-8'))),sort_keys=True))
