"""Prepared metadata/mock contracts; no models, provider or author execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import task_entry as entry
import research_loop as R
import test_research_loop as old


class ParentCallbackLedgerContracts(unittest.TestCase):
    def test_exact_parent_return_binds_actual_job_result_or_honest_missing_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            rawjob=folder/'job.json';rawjob.write_text('{"synthetic":true}',encoding='utf-8')
            rawresult=folder/'result.json';rawresult.write_text('{"status":"ok"}',encoding='utf-8')
            result=dict(status='ok',cleanup_confirmed=True,wall_seconds=1.5,
                observed_worker_tree_peak_bytes=123,release_worker_allocation_seconds=30,
                hpo_fair_reserve_provenance=dict(schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
                    coordinator_killed=None,primary_exception_type=None,prior_result_status='ok'))
            before=deepcopy(result);checkpoints=[]
            ref=entry.persist_parent_callback(result,folder,1,'control-0',dict(path='synthetic-cut',sha256='a'*64),
                task_manifest=dict(path='synthetic-task',sha256='b'*64),source_union={'source':'c'*64},
                spec={'kind':'regression'},recipe={'engine':'lightgbm'},check=lambda:checkpoints.append(True))
            saved=json.loads(Path(ref['path']).read_text('utf-8'))
            self.assertEqual(result,before)
            self.assertEqual(saved['result'],before)
            self.assertEqual(saved['raw_job']['sha256'],hashlib.sha256(rawjob.read_bytes()).hexdigest())
            self.assertEqual(saved['raw_result']['sha256'],hashlib.sha256(rawresult.read_bytes()).hexdigest())
            self.assertEqual(ref['sha256'],hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest())
            self.assertEqual(saved['callback_index'],1)
            self.assertGreater(len(checkpoints),2)
            missing=folder/'missing';missing.mkdir()
            ref2=entry.persist_parent_callback({'status':'error'},missing,2,'round-1-0',{},
                task_manifest={},source_union={},spec={},recipe={},check=lambda:None)
            failure=json.loads(Path(ref2['path']).read_text('utf-8'))
            self.assertIsNone(failure['raw_job']);self.assertIsNone(failure['raw_result'])

    def test_fresh_strong_control_pair_survives_later_winner_and_ledger_counts_callbacks_only(self):
        harness=old.ThreeHourResearchContracts(methodName='runTest')
        clock,gateway,worker,calls,gcalls,saved=harness.harness()
        result=R.run_task(old.task(),clock,gateway,worker,old.normalizer,old.signature,old.compiler,saved.append)
        self.assertEqual(len(result['strong_control_cuts']),2)
        self.assertTrue(all(row['recipe']['params']['v']==0 for row in result['strong_control_cuts']))
        self.assertGreater(result['selected_recipe']['params']['v'],0)
        self.assertEqual(len(result['callback_ledger_refs']),len(calls))
        self.assertEqual(result['worker_calls_attempted'],len(calls))
        self.assertEqual(len({r['path'] for r in result['callback_ledger_refs']}),len(calls))
        completed=result['checkpoints'][result['selected_checkpoint']-1]
        self.assertEqual(completed['status'],'completed')
        self.assertEqual(result['full_refit']['parent_callback_receipt'],completed['full_refit_ref'])
        self.assertIsNone(result['actual_learner_fit_calls'])
        self.assertFalse(result['quality_qualified'])


if __name__=='__main__':unittest.main()
