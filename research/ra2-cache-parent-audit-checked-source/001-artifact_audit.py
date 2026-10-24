"""Fixed-artifact audit only: no model/project runtime imports or fitting."""
from pathlib import Path
import argparse, csv, hashlib, importlib.util, json, math, time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'rq6'
R4=('uq3-cadence-hpo-next-dev/candidate/r4_adapter.py','823d9629119bcd03560cafb62e8b240af8dea5b3f3ba63b4d196b96a62a518cd')
LOSS=('uq3-cadence-hpo-next-dev/candidate/audit_pair.py','f58a17c218ca89461c3c97c3498d197fa105b5a8ea0b240b26b232b12badf7ff')

def need(value,code):
    if not value:raise RuntimeError(code)

def load(p):return json.loads(Path(p).read_text('utf-8'))

def framed_observation(path,check=lambda:None):
    """Independent bounded journal validation; no candidate codec import.

    Validate every complete record, retain the latest complete record only when
    the final append is incomplete. Existing freshness/nonce/identity/cap
    predicates below remain mandatory; truncation never creates a fresh sample.
    """
    path=Path(path);check()
    need(not path.is_symlink() and path.is_file() and 0<path.stat().st_size<=1024**3,'CLASS_observation_regular_bounded_journal')
    latest=None;pending=b'';maximum=262144
    with path.open('rb') as stream:
        while True:
            check();block=stream.read(65536)
            if not block:break
            pending+=block
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1);check()
                need(77<len(line)<=maximum+77 and line[:5]==b'OBS1 ' and line[11:12]==b' '
                    and line[76:77]==b' ','CLASS_complete_observation_frame_header')
                length,digest_hex,payload=line[5:11],line[12:76],line[77:]
                need(all(v in b'0123456789abcdef' for v in length+digest_hex)
                    and 0<int(length,16)<=maximum and len(payload)==int(length,16)
                    and hashlib.sha256(payload).hexdigest().encode('ascii')==digest_hex,'CLASS_complete_observation_frame_integrity')
                value=json.loads(payload.decode('utf-8'),parse_constant=lambda value:need(False,'CLASS_nonfinite_observation_JSON'))
                need(type(value) is dict,'CLASS_complete_observation_frame_object');latest=value
            need(len(pending)<=maximum+80,'CLASS_unbounded_incomplete_observation_tail')
    check();need(latest is not None,'CLASS_no_complete_observation_record')
    return latest

def digest(p,check=lambda:None):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):check();h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def lexical_witness(path,columns):
    """Independent stdlib lexical authority; empty is distinct from NA and001."""
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);need(reader.fieldnames is not None
            and len(reader.fieldnames)==len(set(reader.fieldnames)) and set(columns)<=set(reader.fieldnames),'lexical_header')
        values={c:[] for c in columns}
        for row in reader:
            need(None not in row and all(value is not None for value in row.values()),'lexical_row_width')
            for c in columns:values[c].append(row[c])
    return values

class DeclaredClassCSV:
    """Audit transport facade ONLY for explicit classification cell/path pairs."""
    def __init__(self,pandas,roles):self.pandas,self.roles=pandas,roles
    def __getattr__(self,name):return getattr(self.pandas,name)
    def read_csv(self,path,*args,**kwargs):
        columns=self.roles.get(str(Path(path).resolve()),())
        options=dict(kwargs);converters=dict(options.get('converters') or {})
        for name in columns:converters[name]=str
        if columns:options['converters']=converters
        frame=self.pandas.read_csv(path,*args,**options)
        if columns:
            witness=lexical_witness(path,columns)
            need(all(frame[c].tolist()==witness[c] for c in columns),'declared_class_lexical_drift')
        return frame

SAVED_RUNTIME_SHA256='db277eefd3f94a62785d28c0c1d09c25c94ca55012c9a69bc06996482378ee82'
SAVED_AUDITOR_SHA256='910f8c5374b147c1d665ed01cb93f9b492f17d5cee330621f0f23685854b7209'
SAVED_REFS={
    'original_campaign':('rq6/campaign.json','60afb434d1e6f943d05be02c0761cdb255745fe3e543961ed407e559eaf38725'),
    'original_root':('rq6/terminal-root-closure.json','f9e26b3a9e9223fc903909aafd3172dbd0b4242b142d9d29cf8593a3379d9810'),
    'current_negative':('rq6/current-negative-closure.json','fe8941210806633144b53f2f1345daa3922f7099dc81148637da7240592ce0bc'),
    'post_tool_confirmation':('rq6/current-negative-post-tool-confirmation.json','9ad55350293113fbf7c026762979e06cc40a350b948718c39b998b8dea316fdc')}

def exact_identity(row):
    if (type(row) is not dict or type(row.get('pid')) is not int or row['pid']<=0
        or type(row.get('create_time')) not in (int,float) or not math.isfinite(row['create_time'])
        or row['create_time']<=0):return None
    return row['pid'],row['create_time']

def identity_inventory(rows):
    need(type(rows) is list and len(rows)<=30000,'repair_typed_bounded_identity_list')
    keys=[exact_identity(row) for row in rows]
    need(None not in keys and len(keys)==len(set(keys)),'repair_unique_exact_identity_list')
    return set(keys)

def repair_deadlines(context,unix,monotonic):
    clock=context['clock']
    need(type(clock) is dict and set(clock)=={'start_unix','start_monotonic','absolute_deadline_unix',
        'common_deadline_monotonic','audit_start_unix','audit_start_monotonic','audit_deadline_unix',
        'audit_deadline_monotonic'},'repair_exact_clock_fields')
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in clock.values()),'repair_finite_original_clocks')
    need(clock['absolute_deadline_unix']==clock['start_unix']+600
        and clock['common_deadline_monotonic']==clock['start_monotonic']+600
        and clock['audit_deadline_unix']==clock['audit_start_unix']+120
        and clock['audit_deadline_monotonic']==clock['audit_start_monotonic']+120
        and clock['start_unix']<=clock['audit_start_unix']<clock['audit_deadline_unix']<=clock['absolute_deadline_unix']
        and clock['start_monotonic']<=clock['audit_start_monotonic']<clock['audit_deadline_monotonic']<=clock['common_deadline_monotonic'],
        'repair_same600_and_phase120')
    need(type(unix) in (int,float) and math.isfinite(unix) and type(monotonic) in (int,float) and math.isfinite(monotonic)
        and clock['audit_start_unix']<=unix<min(clock['absolute_deadline_unix'],clock['audit_deadline_unix'])
        and clock['audit_start_monotonic']<=monotonic<min(clock['common_deadline_monotonic'],clock['audit_deadline_monotonic']),
        'repair_original_common_or_phase_deadline')

