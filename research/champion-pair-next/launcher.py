"""Same-process private environment bootstrap; the pair assigns its only clock."""
from pathlib import Path
import argparse,hashlib,json,os,runpy,subprocess,sys

w=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true',required=True)
    for name in ['self-sha256','coordinator-sha256','auditor-sha256','expected-commit']:
        p.add_argument('--'+name,required=True)
    a=p.parse_args()
    assert sha(Path(__file__))==a.self_sha256
    directory=w/'champion-pair-next-dev';coordinator=directory/'run_pair.py';auditor=directory/'audit_pair.py'
    assert sha(coordinator)==a.coordinator_sha256 and sha(auditor)==a.auditor_sha256
    assert not (w/'cp1').exists(),'Exclusive new pair required; no resume or retry'
    git=['git','-c','safe.directory='+(w/'alfa-hack-automl').as_posix(),'-C',str(w/'alfa-hack-automl')]
    head=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()
    assert head==a.expected_commit
    for name,source in [('run_pair.py',coordinator),('audit_pair.py',auditor),('launcher.py',Path(__file__))]:
        published=subprocess.check_output(git+['show','HEAD:research/champion-pair-next/'+name])
        assert hashlib.sha256(published).hexdigest()==sha(source),'Published source binding'
    cfg=json.loads((w/'private/qwen.json').read_text('utf-8'))
    key=next((cfg[n] for n in ['api_key','key','token','OPENAI_API_KEY'] if cfg.get(n)),None)
    base=next((cfg[n] for n in ['base_url','api_base','OPENAI_BASE_URL'] if cfg.get(n)),
        'https://changellenge.up.railway.app/v1')
    assert isinstance(key,str) and key and str(base).rstrip('/')=='https://changellenge.up.railway.app/v1','Authorized private environment unavailable'
    os.environ.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=str(base),OPENAI_MODEL='qwen/qwen3.8-27b',
        AUTOML_REASONING_EFFORT='off',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    del cfg,key
    sys.argv=[str(coordinator),'--launch','--self-sha256',a.coordinator_sha256,
        '--auditor-sha256',a.auditor_sha256,'--stage0-root-closure','cs0/terminal-root-closure.json',
        '--stage0-root-closure-sha256','06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8',
        '--stage0-exec-session','79591','--bootstrap-launcher','launch_champion_pair_r1.py',
        '--bootstrap-launcher-sha256',a.self_sha256]
    runpy.run_path(str(coordinator),run_name='__main__')

if __name__=='__main__':
    try:main()
    except SystemExit:raise
    except BaseException as exc:
        print(json.dumps(dict(status='champion_pair_launch_failed',exception_type=type(exc).__name__,
            errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),API_secret_emitted=False)))
        raise SystemExit(1) from None
