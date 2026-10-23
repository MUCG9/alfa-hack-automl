"""Sequential bounded optional-backend fixture with unchanged-source receipt."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files


def hashes():return {k:hashlib.sha256(v).hexdigest() for k,v in build_files().items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script',choices=['test_lama.py','test_embeddings.py'],required=True)
    parser.add_argument('--expected',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['KEY','TOKEN','SECRET','AUTH','PROXY','PASSWORD'])}
    env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(out/'mpl'))
    before=hashes();started=time.monotonic()
    with (out/'checks.log').open('w') as log:
        process=subprocess.Popen([sys.executable,str(ROOT/'tests'/args.script)],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:status=wait_owned(process,120,int(1.7*2**30))
        except subprocess.TimeoutExpired:status='timeout'
        except MemoryError:status='memory_limit'
    observed=re.findall(r'Ran (\d+) tests? in ',(out/'checks.log').read_text())
    count=int(observed[-1]) if observed else None
    receipt={'script':args.script,'expected':args.expected,'observed':count,'exit_code':status,
        'seconds':time.monotonic()-started,'source_sha256':before,'source_unchanged':before==hashes(),
        'script_sha256':hashlib.sha256((ROOT/'tests'/args.script).read_bytes()).hexdigest()}
    receipt['passed']=status==0 and count==args.expected and receipt['source_unchanged']
    atomic_json(out/'checks.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='source_sha256'}))
    return 0 if receipt['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
