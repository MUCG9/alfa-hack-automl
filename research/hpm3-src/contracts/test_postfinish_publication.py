"""HPM01 real-wrapper/real-helper synthetic publication contracts, SOURCE only.

No optimizer, estimator, model, API, data or experiment clock is run here. Future
fixtures execute only the exact reviewed wrapper and bank helper on temporary
synthetic files; every failure is injected after finish or before adoption.
"""
from contextlib import ExitStack
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automl.infrastructure import hpo_bank as B
from test_default_off_acceptance import runner_helper


class SyntheticTailFailure(RuntimeError):
    pass


class SyntheticDeadline(TimeoutError):
    pass


class PostFinishPublicationContracts(unittest.TestCase):
    def scenario(self, mode):
        temporary = tempfile.TemporaryDirectory(prefix="hpo-postfinish-contract-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        output = root / "study"
        output.mkdir()
        files = {}
        for name, value in (("manifest.json", b'{"synthetic":true}'),
                            ("source.py", b"# synthetic source\n"), ("input.bin", b"synthetic input"),
                            ("native.bin", b"synthetic native"), ("split.bin", b"inner:0,1|2,3")):
            path = root / name
            path.write_bytes(value)
            files[name] = path
        def reference(path):
            raw = path.read_bytes()
            return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        frame = object()
        spec = {"kind": "regression", "metric": "rmse", "target": "y", "features": ["x"]}
        prior = object()
        active = ContextVar("synthetic_active_postfinish", default=prior)
        authority_var = ContextVar("synthetic_postfinish_authority", default=None)
        primary = SyntheticDeadline("original final checkpoint") if mode in {"deadline", "unlink"} else SyntheticTailFailure("postfinish " + mode)
        state = {"after_finish": False, "after_write": False, "hash_fault_fired": False,
                 "target_unlinks": [], "report": None, "producer": None}
        index_path = output / "trial-bank" / "bank.json"
        unrelated_path = index_path.with_name("unrelated-diagnostic.json")
        unrelated = b"unrelated diagnostic must survive"
        replacement = b"unrelated replacement index must survive"
        def check():
            if mode in {"deadline", "unlink"} and state["after_write"]:
                raise primary
        authority = {"frame": frame, "spec": spec, "check": check,
                     "budget": SimpleNamespace(clock=lambda: 1.0),
                     "manifest": reference(files["manifest.json"]),
                     "source_refs": {str(files["source.py"]): reference(files["source.py"])["sha256"]},
                     "input_refs": {str(files["input.bin"]): reference(files["input.bin"])["sha256"]},
                     "native_refs": {str(files["native.bin"]): reference(files["native.bin"])["sha256"]}}
        numeric_ledger = {"status": "ok", "trials": [{"number": 0, "status": "synthetic", "value": 2.5}],
                          "best_inner_value": 2.5, "selected_recipe": {"engine": "lightgbm"}}
        def atomic_json(path, value):
            Path(path).write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
            state["after_write"] = True
            if mode == "write":
                raise primary
        namespace = {"Path": Path, "atomic_json": atomic_json,
                     "_HPO_TRIAL_BANK_AUTHORITY": authority_var, "_HPO_TRIAL_BANK_ACTIVE": active,
                     "_STRICT_RUNTIME": ContextVar("synthetic_postfinish_runtime", default=True),
                     "_STRICT_TASK_CONTRACT": ContextVar("synthetic_postfinish_contract", default=True)}
        helper = runner_helper("_optimize_with_trial_bank", namespace)
        def original(*args, **kwargs):
            producer = kwargs["bank_producer"]
            state["producer"] = producer
            producer.bind_study(spec, B.canonical_digest([0, 1, 2, 3]), reference(files["split.bin"]),
                                B.canonical_digest([[0, 1], [2, 3]]))
            unrelated_path.write_bytes(unrelated)
            if mode == "preexisting":
                index_path.write_bytes(replacement)
            report = deepcopy(numeric_ledger)
            state["report"] = report
            (output / "hpo.json").write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
            return report["selected_recipe"], report
        real_finish, real_ref = B.TrialBankProducer.finish, B.file_ref
        real_unlink, real_lstat = Path.unlink, Path.lstat
        def finished(producer, status):
            value = real_finish(producer, status)
            if mode == "replacement":
                real_unlink(index_path)
                index_path.write_bytes(replacement)
            state["after_finish"] = True
            return value
        def checked_ref(path, checkpoint):
            if state["after_finish"] and Path(path) == index_path and mode in {"hash", "replacement", "symlink"} and not state["hash_fault_fired"]:
                state["hash_fault_fired"] = True
                raise primary
            return real_ref(path, checkpoint)
        def unlink(path, *args, **kwargs):
            if state["after_finish"] and path == index_path:
                state["target_unlinks"].append(str(path))
                if mode == "unlink":
                    raise PermissionError("synthetic unlink denial")
            return real_unlink(path, *args, **kwargs)
        def lstat(path, *args, **kwargs):
            observed = real_lstat(path, *args, **kwargs)
            if state["after_finish"] and path == index_path and mode == "symlink":
                return SimpleNamespace(st_mode=stat.S_IFLNK | stat.S_IMODE(observed.st_mode),
                    st_dev=observed.st_dev, st_ino=observed.st_ino, st_size=observed.st_size)
            return observed
        token = authority_var.set(authority)
        observed_error = None
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(B.TrialBankProducer, "finish", finished))
                stack.enter_context(patch.object(B, "file_ref", checked_ref))
                stack.enter_context(patch.object(Path, "unlink", unlink))
                stack.enter_context(patch.object(Path, "lstat", lstat))
                try:
                    helper(original, spec, frame, object(), object(), {"engine": "lightgbm"},
                           output, object(), 100.0, trials=8)
                except BaseException as exc:
                    observed_error = exc
                else:
                    self.fail("Injected publication failure must propagate")
                self.assertIs(active.get(), prior)
                self.assertIs(authority_var.get(), authority)
        finally:
            authority_var.reset(token)
        self.assertIsNotNone(observed_error)
        self.assertEqual({key: state["report"][key] for key in numeric_ledger}, numeric_ledger)
        self.assertNotIn("trial_bank_producer", state["report"])
        disk_report = json.loads((output / "hpo.json").read_text(encoding="utf-8"))
        self.assertEqual({key: disk_report[key] for key in numeric_ledger}, numeric_ledger)
        if "trial_bank_producer" in disk_report:
            self.assertEqual(disk_report["trial_bank_producer"]["state"], "pending_wrapper_parent_qualification")
            self.assertFalse(disk_report["trial_bank_producer"]["qualifies_completed_handoff"])
        self.assertEqual(unrelated_path.read_bytes(), unrelated)
        return {"error": observed_error, "primary": primary, "state": state,
                "index": index_path, "replacement": replacement, "disk_report": disk_report}

    def test_real_wrapper_postfinish_hash_write_and_deadline_keep_primary_and_revoke_owned_index(self):
        for mode in ("hash", "write", "deadline"):
            with self.subTest(mode=mode):
                result = self.scenario(mode)
                self.assertIs(result["error"], result["primary"])
                self.assertFalse(result["index"].exists())
                self.assertTrue(result["error"].bank_index_revocation_confirmed)
                self.assertTrue(result["error"].bank_index_revocation["absence_confirmed"])
                self.assertTrue(result["error"].bank_index_revocation["removed"])
                self.assertEqual(len(result["state"]["target_unlinks"]), 1)

    def test_revocation_refuses_replacement_symlink_and_preexisting_target_without_adoption(self):
        for mode in ("replacement", "symlink", "preexisting"):
            with self.subTest(mode=mode):
                result = self.scenario(mode)
                self.assertTrue(result["index"].exists())
                self.assertEqual(result["state"]["target_unlinks"], [])
                if mode == "preexisting":
                    self.assertIsInstance(result["error"], FileExistsError)
                    self.assertIsNone(result["state"]["producer"].completed_index_ref())
                    self.assertEqual(result["index"].read_bytes(), result["replacement"])
                else:
                    self.assertIs(result["error"], result["primary"])
                    self.assertFalse(result["error"].bank_index_revocation_confirmed)
                    self.assertIn("BankRejected", result["error"].bank_cleanup_secondary_types)
                    if mode == "replacement":
                        self.assertEqual(result["index"].read_bytes(), result["replacement"])

    def test_failed_unlink_retains_primary_secondary_and_only_nonqualifying_pending_receipt(self):
        result = self.scenario("unlink")
        self.assertIs(result["error"], result["primary"])
        self.assertIsInstance(result["error"], SyntheticDeadline)
        self.assertFalse(result["error"].bank_index_revocation_confirmed)
        self.assertIn("PermissionError", result["error"].bank_cleanup_secondary_types)
        self.assertTrue(result["index"].exists())
        self.assertEqual(len(result["state"]["target_unlinks"]), 1)
        receipt = result["disk_report"]["trial_bank_producer"]
        self.assertEqual(receipt["state"], "pending_wrapper_parent_qualification")
        self.assertFalse(receipt["qualifies_completed_handoff"])
        self.assertFalse(receipt["consumer_implemented"])
        self.assertEqual(receipt["reuse_count"], 0)
        self.assertIsNone(receipt["savings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
