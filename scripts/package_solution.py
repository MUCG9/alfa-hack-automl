"""Build a flat platform archive, never upload it or overwrite an existing file."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_SHA = '9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('dist/solution.zip'))
    args = parser.parse_args()
    destination = args.output if args.output.is_absolute() else ROOT / args.output
    requirement = ROOT / 'requirements.txt'
    if hashlib.sha256(requirement.read_bytes()).hexdigest() != REQUIREMENTS_SHA:
        raise RuntimeError('requirements.txt differs from the supplied platform file')
    sources = sorted(ROOT.glob('*.py')) + [requirement]
    if not (ROOT / 'solution.py').is_file():
        raise RuntimeError('Missing root solution.py')
    for source in sources:
        content = source.read_text(encoding='utf-8')
        if re.search(r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}', content):
            raise RuntimeError(f'Possible hardcoded secret in {source.name}; inspect before packaging')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            archive.write(source, source.name)
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        assert all('/' not in name and '\\' not in name for name in names)
        assert set(names) == {source.name for source in sources}
    if destination.stat().st_size > 100_000_000:
        raise RuntimeError('ZIP exceeds 100 MB; do not submit')
    print(destination)
    print('Files:', ', '.join(names))
    print('SHA-256:', hashlib.sha256(destination.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
