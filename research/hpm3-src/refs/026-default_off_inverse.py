"""Closed SOURCE/AST inverse for this exact producer overlay; no target import.

This is an integration proof tool, not a runtime feature switch. Its exact
normalized source SHA allowlist is checked before ANY AST transformation.
Unknown edits remain in old code and fail the final whole-module comparison.
"""
import ast
from copy import deepcopy
import hashlib

CANDIDATE_TEXT_SHA256={
    'src/automl/search/runner.py':'86ee2f295fe73c32723e4dedad1dc02ba5d9f79f212f66ff109437c3e455724c',
    'src/automl/search/hpo.py':'837b28c5a4da1f8ff2f547d58b66ff626156ce357d7bd1185b281b5335f90cfa',
    'src/automl/execution/worker.py':'2f629eb465a80ed6d1ea5cdccdb3c53bcac249570291281e212480c0208281bc',
}

RUNNER_HELPERS={'_hpo_trial_bank_options','_hpo_trial_bank_manifest',
    '_hpo_trial_bank_strict_authority','_optimize_with_trial_bank','_hpo_trial_bank_checkpoint'}
WORKER_HELPERS={'_bank_recorder','_bank_value','_bank_callable','_bank_native',
    '_bank_before_fit','_bank_after_fit','_bank_aggregate'}


def names(node):return {n.id for n in ast.walk(node) if isinstance(n,ast.Name)}
def assigned(node):
    return {t.id for t in node.targets if isinstance(t,ast.Name)} if isinstance(node,ast.Assign) else set()
def called(node,name):
    return isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id==name


def project(relative,source):
    """Return the OFF tree and exact removed-node fingerprints for review."""
    if (type(source) is not str or relative not in CANDIDATE_TEXT_SHA256
            or hashlib.sha256(source.encode('utf-8')).hexdigest()!=CANDIDATE_TEXT_SHA256[relative]):
        raise ValueError('exact_reviewed_producer_source_required_before_OFF_projection')
    tree=ast.parse(source);removed=[]
    def drop(node):
        removed.append(dict(kind=type(node).__name__,AST_sha256=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()))
        return None
    class Overlay(ast.NodeTransformer):
        def visit_FunctionDef(self,node):
            if relative.endswith('/runner.py') and node.name in RUNNER_HELPERS:return drop(node)
            if relative.endswith('/worker.py') and node.name in WORKER_HELPERS:return drop(node)
            if relative.endswith('/hpo.py') and node.name=='_bind_trial_bank':return drop(node)
            node=self.generic_visit(node)
            if relative.endswith('/hpo.py') and node.name in {'optimize_recipe','_optimize_recipe_fair_reserve'}:
                assert node.args.args[-1].arg=='bank_producer'
                node.args.args.pop();node.args.defaults.pop()
            return node

        def visit_Assign(self,node):
            target=assigned(node)
            if relative.endswith('/runner.py') and target & {'_HPO_TRIAL_BANK_AUTHORITY','_HPO_TRIAL_BANK_ACTIVE',
                    'bank_options','bank_token','bank_producer','bank_seen'}:return drop(node)
            if relative.endswith('/worker.py') and target & {'bank_identity','bank_token'}:return drop(node)
            return self.generic_visit(node)

        def visit_If(self,node):
            test=names(node.test)
            if relative.endswith('/runner.py') and test & {'bank_options','bank_producer'}:return drop(node)
            if relative.endswith('/worker.py') and (test & {'bank_identity'} or any(
                    isinstance(n,ast.Constant) and n.value=='_hpo_trial_bank' for n in ast.walk(node.test))):return drop(node)
            if relative.endswith('/hpo.py') and 'bank_producer' in test:return drop(node)
            return self.generic_visit(node)

        def visit_Try(self,node):
            if relative.endswith('/runner.py') and any('bank_token' in names(n) for n in node.finalbody):
                assert not node.handlers and not node.orelse
                # Keep EVERY original operation inside the new context scope.
                return [self.visit(n) for n in node.body]
            return self.generic_visit(node)

        def visit_Expr(self,node):
            if relative.endswith('/runner.py'):
                if called(node,'_hpo_trial_bank_checkpoint') or called(node,'_hpo_trial_bank_options'):return drop(node)
                call=node.value
                if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='add_argument':
                    if call.args and isinstance(call.args[0],ast.Constant) and call.args[0].value in {'--hpo-trial-bank','--hpo-trial-bank-sha256'}:return drop(node)
            return self.generic_visit(node)

        def visit_Call(self,node):
            node=self.generic_visit(node)
            if relative.endswith('/runner.py') and isinstance(node.func,ast.Name) and node.func.id=='_optimize_with_trial_bank':
                assert isinstance(node.args[0],ast.Name) and node.args[0].id=='optimize_recipe'
                node.func=deepcopy(node.args.pop(0))
            if relative.endswith('/hpo.py') and isinstance(node.func,ast.Name) and node.func.id=='_optimize_recipe_fair_reserve':
                assert [k.arg for k in node.keywords]==['bank_producer'];node.keywords=[]
            return node

    result=Overlay().visit(tree)
    if relative.endswith('/worker.py'):
        # Retain the actual dict expression and actual publication destination;
        # do not replace an old numerical/model body with a golden copy.
        fn=next(n for n in result.body if isinstance(n,ast.FunctionDef) and n.name=='run_ensemble')
        index=next(i for i,n in enumerate(fn.body) if assigned(n)=={'ensemble_record'})
        value=fn.body[index].value;publish=fn.body[index+1]
        assert called(publish,'atomic_json') and isinstance(publish.value.args[1],ast.Name) and publish.value.args[1].id=='ensemble_record'
        publish.value.args[1]=value;fn.body.pop(index)
    return ast.fix_missing_locations(result),removed
