"""One shared840s technical child: source, build, exact23, explicit mapped tests."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, subprocess, sys, time, zipfile
sys.dont_write_bytecode=True

def need(value,code):
    if not value:raise RuntimeError(code)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('private-manifest','private-manifest-sha256','deadline-monotonic','deadline-unix','temporary-root'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--mapped',action='store_true');p.add_argument('--one-mapped')
    a=p.parse_args();end=float(a.deadline_monotonic);unix=float(a.deadline_unix)
    need(__debug__ and math.isfinite(end) and math.isfinite(unix),'finite_original_child_clocks_required')
    need(Path(a.private_manifest).is_absolute(),'absolute_forwarded_manifest_required')
    def clock():
        need(time.monotonic()<end and time.time()<unix,'original_child840_allocation_exhausted')
        need(abs((end-time.monotonic())-(unix-time.time()))<=5,'clock_disagreement')
    clock();need(sha(a.private_manifest)==a.private_manifest_sha256,'private_manifest_changed')
    cfg=json.loads(Path(a.private_manifest).read_text('utf-8'));out=Path(cfg['output']);root=Path(cfg['canonical_root'])
    need(cfg['schema']=='uar-full-private-manifest-v1' and cfg['readiness']=='READY_FROZEN_SOURCE_REVIEWED',
         'private_manifest_NOT_READY')
    temporary_root=Path(a.temporary_root)
    need(temporary_root.is_absolute() and temporary_root.resolve()==temporary_root
         and temporary_root.parent.resolve()==(Path(cfg['work_root'])/'t').resolve()
         and not temporary_root.is_symlink() and temporary_root.is_dir(),
         'exclusive_shallow_temporary_root_required')
    ownership=json.loads((out/'temporary-root.json').read_text('utf-8'))
    need(ownership.get('run_id')=='UAR06' and ownership.get('root')==str(temporary_root)
         and ownership.get('scope')=='exclusive_shallow_leaf_environment','temporary_root_receipt_changed')
    for key in ('TMP','TEMP','TMPDIR'):os.environ[key]=str(temporary_root)
    os.environ['MPLCONFIGDIR']=str(temporary_root/'m')
    need(sha(__file__)==cfg['files_sha256'][str(Path(__file__).resolve())],'entry_source_changed')
    helper=Path(__file__).with_name('contracts.py')
    need(sha(helper)==cfg['files_sha256'][str(helper.resolve())],'artifact_contract_source_changed')
    contract=imported('_uar04_contracts',helper)
    if a.one_mapped:
        # This is a fixed reviewed TestSuite, not a manifest-supplied command or arbitrary method lookup.
        suites=[s for s in cfg['mapped_suites'] if s['id']==a.one_mapped]
        need(len(suites)==1,'unknown_fixed_mapped_suite');suite=suites[0]
        path=out/'unpacked/tests'/(suite['id']+'.py');expected,proof=contract.adapted_test(cfg,suite)
        need(path.read_bytes()==expected,'mapped_test_source_changed');clock()
        sys.path.insert(0,str(out/'unpacked'))
        import unittest
        module=imported('_uar04_mapped_'+suite['id'],path);tests=unittest.TestSuite()
        for name in suite['selected_methods']:
            cls,method=name.split('.')
            value=getattr(module,cls);need(issubclass(value,unittest.TestCase),'typed_TestCase_required')
            tests.addTest(value(method))
        clock();result=unittest.TextTestRunner(verbosity=2).run(tests);clock()
        return 0 if result.wasSuccessful() and result.testsRun==suite['expected_tests'] and not result.skipped else 1
    for name,expected in [('owner','8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'),
                          ('processes','fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d')]:
        ref=cfg['helpers'][name];need(ref['sha256']==expected and sha(ref['path'])==expected,'proven_guard_source_changed')
    owner=imported('_uar04_leaf_owner',cfg['helpers']['owner']['path'])
    proc=imported('_uar04_leaf_process',cfg['helpers']['processes']['path'])
    import psutil
    rows=[];first=None
    base=[cfg['python'],'-B','-X','utf8']
    original_args=['--private-manifest',a.private_manifest,'--private-manifest-sha256',a.private_manifest_sha256,
                   '--deadline-monotonic',str(end),'--deadline-unix',str(unix),
                   '--temporary-root',str(temporary_root)]
    def save(path,value):
        clock()
        with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
        clock()
    def leaf(identifier,command,cwd):
        row=dict(id=identifier,status='starting',temporary_root=str(temporary_root));rows.append(row);child=tree=None
        observer=owner.StrictOwnedObserver();verified=False
        with (out/(identifier+'.log')).open('x',encoding='utf-8') as log:
            try:
                clock();child=subprocess.Popen(command,cwd=cwd,env=os.environ.copy(),stdin=subprocess.DEVNULL,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                obj=psutil.Process(child.pid);identity=(obj.pid,obj.create_time())
                row['owned_root']=dict(pid=identity[0],create_time=identity[1]);observer.remember([identity])
                tree=proc.ProcessTree(child);observer.remember(tree.members);verified=identity in tree.members
                need(verified,'initial_leaf_identity_unknown')
                while True:
                    clock();live=observer.observe();tree.members.update(live);need(not observer.denials,'leaf_observation_denied')
                    rss=0
                    for identity,obj in live.items():
                        try:need(obj.create_time()==identity[1],'leaf_identity_changed');rss+=obj.memory_info().rss
                        except psutil.NoSuchProcess:pass
                    need(rss<=1536*2**20,'leaf_subtree_memory_limit')
                    row['peak_tree_rss_mib']=max(row.get('peak_tree_rss_mib',0.),rss/2**20)
                    clock() # Check the inherited bound BEFORE accepting a terminal poll.
                    if child.poll() is not None:row['exit_code']=child.returncode;break
                    time.sleep(.05)
            finally:row.update(owner.cleanup_owned(child,tree,observer,verified,proc.ProcessTree))
        clock();need(row['cleanup_confirmed'] is True,'leaf_cleanup_unconfirmed')
        row['status']='passed' if row.get('exit_code')==0 else 'failed'
        need(row['exit_code']==0,'mandatory_technical_leaf_failed');return row
    try:
        if a.mapped:
            # Only the already sealed archive and adapted tests; no modular source sidecars.
            built=contract.archive(cfg,out,clock);target=out/'unpacked';need(not target.exists(),'exclusive_unpacked_directory')
            target.mkdir();(target/'tests').mkdir()
            with zipfile.ZipFile(out/'candidate.zip') as stream:
                for name in cfg['flat_inventory']:clock();(target/name).write_bytes(stream.read(name))
            for suite in cfg['mapped_suites']:
                clock();data,proof=contract.adapted_test(cfg,suite)
                (target/'tests'/(suite['id']+'.py')).write_bytes(data)
                row=leaf(suite['id'],base+[str(Path(__file__).resolve())]+original_args+
                    ['--one-mapped',suite['id']],target)
                text=(out/(suite['id']+'.log')).read_text('utf-8',errors='replace')
                row.update(proof);row['passed']=contract.counts(text,suite['expected_tests'])
                need(row['passed'],'mapped_explicit_count_or_skip_failed')
        else:
            leaf('source',base+[str(root/'tools/run_checks.py'),'--output',str(out/'source')],root)
            leaf('build',base+[str(root/'tools/build_submission.py'),'--output',str(out/'candidate.zip')],root)
            leaf('exact',base+[str(root/'tools/verify_release.py'),'--archive',str(out/'candidate.zip'),
                '--output',str(out/'exact.json'),'--timeout',str(min(300,max(.001,end-time.monotonic()))),
                '--memory-gb','1.2'],root)
            leaf('mapped',base+[str(Path(__file__).resolve())]+original_args+['--mapped'],out)
    except BaseException as exc:
        first=dict(type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else 'technical_leaf_operation_failed',
                   errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
    passed=first is None
    result=dict(schema='uar-full-technical-results-v1',status='passed' if passed else 'failed',leaves=rows,
        first_failure=first,temporary_root=str(temporary_root),fixture_learner_fits=None,external_API_calls=None,quality_metric=None,
        scope='technical fixtures; no public model experiment or release qualification')
    if a.mapped:result['archive_sha256']=sha(out/'candidate.zip')
    save(out/('mapped-results.json' if a.mapped else 'technical-results.json'),result)
    print(json.dumps(dict(status=result['status'],leaves=len(rows)),allow_nan=False));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