def repair_lineage(context,root,negative,post,clock,manifest_sha256,campaign_sha256):
    """Current absence qualifies a NEW audit; it never repairs the old clock."""
    need(root.get('schema')=='standard-repair-qualification-root-closure-v1'
        and root.get('technical_procedure_passed') is False
        and root.get('actual_exec_session')==49569 and root.get('actual_exec_exit_code_observed_by_root')==1
        and root.get('actual_tool_evidence')=='dbc6a1'
        and root.get('manifest_sha256')==manifest_sha256
        and all(root.get(k) is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
        and root.get('root_errors')==[] and root.get('active_owned_processes')==[] and root.get('uncertain_owned')==[],
        'repair_original_failed_root_exact')
    need(all(root.get(k)==clock[v] for k,v in [('original_start_unix','start_unix'),
        ('original_deadline_unix','absolute_deadline_unix'),('original_start_monotonic','start_monotonic'),
        ('original_end_monotonic','common_deadline_monotonic')]),'repair_old_clock_not_reset')
    for record,schema,count in [(negative,'rq6-separate-current-negative-closure-v1',8010),
            (post,'rq6-current-negative-post-tool-confirmation-v1',8013)]:
        need(record.get('schema')==schema and record.get('technical_procedure_passed') is False
            and record.get('original_RQ6_FAIL_preserved') is True and record.get('root60_requalified') is False
            and record.get('old_clock_reset') is False and record.get('new_qualification') is False
            and all(record.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed',
                'current_temporary_absent','inside_original6000'))
            and record.get('original_manifest_sha256')==manifest_sha256
            and record.get('original_campaign_sha256')==campaign_sha256
            and record.get('original_negative_root_sha256')==SAVED_REFS['original_root'][1]
            and record.get('known_count')==count and type(record.get('known_count')) is int
            and record.get('known_exact_live')==[] and record.get('uncertain')==[]
            and record.get('source_pins_checked')==1017 and record.get('new_model_fits')==0
            and record.get('API_calls')==0,'repair_actual_current_negative_not_old_PASS')
        need(record.get('actual_failed_driver')=={'session':49569,'exit_code':1,'tool':'dbc6a1'},'repair_failed_driver_preserved')
        closer=record.get('actual_failed_frozen_closer',{})
        need(closer.get('exit_code')==1 and closer.get('tool')=='fb3841','repair_failed_closer_preserved')
        need(len(identity_inventory(record.get('known_identities')))==count,'repair_known_count')
    prior=identity_inventory(negative['known_identities']);current=identity_inventory(post['known_identities'])
    old_preparers=identity_inventory(negative.get('observer_preparer_identities'))
    new_preparers=identity_inventory(post.get('observer_preparer_identities'))
    need(len(old_preparers)==len(new_preparers)==3 and not prior&old_preparers
        and current==prior|old_preparers and not current&new_preparers,
        'repair_exact_current_observer_union')
    root_owned=identity_inventory(root.get('owned_identities'))|identity_inventory(root.get('closure_preparer_identities'))
    need(root_owned<=prior and post.get('negative_closure_sha256')==SAVED_REFS['current_negative'][1]
        and post.get('actual_negative_observer')=={'exit_code':0,'tool':'b449e3'}
        and post.get('post_tool_current_confirmation') is True
        and context.get('actual_current_negative_observer')=={'exit_code':0,'tool':'b449e3'}
        and context.get('actual_post_tool_observer')=={'exit_code':0,'tool':'317ee6'},'repair_actual_posttool_linkage')
    return current

def validate_repair_context(context,manifest_path,manifest_sha256,cfg,campaign,clock,output,check):
    need(context.get('schema')=='rq6-saved-terminal-audit-repair-private-v1'
        and context.get('original_failure_preserved') is True
        and context.get('original_RQ6_procedure_requalified') is False,'repair_explicit_separate_procedure')
    def ref(name,expected_path,expected_sha256,decode=True):
        value=context.get(name)
        need(type(value) is dict and set(value)=={'path','sha256'} and Path(value['path']).is_absolute()
            and Path(value['path']).resolve()==Path(expected_path).resolve() and value['sha256']==expected_sha256,
            'repair_exact_reference_'+name)
        need(digest(value['path'],check)==value['sha256'],'repair_reference_changed_'+name)
        return load(value['path']) if decode else None
    ref('original_manifest',manifest_path,manifest_sha256)
    need(manifest_sha256=='f4eb5dca1e3560de66206c76937d0314a790047436bd80f218422c9324afd65a','repair_exact_RQ6_manifest')
    ref('original_auditor',WORK/'last-submission-repair-qualification-next-dev-r6/artifact_audit.py',SAVED_AUDITOR_SHA256,False)
    saved={name:ref(name,WORK/relative,h) for name,(relative,h) in SAVED_REFS.items()}
    need(saved['original_campaign']==campaign and campaign.get('status')=='failed'
        and campaign.get('artifact_procedure_passed') is False,'repair_original_campaign_FAIL_retained')
    runtime=context.get('executor_runtime_sha256')
    need(runtime==SAVED_RUNTIME_SHA256 and cfg['executor']['members_sha256'].get('automl_release_runtime.py')==runtime,
        'repair_exact_successful_sample_producer_source')
    need(Path(context.get('output','')).is_absolute() and Path(context['output']).resolve()==Path(output).resolve()
        and Path(output).resolve().is_relative_to(WORK/'ra2') and not Path(output).exists()
        and not Path(output).is_symlink(),'repair_new_exclusive_output')
    known=repair_lineage(context,saved['original_root'],saved['current_negative'],saved['post_tool_confirmation'],
        clock,manifest_sha256,SAVED_REFS['original_campaign'][1])
    current=current_caller_proof(context,check)
    need(known<=current['known'],'current_caller_must_cover_saved_RQ6_worker_scope')
    return {'producer_schema':'RQ6_CLASS_stable_sample_then_observed_exit_v1','runtime_sha256':runtime,
        'known':current['known'],'caller_pins':current['pins']}

