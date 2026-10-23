"""Run only eight one-thread mocked integration checks for each source setting."""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys,time

sys.dont_write_bytecode=True
WORK=Path(__file__).resolve().parent
OUTPUT=WORK/'four-leaf-default-plan-r1/mock-checks-r3'
sys.path.insert(0,str(WORK/'four-leaf-default-dev/src'))
from automl.infrastructure.processes import wait_owned


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze=json.loads((OUTPUT.parent/'premock-freeze-r3.json').read_text(encoding='utf-8'))
    OUTPUT.mkdir(exist_ok=False)
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in
        ['KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'])}
    env.update(AUTOML_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONUTF8='1',
        PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    rows=[]
    for name,enabled in [('four-leaf-default-dev',False),('four-leaf-default-B-dev',True)]:
        root=WORK/name;before=freeze['sources'][name]
        assert all(digest(root/p)==value for p,value in before.items())
        tree=ast.parse((root/'src/automl/search/policy.py').read_text(encoding='utf-8'))
        flags=[n.value.value for n in tree.body if isinstance(n,ast.Assign) and
            any(isinstance(t,ast.Name) and t.id=='DEFAULT_FIXED_CAPACITY_LAST_SLOT' for t in n.targets)]
        assert flags==[enabled]
        tick=time.monotonic();log=OUTPUT/(name+'.log')
        with log.open('x',encoding='utf-8') as stream:
            process=subprocess.Popen([sys.executable,'-B',str(root/'tests/test_four_leaf_default.py')],
                cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            status=wait_owned(process,timeout=30,memory_bytes=512*2**20)
        text=log.read_text(encoding='utf-8')
        matches=re.findall(r'Ran (\d+) tests in ',text)
        unchanged=all(digest(root/p)==value for p,value in before.items())
        passed=status==0 and matches==['8'] and '\nOK\n' in text and 'skipped=' not in text and unchanged
        rows.append({'tree':name,'source_flag':enabled,'exit_code':status,'checks':8 if matches==['8'] else None,
            'passed':passed,'seconds':round(time.monotonic()-tick,3),'source_unchanged':unchanged,
            'owned_cleanup_confirmed':True,'log_sha256':digest(log)})
        if not passed:break
    result={'status':'passed' if len(rows)==2 and all(r['passed'] for r in rows) else 'failed',
        'rows':rows,'unique_mock_checks':8,'source_config_executions':len(rows),'model_fits':0,
        'api_calls':0,'network_connections':0,'real_worker_launches':0,'threads':1,
        'actual_A_archive_used_as_mock_fixture':False,
        'scope':'New-source OFF fixture vs ON source; synthetic recipes/outcomes only. Actual A is exact88dac and future matched gates/ML remain pending.',
        'promotion':False}
    (OUTPUT/'results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)


if __name__=='__main__':main()
