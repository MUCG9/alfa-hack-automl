"""Local task transitions only. Never starts or recovers an ML process."""
from pathlib import Path
from contextlib import contextmanager
import argparse,hashlib,json,os,re,time

FOLDERS=('drafts','pending','running','results','reviewed','staging')
ID=re.compile(r'[A-Z0-9][A-Z0-9_-]{1,63}\Z')
SHA=re.compile(r'[0-9a-f]{64}\Z')

def need(value,message):
    if not value: raise ValueError(message)

def read(path):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'duplicate JSON key');out[key]=value
        return out
    return json.loads(Path(path).read_text('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,allow_nan=False);f.write('\n')

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identifier(value):
    need(isinstance(value,str) and ID.fullmatch(value),'invalid local identifier')
    return value

def init(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    for name in FOLDERS:(root/name).mkdir(exist_ok=True)
    return root

def inside(root,path):
    root=Path(root).resolve();path=Path(path)
    need(path.resolve().is_relative_to(root),'path outside authoritative queue')
    cursor=path
    while cursor!=root:
        need(not cursor.is_symlink() and not getattr(cursor,'is_junction',lambda:False)(),
             'queue links are not supported')
        cursor=cursor.parent
    return path

@contextmanager
def transition(root):
    root=Path(root).resolve();lock=root/'.transition-lock'
    try:lock.mkdir()
    except FileExistsError:raise ValueError('queue busy or unresolved previous transition; inspect, never auto-steal')
    try:yield root
    finally:lock.rmdir()

def task(packet):
    value=read(packet/'task.json');identifier(value.get('id'))
    need(value.get('schema_version')==1 and value.get('execution_ready') is True,'draft is not executable')
    for key in ('hypothesis','factor','acceptance','repair_policy'):
        need(isinstance(value.get(key),str) and 0<len(value[key])<=4096,'missing experiment contract')
    for key in ('source_sha256','control_sha256','inputs_sha256','splits_sha256','evaluator_sha256'):
        need(isinstance(value.get(key),str) and SHA.fullmatch(value[key]),'missing exact pin')
    need(re.fullmatch('[0-9a-f]{40}',value.get('source_git_sha','')),'missing Git SHA')
    budget=value.get('budget',{})
    for key in ('common_seconds','worker_seconds','memory_bytes','threads'):
        need(type(budget.get(key)) is int and budget[key]>0,'invalid budget')
    need(budget['worker_seconds']<=budget['common_seconds'] and budget['threads']<=2,'incompatible worker cap')
    need(type(budget.get('api_calls')) is int and budget['api_calls']>=0,'invalid API cap')
    deps=value.get('dependencies',[]);need(isinstance(deps,list),'invalid dependencies')
    ids=[]
    for dep in deps:
        ids.append(identifier(dep.get('id')))
        need(dep.get('review_decision') in ('accepted','completed'),'invalid dependency decision')
    need(len(ids)==len(set(ids)) and value['id'] not in ids,'invalid dependency cycle or duplicate')
    return value

def dependencies(root,value):
    for dep in value.get('dependencies',[]):
        packet=inside(root,root/'reviewed'/dep['id'])
        need(packet.is_dir(),'dependency has not been reviewed')
        review=read(packet/'review.json')
        need(review['task_sha256']==digest(packet/'task.json'),'review task changed')
        need(review['terminal_seal_sha256']==digest(packet/'terminal-seal.json'),'reviewed seal changed')
        verify_seal(packet)
        need(review['decision']=='accepted' or dep['review_decision']=='completed','dependency was not accepted')

def promote(root,experiment_id):
    identifier(experiment_id)
    with transition(root) as root:
        src=inside(root,root/'drafts'/experiment_id);value=task(src)
        need(value['id']==experiment_id,'packet ID mismatch');dependencies(root,value)
        for folder in ('pending','results','reviewed'):
            need(not (root/folder/experiment_id).exists(),'duplicate experiment ID')
        need(not list((root/'running').glob('*/'+experiment_id)),'experiment already running')
        os.rename(src,inside(root,root/'pending'/experiment_id))

def claim(root,worker_id):
    identifier(worker_id)
    with transition(root) as root:
        active=[p for p in (root/'running').glob('*/*') if p.is_dir()]
        if active:return None  # Includes unknown/crashed owners; never requeue automatically.
        candidates=sorted(p for p in (root/'pending').iterdir() if p.is_dir())
        for src in candidates:
            inside(root,src);value=task(src);dependencies(root,value)
            need(value['id']==src.name,'packet ID mismatch')
            parent=inside(root,root/'running'/worker_id);parent.mkdir(exist_ok=True)
            dst=parent/src.name;need(not dst.exists(),'destination exists')
            need(not (src/'claim.json').exists(),'pending already claimed')
            write(src/'claim.json',{'worker_id':worker_id,'task_sha256':digest(src/'task.json'),
                'claimed_unix':time.time(),'experiment_clock_assigned':False,
                'launch_authority':'Existing guarded runner and fresh ownership checks required'})
            os.rename(src,dst)
            return value['id']
        return None

TERMINAL_FILES=('task.json','claim.json','receipt.json','metrics.json','closure.json','summary.txt')

def verify_seal(packet):
    seal=read(packet/'terminal-seal.json')
    need(set(seal)==set(TERMINAL_FILES),'invalid terminal seal inventory')
    need(all(digest(packet/name)==value for name,value in seal.items()),'terminal packet changed')

def publish(root,worker_id,experiment_id):
    identifier(worker_id);identifier(experiment_id)
    with transition(root) as root:
        src=inside(root,root/'running'/worker_id/experiment_id);value=task(src)
        need(value['id']==experiment_id,'packet ID mismatch')
        need(read(src/'claim.json')['task_sha256']==digest(src/'task.json'),'claimed task changed')
        result=read(src/'receipt.json');metrics=read(src/'metrics.json')
        need(result.get('status') in ('completed','failed','timeout','oom','interrupted'),'unknown terminal status')
        need(result.get('actual_exec_observed_by_root') is True and result.get('cleanup_confirmed') is True,
             'actual exit and fresh owned cleanup are required before closing task')
        need(result.get('task_sha256')==digest(src/'task.json'),'result task mismatch')
        closure=src/'closure.json';need(digest(closure)==result.get('closure_sha256'),'closure mismatch')
        proof=read(closure)
        need(proof.get('cleanup_confirmed') is True and proof.get('active_owned_processes')==[]
             and proof.get('uncertain_owned',[])==[],
             'unresolved ownership closure')
        need(isinstance(metrics,dict) and (src/'summary.txt').is_file(),'incomplete terminal packet')
        dst=inside(root,root/'results'/experiment_id);need(not dst.exists(),'result already exists')
        write(src/'terminal-seal.json',{name:digest(src/name) for name in TERMINAL_FILES})
        # Files are complete before this rename. Consumers read only results/reviewed.
        os.rename(src,dst)

def review(root,experiment_id,decision):
    identifier(experiment_id);need(decision in ('accepted','rejected','completed'),'invalid decision')
    with transition(root) as root:
        src=inside(root,root/'results'/experiment_id);task(src)
        verify_seal(src)
        expected=digest(src/'task.json')
        need(expected==read(src/'claim.json')['task_sha256']==read(src/'receipt.json')['task_sha256'],
             'published task changed before review')
        dst=inside(root,root/'reviewed'/experiment_id);need(not dst.exists(),'review already exists')
        write(src/'review.json',{'decision':decision,'task_sha256':digest(src/'task.json'),
            'terminal_seal_sha256':digest(src/'terminal-seal.json'),'reviewed_unix':time.time()})
        os.rename(src,dst)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    sub=p.add_subparsers(dest='action',required=True);sub.add_parser('init')
    for name in ('promote','claim','publish','review'):
        q=sub.add_parser(name)
        if name in ('claim','publish'):q.add_argument('--worker',required=True)
        if name in ('promote','publish','review'):q.add_argument('--id',required=True)
        if name=='review':q.add_argument('--decision',required=True)
    a=p.parse_args()
    if a.action=='init':init(a.root);out={'status':'initialized'}
    elif a.action=='promote':promote(a.root,a.id);out={'status':'pending','id':a.id}
    elif a.action=='claim':out={'claimed_id':claim(a.root,a.worker)}
    elif a.action=='publish':publish(a.root,a.worker,a.id);out={'status':'results','id':a.id}
    else:review(a.root,a.id,a.decision);out={'status':'reviewed','id':a.id}
    print(json.dumps(out))
if __name__=='__main__':main()
