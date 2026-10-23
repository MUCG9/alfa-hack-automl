"""Root-use source copy only. No runtime imports, tests, models, API or clocks."""
from pathlib import Path
import argparse
import hashlib
import json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--output',required=True,help='New work-relative isolated source root')
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args();work=args.work_root.resolve()
    manifest=Path(__file__).resolve().parent/'materialization.json'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(manifest)==args.manifest_sha256,'Materialization inventory changed'
    config=json.loads(manifest.read_text('utf-8'))
    target=(work/args.output).resolve()
    assert not Path(args.output).is_absolute() and target.is_relative_to(work) and target!=work
    assert not target.exists(),'New isolated source root required; no overwrite or retry'
    for name,entry in config['files'].items():
        source=(work/entry['path']).resolve();relative=Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and source.is_relative_to(work)
        assert source.is_file() and digest(source)==entry['sha256'],'Pinned source/fixture changed'
    target.mkdir()
    for name,entry in config['files'].items():
        destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((work/entry['path']).read_bytes())
        assert digest(destination)==entry['sha256'],'Isolated source copy changed'
    receipt=dict(status='isolated_source_materialized_no_execution',source_inventory_sha256=args.manifest_sha256,
        files_sha256={name:entry['sha256'] for name,entry in config['files'].items()},
        tests_run=0,model_fits=0,API_calls=0,clock_assigned=False)
    with (target/'source-copy-receipt.json').open('x',encoding='utf-8') as stream:
        json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'status':receipt['status'],'files':len(receipt['files_sha256'])}))


if __name__=='__main__':main()
