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
from automl.task_understanding.api import load_inputs
sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files
from automl.infrastructure.processes import wait_owned

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--time-budget',type=int,default=9900)
    parser.add_argument('--max-experiments',type=int,help='Explicit bounded lifecycle check; omit for default search')
    parser.add_argument('--search-until-deadline',action='store_true')
    parser.add_argument('--finalization-reserve',type=int,default=1200)
    parser.add_argument('--max-extended-experiments',type=int,default=1000)
    parser.add_argument('--jobs',type=int,default=1,choices=[1,2])
    parser.add_argument('--threads',type=int,default=4,choices=range(1,9))
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--expected-archive-sha256',help='Explicit SHA for a trusted historical baseline; otherwise require current sources')
    parser.add_argument('--memory-gb',type=float,default=2,help='Local whole-process-tree limit, not a platform limit')
    parser.add_argument('--watchdog-seconds',type=int)
    parser.add_argument('--validation-strategy',choices=['legacy','auto'])
    args=parser.parse_args(); output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    sources=build_files()
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            if any('/' in n or '\\' in n for n in archive.namelist()): raise ValueError('Archive must be flat')
            packed={name:archive.read(name) for name in archive.namelist()}
        if args.expected_archive_sha256:
            if hashlib.sha256(args.archive.read_bytes()).hexdigest()!=args.expected_archive_sha256: raise ValueError('Historical archive SHA mismatch')
        elif packed!=sources: raise ValueError('Archive does not match current compiled sources')
        sources=packed
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in sources.items()}
    atomic_json(output/'source_manifest.json',manifest)
    def run(item):
        number,path=item; path=path.resolve(); inputs=load_inputs(path)
        target=output/f'task-{number:02d}'; target.mkdir()
        shutil.copy2(path,target/'task.md')
        for value in inputs['paths'].values():
            source=Path(value); destination=target/source.relative_to(path.parent)
            destination.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,destination)
        del inputs
        for name,data in sources.items(): (target/name).write_bytes(data)
        env=os.environ.copy(); env['AUTOML_THREADS']=str(args.threads)
        command=[sys.executable,'-u','solution.py','task.md']
        if args.offline: command.append('--offline')
        if args.validation_strategy is not None: command.extend(['--validation-strategy',args.validation_strategy])
        if args.time_budget!=9900: command.extend(['--time-budget',str(args.time_budget)])
        if args.max_experiments is not None: command.extend(['--max-experiments',str(args.max_experiments)])
        if args.search_until_deadline:
            command.extend(['--search-until-deadline','--finalization-reserve',str(args.finalization_reserve),
                            '--max-extended-experiments',str(args.max_extended_experiments)])
        started=time.monotonic()
        with (target/'process.log').open('w',encoding='utf-8') as stream:
            try:
                process=subprocess.Popen(command,cwd=target,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                status=wait_owned(process,timeout=args.watchdog_seconds or args.time_budget+180,memory_bytes=int(args.memory_gb*2**30))
            except subprocess.TimeoutExpired:
                status='watchdog_timeout'
            except MemoryError:
                status='local_memory_limit'
        result={'task':str(path),'command':command,'threads':args.threads,'exit_code':status,'elapsed_seconds':round(time.monotonic()-started,3)}
        report=target/'automl_runs/run-v2/report.json'
        if not report.exists():
            multi=list((target/'automl_runs').glob('multi-target-*/report.json'))
            if len(multi)==1: report=multi[0]
        if report.exists():
            value=json.loads(report.read_text())
            result.update({k:value[k] for k in ['best_validation','selection','final_fit_status','integrity_ok','submission_sha256','score_scope'] if k in value})
            result.update({k:value[k] for k in ['baseline','exported_mean','best_observed_mean','confirmation_metric','exported_full_fit_ok','anytime'] if k in value})
            if value.get('version')=='independent-multi-target-v1':
                result['targets']=value['targets']
                result['children']=[{k:c[k] for k in ['target','status','trained','final_fit_status','best_validation','budget_seconds'] if k in c} for c in value['children']]
        atomic_json(target/'assessment.json',result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.jobs) as pool: values=list(pool.map(run,enumerate(args.task)))
    atomic_json(output/'assessments.json',values)

if __name__=='__main__': main()
