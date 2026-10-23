"""Bound one source-only preparation and record exact owned identities.
Does not start model workers, assign an ML campaign clock, or retry a failure.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
WORK=Path(__file__).resolve().parent
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--receipt-directory',required=True)
    a=p.parse_args();script=(WORK/a.source).resolve();out=(WORK/a.receipt_directory).resolve()
    assert script.is_relative_to(WORK) and out.is_relative_to(WORK) and not out.exists()
    assert hashlib.sha256(script.read_bytes()).hexdigest()==a.sha256
    start,mono=time.time(),time.monotonic();end=mono+75;unix=start+75
    out.mkdir();selfproc=psutil.Process();owned={(selfproc.pid,selfproc.create_time())};bootstrap=[]
    parent=selfproc.parent()
    while parent and parent.name().lower() in ('python.exe','pythonw.exe'):
        bootstrap.append(dict(pid=parent.pid,create_time=parent.create_time()));parent=parent.parent()
    r=dict(status='starting',start_unix=start,start_monotonic=mono,absolute_deadline_unix=unix,
        common_deadline_monotonic=end,source_preparation_cap_seconds=60,engineering_total_cap_seconds=75,
        stage0_ML_clock_assigned=False,source=a.source,source_sha256=a.sha256,
        self_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        coordinator_bootstrap_identities=bootstrap,owned_root=dict(pid=selfproc.pid,create_time=selfproc.create_time()),
        tests=0,model_fits=0,API_calls=0,peak_owned_tree_rss_mib=0.,error_history=[])
    allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    child=None;root=None;last=time.monotonic();lastwall=time.time()
    try:
        with (out/'preparation.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(script),'--self-sha256',a.sha256],
                cwd=WORK.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            proc=psutil.Process(child.pid);root=(proc.pid,proc.create_time());owned.add(root)
            while True:
                now,wall=time.monotonic(),time.time()
                assert max(now-last,wall-lastwall)<=10,'source_preparation_observation_gap'
                assert now<mono+60 and wall<start+60,'source_preparation_timeout'
                assert abs((end-now)-(unix-wall))<=5,'wall_mono_disagreement'
                last,lastwall=now,wall;rss=selfproc.memory_info().rss
                try:
                    proc=psutil.Process(root[0]);assert proc.create_time()==root[1]
                    children=[proc]+proc.children(recursive=True)
                    for item in children:
                        try:owned.add((item.pid,item.create_time()));rss+=item.memory_info().rss
                        except psutil.NoSuchProcess:pass
                except psutil.NoSuchProcess:pass
                for item in bootstrap:
                    try:
                        proc=psutil.Process(item['pid'])
                        if proc.create_time()==item['create_time']:rss+=proc.memory_info().rss
                    except psutil.NoSuchProcess:pass
                assert rss<=1.5*2**30,'source_preparation_memory_limit'
                r['peak_owned_tree_rss_mib']=max(r['peak_owned_tree_rss_mib'],rss/2**20)
                if child.poll() is not None:break
                time.sleep(.1)
        r['exit_code']=child.returncode;r['status']='ok' if child.returncode==0 else 'child_failed'
    except BaseException as e:
        r['status']='technical_failure';r['error_history'].append(dict(type=type(e).__name__,code=str(e) if isinstance(e,AssertionError) else 'preparation_supervision_error'))
    finally:
        if child is not None and child.poll() is None:
            for pid,birth in sorted(owned,reverse=True):
                if pid==selfproc.pid:continue
                try:
                    proc=psutil.Process(pid)
                    if proc.create_time()==birth:proc.kill()
                except psutil.NoSuchProcess:pass
            child.wait(timeout=3)
        live=[];uncertain=[]
        for pid,birth in owned:
            if pid==selfproc.pid:continue
            try:
                if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
            except psutil.NoSuchProcess:pass
            except psutil.AccessDenied:uncertain.append(dict(pid=pid,create_time=birth))
        r.update(owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(owned)],
            child_active_owned_processes=live,uncertain_owned=uncertain,
            cleanup_confirmed=not live and not uncertain,elapsed_seconds=time.monotonic()-mono,
            source_unchanged=hashlib.sha256(script.read_bytes()).hexdigest()==a.sha256)
        if time.monotonic()>=end or time.time()>=unix:r['status']='terminal_timeout'
        save(out/'receipt.json',r)
    print(json.dumps({k:r[k] for k in ['status','cleanup_confirmed','source_unchanged','elapsed_seconds','peak_owned_tree_rss_mib']}))
    raise SystemExit(0 if r['status']=='ok' and r['cleanup_confirmed'] and r['source_unchanged'] else 1)
if __name__=='__main__':main()
