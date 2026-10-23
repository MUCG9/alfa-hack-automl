"""Optional exact-pin LAMA lifecycle, not a public quality benchmark."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from automl.contracts.lama import LamaRequest
from automl.execution.lama_api import fit_predict_lama
import test_embeddings as embedding_fixtures


def job(kind):
    old,frame,test=embedding_fixtures.fixture(kind)
    return LamaRequest(old.task,old.categorical_features,old.classes,old.fitting_rows,
        old.inner_training_rows,old.inner_validation_rows,old.evaluation_rows,
        seconds=60,iterations=12,threads=1),frame,test


class LamaTests(unittest.TestCase):
    def test_partition_validation(self):
        request,_,_=job('regression')
        for changes in ({'evaluation_rows':(1,)},{'inner_validation_rows':(1,)},{'inner_training_rows':(500,)}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(request,**changes).validate(600)

    def test_resource_validation(self):
        request,_,_=job('regression')
        for changes in ({'seconds':float('nan')},{'iterations':401},{'threads':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(request,**changes).validate(600)

    def test_unknown_category_validation(self):
        request,_,_=job('regression')
        with self.assertRaises(ValueError):replace(request,categorical_features=('target',)).validate(600)

    def test_class_order_and_full_refit_export(self):
        request,frame,test=job('classification')
        value=fit_predict_lama(request,frame,test)
        self.assertTrue(value.full_fit_ok);self.assertEqual(value.classes,('b','a'))
        self.assertEqual(value.evaluation_probabilities.shape,(150,2))
        self.assertEqual(value.metadata['refit_rows'],450)
        self.assertEqual(value.metadata['refit_iterations'],value.best_iteration)
        self.assertFalse(value.metadata['random_folds']);self.assertFalse(value.metadata['target_encoding'])
        np.testing.assert_array_equal(value.test_prediction,np.asarray(request.classes)[value.test_probabilities.argmax(axis=1)])
        embedding_fixtures.EmbeddingTests().check_export(request,test,value.test_prediction)

    def test_regression_full_refit_export(self):
        request,frame,test=job('regression')
        value=fit_predict_lama(request,frame,test)
        self.assertTrue(value.full_fit_ok);self.assertIsNone(value.test_probabilities)
        self.assertTrue(np.isfinite(value.test_prediction).all())
        self.assertEqual(value.metadata['refit_rows'],450)
        embedding_fixtures.EmbeddingTests().check_export(request,test,value.test_prediction)

    def test_external_target_perturbation_cannot_change_fit(self):
        request,frame,test=job('regression')
        first=fit_predict_lama(request,frame,test)
        changed=frame.copy();changed.loc[450:,'target']=999999.
        second=fit_predict_lama(request,changed,test)
        np.testing.assert_allclose(first.test_prediction,second.test_prediction,rtol=0,atol=0)


if __name__=='__main__':unittest.main()
