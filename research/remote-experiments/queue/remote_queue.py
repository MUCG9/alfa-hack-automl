"""Immutable Git handoff. No job, model, shell payload or patch is executed."""
from pathlib import Path
import argparse,hashlib,json,math,os,re,subprocess,tempfile,time,uuid
JOB_DIR='research/remote-experiments/jobs'
CLAIMS='refs/heads/research/remote-claims/'
RESULTS='refs/heads/research/remote-results/'
MAX_FILE,MAX_TOTAL,MAX_FILES,MAX_JOBS=131072,524288,16,128
EXTENSIONS={'.py','.patch','.json','.txt','.md'}
RESERVED={'con','prn','aux','nul',*[f'com{i}' for i in range(1,10)],*[f'lpt{i}' for i in range(1,10)]}
USAGE={'wall_seconds','cpu_threads','worker_memory_mib','whole_memory_mib','fits','api_calls'}
class QueueError(RuntimeError):pass
def need(v,c):
    if not v:raise QueueError(c)
def digest(b):return hashlib.sha256(b).hexdigest()
def encode(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def ident(v):
    need(isinstance(v,str) and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',v) and v not in RESERVED,'invalid_id');return v
def oid(v):
    need(isinstance(v,str) and re.fullmatch('[0-9a-f]{40}',v),'invalid_git_oid');return v
def safe_text(v):
    need(isinstance(v,str) and len(v.encode())<=MAX_FILE and '\x00' not in v,'invalid_public_text')
    need(not re.search(r'(?i)sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|Bearer\s+[A-Za-z0-9._-]{12,}|-----BEGIN[^\n]*PRIVATE KEY',v),'secret_material_denied')
    need(not re.search(r"""(?i)(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*["'][^"'\n]{8,}["']""",v),'literal_credential_denied')
    text=re.sub(r'(?m)^[+-]{3} /dev/null$', '',v)
    need(not re.search(r'[A-Za-z]:[\\/]|\\\\[A-Za-z0-9][A-Za-z0-9._-]*[\\/]|(?:^|[\s\x22\x27(=])/(?:[A-Za-z][A-Za-z0-9._-]*/)',text),'absolute_or_private_path_denied')
    return v
def public_path(v,artifact=False):
    need(isinstance(v,str) and 1<=len(v)<=180 and '\\' not in v and not v.startswith('/'),'invalid_public_path')
    parts=v.split('/')
    need(all(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',p) and p.lower().split('.')[0] not in RESERVED for p in parts),'unsafe_public_path')
    need(Path(v).suffix.lower() in EXTENSIONS,'public_extension_denied')
    if artifact:
        need(len(parts)==1,'artifact_must_be_flat')
        need(not re.search(r'(?i)(?:^|[_.-])(?:data|dataset|train|predictions?|probabilities|weights?|checkpoints?|secrets?|credentials?|keys?|tokens?)(?:[_.-]|$)',v),'data_prediction_weight_artifact_denied')
    return v
def bounded_json(v,depth=0,count=None):
    if count is None:count=[0]
    count[0]+=1;need(count[0]<=2048 and depth<=8,'json_structure_cap')
    if v is None or type(v) is bool:return
    if type(v) in [int,float]:need(math.isfinite(v),'nonfinite_json');return
    if isinstance(v,str):safe_text(v);need(len(v)<=8192,'json_string_cap');return
    if isinstance(v,list):
        need(len(v)<=128,'json_array_cap')
        for x in v:bounded_json(x,depth+1,count)
        return
    need(isinstance(v,dict) and len(v)<=128,'json_object_cap')
    for k,x in v.items():need(isinstance(k,str) and len(k)<=180,'json_key_cap');safe_text(k);bounded_json(x,depth+1,count)
def decode(raw,cap=MAX_FILE):
    need(len(raw)<=cap,'json_byte_cap')
    try:v=json.loads(raw.decode('utf-8'),parse_constant=lambda _:(_ for _ in ()).throw(QueueError('nonfinite_json')))
    except (ValueError,UnicodeError):raise QueueError('invalid_json')
    bounded_json(v);return v
def validate_job(j):
    need(isinstance(j,dict) and set(j)=={'schema','id','kind','readiness','objective','caps','source_refs','dependencies','expected_outputs'},'job_schema')
    need(j['schema']==1 and j['kind'] in ['source_only','bounded_experiment'] and j['readiness'] in ['draft','ready'],'job_kind_readiness')
    ident(j['id']);safe_text(j['objective']);need(1<=len(j['objective'])<=8192,'job_objective_cap')
    c=j['caps'];need(isinstance(c,dict) and set(c)=={'wall_seconds','cpu_threads','worker_memory_mib','whole_memory_mib','max_fits','max_api_calls'},'job_caps_schema')
    need(all(type(x) is int for x in c.values()) and 1<=c['wall_seconds']<=10800 and 1<=c['cpu_threads']<=2 and 128<=c['worker_memory_mib']<=1536 and c['worker_memory_mib']<=c['whole_memory_mib']<=2048 and 0<=c['max_fits']<=128 and c['max_api_calls']==0,'job_caps_out_of_bounds')
    need(j['kind']!='source_only' or c['max_fits']==0,'source_only_cannot_fit')
    need(isinstance(j['source_refs'],list) and len(j['source_refs'])<=128,'source_refs_cap');seen=set()
    for r in j['source_refs']:
        need(isinstance(r,dict) and set(r)=={'path','sha256'},'source_ref_schema');public_path(r['path'])
        need(isinstance(r['sha256'],str) and re.fullmatch('[0-9a-f]{64}',r['sha256']) and r['path'] not in seen,'source_ref_hash_duplicate');seen.add(r['path'])
    need(j['readiness']!='ready' or j['source_refs'],'ready_job_requires_pinned_source')
    need(isinstance(j['dependencies'],list) and len(j['dependencies'])<=16,'dependency_cap')
    for x in j['dependencies']:ident(x);need(x!=j['id'],'self_dependency')
    need(len(set(j['dependencies']))==len(j['dependencies']),'duplicate_dependency')
    need(isinstance(j['expected_outputs'],list) and len(j['expected_outputs'])<=16,'expected_output_cap')
    for x in j['expected_outputs']:public_path(x,True)
    need(len({x.casefold() for x in j['expected_outputs']})==len(j['expected_outputs']),'case_colliding_declared_outputs')
    need(j['readiness']!='ready' or j['expected_outputs'],'ready_job_requires_outputs')
    bounded_json(j);return j

class Git:
    def __init__(self,repo,remote='origin'):
        self.repo=Path(repo).resolve();self.remote=remote
        need(self.repo.is_dir() and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,63}',remote),'invalid_repo_or_remote')
    def run(self,*args,data=None,ok=True):
        env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GIT_NO_REPLACE_OBJECTS='1',GIT_AUTHOR_NAME='Remote Queue',GIT_AUTHOR_EMAIL='queue@local.invalid',GIT_COMMITTER_NAME='Remote Queue',GIT_COMMITTER_EMAIL='queue@local.invalid')
        for k in ['GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_CONFIG_COUNT']:env.pop(k,None)
        for k in list(env):
            if k.startswith(('QWEN_','OPENAI_','ANTHROPIC_','HF_','HUGGINGFACE_')):env.pop(k,None)
        try:
            with tempfile.TemporaryDirectory(prefix='remote-queue-hooks-') as hooks:
                r=subprocess.run(['git','-C',str(self.repo),'-c','core.hooksPath='+hooks,'-c','protocol.ext.allow=never',*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,env=env,shell=False)
        except subprocess.TimeoutExpired:raise QueueError('git_operation_timeout')
        need(len(r.stdout)<=4*1024*1024,'git_output_cap')
        if r.returncode:
            auth=r.stderr.lower()
            need(not any(x in auth for x in [b'authentication failed',b'could not read username',b'could not read password',b'terminal prompts disabled',b'permission denied (publickey)',b'cannot prompt',b'interactivity has been disabled']),'git_authentication_blocked')
            if ok:raise QueueError('git_operation_failed')
        return r.stdout if ok else r
    def remote_oid(self,ref):
        need(ref.startswith(CLAIMS) or ref.startswith(RESULTS) or re.fullmatch('refs/heads/research/[A-Za-z0-9._/-]+',ref),'undeclared_remote_ref')
        rows=self.run('ls-remote','--refs',self.remote,ref).decode().splitlines();need(len(rows)<=1,'ambiguous_remote_ref')
        if not rows:return None
        value,name=rows[0].split();need(name==ref,'unexpected_remote_ref');return oid(value)
    def fetch(self,ref):
        v=self.remote_oid(ref);need(v is not None,'remote_ref_missing');self.run('fetch','--no-tags','--no-write-fetch-head',self.remote,ref)
        need(self.remote_oid(ref)==v,'remote_ref_changed_during_fetch');self.run('cat-file','-e',v+'^{commit}');return v
    def blob(self,commit,path,cap=MAX_FILE):
        public_path(path);rows=self.run('ls-tree','-z',oid(commit),'--',path).split(b'\0')
        need(len(rows)==2 and rows[1]==b'' and rows[0],'blob_missing_or_multiple')
        head,actual=rows[0].split(b'\t',1);mode,kind,value=head.decode().split()
        need(actual.decode()==path and mode=='100644' and kind=='blob','symlink_or_nonregular_git_file')
        need(int(self.run('cat-file','-s',value))<=cap,'git_blob_cap');return self.run('cat-file','blob',value)
    def files(self,commit):
        out={}
        for entry in self.run('ls-tree','-r','-z',oid(commit)).split(b'\0'):
            if not entry:continue
            head,p=entry.split(b'\t',1);mode,kind,_=head.decode().split();path=p.decode('utf-8')
            need(mode=='100644' and kind=='blob','symlink_or_nonregular_git_file');public_path(path)
            need(len(out)<MAX_FILES+3,'packet_file_count_cap');out[path]=self.blob(commit,path)
        need(sum(map(len,out.values()))<=MAX_TOTAL,'packet_total_byte_cap');return out
    def parent(self,commit):
        v=self.run('rev-list','--parents','-n','1',oid(commit)).decode().split();need(len(v)==2,'exact_single_commit_parent_required');return v[1]
    def commit(self,parent,files,message):
        need(len(files)<=MAX_FILES+3 and sum(map(len,files.values()))<=MAX_TOTAL,'packet_cap')
        def tree(entries):
            rows=[];groups={}
            for path,b in entries.items():
                public_path(path)
                if '/' in path:a,tail=path.split('/',1);groups.setdefault(a,{})[tail]=b
                else:rows.append(('100644','blob',self.run('hash-object','-w','--stdin',data=b).decode().strip(),path))
            for name,values in groups.items():rows.append(('040000','tree',tree(values),name))
            data=''.join(f'{m} {k} {v}\t{n}\n' for m,k,v,n in sorted(rows,key=lambda x:x[3])).encode()
            return self.run('mktree',data=data).decode().strip()
        return oid(self.run('commit-tree',tree(files),'-p',oid(parent),data=(message+'\n').encode()).decode().strip())
    def push_new(self,commit,ref):
        need(self.remote_oid(ref) is None,'immutable_ref_already_exists')
        r=self.run('push','--porcelain',self.remote,oid(commit)+':'+ref,ok=False)
        need(r.returncode==0,'atomic_new_ref_push_rejected');need(self.remote_oid(ref)==commit,'push_readback_not_confirmed')

def snapshot(g,branch,expected=None):
    need(re.fullmatch('research/[A-Za-z0-9][A-Za-z0-9._/-]{0,150}',branch) and '..' not in branch,'research_dispatch_branch_required')
    v=g.fetch('refs/heads/'+branch)
    if expected:need(v==oid(expected),'dispatch_tip_differs_from_pin')
    return v
def jobs(g,dispatch):
    deleted=g.run('log','--no-renames','--format=','--name-only','--diff-filter=D','--max-count=1',oid(dispatch),'--',JOB_DIR).strip()
    need(not deleted,'immutable_published_job_deleted')
    paths=g.run('ls-tree','-r','--name-only',oid(dispatch),'--',JOB_DIR).decode().splitlines();need(len(paths)<=MAX_JOBS,'job_count_cap');out={}
    for path in paths:
        need(path.startswith(JOB_DIR+'/') and path.count('/')==JOB_DIR.count('/')+1,'nested_job_path_denied')
        raw=g.blob(dispatch,path,32768);j=validate_job(decode(raw,32768));need(path==JOB_DIR+'/'+j['id']+'.json','job_id_filename_mismatch')
        revisions=g.run('log','--format=%H','--max-count=65',dispatch,'--',path).decode().splitlines();need(1<=len(revisions)<=64,'job_history_cap')
        for rev in revisions:need(digest(g.blob(rev,path,32768))==digest(raw),'immutable_job_modified_or_deleted')
        for r in j['source_refs']:
            b=g.blob(dispatch,r['path']);need(digest(b)==r['sha256'],'pinned_source_ref_changed');safe_text(b.decode('utf-8'))
        out[j['id']]=(j,raw)
    return out
def prompt(j,claim_sha=None):
    return ('Read REMOTE_AGENT_START.txt once. This tool never executes the job. Use only existing authorized context. No new agent/service, private data or credentials. Keep the original claim clock and failures. Public source/notes only; metrics require independent verification.\nCLAIM_SHA='+str(claim_sha)+'\n'+json.dumps(j,ensure_ascii=False,indent=2))
def read_claim(g,jobid):
    value=g.fetch(CLAIMS+ident(jobid));files=g.files(value);need(set(files)=={'claim.json','job.json','AGENT_PROMPT.txt'},'claim_packet_inventory')
    c=decode(files['claim.json']);j=validate_job(decode(files['job.json'],32768))
    need(isinstance(c,dict) and set(c)=={'schema','job_id','job_sha256','dispatch_sha','worker_id','claimed_at_unix','deadline_unix','nonce'},'claim_schema')
    need(c['schema']==1 and c['job_id']==jobid==j['id'] and c['job_sha256']==digest(files['job.json']) and g.parent(value)==oid(c['dispatch_sha']),'claim_job_parent_binding')
    ident(c['worker_id']);need(type(c['claimed_at_unix']) in [int,float] and math.isfinite(c['claimed_at_unix']) and c['deadline_unix']==c['claimed_at_unix']+j['caps']['wall_seconds'],'claim_original_clock')
    need(g.blob(c['dispatch_sha'],JOB_DIR+'/'+jobid+'.json',32768)==files['job.json'],'claim_dispatch_job_changed')
    need(files['AGENT_PROMPT.txt'].decode()==prompt(j),'claim_prompt_changed');return value,c,j,files
def claim(g,dispatch,jobid,worker):
    ident(jobid);ident(worker)
    if g.remote_oid(CLAIMS+jobid):
        value,c,j,_=read_claim(g,jobid);need(c['worker_id']==worker,'job_already_owned_no_reclaim')
        return dict(status='already_owned_original_clock_retained',claim_sha=value,claim=c,claimed_job=j,AGENT_PROMPT=prompt(j,value))
    available=jobs(g,dispatch);need(jobid in available,'job_not_declared');j,raw=available[jobid];need(j['readiness']=='ready','job_is_draft')
    for other in available:
        if other!=jobid and g.remote_oid(CLAIMS+other) and not g.remote_oid(RESULTS+other):
            _,active,_,_=read_claim(g,other);need(active['worker_id']!=worker,'worker_has_unfinished_claim')
    if j['kind']=='bounded_experiment':bounded_admission(g,dispatch,j,worker)
    for dep in j['dependencies']:need(collect(g,dep)['report']['status']=='completed','dependency_not_completed')
    start=time.time();c=dict(schema=1,job_id=jobid,job_sha256=digest(raw),dispatch_sha=dispatch,worker_id=worker,claimed_at_unix=start,deadline_unix=start+j['caps']['wall_seconds'],nonce=uuid.uuid4().hex)
    value=g.commit(dispatch,{'claim.json':encode(c),'job.json':raw,'AGENT_PROMPT.txt':prompt(j).encode()},'claim '+jobid);g.push_new(value,CLAIMS+jobid)
    return dict(status='claimed',claim_sha=value,claim=c,claimed_job=j,AGENT_PROMPT=prompt(j,value))
def bounded_admission(g,dispatch,job,worker):
    """Only primary-published pinned approval of this worker's source result."""
    for dep in job['dependencies']:
        approval_path='research/remote-experiments/reviews/'+dep+'.json'
        refs=[r for r in job['source_refs'] if r['path']==approval_path]
        if not refs:continue
        _,_,source_job,_=read_claim(g,dep);result=collect(g,dep)
        need(source_job['kind']=='source_only' and result['report']['status']=='completed' and result['worker_id']==worker,'bounded_dependency_worker_or_source_result_mismatch')
        raw=g.blob(dispatch,approval_path);need(digest(raw)==refs[0]['sha256'],'primary_approval_pin_changed')
        a=decode(raw);need(isinstance(a,dict) and set(a)=={'schema','job_id','result_sha','worker_id','approved_for_bounded_experiments','caps'},'primary_approval_schema')
        need(a['schema']==1 and a['job_id']==dep and a['result_sha']==result['result_sha'] and a['worker_id']==worker and a['approved_for_bounded_experiments'] is True,'primary_approval_result_or_worker_mismatch')
        validate_job(dict(job,caps=a['caps']))
        need(all(job['caps'][k]<=a['caps'][k] for k in job['caps']),'requested_caps_exceed_primary_approval')
        return
    raise QueueError('bounded_claim_requires_pinned_primary_capability_approval')
def validate_report(r,j,c):
    need(isinstance(r,dict) and set(r)=={'schema','status','start_unix','deadline_unix','finished_unix','metrics','usage','first_error','secondary_errors'},'report_schema')
    need(r['schema']==1 and r['status'] in ['completed','failed','timeout','blocked'],'report_status')
    need(r['start_unix']==c['claimed_at_unix'] and r['deadline_unix']==c['deadline_unix'],'original_clock_reset_denied')
    need(type(r['finished_unix']) in [int,float] and math.isfinite(r['finished_unix']) and r['finished_unix']>=r['start_unix'],'report_finish_time')
    need(isinstance(r['metrics'],dict) and len(r['metrics'])<=128,'metrics_cap')
    for k,v in r['metrics'].items():need(isinstance(k,str) and re.fullmatch('[A-Za-z0-9_.-]{1,100}',k) and (v is None or type(v) in [int,float] and math.isfinite(v)),'metric_must_be_scalar_finite_or_null')
    need(isinstance(r['usage'],dict) and set(r['usage'])==USAGE,'usage_schema')
    for v in r['usage'].values():need(v is None or type(v) in [int,float] and math.isfinite(v) and v>=0,'invalid_usage')
    for k in ['cpu_threads','fits','api_calls']:need(r['usage'][k] is None or type(r['usage'][k]) is int,'usage_count_requires_integer')
    mapping={'cpu_threads':'cpu_threads','worker_memory_mib':'worker_memory_mib','whole_memory_mib':'whole_memory_mib','fits':'max_fits','api_calls':'max_api_calls','wall_seconds':'wall_seconds'}
    over=any(r['usage'][k] is not None and r['usage'][k]>j['caps'][v] for k,v in mapping.items());numeric=any(v is not None for v in r['metrics'].values())
    if r['status']=='completed':need(not over and r['finished_unix']<=c['deadline_unix'],'completed_result_exceeded_original_caps')
    else:need(not numeric and r['first_error'] is not None,'failure_requires_null_metrics_and_first_error')
    if numeric:need(j['kind']=='bounded_experiment' and all(v is not None for v in r['usage'].values()),'numeric_result_requires_complete_resource_report')
    if j['kind']=='source_only':need(not numeric and r['usage']['fits'] in [0,None] and r['usage']['api_calls'] in [0,None],'source_only_metrics_or_fits_denied')
    def error(v):need(isinstance(v,dict) and set(v)=={'code','detail'} and isinstance(v['code'],str) and re.fullmatch('[A-Za-z0-9_.-]{1,100}',v['code']) and len(safe_text(v['detail']))<=2048,'error_schema')
    if r['first_error'] is not None:error(r['first_error'])
    need(isinstance(r['secondary_errors'],list) and len(r['secondary_errors'])<=16,'secondary_error_cap')
    for e in r['secondary_errors']:error(e)
    bounded_json(r);return r
def artifact_bytes(name,data):
    public_path(name,True);need(len(data)<=MAX_FILE,'artifact_byte_cap')
    try:text=data.decode('utf-8')
    except UnicodeError:raise QueueError('binary_artifact_denied')
    safe_text(text)
    if name.endswith('.json'):bounded_json(decode(data))
    return data
def submit(g,jobid,worker,claim_sha,report,folder):
    value,c,j,cf=read_claim(g,ident(jobid));need(value==oid(claim_sha) and c['worker_id']==ident(worker),'wrong_claim_or_worker');validate_report(report,j,c)
    need(report['finished_unix']<=time.time()+5,'future_report_finish_denied')
    if report['status']=='completed':need(time.time()<=c['deadline_unix'],'publication_started_after_deadline')
    need(g.remote_oid(RESULTS+jobid) is None,'immutable_result_already_exists')
    folder=Path(folder);need(folder.is_dir() and not folder.is_symlink(),'artifact_folder_required');art={}
    for p in folder.iterdir():
        need(p.is_file() and not p.is_symlink(),'artifact_symlink_or_directory_denied');need(p.stat().st_size<=MAX_FILE,'artifact_byte_cap');art[p.name]=artifact_bytes(p.name,p.read_bytes())
    need(len(art)<=MAX_FILES and sum(map(len,art.values()))<=MAX_TOTAL//2,'artifact_packet_cap')
    need(len({n.casefold() for n in art})==len(art),'case_colliding_artifacts')
    need(set(art)<=set(j['expected_outputs']) and (report['status']!='completed' or set(art)==set(j['expected_outputs'])),'artifact_names_differ_from_declared_outputs')
    r=dict(schema=1,job_id=jobid,job_sha256=c['job_sha256'],dispatch_sha=c['dispatch_sha'],claim_sha=value,worker_id=worker,submitted_at_unix=time.time(),nonce=uuid.uuid4().hex,report=report,artifacts_sha256={n:digest(b) for n,b in sorted(art.items())},verification='remote_reported_requires_independent_verification',promotion=False)
    files={'result.json':encode(r),'job.json':cf['job.json'],'claim.json':cf['claim.json']};files.update({'artifacts/'+n:b for n,b in art.items()})
    result=g.commit(value,files,'result '+jobid);g.push_new(result,RESULTS+jobid)
    return dict(status='submitted',result_sha=result,actual_push_completed_unix=time.time(),independent_clock_or_metric_verification=False,promotion=False)
def collect(g,jobid,output=None):
    ident(jobid);claim_oid,c,j,cf=read_claim(g,jobid);value=g.fetch(RESULTS+jobid);files=g.files(value)
    need({'result.json','job.json','claim.json'}<=set(files),'result_packet_inventory');need(files['job.json']==cf['job.json'] and files['claim.json']==cf['claim.json'],'result_job_or_claim_bytes_changed')
    r=decode(files['result.json']);need(isinstance(r,dict) and set(r)=={'schema','job_id','job_sha256','dispatch_sha','claim_sha','worker_id','submitted_at_unix','nonce','report','artifacts_sha256','verification','promotion'},'result_schema')
    need(r['schema']==1 and r['job_id']==jobid and r['job_sha256']==c['job_sha256'] and r['dispatch_sha']==c['dispatch_sha'] and r['claim_sha']==claim_oid and r['worker_id']==c['worker_id'] and g.parent(value)==claim_oid,'result_binding_failed')
    need(r['verification']=='remote_reported_requires_independent_verification' and r['promotion'] is False,'result_may_not_self_promote');validate_report(r['report'],j,c)
    need(type(r['submitted_at_unix']) in [int,float] and math.isfinite(r['submitted_at_unix']) and r['submitted_at_unix']>=r['report']['finished_unix'],'result_submission_clock')
    need(r['report']['status']!='completed' or r['submitted_at_unix']<=c['deadline_unix'],'success_submission_after_deadline');actual={}
    for name,b in files.items():
        if name.startswith('artifacts/'):leaf=name.removeprefix('artifacts/');actual[leaf]=digest(artifact_bytes(leaf,b))
        else:need(name in {'result.json','job.json','claim.json'},'unexpected_result_file')
    need(actual==r['artifacts_sha256'],'result_artifact_hash_mismatch')
    need(len({n.casefold() for n in actual})==len(actual),'case_colliding_artifacts')
    need(set(actual)<=set(j['expected_outputs']) and (r['report']['status']!='completed' or set(actual)==set(j['expected_outputs'])),'artifact_names_differ_from_declared_outputs')
    if output:
        target=Path(output);need(not target.exists(),'exclusive_collect_output_required');target.mkdir(parents=True)
        for name,b in files.items():p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return dict(result_sha=value,claim_sha=claim_oid,job_id=jobid,worker_id=c['worker_id'],report=r['report'],artifacts_sha256=actual,verification='remote_reported_requires_independent_verification',independent_clock_verification=False,promotion=False)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--remote',default='origin');p.add_argument('--dispatch-branch',required=True);sub=p.add_subparsers(dest='command',required=True)
    for name in ['list','poll']:q=sub.add_parser(name);q.add_argument('--worker-id')
    q=sub.add_parser('claim');q.add_argument('--job-id',required=True);q.add_argument('--worker-id',required=True);q.add_argument('--dispatch-sha')
    q=sub.add_parser('submit');q.add_argument('--job-id',required=True);q.add_argument('--worker-id',required=True);q.add_argument('--claim-sha',required=True);q.add_argument('--report',required=True);q.add_argument('--artifacts',required=True)
    q=sub.add_parser('collect');q.add_argument('--job-id',required=True);q.add_argument('--output')
    a=p.parse_args()
    try:
        g=Git(a.repo,a.remote)
        if a.command=='submit':out=submit(g,a.job_id,a.worker_id,a.claim_sha,decode(Path(a.report).read_bytes()),a.artifacts)
        elif a.command=='collect':out=collect(g,a.job_id,a.output)
        else:
            dispatch=snapshot(g,a.dispatch_branch,getattr(a,'dispatch_sha',None))
            if a.command=='claim':out=claim(g,dispatch,a.job_id,a.worker_id)
            else:
                available=jobs(g,dispatch);rows=[dict(job_id=i,readiness=j['readiness'],claim_sha=g.remote_oid(CLAIMS+i),result_sha=g.remote_oid(RESULTS+i)) for i,(j,_) in sorted(available.items())]
                out=dict(status='observed_only_no_agent_connection_claim',dispatch_sha=dispatch,jobs=rows)
                if a.command=='poll':
                    if a.worker_id:
                        ident(a.worker_id)
                        for row in rows:
                            if row['claim_sha'] and not row['result_sha']:
                                value,c,j,_=read_claim(g,row['job_id'])
                                if c['worker_id']==a.worker_id:
                                    out.update(status='already_owned_original_clock_retained',claim_sha=value,claim=c,claimed_job=j,AGENT_PROMPT=prompt(j,value));break
                    for row in rows:
                        if 'claimed_job' not in out and row['readiness']=='ready' and row['claim_sha'] is None:out.update(next_job=row['job_id'],AGENT_PROMPT=prompt(available[row['job_id']][0]));break
        print(json.dumps(out,ensure_ascii=False,allow_nan=False))
    except (QueueError,OSError,ValueError) as e:
        code=str(e) if isinstance(e,QueueError) else type(e).__name__
        print(json.dumps(dict(status='blocked' if code=='git_authentication_blocked' else 'failed',code=code,raw_git_error_suppressed=True)));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
