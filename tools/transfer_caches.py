"""Portable, content-addressed V11/V16 research caches; no original datasets."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNS = ["test-runs/llm-upgrade-20261022/featureviews1-full",
        "test-runs/llm-upgrade-20261022/final-default-parity"]
LIMIT = 48 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed(path):
    if "__pycache__" in path.parts or "mpl-cache" in path.parts:
        return False
    return (path.suffix in {".json", ".py", ".tsv"}
            or path.name in {"task.md", "requirements.txt", "submission.csv",
                             "validation_predictions.csv", "fallback_submission.csv",
                             "split.npz", "validation_probabilities.npz",
                             "test_probabilities.npz"})


def pack(bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    files, objects, archives = [], {}, []
    archive = None
    used = 0
    try:
        for run in RUNS:
            source = ROOT / run
            if not source.is_dir():
                raise ValueError("Missing source run: " + run)
            for path in sorted(source.rglob("*")):
                if not path.is_file() or not allowed(path):
                    continue
                if path.is_symlink():
                    raise ValueError("Symlink source")
                data = path.read_bytes()
                if path.suffix in {".json", ".py", ".tsv", ".md", ".txt"}:
                    if re.search(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}", data):
                        raise ValueError("Possible secret in selected metadata")
                sha = digest(data)
                if sha not in objects:
                    if len(data) > LIMIT:
                        raise ValueError("Single object exceeds shard bound")
                    if archive is None or used + len(data) > LIMIT:
                        if archive is not None:
                            archive.close()
                        name = f"objects-{len(archives):03d}.zip"
                        archives.append(name)
                        archive = zipfile.ZipFile(bundle / name, "x", zipfile.ZIP_DEFLATED)
                        used = 0
                    archive.writestr(sha, data)
                    objects[sha] = {"archive": archives[-1], "bytes": len(data)}
                    used += len(data)
                files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha})
    finally:
        if archive is not None:
            archive.close()
    manifest = {"version": 1, "source_root": str(ROOT), "runs": RUNS,
                "files": files, "objects": objects,
                "archives": {n: {"sha256": digest((bundle / n).read_bytes()),
                                 "bytes": (bundle / n).stat().st_size} for n in archives},
                "excluded": ["original CSV datasets", "credentials", "environment",
                             "model weights", "logs", "pycache"],
                "includes": "Public-task derived predictions, probabilities, split positions, metadata and frozen source copies"}
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"files": len(files), "unique_objects": len(objects),
                      "archive_bytes": sum(v["bytes"] for v in manifest["archives"].values()),
                      "shards": len(archives)}, indent=2))


def verify(bundle, destination=None):
    manifest = json.loads((bundle / "manifest.json").read_text())
    if manifest.get("version") != 1 or manifest["runs"] != RUNS:
        raise ValueError("Unsupported bundle")
    seen = set()
    for name, item in manifest["archives"].items():
        if Path(name).name != name or not re.fullmatch(r"objects-\d{3}\.zip", name):
            raise ValueError("Unsafe shard path")
        data = (bundle / name).read_bytes()
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise ValueError("Shard checksum mismatch")
        with zipfile.ZipFile(bundle / name) as z:
            for member in z.namelist():
                if not re.fullmatch(r"[a-f0-9]{64}", member) or member in seen:
                    raise ValueError("Unsafe or duplicate object")
                spec = manifest["objects"][member]
                payload = z.read(member)
                if spec["archive"] != name or len(payload) != spec["bytes"] or digest(payload) != member:
                    raise ValueError("Object checksum mismatch")
                seen.add(member)
    if seen != set(manifest["objects"]):
        raise ValueError("Missing objects")
    paths = set()
    for item in manifest["files"]:
        path = Path(item["path"])
        if (path.is_absolute() or ".." in path.parts or path.as_posix() in paths
                or not any(path.is_relative_to(Path(r)) for r in RUNS)
                or not allowed(path) or item["sha256"] not in seen):
            raise ValueError("Unsafe restore path")
        paths.add(path.as_posix())
        if destination is not None:
            target = destination / path
            if not target.resolve().is_relative_to(destination):
                raise ValueError("Restore escapes destination")
            if target.exists() and (not target.is_file() or digest(target.read_bytes()) != item["sha256"]):
                raise ValueError("Refusing to overwrite a different existing artifact: " + str(target))
    if destination is not None:
        handles = {}
        try:
            for item in manifest["files"]:
                target = destination / item["path"]
                if target.exists():
                    continue
                name = manifest["objects"][item["sha256"]]["archive"]
                if name not in handles:
                    handles[name] = zipfile.ZipFile(bundle / name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(handles[name].read(item["sha256"]))
        finally:
            for handle in handles.values():
                handle.close()
        print(json.dumps({"root_mapping": {manifest["source_root"]: str(destination)},
                          "note": "Immutable metadata retains original absolute paths; apply this mapping in readers, do not rewrite evidence."}, indent=2))
    print("Verified", len(paths), "files and", len(seen), "objects")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["pack", "verify", "restore"])
    p.add_argument("--bundle", type=Path, default=ROOT / "transfer/v11-v16-caches")
    p.add_argument("--destination", type=Path, default=ROOT)
    a = p.parse_args()
    if a.mode == "pack":
        pack(a.bundle.resolve())
    else:
        verify(a.bundle.resolve(), a.destination.resolve() if a.mode == "restore" else None)
