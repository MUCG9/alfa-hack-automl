"""Prepared parent-origin contracts; synthetic callbacks only, author runs zero."""
from contextvars import ContextVar
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import research_loop as R
import task_entry as entry
import test_research_loop as old


def origin(killed=None,primary=None,prior='ok'):
    return dict(schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
        coordinator_killed=killed,primary_exception_type=primary,prior_result_status=prior)


class WorkerOriginContracts(unittest.TestCase):
    def test_resource_origin_survives_final_timeout_and_stops_before_later_gateway(self):
        for reason in ('memory_limit','worker_memory_limit','whole_memory_limit','disk_space_limit'):
            with self.subTest(reason=reason):
                harness=old.ThreeHourResearchContracts(methodName='runTest')
                clock,gateway,ordinary,calls,gcalls,saved=harness.harness()
                def worker(recipe,cut,timeout,phase,fit_iterations=None):
                    row=ordinary(recipe,cut,timeout,phase,fit_iterations)
                    if recipe['params']['v']==1:
                        row.update(status='timeout',metrics=None,
                            hpo_fair_reserve_provenance=origin(reason,prior=reason))
                    return row
                with self.assertRaises(R.ResearchStop):
                    R.run_task(old.task(),clock,gateway,worker,old.normalizer,old.signature,old.compiler,saved.append)
                self.assertEqual(len(gcalls),1)
                self.assertEqual(len(calls),5)  # Initial complete checkpoint precedes Qwen.
                self.assertEqual(saved[-1]['status'],'failed')
                self.assertEqual(saved[-1]['last_worker_final_status'],'timeout')
                self.assertEqual(saved[-1]['last_worker_parent_origin']['coordinator_killed'],reason)
                self.assertIsNotNone(saved[-1]['full_refit'])
                self.assertEqual(saved[-1]['selected_recipe']['params']['v'],0)
                self.assertFalse(saved[-1]['quality_qualified'])

    def test_missing_incomplete_or_parent_exception_provenance_never_becomes_trial_failure(self):
        good=dict(status='timeout',cleanup_confirmed=True,hpo_fair_reserve_provenance=origin('timeout',prior='timeout'))
        variants=[]
        missing=deepcopy(good);missing.pop('hpo_fair_reserve_provenance');variants.append(missing)
        incomplete=deepcopy(good);incomplete['hpo_fair_reserve_provenance'].pop('primary_exception_type');variants.append(incomplete)
        denied=deepcopy(good);denied['hpo_fair_reserve_provenance']['cleanup_confirmed']=False;variants.append(denied)
        typed=deepcopy(good);typed['hpo_fair_reserve_provenance']['coordinator_killed']=False;variants.append(typed)
        unknown=deepcopy(good);unknown['hpo_fair_reserve_provenance']['prior_result_status']='unverified';variants.append(unknown)
        for error in ('ProcessObservationError','ProcessCleanupError','RuntimeError','UnknownParentError'):
            row=deepcopy(good);row['hpo_fair_reserve_provenance']=origin(primary=error,prior='error');variants.append(row)
        for index,row in enumerate(variants):
            with self.subTest(index=index),self.assertRaises(R.ResearchStop):R.require_worker_origin(row)

    def test_confirmed_ordinary_timeout_is_NULL_and_later_real_hypotheses_continue(self):
        harness=old.ThreeHourResearchContracts(methodName='runTest')
        clock,gateway,ordinary,calls,gcalls,saved=harness.harness()
        def worker(recipe,cut,timeout,phase,fit_iterations=None):
            row=ordinary(recipe,cut,timeout,phase,fit_iterations)
            if recipe['params']['v']==1:
                row.update(status='timeout',metrics=None,
                    hpo_fair_reserve_provenance=origin('timeout',prior='timeout'))
            return row
        result=R.run_task(old.task(),clock,gateway,worker,old.normalizer,old.signature,old.compiler,saved.append)
        self.assertEqual(result['status'],'cores_ready_pending_all_task_seals_and_independent_audit')
        self.assertGreater(result['executed_Qwen_candidates'],1)
        failed=next(row for row in result['records'] if row['status']=='failed')
        self.assertIsNone(failed['scores'])
        self.assertEqual(result['full_refit']['status'],'ok')
        self.assertGreater(len(gcalls),64)
        self.assertEqual(result['stop_reason'],'original_task_time_admission_margin')

    def test_trusted_scope_enables_existing_capture_and_restores_exact_marker_after_failure(self):
        marker=ContextVar('synthetic_parent_origin',default=False)
        runtime=SimpleNamespace(_HPO_FAIR_RESERVE_PROVENANCE=marker)
        failure=ValueError('synthetic failure')
        with self.assertRaises(ValueError) as caught:
            with entry.worker_origin_scope(runtime):
                self.assertIs(marker.get(),True)
                raise failure
        self.assertIs(caught.exception,failure)
        self.assertIs(marker.get(),False)
        token=marker.set(True)
        try:
            with entry.worker_origin_scope(runtime):self.assertIs(marker.get(),True)
            self.assertIs(marker.get(),True)
        finally:marker.reset(token)
        self.assertIs(marker.get(),False)
        with self.assertRaises(RuntimeError):
            with entry.worker_origin_scope(SimpleNamespace(_HPO_FAIR_RESERVE_PROVENANCE=None)):pass


if __name__=='__main__':unittest.main()
