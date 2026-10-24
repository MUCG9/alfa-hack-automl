"""Prepared Q3A01 mock/native synthetic fixtures; no real data/model/provider."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

P=Path(__file__).resolve().parent
source=importlib.util.spec_from_file_location('_role_scoped_independent_auditor',P/'audit_final.py')
A=importlib.util.module_from_spec(source);source.loader.exec_module(A)


class CSVRoleContracts(unittest.TestCase):
    def test_native_numeric_prediction_name_collisions_and_lexical_labels(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();worker=root/'worker-1';component=worker/'component-0';component.mkdir(parents=True)
            train=root/'train.csv';test=root/'test.csv';sample=root/'sample.csv'
            train.write_text('id,label,y_true,y_pred,outcome\n0001,001,1,2,3\n0002,NA,1.0,2.0,3.0\n',encoding='utf-8')
            test.write_text('id,y_true,y_pred,outcome\n0001,1,2,3\n0002,1.0,2.0,3.0\n',encoding='utf-8')
            sample.write_text('id,outcome\n0002,0\n0001,0\n',encoding='utf-8')
            submission=component/'submission.csv';validation=component/'validation_predictions.csv'
            submission.write_text('id,outcome\n0002,NA\n0001,001\n',encoding='utf-8')
            validation.write_text('row_position,y_true,y_pred\n0,001,NA\n1,NA,001\n',encoding='utf-8')
            result=component/'result.json';result.write_text('{}',encoding='utf-8')
            spec=dict(kind='classification',id='id',target='label',output_columns=['outcome'],
                paths=dict(train=str(train),test=str(test),sample_submission=str(sample)))
            parents=[dict(result=dict(output_dir=str(worker)))]
            seal=dict(files_sha256={str(p):A.sha(p) for p in (result,submission,validation)})
            roles=A.exact_csv_roles(spec,parents,seal);parser=A.LiteralCSV(pd,spec,roles)
            actual=parser.read_csv(train);baseline=pd.read_csv(train,converters=dict(id=str,label=str))
            pd.testing.assert_frame_equal(actual,baseline)
            predictors=['y_true','y_pred','outcome']
            self.assertTrue(all(actual[name].dtype.kind in 'if' for name in predictors))
            self.assertEqual(pd.util.hash_pandas_object(actual[predictors],index=False).tolist(),
                pd.util.hash_pandas_object(baseline[predictors],index=False).tolist())
            self.assertEqual(actual.label.tolist(),['001','NA']);self.assertEqual(actual.id.tolist(),['0001','0002'])
            self.assertTrue(all(parser.read_csv(test)[name].dtype.kind in 'if' for name in predictors))
            self.assertIn(parser.read_csv(sample).outcome.dtype.kind,'if')
            self.assertEqual(parser.read_csv(submission).outcome.tolist(),['NA','001'])
            predicted=parser.read_csv(validation)
            self.assertEqual(predicted.y_true.tolist(),['001','NA']);self.assertEqual(predicted.y_pred.tolist(),['NA','001'])
            spec['kind']='regression';regression=A.LiteralCSV(pd,spec,roles).read_csv(submission)
            self.assertTrue(pd.isna(regression.outcome.iloc[0]));self.assertEqual(regression.outcome.iloc[1],1.)

    def test_mock_exact_path_role_controls_converters_not_filename_or_column_name(self):
        class Series(list):
            def tolist(self):return list(self)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();train=root/'train.csv';unknown=root/'submission.csv'
            train.write_text('id,label,y_true\n001,001,1\nNA,NA,1.0\n',encoding='utf-8')
            unknown.write_text('id,label\n001,001\n',encoding='utf-8')
            fake=SimpleNamespace(read_csv=Mock(return_value=dict(id=Series(['001','NA']),label=Series(['001','NA']),y_true=Series([1.,1.]))))
            spec=dict(kind='classification',id='id',target='label',output_columns=['y_true'])
            parser=A.LiteralCSV(fake,spec,{str(train):'train'})
            with self.assertRaisesRegex(A.AuditStop,'exact_CSV_path_and_role'):parser.read_csv(unknown)
            fake.read_csv.assert_not_called()
            frame=parser.read_csv(train)
            self.assertEqual(set(fake.read_csv.call_args.kwargs['converters']),{'id','label'})
            self.assertEqual(frame['y_true'],[1.,1.])
            with self.assertRaisesRegex(A.AuditStop,'converter_outside_exact_declared_role'):
                parser.read_csv(train,converters={'y_true':str})
            self.assertEqual(fake.read_csv.call_count,1)


if __name__=='__main__':unittest.main()
