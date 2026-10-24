"""Synthetic saved-proof contracts; no processes, learners, input data or APIs."""
from pathlib import Path
from copy import deepcopy
import ast
import importlib.util
import unittest

PACKET=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_saved_terminal_audit',PACKET/'artifact_audit.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def identity(pid):return {'pid':pid,'create_time':1000.+pid}

def normal_case():
    own,root=identity(1),identity(2);clock={'start_unix':100.,'start_monotonic':200.,
        'deadline_unix':9970.,'deadline_monotonic':10070.,'actual_failure_type':None,
        'actual_resource_samples':4,'observation_gap_limit_seconds':10,
        'resource_sample_cadence_seconds':.25,'resource_limit_bytes':2048*2**20}
    record={'status':'ok','strict_runtime':True,'cleanup_confirmed':True,
        'terminal_resource_observation':None,'parent_observed_worker_exit_code':0,
        'worker_resource_root':root,'worker_resource_self':own,
        'worker_memory_limit_bytes':1536*2**20,'whole_memory_limit_bytes':2048*2**20,
        'observed_worker_tree_peak_bytes':400,'observed_combined_peak_bytes':600,
        'release_original_clock':clock,
        'verified_resource_sample':{'schema':'verified-known-resource-sample-v1',
            'sampled':[dict(own,rss_bytes=100),dict(root,rss_bytes=200)],'departed':[],
            'sampled_count':2,'required_count':1,'known_count':2,
            'scope':'sampled_stable_known_RSS_not_OS_lifetime_peak'}}
    owned={A.exact_identity(own),A.exact_identity(root)}
    proof={'producer_schema':'RQ6_CLASS_stable_sample_then_observed_exit_v1',
        'runtime_sha256':A.SAVED_RUNTIME_SHA256,'known':set(owned)}
    return record,proof,owned,deepcopy(clock)

def lineage_case():
    prior=[identity(n) for n in range(1,8011)]
    preparers=[identity(n) for n in range(8011,8014)]
    later=[identity(n) for n in range(8014,8017)]
    clock={'start_unix':10.,'start_monotonic':20.,'absolute_deadline_unix':6010.,'common_deadline_monotonic':6020.}
    root={'schema':'standard-repair-qualification-root-closure-v1','technical_procedure_passed':False,
        'actual_exec_session':49569,'actual_exec_exit_code_observed_by_root':1,'actual_tool_evidence':'dbc6a1',
        'manifest_sha256':'manifest','cleanup_confirmed':True,'source_unchanged':True,'temporary_cleanup_confirmed':True,
        'root_errors':[],'active_owned_processes':[],'uncertain_owned':[],
        'original_start_unix':10.,'original_deadline_unix':6010.,'original_start_monotonic':20.,'original_end_monotonic':6020.,
        'owned_identities':prior[:1],'closure_preparer_identities':prior[1:4]}
    negative={'schema':'rq6-separate-current-negative-closure-v1','technical_procedure_passed':False,
        'original_RQ6_FAIL_preserved':True,'root60_requalified':False,'old_clock_reset':False,'new_qualification':False,
        'current_source_unchanged':True,'current_cleanup_confirmed':True,'current_temporary_absent':True,
        'inside_original6000':True,'original_manifest_sha256':'manifest','original_campaign_sha256':'campaign',
        'original_negative_root_sha256':A.SAVED_REFS['original_root'][1],'known_count':8010,
        'known_identities':prior,'known_exact_live':[],'uncertain':[],'source_pins_checked':1017,'new_model_fits':0,'API_calls':0,
        'actual_failed_driver':{'session':49569,'exit_code':1,'tool':'dbc6a1'},
        'actual_failed_frozen_closer':{'exit_code':1,'tool':'fb3841'},'observer_preparer_identities':preparers}
    post=deepcopy(negative);post.update(schema='rq6-current-negative-post-tool-confirmation-v1',known_count=8013,
        known_identities=prior+preparers,observer_preparer_identities=later,
        negative_closure_sha256=A.SAVED_REFS['current_negative'][1],
        actual_negative_observer={'exit_code':0,'tool':'b449e3'},post_tool_current_confirmation=True)
    context={'actual_current_negative_observer':{'exit_code':0,'tool':'b449e3'},
        'actual_post_tool_observer':{'exit_code':0,'tool':'317ee6'}}
    return context,root,negative,post,clock,'manifest','campaign'

