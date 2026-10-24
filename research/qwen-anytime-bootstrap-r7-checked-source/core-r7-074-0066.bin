"""Prepared synthetic credential-boundary contract; no real credentials/API."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from provider_environment import provider_credentials


class ProviderEnvironmentContracts(unittest.TestCase):
    def test_technical_copy_provider_only_and_exact_function_restored_after_failure(self):
        mapping={key:'1' for key in ('AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
        mapping['PATH']='synthetic-local-path';calls=[]
        def original(directory,model,manifest):
            calls.append((directory,model,manifest));self.assertIs(model,False);return mapping
        coor=SimpleNamespace(environment=original)
        synthetic={'OPENAI_API_KEY':'SYNTHETIC_NOT_A_CREDENTIAL','OPENAI_BASE_URL':'https://changellenge.up.railway.app/v1'}
        with patch.dict(os.environ,synthetic,clear=True):
            with self.assertRaisesRegex(RuntimeError,'synthetic-parent-failure'):
                with provider_credentials(coor):
                    result=coor.environment('synthetic-dir',False,{'requested_model':'synthetic-qwen-model','reasoning_effort':'off'})
                    self.assertEqual(result['OPENAI_API_KEY'],synthetic['OPENAI_API_KEY'])
                    self.assertEqual(result['OPENAI_MODEL'],'synthetic-qwen-model')
                    self.assertEqual(result['AUTOML_THREADS'],'1')
                    self.assertNotIn('OPENAI_API_KEY',mapping);self.assertIsNot(result,mapping)
                    with self.assertRaisesRegex(RuntimeError,'technical_environment'):coor.environment('unused',True,{})
                    raise RuntimeError('synthetic-parent-failure')
            self.assertIs(coor.environment,original)
            result=coor.environment('ordinary-technical',False,{})
            self.assertNotIn('OPENAI_API_KEY',result)
        self.assertEqual(len(calls),2)
        self.assertIs(coor.environment,original)


if __name__=='__main__':unittest.main()
