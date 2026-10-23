"""UAR-v1 pure fallback/publication contracts; no learner or API calls.

Prepared in an isolated worktree. Execution requires the coordinator's lease.
"""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.publishing import service as publishing


class UARFallbackWriterTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.output=self.root/'submission.csv'

    def tearDown(self):
        self.directory.cleanup()

    def regression(self,metric='rmse'):
        spec={'kind':'regression','metric':metric,'target':'y','id':'id',
              'prediction_type':'value','output_columns':['y'],
              'sample_test_positions':[2,0,1]}
        test=pd.DataFrame({'id':['b','a','c'],'x':[0,1,2]})
        sample=pd.DataFrame({'id':['c','b','a'],'y':[0.,0.,0.]})
        return spec,test,sample

    def good_output(self):
        spec,test,sample=self.regression()
        publishing.save_submission(spec,sample,test,[30.,10.,20.],self.output)
        return self.output.read_bytes()

    def assert_no_staging(self):
        self.assertEqual(list(self.root.glob('.*.tmp')),[])

    def test_metric_aware_regression_fallback_mean_and_median(self):
        train=pd.DataFrame({'y':[0.,0.,90.]})
        for metric,value in [('rmse',30.),('mse',30.),('mae',0.)]:
            with self.subTest(metric=metric):
                spec={'kind':'regression','metric':metric,'target':'y'}
                np.testing.assert_array_equal(publishing.dummy_predictions(spec,train,3),[value]*3)

    def test_label_majority_and_probability_priors_keep_declared_order(self):
        train=pd.DataFrame({'y':['a','a','b','a']})
        spec={'kind':'classification','metric':'macro_f1','target':'y',
              'prediction_type':'value','classes':['a','b']}
        np.testing.assert_array_equal(publishing.dummy_predictions(spec,train,2),['a','a'])
        scalar=dict(spec,metric='roc_auc',prediction_type='probability',positive_class='a')
        np.testing.assert_array_equal(publishing.dummy_predictions(scalar,train,2),[.75,.75])
        matrix=dict(spec,prediction_type='probability_matrix',output_columns=['b','a','absent'])
        np.testing.assert_array_equal(publishing.dummy_predictions(matrix,train,2),[[.25,.75,0.]]*2)

    def test_submission_keeps_ID_and_sample_order(self):
        spec,test,sample=self.regression()
        publishing.save_submission(spec,sample,test,[30.,10.,20.],self.output)
        actual=pd.read_csv(self.output)
        self.assertEqual(actual.columns.tolist(),['id','y'])
        self.assertEqual(actual.id.tolist(),['c','b','a'])
        self.assertEqual(actual.y.tolist(),[20.,30.,10.])
        self.assert_no_staging()

    def test_probability_columns_and_no_ID_row_order(self):
        spec={'kind':'classification','metric':'macro_f1','target':'y','id':None,
              'classes':['a','b'],'prediction_type':'probability_matrix',
              'output_columns':['b','a'],'sample_test_positions':[1,0]}
        test=pd.DataFrame({'x':[1,2]});sample=pd.DataFrame({'b':[0.,0.],'a':[0.,0.]})
        publishing.save_submission(spec,sample,test,[[.2,.8],[.7,.3]],self.output)
        actual=pd.read_csv(self.output)
        self.assertEqual(actual.columns.tolist(),['b','a'])
        np.testing.assert_allclose(actual.to_numpy(),[[.7,.3],[.2,.8]])

    def test_validation_failure_never_replaces_last_good(self):
        before=self.good_output();spec,test,sample=self.regression()
        for values in [[1.],[1.,np.nan,2.],[1.,np.inf,2.]]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                publishing.save_submission(spec,sample,test,values,self.output)
            self.assertEqual(self.output.read_bytes(),before)
        class_spec=dict(spec,kind='classification',metric='macro_f1',classes=['a','b'])
        with self.assertRaises(ValueError):
            publishing.save_submission(class_spec,sample,test,['a','unknown','b'],self.output)
        self.assertEqual(self.output.read_bytes(),before);self.assert_no_staging()

    def test_write_flush_fsync_and_replace_errors_preserve_last_good(self):
        before=self.good_output();spec,test,sample=self.regression()
        original_tempfile=publishing.tempfile.NamedTemporaryFile

        def partial(frame,stream,*args,**kwargs):
            stream.write('partial output\n')
            raise OSError('injected CSV write failure')

        class FlushFailure:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def __getattr__(self,name):return getattr(self.stream,name)
            def flush(self):raise OSError('injected flush failure')

        cases=[
            ('write',patch.object(pd.DataFrame,'to_csv',partial)),
            ('flush',patch.object(publishing.tempfile,'NamedTemporaryFile',
                side_effect=lambda *a,**k:FlushFailure(original_tempfile(*a,**k)))),
            ('fsync',patch.object(publishing.os,'fsync',side_effect=OSError('injected fsync failure'))),
            ('replace',patch.object(publishing.os,'replace',side_effect=OSError('injected replace failure'))),
        ]
        for name,failure in cases:
            with self.subTest(operation=name),failure,self.assertRaises(OSError):
                publishing.save_submission(spec,sample,test,[7.,8.,9.],self.output)
            self.assertEqual(self.output.read_bytes(),before);self.assert_no_staging()

    def test_unique_sibling_is_fsynced_and_closed_before_replace(self):
        spec,test,sample=self.regression();names=[];streams=[];events=[]
        original_tempfile=publishing.tempfile.NamedTemporaryFile
        original_replace=publishing.os.replace

        def temporary(*args,**kwargs):
            stream=original_tempfile(*args,**kwargs)
            names.append(Path(stream.name));streams.append(stream);return stream

        def replace(source,destination):
            source=Path(source);self.assertEqual(source.parent,self.output.parent)
            self.assertEqual(source.read_bytes().splitlines()[0],b'id,y')
            self.assertTrue(streams[-1].closed)
            self.assertEqual(events[-1],'fsync');events.append('replace')
            original_replace(source,destination)

        with patch.object(publishing.tempfile,'NamedTemporaryFile',side_effect=temporary),\
                patch.object(publishing.os,'fsync',side_effect=lambda fd:events.append('fsync')),\
                patch.object(publishing.os,'replace',side_effect=replace):
            publishing.save_submission(spec,sample,test,[1.,2.,3.],self.output)
            publishing.save_submission(spec,sample,test,[4.,5.,6.],self.output)
        self.assertEqual(len(set(names)),2)
        self.assertEqual(events,['fsync','replace','fsync','replace']);self.assert_no_staging()

    def test_expected_version_refuses_stale_or_midwrite_changed_output(self):
        before=self.good_output();spec,test,sample=self.regression()
        expected=hashlib.sha256(before).hexdigest()
        with patch.object(publishing.tempfile,'NamedTemporaryFile') as temporary:
            with self.assertRaises(ValueError):
                publishing.save_submission(spec,sample,test,[1.,2.,3.],self.output,expected_current_sha='0'*64)
            temporary.assert_not_called()
        self.assertEqual(self.output.read_bytes(),before)
        later=b'id,y\nc,101\nb,102\na,103\n'
        with patch.object(publishing.os,'fsync',side_effect=lambda fd:self.output.write_bytes(later)):
            with self.assertRaises(ValueError):
                publishing.save_submission(spec,sample,test,[1.,2.,3.],self.output,expected_current_sha=expected)
        self.assertEqual(self.output.read_bytes(),later);self.assert_no_staging()
        current=hashlib.sha256(later).hexdigest()
        publishing.save_submission(spec,sample,test,[1.,2.,3.],self.output,expected_current_sha=current)
        self.assertNotEqual(self.output.read_bytes(),later)

    def test_legacy_checkpoint_receipt_does_not_claim_validation(self):
        source=self.root/'legacy.csv';source.write_bytes(b'opaque legacy checkpoint\n')
        receipt=publishing.checkpoint({'submission':source},self.output)
        self.assertEqual(self.output.read_bytes(),source.read_bytes())
        self.assertEqual(receipt['validation'],'not_fully_validated_legacy_copy')
        self.assertTrue(receipt['atomic_publication']);self.assert_no_staging()

    def test_validated_checkpoint_avoids_double_permutation_and_retains_labels(self):
        source=self.root/'candidate.csv';spec,test,sample=self.regression(metric='rmsle')
        publishing.save_submission(spec,sample,test,[30.,10.,20.],source)
        receipt=publishing.checkpoint({'submission':source},self.output,spec=spec,sample=sample,test=test)
        self.assertEqual(pd.read_csv(self.output).y.tolist(),[20.,30.,10.])
        self.assertEqual(receipt['validation'],'validated_output_context')
        cls={'kind':'classification','metric':'macro_f1','target':'y','id':'id',
             'classes':['001','NA'],'prediction_type':'value','output_columns':['y']}
        test=pd.DataFrame({'id':['002','001']});sample=pd.DataFrame({'id':['002','001'],'y':['','']})
        source.write_text('id,y\n002,001\n001,NA\n',encoding='utf-8')
        publishing.checkpoint({'submission':source},self.output,spec=cls,sample=sample,test=test)
        actual=pd.read_csv(self.output,dtype=str,keep_default_na=False)
        self.assertEqual(actual.id.tolist(),['002','001']);self.assertEqual(actual.y.tolist(),['001','NA'])
        matrix={'kind':'classification','metric':'log_loss','target':'y','id':None,
                'classes':['a','b'],'prediction_type':'probability_matrix',
                'output_columns':['b','a'],'sample_test_positions':[1,0]}
        test=pd.DataFrame({'x':[1,2]});sample=pd.DataFrame({'b':[0.,0.],'a':[0.,0.]})
        publishing.save_submission(matrix,sample,test,[[.2,.8],[.7,.3]],source)
        publishing.checkpoint({'submission':source},self.output,spec=matrix,sample=sample,test=test)
        np.testing.assert_allclose(pd.read_csv(self.output).to_numpy(),[[.7,.3],[.2,.8]])

    def test_validated_checkpoint_rejects_bad_contract_without_overwrite(self):
        before=self.good_output();source=self.root/'candidate.csv';spec,test,sample=self.regression()
        for content in ['id,bad\nc,1\nb,2\na,3\n','id,y\na,1\nb,2\nc,3\n',
                        'id,y\nc,1\nb,inf\na,3\n','id,y\nc,1\nb,\na,3\n']:
            source.write_text(content,encoding='utf-8')
            with self.subTest(content=content),self.assertRaises(ValueError):
                publishing.checkpoint({'submission':source},self.output,spec=spec,sample=sample,test=test)
            self.assertEqual(self.output.read_bytes(),before)
        with self.assertRaises(ValueError):
            publishing.checkpoint({'submission':source},self.output,spec=spec)
        self.assertEqual(self.output.read_bytes(),before);self.assert_no_staging()

    def test_multitarget_uses_same_atomic_writer_and_preserves_bad_candidate(self):
        sample=pd.DataFrame({'id':['a','b'],'left':[0.,0.],'right':[0.,0.]})
        parts=[]
        for target,values in [('left',[1.,2.]),('right',[3.,4.])]:
            source=self.root/(target+'.csv')
            pd.DataFrame({'id':['a','b'],target:values}).to_csv(source,index=False)
            parts.append(({'target':target,'id':'id','kind':'regression','prediction_type':'value',
                           'output_columns':[target],'sample_columns':['id',target]},source))
        publishing.publish_targets(parts,sample,self.output)
        before=self.output.read_bytes()
        with patch.object(publishing.os,'replace',side_effect=OSError('injected replace failure')):
            with self.assertRaises(OSError):publishing.publish_targets(parts,sample,self.output)
        self.assertEqual(self.output.read_bytes(),before)
        pd.DataFrame({'id':['b','a'],'right':[3.,4.]}).to_csv(parts[1][1],index=False)
        with self.assertRaises(ValueError):publishing.publish_targets(parts,sample,self.output)
        self.assertEqual(self.output.read_bytes(),before);self.assert_no_staging()


if __name__=='__main__':
    unittest.main(verbosity=2)
