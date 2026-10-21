"""Reproducible exact-command CPU benchmark using external organizer task folders.

Example: python scripts/benchmark_release.py --task /data/reg/task.md
 --task /data/class/task.md --output /work/assessment-v2
No source data or secrets are committed. Output must be a new directory.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse,hashlib,json,os,shutil,signal,subprocess,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from agent_core import discover,atomic_json
sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--time-budget',type=int,default=9900)
    parser.add_argument('--jobs',type=int,default=1,choices=[1,2])
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--watchdog-seconds',type=int)
    args=parser.parse_args(); output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    sources=build_files()
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            packed={name:archive.read(name) for name in archive.namelist()}
        if packed!=sources: raise ValueError('Archive does not match current compiled sources')
        sources=packed
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in sources.items()}
    atomic_json(output/'source_manifest.json',manifest)
    def run(item):
        number,path=item; path=path.resolve(); spec,*_=discover(path)
        target=output/f'task-{number:02d}'; target.mkdir()
        shutil.copy2(path,target/'task.md')
        for value in spec['paths'].values():
            source=Path(value); destination=target/source.relative_to(path.parent)
            destination.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,destination)
        for name,data in sources.items(): (target/name).write_bytes(data)
        env=os.environ.copy(); env['AUTOML_THREADS']='4'
        command=[sys.executable,'-u','solution.py','task.md']
        if args.offline: command.append('--offline')
        if args.time_budget!=9900: command.extend(['--time-budget',str(args.time_budget)])
        started=time.monotonic()
        with (target/'process.log').open('w',encoding='utf-8') as stream:
            try:
                process=subprocess.Popen(command,cwd=target,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                status=process.wait(timeout=args.watchdog_seconds or args.time_budget+180)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL); process.wait()
                status='watchdog_timeout'
        result={'task':str(path),'command':command,'exit_code':status,'elapsed_seconds':round(time.monotonic()-started,3)}
        report=target/'automl_runs/run-v2/report.json'
        if report.exists():
            value=json.loads(report.read_text())
            result.update({k:value[k] for k in ['best_validation','selection','final_fit_status','integrity_ok','submission_sha256','score_scope']})
        atomic_json(target/'assessment.json',result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.jobs) as pool: values=list(pool.map(run,enumerate(args.task)))
    atomic_json(output/'assessments.json',values)

if __name__=='__main__': main()
