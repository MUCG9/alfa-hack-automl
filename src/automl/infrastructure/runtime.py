from pathlib import Path
def project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent/'src/automl').is_dir() and (parent/'solution.py').is_file(): return parent
    return Path(__file__).resolve().parent
def worker_entrypoint():
    root=project_root()
    return root/('agent_worker.py' if (root/'src/automl').is_dir() else 'automl_worker.py')
def source_files():
    root=project_root()
    return sorted((root/'src/automl').rglob('*.py'))+sorted(root.glob('*.py')) if (root/'src/automl').is_dir() else sorted(root.glob('*.py'))