def saved_terminal_bridge(record,proof,owned,intrinsic):
    """Qualify saved stable sample + later exit/cleanup; original None stays None.

    No terminal timestamp exists in this producer schema. Source ordering and
    exact saved/current-owned identities provide the proof, not a backfilled
    terminal status, timestamp, sampled zero, or a fresh observation claim.
    """
    if (type(record) is not dict or record.get('terminal_resource_observation','missing') is not None
        or type(proof) is not dict or proof.get('producer_schema')!='RQ6_CLASS_stable_sample_then_observed_exit_v1'
        or proof.get('runtime_sha256')!=SAVED_RUNTIME_SHA256 or type(proof.get('known')) is not set
        or type(owned) is not set or type(intrinsic) is not dict
        or record.get('status')!='ok' or record.get('strict_runtime') is not True or record.get('cleanup_confirmed') is not True
        or type(record.get('parent_observed_worker_exit_code')) is not int or record['parent_observed_worker_exit_code']!=0):return False
    root=exact_identity(record.get('worker_resource_root'));own=exact_identity(record.get('worker_resource_self'))
    if root is None or own is None or root==own or not {root,own}<=owned or not {root,own}<=proof['known']:return False
    sample=record.get('verified_resource_sample');receipt=record.get('release_original_clock')
    if (type(sample) is not dict or sample.get('schema')!='verified-known-resource-sample-v1'
        or sample.get('scope')!='sampled_stable_known_RSS_not_OS_lifetime_peak'
        or type(sample.get('sampled')) is not list or type(sample.get('departed')) is not list
        or len(sample['sampled'])+len(sample['departed'])>30000
        or type(sample.get('required_count')) is not int or sample['required_count']!=1
        or type(sample.get('sampled_count')) is not int or sample['sampled_count']!=len(sample['sampled'])
        or type(sample.get('known_count')) is not int or sample['known_count']<len(sample['sampled'])+len(sample['departed'])
        or type(receipt) is not dict or any(receipt.get(k)!=intrinsic.get(k) for k in
            ('start_unix','start_monotonic','deadline_unix','deadline_monotonic'))
        or any(type(receipt.get(k)) not in (int,float) or not math.isfinite(receipt[k]) or receipt[k]<=0 for k in
            ('start_unix','start_monotonic','deadline_unix','deadline_monotonic'))
        or receipt.get('deadline_unix')<=receipt['start_unix'] or receipt.get('deadline_monotonic')<=receipt['start_monotonic']
        or 'actual_failure_type' not in receipt or receipt.get('actual_failure_type') is not None
        or type(receipt.get('actual_resource_samples')) is not int or receipt['actual_resource_samples']<=0
        or receipt.get('observation_gap_limit_seconds')!=10 or receipt.get('resource_sample_cadence_seconds')!=.25
        or receipt.get('resource_limit_bytes')!=2048*2**20):return False
    sampled={};departed=set()
    for row in sample['sampled']:
        key=exact_identity(row)
        if key is None or key in sampled or type(row.get('rss_bytes')) is not int or row['rss_bytes']<0:return False
        sampled[key]=row['rss_bytes']
    for row in sample['departed']:
        key=exact_identity(row);replacement=row.get('replacement_create_time') if type(row) is dict else None
        if key is None or key in departed or key in sampled or row.get('rss_bytes') is not None:return False
        if row.get('state')=='fresh_confirmed_absent':
            if replacement is not None:return False
        elif row.get('state')=='fresh_confirmed_reused':
            if type(replacement) not in (int,float) or not math.isfinite(replacement) or replacement<=0 or replacement==key[1]:return False
        else:return False
        departed.add(key)
    if root not in sampled or own not in sampled or sampled[root]<=0 or sampled[own]<=0:return False
    worker=sum(v for key,v in sampled.items() if key!=own);whole=worker+sampled[own]
    peak_worker=record.get('observed_worker_tree_peak_bytes');peak_whole=record.get('observed_combined_peak_bytes')
    return (record.get('worker_memory_limit_bytes')==1536*2**20 and record.get('whole_memory_limit_bytes')==2048*2**20
        and type(peak_worker) is int and worker<=peak_worker<=1536*2**20
        and type(peak_whole) is int and whole<=peak_whole<=2048*2**20)


def verified_cached_mixture_parent(record,folder,phase,full_fit,verified,report,verified_records):
    """A saved R4-verified probability mixture is not an actual fitting leaf.

    This branch proves every immediate cached child is already in the same R4
    verification graph. That graph is recursively populated before its parent.
    The unchanged loop still requires fitting receipts for EVERY real leaf.
    Missing receipts on any non-cache leaf are never excused by its recipe.
    """
    recipe=record.get('recipe');folder=Path(folder).resolve()
    if (record.get('training_reused') is not True or record.get('status')!='ok'
        or record.get('full_fit') is not False or full_fit is not False
        or phase not in ('primary','confirmation') or record.get('components')
        or (folder/'job.json').exists() or type(recipe) is not dict or recipe.get('engine')!='ensemble'
        or type(recipe.get('components')) is not list or not recipe['components']
        or type(recipe.get('weights')) is not list or len(recipe['weights'])!=len(recipe['components'])
        or any(type(w) not in (int,float) or not math.isfinite(w) or w<0 for w in recipe['weights'])
        or sum(recipe['weights'])<=0 or type(verified) is not dict
        or verified.get('folder')!=folder or verified.get('recipe')!=recipe
        or verified_records.get((str(folder),phase,False)) is not verified
        or type(verified.get('mixture_children')) is not int or verified['mixture_children']!=len(recipe['components'])):
        return None
    field='experiments' if phase=='primary' else 'confirmations';rows=report.get(field)
    if type(rows) is not list:return None
    children=[]
    for component in recipe['components']:
        matches=[row for row in rows if row.get('status')=='ok' and row.get('recipe')==component]
        if len(matches)!=1 or type(matches[0].get('output_dir')) is not str:return None
        path=Path(matches[0]['output_dir'])
        if not path.is_absolute():return None
        path=path.resolve();key=(str(path),phase,False);child=verified_records.get(key)
        if (path==folder or type(child) is not dict or child.get('folder')!=path
            or child.get('recipe')!=component or path in children):return None
        children.append(path)
    return children


