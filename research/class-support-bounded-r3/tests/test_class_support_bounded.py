"""PROSPECTIVE pure contract tests; source prepared, NOT executed at handoff.
No model/gateway/runner imports, network, fitting or real research data.
Future execution needs a bounded technical envelope after the actual current predecessor closure.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'src'/'automl'/'search'
spec=importlib.util.spec_from_file_location('bounded_class_support_fixture',SOURCE/'class_support.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
# The future pure screen uses the same exact helper, without importing automl.
for name in ('automl','automl.search'):
    if name not in sys.modules:
        sys.modules[name]=types.ModuleType(name);sys.modules[name].__path__=[]
sys.modules['automl.search.class_support']=support
spec=importlib.util.spec_from_file_location('bounded_screen_fixture',SOURCE/'class_support_screen.py')
screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)


def signature(recipe):
    return hashlib.sha256(json.dumps(recipe,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def task(classes=None):
    return dict(kind='classification',metric='macro_f1',classes=classes or ['a','b'],features=['f'],target='y',id='id')


def packet():
    return support.fitting_class_support(task(),iter(['a','a','b','b']),iter([1,1,2,3]),'0'*64,4,1)[0]


def fixture(root):
    """Synthetic sealed primary files only; no actual data or numeric fits."""
    split=root/'split.npz';split.write_bytes(b'synthetic-array-artifact')
    (root/'split.json').write_text(json.dumps({'split_sha256':'0'*64}),encoding='utf-8')
    records=[]
    for index,values in enumerate(({'a':.5,'b':.6},{'a':.4,'b':.8})):
        directory=root/f'experiment-{index:02d}';directory.mkdir()
        recipe={'engine':'fixture','params':{'index':index}}
        metrics={'per_class_f1':values,'macro_f1':sum(values.values())/2}
        record=dict(status='ok',full_fit=False,recipe=recipe,metrics=metrics,experiment_index=index,output_dir=str(directory))
        job=dict(spec=task(),recipe=recipe,split_path=str(split),output_dir=str(directory),full_fit=False)
        for name,value in [('job.json',job),('result.json',record)]:
            (directory/name).write_text(json.dumps(value),encoding='utf-8')
        (directory/'validation_predictions.csv').write_bytes(b'id,prediction\n1,a\n')
        (directory/'validation_probabilities.npz').write_bytes(b'synthetic-probability-artifact')
        records.append(record)
    protected=root/'protected_control.json';protected.write_text(json.dumps(records[0]['recipe']),encoding='utf-8')
    descriptor=dict(path=str(protected),sha256=hashlib.sha256(protected.read_bytes()).hexdigest())
    binding=support.capture_primary_bindings(task(),records,split,root/'split.json',descriptor,signature(records[0]['recipe']),signature)
    return records,binding


class BoundedSupportTests(unittest.TestCase):
    def rejected(self,code,fn,*args,**kwargs):
        with self.assertRaises(support.ContextRejected) as caught:fn(*args,**kwargs)
        receipt=caught.exception.receipt
        self.assertEqual(receipt['code'],code);self.assertEqual(receipt['API_calls'],0)
        self.assertIsNone(receipt['metrics']);self.assertFalse(receipt['fields_dropped'])

    def test_metric_scope_rejects_regression_and_accuracy(self):
        for changed in ({'kind':'regression'},{'metric':'accuracy'}):
            value=task();value.update(changed)
            self.rejected('only_classification_macro_f1_is_eligible',support.validate_task,value)

    def test_class64_boundary_and65_rejection(self):
        self.assertEqual(len(support.validate_task(task([str(i) for i in range(64)]))),64)
        self.rejected('class_count_limit',support.validate_task,task([str(i) for i in range(65)]))

    def test_label_UTF8_128_boundary_129_and_duplicate(self):
        support.validate_task(task(['я'*64,'b']))
        self.rejected('class_label_UTF8_limit',support.validate_task,task(['я'*64+'a','b']))
        self.rejected('duplicate_class_labels',support.validate_task,task(['a','a']))

    def test_row_limit_checked_before_iterable_consumption(self):
        def forbidden():
            raise AssertionError('over-cap input must not be consumed')
            yield
        self.rejected('fitting_row_limit',support.fitting_class_support,task(),forbidden(),forbidden(),'0'*64,200001)

    def test_exact_row_alignment_and_uint64_required(self):
        self.rejected('aligned_known_fitting_labels_required',support.fitting_class_support,task(),['a'],[1,2],'0'*64,2)
        self.rejected('fitting_row_count_mismatch',support.fitting_class_support,task(),['a'],[1],'0'*64,2)
        self.rejected('original_uint64_hash_required',support.fitting_class_support,task(),['a'],[-1],'0'*64,1)

    def test_duplicates_sharing_absence_and_fixed_rarest(self):
        value,_=support.fitting_class_support(task(['a','b','c']),['a','a','b'],[1,1,1],'0'*64,3,1)
        self.assertEqual(value['raw_fitting_rows_per_class'],dict(a=2,b=1,c=0))
        self.assertEqual(value['original_feature_hash_groups_per_class'],dict(a=1,b=1,c=0))
        self.assertEqual(value['cross_class_shared_hash_groups'],1)
        self.assertEqual(value['rarest_fitting_class'],'c');self.assertEqual(value['classes_absent_from_fitting'],['c'])

    def test_complete_messages_exact_byte_boundary_not_output_tokens(self):
        def raw(n):
            user=json.dumps({'x':'a'*n},ensure_ascii=False)
            return json.dumps([{'role':'system','content':'SYSTEM\nSTAGED'},{'role':'user','content':user}],ensure_ascii=False)
        n=65536-len(raw(0).encode('utf-8'))
        receipt=support.bounded_messages('SYSTEM\nSTAGED',{'x':'a'*n})
        self.assertEqual(receipt['messages_UTF8_bytes'],65536)
        self.assertEqual(receipt['messages_sha256'],hashlib.sha256(raw(n).encode()).hexdigest())
        self.assertTrue(receipt['output_token_limit_is_not_input_bound'])
        self.rejected('serialized_UTF8_limit',support.bounded_messages,'SYSTEM\nSTAGED',{'x':'a'*(n+1)})

    def test_escaping_and_multibyte_counted_in_complete_messages(self):
        value={'x':'я"\\\n'*10}
        receipt=support.bounded_messages('SYSTEM\nSTAGED',value)
        user=json.dumps(value,ensure_ascii=False)
        actual=json.dumps([{'role':'system','content':'SYSTEM\nSTAGED'},{'role':'user','content':user}],ensure_ascii=False).encode('utf-8')
        self.assertEqual(receipt['messages_UTF8_bytes'],len(actual))

    def test_nonfinite_opaque_cycle_and_deep_inputs_reject(self):
        for value in ({'x':float('nan')},{'x':object()}):
            with self.assertRaises(support.ContextRejected):support.bounded_messages('S',value)
        cycle=[];cycle.append(cycle)
        self.rejected('cyclic_JSON_input',support.bounded_messages,'S',cycle)
        deep=0
        for _ in range(34):deep=[deep]
        self.rejected('JSON_shape_limit',support.bounded_messages,'S',deep)

    def test_packet_overflow_rejects_without_trimming_or_base_mutation(self):
        value=packet();value['hash_interpretation']='a'*16384;original=copy.deepcopy(value)
        base={'feedback_read_first':[]}
        self.rejected('serialized_UTF8_limit',support.add_support_context,base,task(),value,[],None,signature)
        self.assertEqual(value,original);self.assertEqual(base,{'feedback_read_first':[]})

    def test_malformed_support_gets_predictable_receipt(self):
        value=packet();value['supported_classes']=None
        self.rejected('support_packet_values_mismatch',support.add_support_context,{'feedback_read_first':[]},task(),value,[],None,signature)

    def test_missing_and_failed_records_are_null_not_certified_boolean(self):
        value,receipt=support.primary_f1_feedback(None,None,packet(),None,signature)
        self.assertIsNone(value);self.assertIsNone(receipt['metrics'])
        with self.assertRaises(TypeError):
            support.primary_f1_feedback(None,None,packet(),None,signature,same_primary_cut=True)

    def test_valid_lineage_deltas_all_class_mean_and_supported_losses(self):
        with tempfile.TemporaryDirectory() as directory:
            records,binding=fixture(Path(directory));value,receipt=support.primary_f1_feedback(records[1],records[0],packet(),binding,signature)
            self.assertEqual(receipt['status'],'saved_primary_lineage_checked');self.assertFalse(receipt['independent_metric_recomputation'])
            self.assertAlmostEqual(value['macro_f1_all_class_delta'],.05)
            self.assertAlmostEqual(value['supported_class_losses']['a'],-.1)
            self.assertAlmostEqual(value['macro_f1_excluding_rarest']['delta'],.2)

    def test_artifact_mutation_missing_and_primary_split_mutation_null(self):
        for name in ('validation_predictions.csv','validation_probabilities.npz','job.json','result.json','split.npz','protected_control.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);records,binding=fixture(root)
                path=root/name if name in ('split.npz','protected_control.json') else root/'experiment-01'/name
                path.write_bytes(path.read_bytes()+b' ')
                value,receipt=support.primary_f1_feedback(records[1],records[0],packet(),binding,signature)
                self.assertIsNone(value);self.assertEqual(receipt['status'],'comparison_unavailable')

    def test_rebound_wrong_split_fullfit_recipe_and_spec_are_still_rejected(self):
        for field in ('split_path','full_fit','recipe','spec'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);records,binding=fixture(root);path=root/'experiment-01'/'job.json';job=json.loads(path.read_text())
                if field=='split_path':job[field]=str(root/'confirmation'/'split.npz')
                elif field=='full_fit':job[field]=True
                elif field=='recipe':job[field]={'engine':'other'}
                else:job[field]=dict(task(),target='different')
                path.write_text(json.dumps(job));binding['records'][str(path.parent)][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertIsNone(support.primary_f1_feedback(records[1],records[0],packet(),binding,signature)[0])

    def test_nonfinite_incomplete_and_wrong_macro_saved_metrics_null(self):
        for change in ('nan','incomplete','wrong_macro','bool'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);records,binding=fixture(root);record=records[1]
                if change=='nan':record['metrics']['per_class_f1']['a']=float('nan')
                elif change=='incomplete':record['metrics']['per_class_f1'].pop('a')
                elif change=='bool':record['metrics']['per_class_f1']['a']=True
                else:record['metrics']['macro_f1']=.99
                path=root/'experiment-01'/'result.json';path.write_text(json.dumps(record))
                binding['records'][str(path.parent)][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertIsNone(support.primary_f1_feedback(record,records[0],packet(),binding,signature)[0])

    def test_OFF_ON_preflight_same_bounds_factor_only_and_base_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            records,binding=fixture(Path(directory));base={'feedback_read_first':[{'recipe_sha256':signature(r['recipe'])} for r in records]};before=copy.deepcopy(base)
            views,receipt=screen.prepare_generation_pair('SYSTEM\nSTAGED',base,task(),packet(),records,binding,signature,4)
            self.assertEqual(views['OFF'],before);self.assertEqual(base,before)
            restored=copy.deepcopy(views['ON']);restored.pop('class_support')
            for row in restored['feedback_read_first']:row.pop('protected_control_comparison')
            self.assertEqual(restored,views['OFF'])
            self.assertEqual(receipt['OFF']['hard_input_byte_limit'],receipt['ON']['hard_input_byte_limit'])
            self.rejected('screen_fitting_row_snapshot_mismatch',screen.prepare_generation_pair,'SYSTEM\nSTAGED',base,task(),packet(),records,binding,signature,3)

    def test_OFF_overflow_prevents_both_views_before_any_API(self):
        self.rejected('serialized_UTF8_limit',screen.prepare_generation_pair,'S',{'x':'a'*65536,'feedback_read_first':[]},task(),packet(),[],None,signature,4)

    def test_IO_time_and_record_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x';path.write_bytes(b'123')
            with patch.object(support,'MAX_PREPARATION_IO_BYTES',2):
                self.rejected('preparation_IO_limit',support._file_sha,path,support.PreparationBudget())
        with patch.object(support.time,'monotonic',return_value=0):budget=support.PreparationBudget()
        with patch.object(support.time,'monotonic',return_value=6):self.rejected('preparation_time_limit',budget.check)
        self.rejected('primary_record_count_limit',support.add_support_context,{},task(),packet(),[{}]*15,None,signature)


    def test_screen_malformed_support_rejects_before_sum(self):
        base={'feedback_read_first':[]}
        for value in (None,[],{},dict(packet(),unexpected=1)):
            with self.subTest(value_type=type(value).__name__),patch('builtins.sum',side_effect=AssertionError('must not sum malformed support')):
                self.rejected('support_packet_schema_mismatch',screen.prepare_generation_pair,'S',base,task(),value,[],None,signature,4)

    def test_external_container_subclasses_reject_without_enumeration(self):
        class TrapDict(dict):
            def __iter__(self):raise AssertionError('external mapping enumerated')
            def __len__(self):raise AssertionError('external mapping length invoked')
            def items(self):raise AssertionError('external mapping items invoked')
            def values(self):raise AssertionError('external mapping values invoked')
        class TrapList(list):
            def __iter__(self):raise AssertionError('external list enumerated')
            def __len__(self):raise AssertionError('external list length invoked')
        self.rejected('support_packet_schema_mismatch',support.validate_support_packet,task(),TrapDict(packet()))
        for field in ('raw_fitting_rows_per_class','original_feature_hash_groups_per_class'):
            value=packet();value[field]=TrapDict(value[field])
            self.rejected('support_count_map_mismatch',support.validate_support_packet,task(),value)
        for field in ('supported_classes','classes_absent_from_fitting'):
            value=packet();value[field]=TrapList(value[field])
            self.rejected('support_packet_values_mismatch',support.validate_support_packet,task(),value)

    def test_count_map_cardinality_rejects_before_value_traversal(self):
        for field in ('raw_fitting_rows_per_class','original_feature_hash_groups_per_class'):
            value=packet();value[field]={'a':object(),'b':object(),'extra':object()}
            with self.subTest(field=field),patch.object(support,'_json_text',side_effect=AssertionError('must reject before JSON traversal')),patch('builtins.sum',side_effect=AssertionError('must not sum over-cap map')):
                self.rejected('support_count_map_mismatch',support.add_support_context,{'feedback_read_first':[]},task(),value,[],None,signature)
                self.rejected('support_count_map_mismatch',screen.prepare_generation_pair,'S',{'feedback_read_first':[]},task(),value,[],None,signature,4)

    def test_support_list_cardinality_rejects_before_value_traversal(self):
        for field in ('supported_classes','classes_absent_from_fitting'):
            value=packet();value[field]=[object(),object(),object()]
            with self.subTest(field=field),patch.object(support,'_json_text',side_effect=AssertionError('must reject before JSON traversal')),patch('builtins.sum',side_effect=AssertionError('must not sum before all container bounds')):
                self.rejected('support_packet_values_mismatch',support.add_support_context,{'feedback_read_first':[]},task(),value,[],None,signature)
                self.rejected('support_packet_values_mismatch',screen.prepare_generation_pair,'S',{'feedback_read_first':[]},task(),value,[],None,signature,4)

    def test_screen_shared_budget_retains_prior_wall_and_IO(self):
        budget=support.PreparationBudget();budget.charge(137)
        _,receipt=screen.prepare_generation_pair('S',{'feedback_read_first':[]},task(),packet(),[],None,signature,4,budget=budget)
        self.assertEqual(receipt['preparation_IO_bytes'],137)
        self.assertEqual(receipt['preparation_budget_scope'],'caller_supplied_cumulative_budget')
        _,local=screen.prepare_generation_pair('S',{'feedback_read_first':[]},task(),packet(),[],None,signature,4)
        self.assertEqual(local['preparation_budget_scope'],'screen_entry_only')
        self.assertTrue(local['earlier_support_capture_requires_same_budget_or_parent_accounting'])
        value=packet()
        with patch.object(support.time,'monotonic',return_value=0):spent=support.PreparationBudget()
        with patch.object(support.time,'monotonic',return_value=6):
            self.rejected('preparation_time_limit',screen.prepare_generation_pair,'S',{'feedback_read_first':[]},task(),value,[],None,signature,4,budget=spent)


if __name__=='__main__':unittest.main()