class SavedTerminalTests(unittest.TestCase):
    def test_stable_sample_then_exit_preserves_original_None_and_unknown_timestamp(self):
        record,proof,owned,clock=normal_case();before=deepcopy(record)
        self.assertTrue(A.verified_terminal(record,repair=proof,owned=owned,intrinsic=clock))
        self.assertEqual(record,before);self.assertIsNone(record['terminal_resource_observation'])
        self.assertNotIn('sampled_unix',record['verified_resource_sample'])

    def test_None_without_qualified_source_or_exact_proof_stops(self):
        record,proof,owned,clock=normal_case()
        self.assertFalse(A.verified_terminal(record))
        for name,value in [('runtime_sha256','unqualified'),('producer_schema','guessed'),('known',set())]:
            changed=deepcopy(proof);changed[name]=value
            self.assertFalse(A.verified_terminal(record,repair=changed,owned=owned,intrinsic=clock))
        self.assertFalse(A.verified_terminal(record,repair=proof,owned=set(),intrinsic=clock))

    def test_missing_denied_or_unconfirmed_strict_receipts_stop(self):
        record,proof,owned,clock=normal_case()
        for name,value in [('status','error'),('cleanup_confirmed',False),('strict_runtime',False),
                ('parent_observed_worker_exit_code',None),('parent_observed_worker_exit_code',True),
                ('verified_resource_sample',None)]:
            bad=deepcopy(record);bad[name]=value
            self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))
        bad=deepcopy(record);bad['release_original_clock']['actual_failure_type']='ProcessObservationError'
        self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))
        bad=deepcopy(record);del bad['release_original_clock']['actual_failure_type']
        self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))

    def test_wrong_birth_or_missing_self_root_is_not_zero_RSS(self):
        record,proof,owned,clock=normal_case()
        for mutate in ('birth','root','self','zero'):
            bad=deepcopy(record)
            if mutate=='birth':bad['worker_resource_root']['create_time']+=1
            elif mutate=='root':bad['verified_resource_sample']['sampled'].pop()
            elif mutate=='self':bad['verified_resource_sample']['sampled'].pop(0)
            else:bad['verified_resource_sample']['sampled'][1]['rss_bytes']=0
            bad['verified_resource_sample']['sampled_count']=len(bad['verified_resource_sample']['sampled'])
            self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))

    def test_duplicate_departed_and_invalid_RSS_samples_stop(self):
        record,proof,owned,clock=normal_case()
        for mode in ('duplicate','departed','negative','boolean','nan'):
            bad=deepcopy(record);sample=bad['verified_resource_sample']
            if mode=='duplicate':sample['sampled'].append(deepcopy(sample['sampled'][0]))
            elif mode=='departed':sample['departed']=[dict(identity(2),rss_bytes=None,state='fresh_confirmed_absent',replacement_create_time=None)]
            else:sample['sampled'][0]['rss_bytes']={'negative':-1,'boolean':True,'nan':float('nan')}[mode]
            sample['sampled_count']=len(sample['sampled']);sample['known_count']=len(sample['sampled'])+len(sample['departed'])
            self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))

    def test_worker_whole_caps_and_underreported_peaks_stop(self):
        record,proof,owned,clock=normal_case()
        for mode in ('worker','whole','peak','cap'):
            bad=deepcopy(record)
            if mode=='worker':bad['verified_resource_sample']['sampled'][1]['rss_bytes']=1536*2**20+1
            elif mode=='whole':bad['verified_resource_sample']['sampled'][0]['rss_bytes']=2048*2**20
            elif mode=='peak':bad['observed_worker_tree_peak_bytes']=199
            else:bad['whole_memory_limit_bytes']+=1
            self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))

    def test_original_clock_or_actual_sample_receipt_mismatch_stops(self):
        record,proof,owned,clock=normal_case()
        for key,value in [('start_unix',101.),('actual_resource_samples',0),('observation_gap_limit_seconds',11),
                ('resource_sample_cadence_seconds',1.),('resource_limit_bytes',1)]:
            bad=deepcopy(record);bad['release_original_clock'][key]=value
            self.assertFalse(A.verified_terminal(bad,repair=proof,owned=owned,intrinsic=clock))

    def test_original_two_terminal_branches_remain_separate_and_malformed_stops(self):
        for status in ('sampled_before_terminal_acceptance','root_absent_after_observed_exit'):
            self.assertTrue(A.verified_terminal({'terminal_resource_observation':{'status':status}}))
        for terminal in ([],1,'unknown',{}, {'status':'unknown'}):
            self.assertFalse(A.verified_terminal({'terminal_resource_observation':terminal}))

    def test_current_negative_exact_union_never_changes_old_FAIL(self):
        args=lineage_case();before=deepcopy(args)
        known=A.repair_lineage(*args)
        self.assertEqual(len(known),8013);self.assertEqual(args,before)
        self.assertIs(args[1]['technical_procedure_passed'],False)
        self.assertIs(args[2]['root60_requalified'],False)

    def test_negative_post_actual_exit_and_current_identity_gaps_stop(self):
        for mode in ('tool','missing','duplicate','live','old_PASS','reset'):
            args=list(lineage_case())
            if mode=='tool':args[0]['actual_post_tool_observer']['exit_code']=1
            elif mode=='missing':args[3]['known_identities'][-1]=identity(99999)
            elif mode=='duplicate':args[3]['known_identities'][-1]=args[3]['known_identities'][0]
            elif mode=='live':args[3]['known_exact_live']=[identity(1)]
            elif mode=='old_PASS':args[1]['technical_procedure_passed']=True
            else:args[2]['old_clock_reset']=True
            with self.assertRaises(RuntimeError):A.repair_lineage(*args)

    def test_new_phase_and_common_clocks_are_both_original_and_finite(self):
        context={'clock':{'start_unix':100.,'start_monotonic':200.,'absolute_deadline_unix':700.,
            'common_deadline_monotonic':800.,'audit_start_unix':280.,'audit_start_monotonic':380.,
            'audit_deadline_unix':400.,'audit_deadline_monotonic':500.}}
        A.repair_deadlines(context,399.,499.)
        for unix,mono in [(400.,499.),(399.,500.),(279.,499.),(399.,379.),(float('nan'),499.)]:
            with self.assertRaises(RuntimeError):A.repair_deadlines(context,unix,mono)
        bad=deepcopy(context);bad['clock']['absolute_deadline_unix']+=600
        with self.assertRaises(RuntimeError):A.repair_deadlines(bad,399.,499.)

    def test_all_cores_and_repair_proofs_precede_first_manual_verifier_import(self):
        tree=ast.parse((PACKET/'artifact_audit.py').read_text('utf-8'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        first_import=min(n.lineno for n in calls if n.func.id=='imported')
        self.assertLess(next(n.lineno for n in calls if n.func.id=='validate_repair_context'),first_import)
        marker=next(n for n in ast.walk(main) if isinstance(n,ast.Constant) and n.value=='sealed_core_changed')
        self.assertLess(marker.lineno,first_import)
        original=ast.parse((PACKET/'source-evidence/original-artifact_audit.py').read_text('utf-8'))
        for name in ('framed_observation','lexical_witness'):
            left=next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name==name)
            right=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(left,include_attributes=False),ast.dump(right,include_attributes=False))

