"""Conservative dev-only reuse of successful immutable training artifacts."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
from automl.infrastructure.atomic import atomic_json

FIELDS={'source_sha256','input_sha256','spec','task_sha256','recipe','split_rows_sha256',
        'threads','full_fit','fit_iterations','python','libraries'}


def cache_key(context):
    if set(context)!=FIELDS:raise ValueError('Cache context fields missing or unknown')
    payload=deepcopy(context)
    payload['recipe'].pop('hypothesis',None)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def artifacts(directory):
    directory=Path(directory)
    paths=list(directory.rglob('*'))
    if any(p.is_symlink() for p in paths):raise ValueError('Cache refuses linked artifacts')
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


class ExecutionCache:
    def __init__(self,directory,owned_root):
        self.directory=Path(directory).resolve();self.owned_root=Path(owned_root).resolve()
        if not self.directory.is_relative_to(self.owned_root):raise ValueError('Cache must be owned')
        self.directory.mkdir(parents=True,exist_ok=False);self.entries={}

    def store(self,context,record):
        if record.get('status')!='ok':raise ValueError('Failed worker cannot enter cache')
        origin=Path(record['output_dir']).resolve()
        if not origin.is_relative_to(self.owned_root):raise ValueError('Cache origin must be owned')
        native=json.loads((origin/'result.json').read_text())
        if native.get('status')!='ok' or native.get('metrics')!=record.get('metrics'):raise ValueError('Native result differs')
        job=json.loads((origin/'job.json').read_text())
        for key in ['spec','threads','full_fit']:
            if job[key]!=context[key]:raise ValueError('Stored worker context differs')
        if job.get('fit_iterations')!=context['fit_iterations']:raise ValueError('Iteration context differs')
        effective=lambda recipe:{k:v for k,v in recipe.items() if k!='hypothesis'}
        if effective(job['recipe'])!=effective(context['recipe']):raise ValueError('Stored recipe differs')
        fingerprint=cache_key(context)
        self.entries[fingerprint]={'origin':str(origin),'record':deepcopy(record),'artifacts':artifacts(origin)}
        atomic_json(self.directory/'index.json',self.entries)

    def lookup(self,context):
        fingerprint=cache_key(context);entry=self.entries.get(fingerprint)
        if entry is None:return None
        origin=Path(entry['origin'])
        if artifacts(origin)!=entry['artifacts']:raise ValueError('Successful origin artifacts changed; reuse refused')
        result=deepcopy(entry['record'])
        result.update(cache_hit=True,cache_key=fingerprint,cache_origin=str(origin),actual_worker_launched=False)
        return result

    def execute(self,context,requested_directory,fit):
        result=self.lookup(context)
        if result is not None:
            requested=Path(requested_directory).resolve()
            if not requested.is_relative_to(self.owned_root):raise ValueError('Reuse receipt must be owned')
            requested.mkdir(parents=True,exist_ok=False)
            atomic_json(requested/'cache_reuse.json',{'cache_key':result['cache_key'],'origin':result['cache_origin'],
                'requested_directory':str(requested),'actual_worker_launched':False,'origin_artifacts_verified':True,
                'full_fit_performed_here':False})
            return result
        result=fit()
        if result.get('status')=='ok':self.store(context,result)
        return dict(result,cache_hit=False,actual_worker_launched=True)
