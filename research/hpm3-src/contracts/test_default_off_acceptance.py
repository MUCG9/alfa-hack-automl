"""Independent synthetic boundary contracts for the reviewed optional producer.

Only exact helper FunctionDefs are compiled during a future authorized test run;
no runner module, learner, arrays, data or provider is imported by this entrypoint.
The runner path derives from the actual hpo_bank package loaded by that runner.
"""
import ast
import builtins
import hashlib
import json
from contextvars import ContextVar
from pathlib import Path
import unittest
from types import SimpleNamespace

from automl.infrastructure import hpo_bank as B


def runner_helper(name, namespace):
    path = Path(B.__file__).resolve().parents[1] / "search" / "runner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError("Exactly one source-bound producer helper is required")
    code = ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[]))
    exec(compile(code, str(path), "exec"), namespace)
    return namespace[name]


class DefaultOffAcceptanceContracts(unittest.TestCase):
    def test_OFF_is_exact_original_call_with_no_producer_import_IO_or_copy(self):
        events = []
        def forbidden(*args, **kwargs):
            events.append((args, kwargs))
            raise AssertionError("Producer OFF must not import or perform bank IO")
        safe_builtins = dict(vars(builtins), __import__=forbidden, open=forbidden)
        authority = ContextVar("synthetic_hpo_bank_authority", default=None)
        namespace = {"__builtins__": safe_builtins,
                     "_HPO_TRIAL_BANK_AUTHORITY": authority,
                     "Path": forbidden, "TrialBankProducer": forbidden}
        helper = runner_helper("_optimize_with_trial_bank", namespace)
        values = [object() for _ in range(8)]
        options = {"trials": object(), "sampler": object(), "fair_reserve": object()}
        returned = object()
        calls = []
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return returned
        answer = helper(original, *values, **options)
        self.assertIs(answer, returned)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][0]), len(values))
        self.assertTrue(all(actual is expected for actual, expected in zip(calls[0][0], values)))
        self.assertEqual(set(calls[0][1]), set(options))
        self.assertTrue(all(calls[0][1][key] is value for key, value in options.items()))
        self.assertEqual(events, [])
        self.assertIsNone(authority.get())


    def test_OFF_options_read_nothing_and_partial_flags_cannot_grant_authority(self):
        events = []
        def forbidden(*args, **kwargs):
            events.append((args, kwargs))
            raise AssertionError("Option validation must not perform bank IO")
        namespace = {"__builtins__": dict(vars(builtins), open=forbidden), "Path": forbidden}
        helper = runner_helper("_hpo_trial_bank_options", namespace)
        off = SimpleNamespace(hpo_trial_bank=None, hpo_trial_bank_sha256=None)
        helper(off)
        self.assertEqual(events, [])
        self.assertIsNone(off.hpo_trial_bank)
        self.assertIsNone(off.hpo_trial_bank_sha256)
        for path, sha in (("synthetic-authority.json", None), (None, "a" * 64)):
            with self.subTest(path_present=path is not None), self.assertRaises(ValueError):
                helper(SimpleNamespace(hpo_trial_bank=path, hpo_trial_bank_sha256=sha,
                    strict_runtime=True, strict_task_contract=True, four_stage=True, hpo_trials=8))
        self.assertEqual(events, [])


    def test_opted_in_exception_restores_exact_active_context_and_rejects_changed_frame(self):
        events = []
        created = []
        frame = object()
        spec = {"kind": "regression", "features": ["x"], "validation_strategy": "random"}
        prior = object()
        active = ContextVar("synthetic_active_producer", default=prior)
        authority_var = ContextVar("synthetic_authority", default=None)
        def checkpoint():
            events.append("original-checkpoint")
        authority = {"frame": frame, "spec": spec,
                     "check": checkpoint, "budget": SimpleNamespace(clock=lambda: 1.0),
                     "manifest": {"path": "synthetic-manifest", "sha256": "1" * 64},
                     "source_refs": {"source": "2" * 64},
                     "input_refs": {"input": "3" * 64},
                     "native_refs": {"native": "4" * 64}}
        class SyntheticFailure(Exception):
            pass
        class SyntheticProducer:
            def __init__(self, payload, check):
                check()
                self.payload = payload
                created.append(self)
        def imports(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "automl.infrastructure.hpo_bank":
                return SimpleNamespace(TrialBankProducer=SyntheticProducer, BankRejected=B.BankRejected)
            if name == "copy":
                return builtins.__import__(name, globals, locals, fromlist, level)
            raise AssertionError("Unexpected producer boundary import")
        namespace = {"__builtins__": dict(vars(builtins), __import__=imports), "Path": Path,
                     "_HPO_TRIAL_BANK_AUTHORITY": authority_var,
                     "_HPO_TRIAL_BANK_ACTIVE": active,
                     "_STRICT_RUNTIME": ContextVar("synthetic_strict_runtime", default=True),
                     "_STRICT_TASK_CONTRACT": ContextVar("synthetic_strict_task", default=True)}
        helper = runner_helper("_optimize_with_trial_bank", namespace)
        token = authority_var.set(authority)
        derived = dict(spec, validation_strategy="time", time_column="time")
        calls = []
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            self.assertIs(active.get(), created[-1])
            self.assertIs(kwargs["bank_producer"], created[-1])
            raise SyntheticFailure("original callable failure")
        try:
            with self.assertRaises(SyntheticFailure):
                helper(original, derived, frame, object(), object(), {"engine": "lightgbm"},
                       "synthetic-output", object(), 100.0, trials=8)
            self.assertIs(active.get(), prior)
            self.assertIs(authority_var.get(), authority)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1]["trials"], 8)
            self.assertEqual(created[0].payload["spec"], derived)
            self.assertEqual(events, ["original-checkpoint"])
            for wrong_spec, wrong_frame in ((dict(derived, features=["wrong"]), frame), (derived, object())):
                with self.subTest(changed_frame=wrong_frame is not frame), self.assertRaises(B.BankRejected):
                    helper(original, wrong_spec, wrong_frame, object(), object(), {},
                           "synthetic-output", object(), 100.0)
                self.assertIs(active.get(), prior)
            self.assertEqual(len(created), 1)
            self.assertEqual(len(calls), 1)
        finally:
            authority_var.reset(token)


    def test_closed_OFF_inverse_restores_whole_base_and_rejects_removed_scaffold_edits(self):
        packet = Path(B.__file__).resolve().parents[3]
        inverse_path = packet / "default_off_inverse.py"
        namespace = {"__name__": "_synthetic_closed_OFF_inverse"}
        exec(compile(ast.parse(inverse_path.read_text(encoding="utf-8")),
                     str(inverse_path), "exec"), namespace)
        contract = json.loads(Path(__file__).with_name("acceptance-contract.json").read_text(encoding="utf-8"))
        bases = contract["default_OFF_basis"]
        self.assertEqual(set(bases), {"src/automl/search/runner.py", "src/automl/search/hpo.py",
                                     "src/automl/execution/worker.py"})
        helpers = {"src/automl/search/runner.py": "_optimize_with_trial_bank",
                   "src/automl/search/hpo.py": "_bind_trial_bank",
                   "src/automl/execution/worker.py": "_bank_value"}
        for relative, expected in bases.items():
            with self.subTest(relative=relative):
                source = (packet / relative).read_text(encoding="utf-8")
                projected, removed = namespace["project"](relative, source)
                self.assertEqual(hashlib.sha256(ast.dump(projected, include_attributes=False).encode()).hexdigest(),
                                 expected["base_AST_sha256"])
                self.assertTrue(removed)
                mutated = ast.parse(source)
                recognized = next(node for node in mutated.body if isinstance(node, ast.FunctionDef)
                                  and node.name == helpers[relative])
                recognized.body.append(ast.Expr(value=ast.Constant(value="unreviewed scaffold edit")))
                changed = ast.unparse(ast.fix_missing_locations(mutated))
                with self.assertRaises(ValueError):
                    namespace["project"](relative, changed)
                self.assertEqual((packet / relative).read_text(encoding="utf-8"), source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