class CachedMixtureContracts(unittest.TestCase):
    def cache(self,root,phase='primary'):
        parent=root/'cached';parent.mkdir();children=[root/'leaf-a',root/'leaf-b']
        for p in children:p.mkdir()
        recipes=[{'engine':'synthetic-a','params':{}},{'engine':'synthetic-b','params':{}}]
        recipe={'engine':'ensemble','components':recipes,'weights':[.75,.25]}
        record={'status':'ok','recipe':recipe,'full_fit':False,'training_reused':True}
        verified={'folder':parent,'recipe':recipe,'mixture_children':2}
        graph={(str(parent),phase,False):verified}
        graph.update({(str(p),phase,False):{'folder':p,'recipe':r,'mixture_children':0} for p,r in zip(children,recipes)})
        field='experiments' if phase=='primary' else 'confirmations'
        report={field:[dict(status='ok',recipe=r,output_dir=str(p)) for p,r in zip(children,recipes)]}
        return record,parent,phase,False,verified,report,graph

    def test_cached_mixture_requires_same_R4_parent_and_all_children_without_faking_leaf_receipts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            args=self.cache(Path(tmp).resolve());before=deepcopy(args[0])
            children=A.verified_cached_mixture_parent(*args)
            self.assertEqual(len(children),2);self.assertEqual(args[0],before)
            self.assertNotIn('data_policy_runs',args[0]);self.assertNotIn('components',args[0])
            for path in children:self.assertIn((str(path),'primary',False),args[-1])
            self.assertIsNone(A.verified_cached_mixture_parent(*[dict(args[0],training_reused=False),*args[1:]]))
            # A real leaf with no receipt cannot enter this cache-only bridge.
            self.assertIsNone(A.verified_cached_mixture_parent(*[dict(args[0],recipe={'engine':'synthetic-a'}),*args[1:]]))
            source=(PACKET/'artifact_audit.py').read_text('utf-8')
            self.assertIn("receipts=record.get('data_policy_runs');need(type(receipts) is list and receipts,'fitting_receipts_required')",source)
            self.assertIn("v.get('source_parent_sha256')==r4.canonical(parent.tolist())",source)

    def test_unverified_missing_duplicate_wrong_cut_full_or_job_cached_parent_stops(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            args=self.cache(Path(tmp).resolve())
            for mode in ('missing','duplicate','phase','full','parent','weight'):
                value=list(deepcopy(args))
                if mode=='missing':del value[-1][(str(value[1].parent/'leaf-a'),'primary',False)]
                elif mode=='duplicate':value[-2]['experiments'].append(deepcopy(value[-2]['experiments'][0]))
                elif mode=='phase':value[2]='confirmation'
                elif mode=='full':value[3]=True
                elif mode=='parent':value[4]=dict(value[4])
                else:value[0]['recipe']['weights']=[float('nan'),.25]
                with self.subTest(mode=mode):self.assertIsNone(A.verified_cached_mixture_parent(*value))
            (args[1]/'job.json').write_text('{}',encoding='utf-8')
            self.assertIsNone(A.verified_cached_mixture_parent(*args))

    def test_hash_bound_current_caller_requires_exact_failed_RA1_and_current_full_union(self):
        import tempfile,hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'caller.json';path.write_text('{}',encoding='utf-8')
            current={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            fixed={'manifest':(A.WORK/'private/ra1-manifest.ready-r2.json','84b93538b73d73e2636b0730ad4cd105b2901633990e4654ccf9463e724d63f3'),
                'campaign':(A.WORK/'ra1/campaign.json','20fb2e4f4251218e62f1e91126ce581dc2c4cfc6a692d004d4b1b6aad7585536'),
                'root':(A.WORK/'ra1/terminal-root-closure.json','94132c7d68a49e7e85ee795f648db724891b8ea6ba7f670dacb151ac63afc6ca'),
                'negative':(A.WORK/'ra1/current-negative-closure.json','a'*64),
                'post':(A.WORK/'ra1/current-negative-post-tool-confirmation.json','b'*64)}
            prior={k:dict(path=str(p),sha256=h) for k,(p,h) in fixed.items()}
            prior.update(driver_actual=dict(session=25644,exit_code=1,tool='19905f'),closer_actual=dict(exit_code=1,tool='8efa0b'),
                negative_actual=dict(exit_code=0,tool='negative-actual'),post_actual=dict(exit_code=0,tool='post-actual'))
            rows=lambda a,b:[identity(i) for i in range(a,b)]
            negative=dict(schema='ra1-separate-current-negative-closure-v1',technical_procedure_passed=False,
                original_RA1_FAIL_preserved=True,original_RQ6_FAIL_preserved=True,root60_requalified=False,source_pins_checked=1560,
                current_source_unchanged=True,current_cleanup_confirmed=True,current_temporary_absent=True,
                original_manifest_sha256=prior['manifest']['sha256'],original_campaign_sha256=prior['campaign']['sha256'],
                original_negative_root_sha256=prior['root']['sha256'],actual_failed_driver=prior['driver_actual'],
                actual_failed_frozen_closer=prior['closer_actual'],known_exact_live=[],uncertain=[],known_count=8039,
                known_identities=rows(1,8040),observer_preparer_identities=rows(8040,8043))
            post=deepcopy(negative);post.update(schema='ra1-current-negative-post-tool-confirmation-v1',known_count=8042,
                known_identities=rows(1,8043),observer_preparer_identities=rows(8043,8046),post_tool_current_confirmation=True,
                negative_closure_sha256=prior['negative']['sha256'],actual_negative_observer=prior['negative_actual'])
            root=dict(schema='postfailure-standard-artifact-qualification-root-v1',technical_procedure_passed=False,
                actual_exec_session=25644,actual_exec_exit_code_observed_by_root=1,actual_tool_evidence='19905f',
                manifest_sha256=prior['manifest']['sha256'],cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True,
                independent_audit=None,quality_metric=None,owned_identities=rows(1,2),closure_preparer_identities=rows(2,5))
            docs={prior[k]['path']:v for k,v in [('manifest',{}),('campaign',dict(status='failed',artifact_procedure_passed=False,independent_audit=None)),
                ('root',root),('negative',negative),('post',post)]}
            source=str(Path(A.__file__).resolve());hashes={ref['path']:ref['sha256'] for ref in prior.values() if 'path' in ref}
            hashes[source]='c'*64
            caller=dict(schema='postfailure-standard-artifact-qualification-private-v1',readiness='READY_REVIEWED_FROZEN',missing_bindings=[],
                output=str(A.WORK/'ra2'),immutable_files=hashes,common_seconds=600,caps=dict(setup=180,audit=[120,90],final=240,root=60),
                auditor=dict(path=source,sha256=hashes[source]),ra1_previous=prior)
            docs[current['path']]=caller;observed={**hashes,current['path']:current['sha256']}
            def checked(changed):
                with patch.object(A,'digest',side_effect=lambda p,*args:observed[str(p)]),patch.object(A,'load',side_effect=lambda p:changed[str(p)]):
                    return A.current_caller_proof({'current_caller_manifest':current},lambda:None)
            self.assertEqual(len(checked(docs)['known']),8042)
            for name,key,bad in [('root','technical_procedure_passed',True),('post','known_count',8041),('negative','current_cleanup_confirmed',False)]:
                changed=deepcopy(docs);changed[prior[name]['path']][key]=bad
                with self.subTest(key=key),self.assertRaises(RuntimeError):checked(changed)
            changed=deepcopy(docs);changed[current['path']]['output']=str(A.WORK/'ra1')
            with self.assertRaises(RuntimeError):checked(changed)
            with self.assertRaises(RuntimeError):A.current_caller_proof({},lambda:None)


if __name__=='__main__':unittest.main()