def current_caller_proof(context,check):
    """Hash-bound actual RA2 caller, with separately preserved RA1 failure.

    The private manifest is referenced from the runtime context, not from its
    own immutable map; this avoids a circular hash. All predecessor refs are
    separately members of that private immutable map and rehashed here.
    """
    ref=context.get('current_caller_manifest')
    need(type(ref) is dict and set(ref)=={'path','sha256'} and Path(ref['path']).is_absolute()
         and Path(ref['path']).is_file() and not Path(ref['path']).is_symlink() and Path(ref['path']).stat().st_size<=4*2**20
         and digest(ref['path'],check)==ref['sha256'],'actual_current_caller_manifest_required')
    caller=load(ref['path']);pins=caller.get('immutable_files');source=str(Path(__file__).resolve())
    need(caller.get('schema')=='postfailure-standard-artifact-qualification-private-v1'
         and caller.get('readiness')=='READY_REVIEWED_FROZEN' and caller.get('missing_bindings')==[]
         and caller.get('output')==str(WORK/'ra2') and type(pins) is dict and 1<=len(pins)<=4096
         and caller.get('common_seconds')==600 and caller.get('caps')==dict(setup=180,audit=[120,90],final=240,root=60)
         and pins.get(source)==digest(__file__,check)
         and caller.get('auditor')==dict(path=source,sha256=pins[source]),'exact_current_RA2_caller_source_and_caps')
    for path,h in pins.items():
        need(type(path) is str and Path(path).is_absolute() and type(h) is str and len(h)==64
             and all(c in '0123456789abcdef' for c in h) and digest(path,check)==h,'current_caller_immutable_changed')
    prior=caller.get('ra1_previous')
    need(type(prior) is dict and set(prior)=={'manifest','campaign','root','negative','post',
        'driver_actual','closer_actual','negative_actual','post_actual'},'exact_RA1_previous_proof_fields')
    def bound(name):
        value=prior[name]
        need(type(value) is dict and set(value)=={'path','sha256'} and Path(value['path']).is_absolute()
             and pins.get(value['path'])==value['sha256'] and digest(value['path'],check)==value['sha256'],
             'current_RA1_predecessor_ref_changed')
        return load(value['path'])
    expected={'manifest':(WORK/'private/ra1-manifest.ready-r2.json','84b93538b73d73e2636b0730ad4cd105b2901633990e4654ccf9463e724d63f3'),
        'campaign':(WORK/'ra1/campaign.json','20fb2e4f4251218e62f1e91126ce581dc2c4cfc6a692d004d4b1b6aad7585536'),
        'root':(WORK/'ra1/terminal-root-closure.json','94132c7d68a49e7e85ee795f648db724891b8ea6ba7f670dacb151ac63afc6ca')}
    for key,(path,h) in expected.items():need(prior[key]==dict(path=str(path),sha256=h),'exact_RA1_failed_source_refs')
    documents={key:bound(key) for key in ('manifest','campaign','root','negative','post')}
    root=documents['root'];state=documents['campaign']
    need(prior['driver_actual']==dict(session=25644,exit_code=1,tool='19905f')
         and prior['closer_actual']==dict(exit_code=1,tool='8efa0b')
         and root.get('schema')=='postfailure-standard-artifact-qualification-root-v1'
         and root.get('technical_procedure_passed') is False and root.get('actual_exec_session')==25644
         and root.get('actual_exec_exit_code_observed_by_root')==1 and root.get('actual_tool_evidence')=='19905f'
         and root.get('manifest_sha256')==prior['manifest']['sha256']
         and all(root.get(k) is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
         and root.get('independent_audit') is None and root.get('quality_metric') is None
         and state.get('status')=='failed' and state.get('artifact_procedure_passed') is False
         and state.get('independent_audit') is None,'RA1_failed_procedure_preserved_not_requalified')
    negative,post=documents['negative'],documents['post']
    for value,schema,count in [(negative,'ra1-separate-current-negative-closure-v1',8039),
            (post,'ra1-current-negative-post-tool-confirmation-v1',8042)]:
        need(value.get('schema')==schema and value.get('technical_procedure_passed') is False
             and value.get('original_RA1_FAIL_preserved') is True and value.get('original_RQ6_FAIL_preserved') is True
             and value.get('root60_requalified') is False and value.get('source_pins_checked')==1560
             and all(value.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent'))
             and value.get('original_manifest_sha256')==prior['manifest']['sha256']
             and value.get('original_campaign_sha256')==prior['campaign']['sha256']
             and value.get('original_negative_root_sha256')==prior['root']['sha256']
             and value.get('actual_failed_driver')==prior['driver_actual']
             and value.get('actual_failed_frozen_closer')==prior['closer_actual']
             and value.get('known_exact_live')==value.get('uncertain')==[]
             and len(identity_inventory(value['known_identities']))==value.get('known_count')==count,
             'actual_current_RA1_negative_proofs_required')
    for key in ('negative_actual','post_actual'):
        value=prior[key];need(type(value) is dict and set(value)=={'exit_code','tool'} and type(value['exit_code']) is int
            and value['exit_code']==0 and type(value['tool']) is str and value['tool'] and 'PENDING' not in value['tool'],
            'actual_current_RA1_observer_exit_required')
    known=identity_inventory(post['known_identities']);pre=identity_inventory(negative['known_identities'])
    observers=identity_inventory(negative['observer_preparer_identities']);later=identity_inventory(post['observer_preparer_identities'])
    need(len(observers)==len(later)==3 and not pre&observers and known==pre|observers
         and not known&later and len(known|later)==8045
         and post.get('negative_closure_sha256')==prior['negative']['sha256']
         and post.get('actual_negative_observer')==prior['negative_actual']
         and post.get('post_tool_current_confirmation') is True
         and identity_inventory(root['owned_identities']+root['closure_preparer_identities'])<=pre,
         'complete_current_RA1_root_and_observer_union_required')
    return {'known':known,'pins':pins}


def verified_terminal(record,*,repair=None,owned=(),intrinsic=None):
    """Only the new exact-known departure variant needs this typed bridge.

    Original two statuses retain their existing predicate. The new branch is
    bound to parent-captured worker/self identities and completed strict cleanup.
    A departed old identity has unknown RSS, never a measured zero.
    """
    terminal=record.get('terminal_resource_observation',{})
    if terminal is None:return saved_terminal_bridge(record,repair,owned,intrinsic)
    if type(terminal) is not dict:return False
    if terminal.get('status') in {'sampled_before_terminal_acceptance','root_absent_after_observed_exit'}:return True
    if terminal.get('status')!='fresh_known_root_departed_after_observed_exit':return False
    def identity(row):
        if (type(row) is not dict or type(row.get('pid')) is not int or row['pid']<=0
            or type(row.get('create_time')) not in (int,float) or not math.isfinite(row['create_time'])
            or row['create_time']<=0):return None
        return row['pid'],row['create_time']
    sample=record.get('verified_resource_sample');root=identity(record.get('worker_resource_root'));own=identity(record.get('worker_resource_self'))
    if (root is None or own is None or root==own or type(sample) is not dict
        or sample.get('schema')!='verified-known-resource-sample-v1'
        or type(sample.get('sampled')) is not list or type(sample.get('departed')) is not list
        or len(sample['sampled'])+len(sample['departed'])>30000
        or type(sample.get('required_count')) is not int or sample['required_count']!=1
        or type(sample.get('sampled_count')) is not int or sample['sampled_count']!=len(sample['sampled'])
        or type(sample.get('known_count')) is not int or sample['known_count']<len(sample['sampled'])+len(sample['departed'])
        or sample.get('scope')!='sampled_stable_known_RSS_not_OS_lifetime_peak'
        or record.get('parent_observed_worker_exit_code')!=0 or type(record.get('parent_observed_worker_exit_code')) is not int
        or record.get('cleanup_confirmed') is not True
        or terminal.get('worker_root_rss_bytes') is not None
        or terminal.get('remaining_owned_cleanup_still_required') is not True
        or terminal.get('departed')!=sample['departed']):return False
    sampled={};departed={}
    for row in sample['sampled']:
        key=identity(row)
        if key is None or key in sampled or type(row.get('rss_bytes')) is not int or row['rss_bytes']<0:return False
        sampled[key]=row['rss_bytes']
    for row in sample['departed']:
        key=identity(row)
        if key is None or key in departed or key in sampled or row.get('rss_bytes') is not None:return False
        replacement=row.get('replacement_create_time')
        if row.get('state')=='fresh_confirmed_absent':
            if replacement is not None:return False
        elif row.get('state')=='fresh_confirmed_reused':
            if type(replacement) not in (int,float) or not math.isfinite(replacement) or replacement<=0 or replacement==key[1]:return False
        else:return False
        departed[key]=row
    if root not in departed or root in sampled or own not in sampled:return False
    worker_rss=sum(value for key,value in sampled.items() if key!=own)
    return (type(terminal.get('sampled_known_worker_rss_bytes')) is int
        and terminal['sampled_known_worker_rss_bytes']==worker_rss
        and worker_rss<=1536*2**20 and worker_rss+sampled[own]<=2048*2**20)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','self-sha256','repair-context','repair-context-sha256','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();need(__debug__ and all(Path(v).is_absolute() for v in (a.manifest,a.repair_context,a.output)),'bounded_explicit_audit_manifest')
    need(digest(a.manifest)==a.manifest_sha256 and digest(__file__)==a.self_sha256
        and digest(a.repair_context)==a.repair_context_sha256,'audit_source_or_manifest_changed')
    cfg=load(a.manifest);campaign=load(OUT/'campaign.json');barrier_ref=campaign['pretruth_barrier']
    need(digest(barrier_ref['path'])==barrier_ref['sha256'],'pretruth_barrier_changed')
    barrier=load(barrier_ref['path']);clock=barrier['clock'];repair_context=load(a.repair_context)
    def check():
        need(time.monotonic()<clock['common_deadline_monotonic'] and time.time()<clock['absolute_deadline_unix'],
            'original_release_qualification_deadline')
        repair_deadlines(repair_context,time.time(),time.monotonic())
    need(barrier['manifest_sha256']==a.manifest_sha256 and len(barrier['tasks'])==2
        and [e['kind'] for e in barrier['tasks']]==['regression','classification'], 'both_sealed_tasks_before_truth')
    need(clock['absolute_deadline_unix']==clock['start_unix']+6000
        and clock['common_deadline_monotonic']==clock['start_monotonic']+6000,'same_assigned6000')
    check();repair=validate_repair_context(repair_context,a.manifest,a.manifest_sha256,cfg,campaign,clock,a.output,check)
    # ALL task cores and both saved terminal supervisors are rehashed before numerical/data imports.
    actual={str(Path(__file__).resolve()):a.self_sha256,str(Path(a.manifest).resolve()):a.manifest_sha256,
            barrier_ref['path']:barrier_ref['sha256'],str(Path(a.repair_context).resolve()):a.repair_context_sha256}
    actual.update({v['path']:v['sha256'] for v in repair_context.values() if type(v) is dict and set(v)=={'path','sha256'}})
    need(all((path not in actual or actual[path]==h) and (path not in cfg['immutable_files'] or cfg['immutable_files'][path]==h)
        for path,h in repair['caller_pins'].items()),'current_caller_original_pin_collision')
    actual.update(repair['caller_pins'])
    for path,h in cfg['immutable_files'].items():need(digest(path,check)==h,'immutable_before_truth_changed')
    sealed={}
    for entry in barrier['tasks']:
        ref=entry['supervisor'];need(digest(ref['path'],check)==ref['sha256'],'closed_supervisor_changed')
        supervisor=load(ref['path']);need(supervisor==ref['record'],'inline_saved_terminal_mismatch')
        parent,child={'regression':(900,870),'classification':(3600,3570)}[entry['kind']]
        need(supervisor.get('parent_cap_seconds')==parent and supervisor.get('child_cap_seconds')==child
            and supervisor.get('solver_budget_seconds') is None and supervisor.get('status')=='ok' and supervisor.get('exit_code')==0
            and supervisor.get('cleanup_confirmed') is True and not supervisor.get('error_history')
            and supervisor['end_unix']<clock['absolute_deadline_unix']
            and supervisor['seconds']<parent
            and supervisor['end_unix']<supervisor['start_unix']+parent
            and supervisor.get('maximum_observed_concurrent_worker_jobs',0)<=1
            and supervisor.get('peak_owned_tree_rss_mib',float('inf'))<=2048,
            'actual_terminal_caps_or_cleanup_failed')
        actual[ref['path']]=ref['sha256'];seal=entry['seal']
        need(digest(seal['path'],check)==seal['sha256'],'core_seal_changed');actual[seal['path']]=seal['sha256']
        rows=load(seal['path'])['files_sha256'];need(type(rows) is dict and 1<=len(rows)<=20000,'bounded_sealed_core')
        for path,h in rows.items():need(digest(path,check)==h,'sealed_core_changed')
        sealed[entry['kind']]=rows;actual.update(rows)
    for relative,h in (R4,LOSS):need(digest(WORK/relative,check)==h,'manual_verifier_changed')
    # The first pristine target read occurs only below this barrier.
    r4=imported('_br_fixed_manual_R4',WORK/R4[0]);r4.WORK=WORK
    loss=imported('_br_fixed_loss_receipts',WORK/LOSS[0]);pd=r4.pd;rows={}
    for task,entry in zip(cfg['tasks'],barrier['tasks']):
        kind=task['kind'];directory=Path(entry['directory']);report=load(entry['report']);spec=report['spec']
        kind=task['kind'];run=Path(entry['report']).parent
        need(spec['kind']==kind and spec['metric']==('rmse' if kind=='regression' else 'macro_f1'),'metric_kind_changed')
        if kind=='regression':
            need(report.get('schema')=='fixed-recipe-standard-release-v1'
                and report.get('status')=='completed_pending_independent_qualification'
                and report.get('recipe')==task['expected_recipe'] and report.get('source_unchanged') is True
                and report.get('cleanup_confirmed') is True and report.get('first_failure') is None
                and report.get('secondary_failures')==[] and report.get('search_or_optimization_performed') is False
                and report.get('API_calls')==report.get('Qwen_calls')==report.get('HPO_trials')==0,
                'unchanged_fixed_REG_procedure_required')
            need(report['metric'].get('status')=='resolved' and report['metric'].get('name')==spec['metric'],'REG_strict_metric_required')
            declared={**{'input:'+name:task['files'][filename] for name,filename in
                [('train','train.csv'),('test','test.csv'),('sample_submission','sample_submission.csv'),('data_dictionary','data_dictionary.csv')]},
                'task':task['files']['task.md'],**{'source:'+name:h for name,h in cfg['executor']['members_sha256'].items()}}
            need(report['source_and_input_sha256']==declared,'REG_source_and_input_map_changed')
            intrinsic=report['original_clock'];measurements=report['measurements'];recipe=task['expected_recipe']
            need(len(measurements)==2,'two_REG_cut_records_required')
            records=dict(zip(('primary','confirmation'),measurements));full=report['full_refit']
            full_partition_name='confirmation-split.npz'
            declared_median=report['actual_median_refit_iterations']
        else:
            need(report.get('version')=='v4-quality-research' and report.get('final_fit_status')=='ok'
                and report.get('integrity_ok') is True and report.get('selected_recipe') is not None
                and report.get('llm_calls')==[],'complete_offline_CLASS_report_required')
            # No HPO/four-stage/gateway predicate is borrowed from whole-agent R4.
            # Missing selected confirmation is a hard STOP, including successful refits.
            records=r4.selected_records(report);recipe=report['selected_recipe']
            need(set(records)=={'primary','confirmation'} and all(r.get('status')=='ok'
                and r.get('recipe')==recipe for r in records.values()),'selected_matching_CLASS_cuts_required')
            refs=entry['delegation'];supervision=load(refs['supervision.json']);authority=load(refs['authority.json'])
            observation=framed_observation(refs['observation.json'],check);diagnostic=load(refs['child-diagnostic.json']);hello=load(refs['hello.json'])
            need(all(p in sealed[kind] for p in refs.values()),'CLASS_delegation_must_be_sealed_before_truth')
            need(supervision.get('schema')=='owned-class-supervision-v1'
                and supervision.get('status')=='completed_pending_independent_qualification'
                and supervision.get('cleanup_confirmed') is True and supervision.get('first_failure') is None
                and supervision.get('secondary_failures')==[] and supervision.get('actual_child_exit_code')==0
                and supervision.get('API_calls')==0 and supervision.get('actual_successful_resource_samples',0)>0
                and supervision.get('maximum_observation_gap_seconds',float('inf'))<=10
                and supervision.get('worker_cap')==1536*2**20 and supervision.get('whole_cap')==2048*2**20
                and supervision.get('observed_worker_tree_peak_bytes',float('inf'))<=1536*2**20
                and supervision.get('observed_whole_peak_bytes',float('inf'))<=2048*2**20,'actual_CLASS_parent_caps_cleanup_failed')
            need(authority.get('schema')=='owned-class-parent-authority-v1'
                and authority.get('source_sha256')==cfg['executor']['members_sha256']
                and authority.get('worker_cap')==1536*2**20 and authority.get('whole_cap')==2048*2**20
                and authority.get('declared_seconds')==9900
                and authority['global_deadline_unix']==authority['start_unix']+9900
                and authority['global_deadline_monotonic']==authority['start_monotonic']+9900
                and authority['execution_deadline_unix']==authority['global_deadline_unix']-30
                and authority['execution_deadline_monotonic']==authority['global_deadline_monotonic']-30
                and authority['observation_path']==refs['observation.json'],'exact_CLASS_original_authority_required')
            need(diagnostic.get('schema')=='owned-class-child-diagnostic-v1' and diagnostic.get('status')=='completed'
                and diagnostic.get('first_failure') is None and diagnostic.get('secondary_failures')==[]
                and diagnostic.get('child_identity')==authority['child_identity']
                and hello.get('child_identity')==authority['child_identity']
                and diagnostic.get('session')==authority.get('session')==supervision.get('session')==observation.get('session')==hello.get('session')
                and supervision.get('child_failure')==diagnostic,'CLASS_actual_child_and_parent_receipts_mismatch')
            result=diagnostic['result'];intrinsic=result['original_clock']
            need(result.get('policy')=='V16_offline_portfolio_confirmation_blend'
                and result.get('final_fit_status')=='ok' and result.get('integrity_ok') is True
                and result.get('selected_recipe')==recipe and result.get('final_fit_iterations')==report['final_fit_iterations']
                and result.get('submission_sha256')==report['submission_sha256']
                and result.get('API_calls')==result.get('Qwen_calls')==0
                and all(intrinsic[k]==authority[v] for k,v in [('start_unix','start_unix'),('start_monotonic','start_monotonic'),
                    ('deadline_unix','execution_deadline_unix'),('deadline_monotonic','execution_deadline_monotonic')]),'CLASS_complete_refit_receipt_required')
            need(observation.get('schema')=='owned-class-parent-observation-v1'
                and all(observation.get(k)==authority[k] for k in ('parent_identity','child_identity','start_unix','start_monotonic',
                    'execution_deadline_unix','execution_deadline_monotonic'))
                and observation['observation'].get('failure') is None
                and observation['observation'].get('actual_successful_samples',0)>0
                and observation['observation'].get('whole_rss_bytes',float('inf'))<=2048*2**20
                and observation['observation'].get('worker_tree_rss_bytes',float('inf'))<=1536*2**20,
                'CLASS_final_fresh_parent_observation_required')
            outer=entry['supervisor']['record'];outer_ids={(x['pid'],x['create_time']) for x in outer['owned_process_identities']}
            if outer.get('owned_root'):outer_ids.add((outer['owned_root']['pid'],outer['owned_root']['create_time']))
            need(all(tuple(authority[k]) in outer_ids for k in ('parent_identity','child_identity','launch_identity')),
                'CLASS_delegated_processes_not_bound_to_outer_owned_tree')
            provenance=load(report['provenance_path'])['sha256']
            need(Path(report['provenance_path']).resolve().is_relative_to(run) and Path(report['journal_path']).resolve().is_relative_to(run)
                and provenance=={**{'input:'+name:task['files'][filename] for name,filename in
                [('train','train.csv'),('test','test.csv'),('sample_submission','sample_submission.csv'),('data_dictionary','data_dictionary.csv')]},
                'task':task['files']['task.md'],
                **{'source:'+str(directory/name):h for name,h in cfg['executor']['members_sha256'].items() if name.endswith('.py')}},
                'CLASS_protected_source_input_provenance_changed')
            # requirements.txt is not emitted by legacy source_files(); its
            # actual deployed bytes remain bound by the all-task sealed inventory.
            need(sealed[kind].get(str(directory/'requirements.txt'))==cfg['executor']['members_sha256']['requirements.txt'],
                'CLASS_requirements_actual_deployment_changed')
            full=dict(load(run/'final-fit/result.json'),output_dir=str(run/'final-fit'))
            full_partition_name='split.npz';declared_median=report['final_fit_iterations']
        identifier=spec.get('id');source=Path(task['source']);train_path=source/'train.csv'
        dictionary=lexical_witness(source/'data_dictionary.csv',['feature','role'])
        targets=[name for name,role in zip(dictionary['feature'],dictionary['role']) if role.strip().lower()=='target']
        identifiers=[name for name,role in zip(dictionary['feature'],dictionary['role']) if role.strip().lower()=='id']
        need(targets==[spec['target']] and len(identifiers)<=1 and len(set(targets+identifiers))==len(targets+identifiers)
            and identifier==(identifiers[0] if identifiers else None),'independent_explicit_dictionary_authority_mismatch')
        roles={}
        if kind=='classification':
            roles[str(train_path.resolve())]=[spec['target']]
            for path in sealed[kind]:
                path=Path(path)
                if path.name=='validation_predictions.csv':roles[str(path.resolve())]=['y_true','y_pred']
                elif path.name=='submission.csv':roles[str(path.resolve())]=[spec['output_columns'][0]]
        parser=DeclaredClassCSV(pd,roles);r4.pd=parser
        converters={identifier:str} if identifier is not None else {}
        train=parser.read_csv(train_path,converters=converters)
        test=parser.read_csv(source/'test.csv',converters=converters)
        sample=parser.read_csv(source/'sample_submission.csv',converters=converters)
        if identifier is not None:
            for frame,path in [(train,train_path),(test,source/'test.csv'),(sample,source/'sample_submission.csv')]:
                need(frame[identifier].tolist()==lexical_witness(path,[identifier])[identifier], 'independent_lexical_ID_drift')
        if kind=='classification':need(all(v!='' for v in train[spec['target']]),'empty_class_label_not_missing_NA')
        verifier=r4.TaskVerifier(directory,report,train,test,sample);sup=entry['supervisor']['record']
        intrinsic_seconds=9900 if kind=='regression' else 9870
        need(intrinsic.get('actual_failure_type') is None and intrinsic['actual_resource_samples']>0
            and (kind=='classification' or (intrinsic['deadline_unix']==intrinsic['start_unix']+intrinsic_seconds
                and intrinsic['deadline_monotonic']==intrinsic['start_monotonic']+intrinsic_seconds))
            and sup['start_monotonic']<=intrinsic['start_monotonic']<=sup['child_start_monotonic']+1
            and intrinsic['resource_limit_bytes']==2048*2**20
            and intrinsic['observed_parent_conservative_total_peak_bytes']<=2048*2**20
            and intrinsic['observation_gap_limit_seconds']==10 and intrinsic['resource_sample_cadence_seconds']==.25,
            'intrinsic_origin_mismatch_not_outer_entitlement')
        cuts={};parts={};strict_records=[]
        for phase in ('primary','confirmation'):
            name=phase+'-split.npz' if kind=='regression' else ('split.npz' if phase=='primary' else 'confirmation_split.npz')
            partition=run/name;parts[phase]=partition;record=records[phase]
            expected=r4.expected_partition(task,spec,train,phase,cfg['verification_plan']);observed=r4.split(partition,len(train))
            need(all(r4.np.array_equal(a,b) for a,b in zip(expected,observed)),'frozen_cut_rows_changed')
            verifier.verify(record,partition,phase,expected_recipe=recipe);cuts[phase]=r4.diagnostics(verifier,record,partition,phase)
        median=r4.median_iterations(records['primary']['fit_iterations'],records['confirmation']['fit_iterations'])
        need(declared_median==full['fit_iterations']==median,'fresh_actual_recursive_median_required')
        if kind=='regression':strict_records=list(records.values())+[full]
        else:
            # The existing CLASS report retains strict receipts for actual cut
            # workers, not cached blend pseudo-jobs. R4 resolves every cached child.
            by_path={str(Path(r['output_dir']).resolve()):r for field in ('experiments','confirmations')
                for r in report.get(field,[]) if r.get('status')=='ok' and r.get('output_dir')}
            for (folder,phase,is_full),verified in verifier.records.items():
                if (Path(folder)/'job.json').exists():
                    need(folder in by_path,'selected_actual_cut_worker_receipt_missing');strict_records.append(by_path[folder])
        saved_owned=identity_inventory(sup['owned_process_identities'])
        if sup.get('owned_root'):saved_owned.add(exact_identity(sup['owned_root']))
        for record in strict_records:
            job=load(Path(record['output_dir'])/'job.json')
            if not job.get('full_fit'):need('fit_iterations' not in job,'cut_iteration_override_forbidden')
            need(job['threads']==2,'actual_worker_threads_must_equal2')
            receipt=record.get('release_original_clock',{})
            need(record.get('cleanup_confirmed') is True and record.get('strict_runtime') is True
                and record.get('worker_memory_limit_bytes')==1536*2**20 and record.get('whole_memory_limit_bytes')==2048*2**20
                and record.get('observed_worker_tree_peak_bytes',float('inf'))<=1536*2**20
                and record.get('observed_combined_peak_bytes',float('inf'))<=2048*2**20 and verified_terminal(record,repair=repair if kind=='classification' else None,owned=saved_owned,intrinsic=intrinsic)
                and all(receipt.get(key)==intrinsic[key] for key in ('start_unix','start_monotonic','deadline_unix','deadline_monotonic'))
                and receipt.get('actual_failure_type') is None,'strict_worker_terminal_caps_cleanup_or_original_clock_failed')
        need(Path(full['output_dir']).resolve()==run/'final-fit','fresh_full_refit_directory')
        checked_full=verifier.verify(full,run/full_partition_name,'final',full=True,expected_recipe=recipe)
        need(digest(directory/'submission.csv')==report['submission_sha256'],'published_CSV_hash_changed')
        published=parser.read_csv(directory/'submission.csv',converters=converters)
        need(list(published)==list(sample) and len(published)==len(sample)
            and not published.isna().any().any(),'fullrefit_CSV_shape_or_missing')
        if identifier is not None:need(published[identifier].equals(sample[identifier]),'fullrefit_lexical_sample_order')
        column=spec['output_columns'][0]
        if kind=='classification':
            expected=r4.np.asarray(spec['classes'])[checked_full['test'].argmax(axis=1)][verifier.sample_positions]
            need(r4.np.array_equal(published[column].to_numpy(),expected),'published_class_values_not_actual_fullrefit')
        else:need(r4.np.allclose(published[column].to_numpy(dtype=float),checked_full['test'],atol=1e-12,rtol=1e-12),
            'published_numeric_values_not_actual_fullrefit')
        fitted=[];cached_parent_proofs=[]
        for (folder,phase,full_fit),verified in verifier.records.items():
            record=load(Path(folder)/'result.json');recipe=record['recipe']
            if record.get('components'):continue
            if record.get('training_reused') is True:
                children=verified_cached_mixture_parent(record,folder,phase,full_fit,verified,report,verifier.records)
                need(children is not None,'unsupported_or_unverified_cached_mixture_parent')
                cached_parent_proofs.append(dict(path=str(Path(folder).relative_to(directory)),phase=phase,
                    independently_R4_verified_children=[str(path.relative_to(directory)) for path in children],
                    actual_fitting_leaf=False,actual_new_model_fits=0))
                continue
            partition=parts['confirmation'] if phase=='confirmation' or full_fit else parts['primary']
            parent=r4.np.arange(len(train),dtype=r4.np.int64) if full_fit else r4.split(partition,len(train))[0]
            receipts=record.get('data_policy_runs');need(type(receipts) is list and receipts,'fitting_receipts_required')
            need(any(v.get('source_rows')==len(parent) and v.get('source_parent_sha256')==r4.canonical(parent.tolist())
                and v.get('synthetic_rows')==0 for v in receipts),'outer_or_full_fitting_lineage_changed')
            if not full_fit:
                need(record.get('early_stopping_source')=='inner_training_holdout'
                    and record.get('inner_split_error') is None,'fitting_only_nested_stopping_required')
            if recipe.get('params',{}).get('loss_profile_id'):
                loss.loss_telemetry(record,recipe,verifier,r4,partition)
            fitted.append(dict(path=str(Path(folder).relative_to(directory)),full_fit=full_fit,
                completed_policy_callbacks=len(receipts),actual_total_learner_fits=None))
        mean=sum(cuts[p]['value'] for p in ('primary','confirmation'))/2
        need(math.isfinite(mean),'nonfinite_metric')
        rows[kind]=dict(cuts=cuts,selected_cut_mean=mean,full_refit_iterations=median,
            full_CSV_sha256=report['submission_sha256'],fitting_receipts=fitted,cached_mixture_parent_proofs=cached_parent_proofs,
            historical_reference_mean=task.get('reference_mean'),historical_reference_is_qualification_gate=False,
            CLASS_final_worker_terminal_receipt_serialized=False if kind=='classification' else True,
            full_resource_authority='actual clean delegated parent subtree plus source-bound strict worker completion' if kind=='classification' else 'saved strict worker receipt',
            scope='New independently recomputed reused-public two-cut selected procedure; no hidden-test score')
        r4.pd=pd;check()
    for path,h in {**cfg['immutable_files'],**actual}.items():need(digest(path,check)==h,'posttruth_source_or_core_changed')
    result=dict(schema='postfailure-standard-artifact-audit-v1',artifact_procedure_passed=True,
        repair_context_sha256=a.repair_context_sha256,audit_within_repair_clock=True,
        original_RQ6_procedure_requalified=False,original_failure_preserved=True,
        saved_None_terminal_qualification='source_ordered_stable_sample_then_observed_exit_and_strict_cleanup',
        saved_None_terminal_timestamp=None,saved_terminal_records_mutated=False,
        quality_metric={k:r['selected_cut_mean'] for k,r in rows.items()},tasks=rows,
        original_common_seconds=6000,audit_within_original_common_clock=True,
        archive_sha256=cfg['executor']['archive']['sha256'],manifest_sha256=a.manifest_sha256,
        actual_artifact_sha256=actual,manual_R4_source_sha256=R4[1],loss_receipt_source_sha256=LOSS[1],
        audit_only_lexical_class_facade=True,manual_R4_source_bytes_unchanged=True,
        reported_API_calls=0,independent_external_API_measurement=None,new_model_fits=0,
        parent_actual_exit_and_root_closure_required=True,official_hidden_test_score=None,promotion=False,submit=False)
    output=Path(a.output);need(not output.exists(),'exclusive_audit_output');check()
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    check();return 0

if __name__=='__main__':raise SystemExit(main())
