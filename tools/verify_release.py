"""Verify current compiled archive, then run the old compatibility suite unpacked."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from build_submission import build_files
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.processes import wait_owned


def run_check(command,cwd,env,timeout,memory_bytes):
    with tempfile.TemporaryFile(mode='w+t') as stdout,tempfile.TemporaryFile(mode='w+t') as stderr:
        process=subprocess.Popen(command,cwd=cwd,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            status=wait_owned(process,timeout=timeout,memory_bytes=memory_bytes)
        except subprocess.TimeoutExpired:
            status='timeout'
        except MemoryError:
            status='memory_limit'
        stdout.seek(0);stderr.seek(0)
        return {'exit_code':status,'stdout':stdout.read(),'stderr':stderr.read()}


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--archive',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=300,help='Local per-script watchdog, not the platform task limit')
    parser.add_argument('--memory-gb',type=float,default=1.2,help='Local whole-tree memory guard')
    parser.add_argument('--research-profile',choices=['incumbent_mix'],default=None)
    args=parser.parse_args(argv)
    if args.timeout<=0 or args.memory_gb<=0: parser.error('Timeout and memory must be positive')
    expected=build_files() if args.research_profile is None else build_files(args.research_profile)
    checks=[]
    with zipfile.ZipFile(args.archive) as archive:
        if len(archive.namelist())!=len(set(archive.namelist())) or set(archive.namelist())!=set(expected): raise ValueError('Archive manifest mismatch')
        for name,data in expected.items():
            if archive.read(name)!=data: raise ValueError('Archive source mismatch: '+name)
        with tempfile.TemporaryDirectory(prefix='modular-verify-') as directory:
            target=Path(directory); archive.extractall(target)
            (target/'tests').mkdir()
            for name in ['test_v2.py','test_resilience.py','smoke.py']:
                shutil.copy2(ROOT/'tests'/name,target/'tests'/name)
                env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'])}
                env['AUTOML_THREADS']='1'
                check=run_check([sys.executable,str(target/'tests'/name)],target,env,args.timeout,int(args.memory_gb*2**30))
                checks.append(dict(script=name,**check))
                print(name,check['exit_code'],flush=True)
                if check['exit_code']!=0: break
    result={'sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),'compiled_files':len(expected),
            'matches_current_source':True,'deployment_profile':args.research_profile,
            'checks':checks,'passed':len(checks)==3 and all(c['exit_code']==0 for c in checks)}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']: raise SystemExit(1)
if __name__=='__main__': main()
