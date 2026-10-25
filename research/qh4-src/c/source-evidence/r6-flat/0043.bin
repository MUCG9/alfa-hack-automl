"""Provider-only scoped facade over the unchanged technical environment."""
from contextlib import contextmanager
import os


@contextmanager
def provider_credentials(coordinator):
    original=coordinator.environment
    def environment(directory,model,manifest):
        if model is not False:
            raise RuntimeError('provider_facade_requires_technical_environment')
        # Copy, never mutate the original returned mapping or process environment.
        result=dict(original(directory,False,manifest))
        if (not os.environ.get('OPENAI_API_KEY') or
                os.environ.get('OPENAI_BASE_URL','').rstrip('/')!='https://changellenge.up.railway.app/v1'):
            raise RuntimeError('authorized_existing_provider_environment_missing')
        result.update(OPENAI_API_KEY=os.environ['OPENAI_API_KEY'],OPENAI_BASE_URL=os.environ['OPENAI_BASE_URL'],
            OPENAI_MODEL=manifest.get('requested_model','qwen/qwen3.8-27b'),
            AUTOML_REASONING_EFFORT=manifest.get('reasoning_effort','off'))
        for key in ('AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            if result.get(key)!='1':raise RuntimeError('provider_technical_thread_caps_changed')
        return result
    coordinator.environment=environment
    try:yield
    finally:coordinator.environment=original
