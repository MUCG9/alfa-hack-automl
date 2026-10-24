"""Prepared synthetic/mock contracts only; author execution is zero."""
import ast
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))

from automl.contracts.metrics import MetricSpec, UnresolvedMetricError
from automl.search import fit_context_gateway as G
from automl.search import runner as R


class Frame:
    def __len__(self): return 6
    def __getitem__(self, key): raise AssertionError('Consumer may not read a scalar or ID')


class Guard:
    def __init__(self): self.calls = 0; self.failure = None
    def __call__(self, **kwargs):
        self.calls += 1
        if self.failure is not None: raise self.failure


class FalseOriginalBudget:
    started=1.
    deadline=99.
    def __bool__(self): return False
    def clock(self): return 2.


class Budget:
    def __init__(self, original, checkpoint, *, io_bytes_already_charged):
        if not original or not checkpoint: raise ValueError('original budget required')
        self.original, self.checkpoint = original, checkpoint
        self.started, self.deadline = original.started, original.deadline
        self.io_bytes = io_bytes_already_charged
    def check(self): self.checkpoint()
    def charge_io(self, count): self.check(); self.io_bytes += count


def packet_proof(packet):
    raw = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return dict(status='fitting_context_prepared', packet_UTF8_bytes=len(raw.encode()),
                packet_sha256=hashlib.sha256(raw.encode()).hexdigest())


def preflight(prompt, packet, *, receipt, bounds, budget):
    budget.check()
    proof = packet_proof(packet)
    if proof != receipt: raise ValueError('builder_packet_receipt_mismatch')
    if proof['packet_UTF8_bytes'] > 8192: raise ValueError('packet_overflow')
    context = {'fitting_context': deepcopy(packet)}
    raw = json.dumps([{'role':'system','content':prompt},
        {'role':'user','content':json.dumps(context,ensure_ascii=False,default=str)}], ensure_ascii=False)
    return context, dict(messages_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                        messages_UTF8_bytes=len(raw.encode()))


def positions(rows, size, budget, code):
    budget.check()
    if (type(rows) not in (list,tuple) or not 1 <= len(rows) < size
            or any(type(x) is not int or not 0 <= x < size for x in rows)
            or len(set(rows)) != len(rows)):
        raise ValueError(code)
    return set(rows), hashlib.sha256(b''.join(struct.pack('<q',x) for x in rows)).hexdigest()


