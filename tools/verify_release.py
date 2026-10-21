"""Verify current compiled archive, then run the old compatibility suite unpacked."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from build_submission import build_files
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--archive',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); expected=build_files(); checks=[]
    with zipfile.ZipFile(args.archive) as archive:
        if set(archive.namelist())!=set(expected): raise ValueError('Archive manifest mismatch')
        for name,data in expected.items():
            if archive.read(name)!=data: raise ValueError('Archive source mismatch: '+name)
        with tempfile.TemporaryDirectory(prefix='modular-verify-') as directory:
            target=Path(directory); archive.extractall(target)
            (target/'tests').mkdir()
            for name in ['test_v2.py','test_resilience.py','smoke.py']:
                shutil.copy2(ROOT/'tests'/name,target/'tests'/name)
                env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env['AUTOML_THREADS']='1'
                proc=subprocess.run([sys.executable,str(target/'tests'/name)],cwd=target,env=env,capture_output=True,text=True,timeout=300)
                checks.append({'script':name,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
                print(name,proc.returncode,flush=True)
                if proc.returncode: break
    result={'sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),'compiled_files':len(expected),
            'matches_current_source':True,'checks':checks,'passed':len(checks)==3 and all(c['exit_code']==0 for c in checks)}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']: raise SystemExit(1)
if __name__=='__main__': main()
