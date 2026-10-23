"""Private organizer configuration and explicit thinking budgets for dev research."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
MAX_OUTPUT=32768
CALL_TIMEOUT=300
WALL_SECONDS=360


def configure():
    from dotenv import dotenv_values
    private=dotenv_values(ROOT/'.env')
    for key in ['OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL']:
        if not private.get(key):raise ValueError('Authorized private organizer environment missing')
        os.environ[key]=private[key]
    if os.environ['OPENAI_BASE_URL'].rstrip('/')!='https://changellenge.up.railway.app/v1':raise ValueError('Unexpected organizer endpoint')
    effort=private.get('AUTOML_REASONING_EFFORT','xhigh').strip().lower()
    if effort!='xhigh':raise ValueError('Current research protocol requires explicit xhigh')
    os.environ['AUTOML_REASONING_EFFORT']=effort
    return {'reasoning_effort_requested':effort,'maximum_output_tokens_combined':MAX_OUTPUT,
            'call_timeout_seconds':CALL_TIMEOUT,'wall_budget_seconds':WALL_SECONDS,
            'automatic_effort_downgrade':False,'server_effective_effort_echoed':None}