class InitialFittingConsumerContracts(unittest.TestCase):
    def arguments(self, directory):
        original = SimpleNamespace(started=1., deadline=99., clock=lambda: 2.)
        guard = Guard()
        metric = MetricSpec('rmse','minimize','value','resolved','explicit synthetic declaration')
        spec = dict(kind='regression', metric='rmse', target='response', id='identifier',
            features=['renamed_feature'], n_train=6,
            strict_task_contract=dict(full_input_provenance_verified=True,metric_spec=metric.to_dict()))
        frame, declared = Frame(), SimpleNamespace(receipt={'synthetic':True})
        fingerprints = {'task':'a'*64,'input:train':'b'*64,'input:test':'c'*64,
                        'input:sample_submission':'d'*64}
        paths = {k:Path(directory)/(str(i)+'.txt') for i,k in enumerate(fingerprints)}
        authority = G.InitialFittingAuthority(frame,spec,declared,metric,original,guard,fingerprints,paths)
        split = Path(directory)/'split.bin'; split.write_bytes(b'ordered synthetic split authority')
        packet = {'schema':'fitting-context-v1','data':{'target':{'mean':4.}},'advice':{}}
        def prepare(**kw):
            self.assertIs(kw['witness'].producer_frame,frame)
            self.assertIs(kw['witness'].producer_spec,kw['spec'])
            self.assertIs(kw['witness'].producer_budget,original)
            self.assertIs(kw['witness'].producer_checkpoint,guard)
            self.assertEqual(kw['fitting_positions'],[4,0,2])
            self.assertEqual(kw['validation_positions'],[1,3])
            context, proof = preflight(kw['system_prompt'],packet,receipt=packet_proof(packet),
                                       bounds=None,budget=kw['budget'])
            return context, dict(builder=packet_proof(packet),gateway_preflight=proof,
                upstream_native_parser_IO_bytes=None,total_parent_IO_qualified=False)
        deps = SimpleNamespace(CallerBudget=Budget,RoleAuthority=lambda **kw:SimpleNamespace(**kw),
            SplitInputAuthority=lambda **kw:SimpleNamespace(**kw),TrustedFrameWitness=lambda **kw:SimpleNamespace(**kw),
            roles_sha=lambda role:G.canonical(vars(role)),positions=positions,prepare=Mock(side_effect=prepare),
            preflight=preflight,bounds=object(),current_budget=lambda:original,MAX_ROWS=200000)
        return dict(authority=authority,spec=dict(spec,validation_strategy='auto',time_column=None),frame=frame,
            fitting_positions=[4,0,2],validation_positions=[1,3],split_path=split,
            fingerprints=dict(fingerprints),system_prompt='SAME SYSTEM + STAGED',_dependencies=deps)

    def test_optin_requires_both_strict_modes_and_four_stage(self):
        R._fitting_context_initial_options(SimpleNamespace(fitting_context_initial=False))
        for missing in ('strict_runtime','strict_task_contract','four_stage'):
            args=dict(fitting_context_initial=True,strict_runtime=True,strict_task_contract=True,four_stage=True)
            args[missing]=False
            with self.subTest(missing=missing),self.assertRaises(ValueError):
                R._fitting_context_initial_options(SimpleNamespace(**args))
        R._fitting_context_initial_options(SimpleNamespace(fitting_context_initial=True,
            strict_runtime=True,strict_task_contract=True,four_stage=True))

    def test_direct_solver_without_live_authority_stops_before_discovery(self):
        args=SimpleNamespace(fitting_context_initial=True,strict_runtime=True,strict_task_contract=True,four_stage=True)
        with patch.object(R,'discover',side_effect=AssertionError('No guessed authority')) as discover:
            with self.assertRaisesRegex(ValueError,'live strict CLI'): R.solve_single(args)
        discover.assert_not_called()

    def test_scoped_producer_authority_reset_is_in_finally(self):
        tree=ast.parse(inspect.getsource(R._strict_task_flow))
        resets=[n for n in ast.walk(tree) if isinstance(n,ast.Try) and any(
            isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='reset'
            and isinstance(c.func.value,ast.Name) and c.func.value.id=='_FITTING_INITIAL_AUTHORITY'
            for final in n.finalbody for c in ast.walk(final))]
        self.assertEqual(len(resets),1)
        self.assertTrue(any(isinstance(n,ast.Return) for n in ast.walk(resets[0])))
        self.assertIsNone(R._FITTING_INITIAL_AUTHORITY.get())

    def test_frame_and_original_budget_identity_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory)
            for change in ('frame','budget'):
                b=dict(a)
                if change=='frame': b['frame']=Frame()
                else: b['_dependencies']=SimpleNamespace(**vars(a['_dependencies']))
                if change=='budget': b['_dependencies'].current_budget=lambda:object()
                with self.subTest(change=change),self.assertRaisesRegex(G.InitialFittingContextRejected,'same_strict'):
                    G.prepare_initial_fitting_context(**b)
            a['_dependencies'].prepare.assert_not_called()

    def test_derived_validation_copy_allows_only_existing_four_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory)
            a['spec'].update(group_column=None,validation_warning='synthetic supported warning')
            result=G.prepare_initial_fitting_context(**a)
            self.assertEqual(set(result.receipt['derived_validation_spec_fields']),G.VALIDATION_FIELDS)
            a['spec']['target']='different'
            with self.assertRaisesRegex(G.InitialFittingContextRejected,'choose_validation'):
                G.prepare_initial_fitting_context(**a)

    def test_mutated_strict_source_or_input_witness_rejects(self):
        for field in ('producer_spec','source_fingerprints','source_paths'):
            with tempfile.TemporaryDirectory() as directory:
                a=self.arguments(directory)
                getattr(a['authority'],field)['new']='changed'
                with self.subTest(field=field),self.assertRaisesRegex(G.InitialFittingContextRejected,'authority_mutated'):
                    G.prepare_initial_fitting_context(**a)
                a['_dependencies'].prepare.assert_not_called()

    def test_unknown_metric_and_incompatible_resolved_objective_do_not_default(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); old=a['authority']
            metric=MetricSpec(None,None,None,'unknown','explicit missing evidence')
            with self.assertRaises(UnresolvedMetricError):
                G.InitialFittingAuthority(old.producer_frame,old.producer_spec,old.producer_declaration,
                    metric,old.producer_budget,old.producer_checkpoint,old.source_fingerprints,old.source_paths)
            spec=deepcopy(old.producer_spec); metric=MetricSpec('mae','minimize','value','resolved','explicit synthetic')
            spec['metric']='mae'; spec['strict_task_contract']['metric_spec']=metric.to_dict()
            a['authority']=G.InitialFittingAuthority(old.producer_frame,spec,old.producer_declaration,
                metric,old.producer_budget,old.producer_checkpoint,old.source_fingerprints,old.source_paths)
            a['spec']=dict(spec)
            with self.assertRaisesRegex(G.InitialFittingContextRejected,'RMSE_or_MacroF1'):
                G.prepare_initial_fitting_context(**a)

    def test_original_row_order_preserved_and_invalid_indices_not_coerced(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory)
            result=G.prepare_initial_fitting_context(**a)
            actual=a['_dependencies'].prepare.call_args.kwargs
            self.assertEqual(actual['fitting_positions'],[4,0,2])
            self.assertFalse(result.receipt['legacy_context_merged'])
            b=dict(a,fitting_positions=R.np.asarray([4,0,2],dtype='int64'))
            G.prepare_initial_fitting_context(**b)
            for dtype in ('float64','bool'):
                b=dict(a,fitting_positions=R.np.asarray([4,0,2],dtype=dtype))
                with self.subTest(dtype=dtype),self.assertRaises(ValueError):
                    G.prepare_initial_fitting_context(**b)
            for rows in ([True,0,2],[4.,0,2],['4',0,2],[4,4,2],[6,0,2],[1,0,2]):
                b=dict(a,fitting_positions=rows)
                with self.subTest(rows=rows),self.assertRaises(ValueError): G.prepare_initial_fitting_context(**b)

    def test_fresh_context_itself_has_no_profile_split_feedback_or_retention_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); result=G.prepare_initial_fitting_context(**a)
            self.assertEqual(set(result.context),{'fitting_context'})
            self.assertEqual(result.context['fitting_context']['data']['target']['mean'],4.)
            self.assertIsNone(result.receipt['upstream_native_parser_IO_bytes'])
            self.assertFalse(result.receipt['total_parent_IO_qualified'])
            self.assertFalse(result.receipt['whole_feedback_fitting_only'])
            self.assertEqual(result.receipt['actual_gateway_calls_from_preparation'],0)

    def test_exact_prompt_and_packet_are_rechecked_immediately_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); result=G.prepare_initial_fitting_context(**a); gateway=Mock()
            with self.assertRaisesRegex(G.InitialFittingContextRejected,'exact_SYSTEM'):
                result.before_request('CHANGED PROMPT')
            result.context['fitting_context']['data']['target']['mean']=999.
            with self.assertRaisesRegex(ValueError,'builder_packet_receipt'):
                result.before_request(a['system_prompt'])
            gateway.assert_not_called()

    def test_packet_and_complete_message_UTF8_caps_fail_before_gateway(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); a['system_prompt']='Ж'*40000
            with self.assertRaisesRegex(G.InitialFittingContextRejected,'complete_message'):
                G.prepare_initial_fitting_context(**a)
            a=self.arguments(directory)
            result=G.prepare_initial_fitting_context(**a)
            result.receipt['builder']['packet_UTF8_bytes']=8193
            with self.assertRaises(ValueError): result.before_request(a['system_prompt'])

    def test_original_guard_failure_propagates_without_new_clock_or_request(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); guard=a['authority'].producer_checkpoint
            primary=PermissionError('synthetic existing guard denial'); guard.failure=primary
            with self.assertRaises(PermissionError) as caught: G.prepare_initial_fitting_context(**a)
            self.assertIs(caught.exception,primary)
            self.assertEqual(a['authority'].producer_budget.started,1.)
            self.assertEqual(a['authority'].producer_budget.deadline,99.)
            a['_dependencies'].prepare.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory); old=a['authority']; original=FalseOriginalBudget()
            a['authority']=G.InitialFittingAuthority(old.producer_frame,old.producer_spec,
                old.producer_declaration,old.producer_metric_spec,original,old.producer_checkpoint,
                old.source_fingerprints,old.source_paths)
            a['_dependencies'].current_budget=lambda:original
            with self.assertRaisesRegex(ValueError,'original budget required'):
                G.prepare_initial_fitting_context(**a)
            a['_dependencies'].prepare.assert_not_called()

    def test_gateway_arguments_unchanged_and_preflight_precedes_each_initial_call(self):
        tree=ast.parse(inspect.getsource(R.solve_single))
        branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and any(
            isinstance(v,ast.Name) and v.id=='four_stage' for v in ast.walk(n.test)) and any(
            isinstance(v,ast.Call) and isinstance(v.func,ast.Name) and v.func.id=='request_json'
            for v in ast.walk(n)))
        calls=[n for n in ast.walk(branch) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='request_json']
        self.assertEqual(len(calls),2)
        for call in calls:
            self.assertEqual(call.args[1].id,'context')
            self.assertEqual(next(k.value.value for k in call.keywords if k.arg=='max_output'),8192)
        preflights=[n for n in ast.walk(branch) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                    and n.func.attr=='before_request']
        self.assertEqual(len(preflights),2)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
            and n.func.attr=='update' and isinstance(n.func.value,ast.Name)
            and n.func.value.id=='context' for n in ast.walk(branch)))

    def test_bounded_split_byte_read_and_no_gateway_parser_or_clock_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            a=self.arguments(directory)
            b=Budget(a['authority'].producer_budget,a['authority'].producer_checkpoint,io_bytes_already_charged=0)
            expected=hashlib.sha256(Path(a['split_path']).read_bytes()).hexdigest()
            self.assertEqual(G.split_digest(a['split_path'],b),expected)
            self.assertEqual(b.io_bytes,Path(a['split_path']).stat().st_size)
            charged=b.io_bytes
            with Path(a['split_path']).open('wb') as stream:
                stream.seek(8*2**20); stream.write(b'x')
            with self.assertRaisesRegex(G.InitialFittingContextRejected,'bounded_saved_original_split'):
                G.split_digest(a['split_path'],b)
            self.assertEqual(b.io_bytes,charged)
        source=ast.parse(inspect.getsource(G))
        names={n.func.id for n in ast.walk(source) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse({'request_json','load_inputs','discover','RunBudget','PreparationBudget'} & names)


if __name__=='__main__': unittest.main(verbosity=2)
