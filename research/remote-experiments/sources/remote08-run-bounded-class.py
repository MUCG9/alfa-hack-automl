"""Fixed reviewed invocation of the six-job Linux component driver."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, platform, sys

JOB = "remote-port-08-class-kernel-components"
WORKER = "remote-worker-f7dd39e0"
QUEUE_SHA = "d42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49"
SOURCE_PATH = "research/remote-experiments/sources/remote08-run-bounded-class.py"
EXECUTION = {
 "portable_harness.py": "8b14a7c9db4a37623fac0555e7989a79f94971f2768aebaf5752488f2b540342",
 "component_audit.py": "befcca2f8e630b9fb8e1bca81ce46b4d08f6f17773c65a38f133a56c277d2ffd",
 "experiment_driver.py": "ea80bf0d35692a278c490ca953596ac2c0490481560bbf5522158ac8f0586a0d",
 "pure_contracts.py": "783830691e558748b4437a734d27cd4cb332c6731f683c3058cd21ea18597286",
}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(value, code):
    if not value:
        raise RuntimeError(code)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["repo", "queue-file", "root", "prepared-authority", "clock-path", "claim-sha"]:
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    need(__debug__ and platform.system() == "Linux", "nonoptimized_actual_linux_required")
    repo, root = Path(a.repo).resolve(), Path(a.root).resolve()
    queue = Path(a.queue_file).resolve()
    need(queue == repo / "research/remote-experiments/queue/remote_queue.py" and digest(queue) == QUEUE_SHA, "exact_queue_source")
    need(Path(__file__).resolve() == repo / SOURCE_PATH, "exact_reviewed_caller_location")
    need(Path(a.prepared_authority).resolve() == root / "prepared-authority-r1.json", "new_authority_required")
    need(Path(a.clock_path).resolve() == root / "bounded08-clock.json", "single_retained08_clock_required")
    spec = importlib.util.spec_from_file_location("_remote08_pinned_queue", queue)
    q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
    g = q.Git(repo); oid, claim, job, unused = q.read_claim(g, JOB)
    need(oid == a.claim_sha and claim["worker_id"] == WORKER, "exact_claim_worker")
    refs = {v["path"]: v["sha256"] for v in job["source_refs"]}
    need(SOURCE_PATH in refs and digest(__file__) == refs[SOURCE_PATH], "reviewed_caller_pin")
    for name, pin in EXECUTION.items():
        need(digest(root / "execution-r1" / name) == pin, "exact_prepared_execution_source")
    sys.path.insert(0, str(root / "execution-r1"))
    import experiment_driver
    result = experiment_driver.execute(str(repo), str(queue), JOB, WORKER, a.claim_sha, str(root), a.prepared_authority, a.clock_path)
    print(json.dumps({k: result.get(k) for k in ["status", "actual_learner_fits", "api_calls", "full_refit", "promotion"]}))
    return 0 if result.get("status") == "component_complete" else 1

if __name__ == "__main__":
    raise SystemExit(main())
