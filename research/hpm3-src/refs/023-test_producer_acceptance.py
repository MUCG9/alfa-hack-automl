"""Independent producer-only contracts; synthetic descriptors, no learner/API.

This file is SOURCE prepared only.  A future authorized runner must put the
reviewed candidate package on sys.path.  It must not load an older canonical
producer, execute a consumer, or turn these mock receipts into runtime evidence.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automl.infrastructure import hpo_bank as B


def synthetic_ref(path):
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


class ProducerAcceptanceContracts(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="hpo-bank-contract-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        source, inputs, native, manifest, split = [root / name for name in (
            "synthetic-source.py", "synthetic-input.bin", "synthetic-native.bin",
            "synthetic-manifest.json", "synthetic-split.bin")]
        for path, value in ((source, b"# synthetic source\n"), (inputs, b"input\x00fixture"),
                            (native, b"native\x00fixture"), (manifest, b'{"fixture":true}'),
                            (split, b"ordered-inner-rows:0,1|2,3")):
            path.write_bytes(value)
        spec = {"kind": "regression", "metric": "rmse", "target": "answer",
                "features": ["x"], "greater_is_better": False,
                "duplicate_feature_rate": 0.0}
        authority = {"schema": "hpo-trial-bank-authority-v1",
                     "manifest": synthetic_ref(manifest),
                     "source_refs": {str(source): synthetic_ref(source)["sha256"]},
                     "input_refs": {str(inputs): synthetic_ref(inputs)["sha256"]},
                     "native_refs": {str(native): synthetic_ref(native)["sha256"]},
                     "spec": deepcopy(spec), "bank_root": str(root / "bank")}
        events = []
        producer = B.TrialBankProducer(authority, lambda: events.append("checkpoint"))
        producer.bind_study(spec, B.canonical_digest([0, 1, 2, 3]),
                            synthetic_ref(split), B.canonical_digest([[0, 1], [2, 3]]))
        return {"root": root, "source": source, "native_file": native, "split": split,
                "spec": spec, "authority": authority, "producer": producer, "events": events}

    def prepared(self, fixture):
        return {"scope": "outer", "fit_x": {"schema": "synthetic-prepared-v1",
                    "shape": [2, 1], "columns": ["x"], "dtypes": ["float64"],
                    "index": [0, 1], "values_sha256": "1" * 64,
                    "missing_sha256": "2" * 64, "categories": []},
                "targets": {"dtype": "float64", "ordered_values_sha256": "3" * 64},
                "weights": {"dtype": "float64", "ordered_values_sha256": "4" * 64},
                "parents": [0, 1], "validation_x": {"index": [2, 3], "sha256": "5" * 64},
                "validation_y": {"dtype": "float64", "sha256": "6" * 64},
                "constructor": {"engine": "lightgbm", "objective": "regression",
                                "random_state": 7, "n_jobs": 2},
                "fit_settings": {"fit_iterations_present": False,
                                 "stopping_metric": "rmse", "early_stopping_rounds": 20},
                "native": {"files": deepcopy(fixture["authority"]["native_refs"]),
                           "python": {"implementation": "CPython", "abi": "synthetic-abi"},
                           "threads": [{"internal_api": "openmp", "num_threads": 2}],
                           "environment": {"AUTOML_THREADS": "2", "OMP_NUM_THREADS": "2"}}}

    def recorded_trial(self, fixture, *, recipe=None):
        producer = fixture["producer"]
        recipe = deepcopy(recipe or {"engine": "lightgbm", "params": {"num_leaves": 31}})
        job = {"spec": deepcopy(fixture["spec"]), "recipe": recipe}
        job["_hpo_trial_bank"] = producer.worker_request(job, 100.0)
        recorder = B.FitIdentityRecorder(job, lambda: fixture["events"].append("fit-checkpoint"))
        token = recorder.before_fit(**self.prepared(fixture))
        recorder.after_fit(token, {"booster_params": {"objective": "regression", "seed": 7,
                                                     "num_threads": 2}, "actual_trees": 17})
        result = {"status": "ok", "metrics": {"rmse": 2.5}, "fit_iterations": 17,
                  "hpo_fit_identity": recorder.receipt()}
        job_path = fixture["root"] / "job.json"
        job_path.write_text(json.dumps(job, allow_nan=False), encoding="utf-8")
        job_path.with_name("result.json").write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
        return recipe, job, result, job_path

    def qualify(self, fixture, result, job_path, **overrides):
        arguments = {"job_path": job_path, "split_path": fixture["split"],
                     "process_identities": [{"pid": 1234, "create_time": 10.25}],
                     "actual_exit_code": 0, "cleanup_confirmed": True,
                     "primary_exception_type": None, "coordinator_killed": None}
        arguments.update(overrides)
        return fixture["producer"].qualify_parent(result, **arguments)

    def commit(self, fixture, recipe, result, **overrides):
        arguments = {"number": 0, "sampling_phase": "anchor", "recipe": recipe,
                     "objective": 2.5, "result": result}
        arguments.update(overrides)
        return fixture["producer"].commit_trial(**arguments)

    def assert_not_admitted(self, answer):
        self.assertEqual(answer["status"], "not_qualified")
        self.assertIsNone(answer["objective"])
        self.assertFalse(answer["reuse_eligible"])
        self.assertIsNone(answer["savings"])
        self.assertTrue(answer["reason"])

    def test_closed_typed_digest_distinguishes_values_and_preserves_order(self):
        values = [True, 1, 1.0, "1", b"1", [1], (1,), 0.0, -0.0]
        digests = [B.canonical_digest(value) for value in values]
        self.assertEqual(len(set(digests)), len(values))
        self.assertNotEqual(B.canonical_digest([0, 1]), B.canonical_digest([1, 0]))
        self.assertEqual(B.canonical_digest({"b": [2, 1], "a": 0}),
                         B.canonical_digest({"a": 0, "b": [2, 1]}))
        self.assertNotEqual(B.canonical_digest({"a": 0}), B.canonical_digest({"a": False}))

    def test_closed_digest_rejects_unknown_cycles_nonfinite_without_repr(self):
        called = []
        class Unknown:
            def __repr__(self):
                called.append("repr")
                raise AssertionError("repr must not become identity")
        cycle = []
        cycle.append(cycle)
        for value in (Unknown(), {1: "wrong-key"}, {1, 2}, cycle,
                      float("nan"), float("inf"), float("-inf")):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(B.BankRejected):
                B.canonical_digest(value)
        self.assertEqual(called, [])

    def test_each_prepared_native_and_effective_dimension_changes_identity(self):
        fixture = self.fixture()
        _, job, _, _ = self.recorded_trial(fixture)
        baseline = self.prepared(fixture)
        changes = [lambda d: d["fit_x"]["index"].reverse(),
                   lambda d: d["fit_x"]["dtypes"].__setitem__(0, "float32"),
                   lambda d: d["fit_x"].__setitem__("missing_sha256", "a" * 64),
                   lambda d: d["targets"].__setitem__("ordered_values_sha256", "a" * 64),
                   lambda d: d["weights"].__setitem__("ordered_values_sha256", "b" * 64),
                   lambda d: d["parents"].reverse(),
                   lambda d: d["validation_x"]["index"].reverse(),
                   lambda d: d["validation_y"].__setitem__("sha256", "c" * 64),
                   lambda d: d["constructor"].__setitem__("random_state", 8),
                   lambda d: d["fit_settings"].__setitem__("fit_iterations_present", True),
                   lambda d: d["native"]["python"].__setitem__("abi", "different-abi"),
                   lambda d: d["native"]["threads"][0].__setitem__("num_threads", 1),
                   lambda d: d["native"]["environment"].__setitem__("OMP_NUM_THREADS", "1")]
        base_recorder = B.FitIdentityRecorder(job, lambda: None)
        base_token = base_recorder.before_fit(**baseline)
        baseline_sha = base_recorder.receipt()["nodes"][base_token]["input_sha256"]
        for index, change in enumerate(changes):
            with self.subTest(dimension=index):
                descriptor = deepcopy(baseline)
                change(descriptor)
                recorder = B.FitIdentityRecorder(job, lambda: None)
                token = recorder.before_fit(**descriptor)
                self.assertNotEqual(recorder.receipt()["nodes"][token]["input_sha256"], baseline_sha)

    def test_recorder_requires_actual_completion_and_native_files(self):
        fixture = self.fixture()
        _, job, _, _ = self.recorded_trial(fixture)
        recorder = B.FitIdentityRecorder(job, lambda: None)
        token = recorder.before_fit(**self.prepared(fixture))
        self.assertFalse(recorder.receipt()["complete"])
        recorder.after_fit(token, {})
        self.assertFalse(recorder.receipt()["complete"])
        descriptor = self.prepared(fixture)
        descriptor["native"] = {"version": "4.0"}
        rejected = B.FitIdentityRecorder(job, lambda: None)
        rejected.before_fit(**descriptor)
        self.assertFalse(rejected.receipt()["complete"])
        descriptor = self.prepared(fixture)
        fixture["native_file"].write_bytes(b"changed native bytes")
        changed = B.FitIdentityRecorder(job, lambda: None)
        changed.before_fit(**descriptor)
        self.assertFalse(changed.receipt()["complete"])

    def test_recorder_snapshots_before_and_after_fit_inputs(self):
        fixture = self.fixture()
        _, job, _, _ = self.recorded_trial(fixture)
        descriptor = self.prepared(fixture)
        recorder = B.FitIdentityRecorder(job, lambda: None)
        token = recorder.before_fit(**descriptor)
        captured = deepcopy(recorder.receipt()["nodes"][token]["identity"])
        descriptor["fit_x"]["index"].reverse()
        descriptor["native"]["threads"][0]["num_threads"] = 99
        effective = {"booster_params": {"num_threads": 2}, "actual_trees": 17}
        recorder.after_fit(token, effective)
        effective["actual_trees"] = 999
        receipt = recorder.receipt()
        self.assertTrue(receipt["complete"])
        self.assertEqual(receipt["nodes"][token]["identity"], captured)
        self.assertEqual(receipt["nodes"][token]["effective"]["actual_trees"], 17)
        self.assertIsNone(receipt["actual_recursive_learner_fits"])

    def test_worker_booleans_and_copied_result_cannot_forge_parent_authority(self):
        fixture = self.fixture()
        recipe, _, result, job_path = self.recorded_trial(fixture)
        result["_hpo_bank_parent"] = {"cleanup_confirmed": True, "source_qualified": True,
                                     "actual_exit_code": 0}
        self.assert_not_admitted(self.commit(fixture, recipe, result))
        result.pop("_hpo_bank_parent")
        self.qualify(fixture, result, job_path)
        self.assert_not_admitted(self.commit(fixture, recipe, deepcopy(result), number=1))
        self.assertEqual(self.commit(fixture, recipe, result, number=2)["status"], "admitted")

    def test_valid_anchor_seals_once_and_reports_no_consumer_or_savings(self):
        fixture = self.fixture()
        recipe, _, result, job_path = self.recorded_trial(fixture)
        self.qualify(fixture, result, job_path)
        answer = self.commit(fixture, recipe, result)
        self.assertEqual(answer["status"], "admitted")
        entry = json.loads(Path(answer["entry"]["path"]).read_text(encoding="utf-8"))
        self.assertTrue(entry["anchor"])
        self.assertFalse(entry["reuse_eligible"])
        self.assertFalse(entry["future_preworker_hit_validation"])
        self.assertEqual(entry["epoch_id"], fixture["producer"].epoch_id)
        original_entry_bytes = Path(answer["entry"]["path"]).read_bytes()
        self.assert_not_admitted(self.commit(fixture, recipe, result))
        self.assertEqual(Path(answer["entry"]["path"]).read_bytes(), original_entry_bytes)
        self.assertFalse((fixture["root"] / "bank" / "bank.json").exists())
        index = fixture["producer"].finish("completed")
        self.assertEqual(index["entries"][0]["objective"], 2.5)
        self.assertFalse(index["consumer_implemented"])
        self.assertEqual(index["reuse_count"], 0)
        self.assertIsNone(index["savings"])
        self.assertIsNone(index["actual_model_process_launches"])
        self.assertIsNone(index["actual_recursive_learner_fits"])
        self.assertIsNone(fixture["producer"].actual_process_launches)
        self.assertIsNone(fixture["producer"].actual_learner_fits)
        self.assertTrue(fixture["events"])

    def test_invalid_objectives_and_failed_trials_remain_bank_null(self):
        for index, (objective, status) in enumerate(((True, "ok"), (float("nan"), "ok"),
                (float("inf"), "ok"), (None, "ok"), (2.5, "timeout"), (2.5, "error"))):
            with self.subTest(case=index):
                fixture = self.fixture()
                recipe, _, result, job_path = self.recorded_trial(fixture)
                result["status"] = status
                self.qualify(fixture, result, job_path)
                original = deepcopy(result)
                self.assert_not_admitted(self.commit(fixture, recipe, result, objective=objective))
                self.assertEqual(result, original)
                self.assertFalse((fixture["root"] / "bank" / "trial-0.json").exists())

    def test_unclean_parent_source_and_original_deadline_cannot_publish(self):
        for failure in ("exit", "cleanup", "exception", "killed", "source", "deadline"):
            with self.subTest(failure=failure):
                fixture = self.fixture()
                recipe, _, result, job_path = self.recorded_trial(fixture)
                overrides = {"exit": {"actual_exit_code": 1}, "cleanup": {"cleanup_confirmed": False},
                             "exception": {"primary_exception_type": "TimeoutError"},
                             "killed": {"coordinator_killed": "original_deadline"}}.get(failure, {})
                self.qualify(fixture, result, job_path, **overrides)
                if failure == "source":
                    fixture["source"].write_bytes(b"changed source bytes")
                elif failure == "deadline":
                    def original_checkpoint():
                        raise B.BankRejected("original_deadline_expired")
                    fixture["producer"].checkpoint = original_checkpoint
                self.assert_not_admitted(self.commit(fixture, recipe, result))
                self.assertFalse((fixture["root"] / "bank" / "trial-0.json").exists())

    def test_post_parent_receipt_tampering_and_wrong_epoch_are_rejected(self):
        mutations = [lambda r: r["hpo_fit_identity"].__setitem__("epoch_id", "f" * 64),
                     lambda r: r["hpo_fit_identity"].__setitem__("complete", False),
                     lambda r: r["hpo_fit_identity"].__setitem__("nodes", []),
                     lambda r: r["hpo_fit_identity"]["nodes"][0].__setitem__("status", "pending"),
                     lambda r: r["hpo_fit_identity"]["nodes"][0]["identity"]["parents"].reverse(),
                     lambda r: r["hpo_fit_identity"]["nodes"][0]["effective"].__setitem__("actual_trees", 18),
                     lambda r: r["hpo_fit_identity"]["nodes"].append(deepcopy(r["hpo_fit_identity"]["nodes"][0]))]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                fixture = self.fixture()
                recipe, _, result, job_path = self.recorded_trial(fixture)
                self.qualify(fixture, result, job_path)
                mutate(result)
                self.assert_not_admitted(self.commit(fixture, recipe, result))
                self.assertFalse((fixture["root"] / "bank" / "trial-0.json").exists())

    def test_sealed_artifact_change_and_unsupported_recipe_do_not_change_hpo_value(self):
        for failure in ("result", "split", "unsupported"):
            with self.subTest(failure=failure):
                fixture = self.fixture()
                recipe, _, result, job_path = self.recorded_trial(fixture)
                self.qualify(fixture, result, job_path)
                if failure == "result":
                    job_path.with_name("result.json").write_bytes(b"changed result bytes")
                elif failure == "split":
                    fixture["split"].write_bytes(b"changed partition order")
                else:
                    recipe = {"engine": "catboost", "params": {}}
                original = deepcopy(result)
                self.assert_not_admitted(self.commit(fixture, recipe, result))
                self.assertEqual(result, original)
                self.assertEqual(result["metrics"]["rmse"], 2.5)

    def test_late_index_io_failure_cannot_leave_a_discoverable_positive_bank(self):
        fixture = self.fixture()
        recipe, _, result, job_path = self.recorded_trial(fixture)
        self.qualify(fixture, result, job_path)
        self.assertEqual(self.commit(fixture, recipe, result)["status"], "admitted")
        with patch.object(B.os, "fsync", side_effect=OSError("synthetic index durability failure")):
            with self.assertRaises(OSError):
                fixture["producer"].finish("completed")
        index_path = fixture["root"] / "bank" / "bank.json"
        if index_path.exists():
            try:
                value = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                value = None
            self.assertFalse(isinstance(value, dict) and value.get("schema") == "hpo-trial-bank-index-v1"
                             and value.get("study_status") == "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
