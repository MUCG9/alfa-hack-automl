"""Offline application-role contracts; no live provider or new ML fits."""
from dataclasses import replace
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.assistants import AssistantRequest,MetricEvidence
from automl.infrastructure.run_budget import RunBudget
from automl.infrastructure import llm_gateway as gateway
from automl.search import assistants
from automl.search.api import request_advice

ENV={'OPENAI_API_KEY':'fixture-only-not-a-real-credential','OPENAI_BASE_URL':'https://fixture.invalid/v1'}


def fixture():
    base={'engine':'lightgbm','params':{'num_leaves':63,'reg_lambda':8}}
    alternatives=[dict(base,params=dict(base['params'],**change)) for change in ({'num_leaves':127},{'reg_lambda':15})]
    return AssistantRequest('classification','macro_f1',(MetricEvidence('Backdoor/f1',.21),),
        json.dumps(base),tuple(json.dumps(r) for r in alternatives))


class AssistantTests(unittest.TestCase):
    def run_mock(self,request=None,responses=None,calls=3,seconds=100):
        request=request or fixture();seen=[]
        def transport(system,context,cap,timeout):
            seen.append((context,cap,timeout))
            ids=[r['id'] for r in context['catalog']]
            default={'analyst':{'issue':'rare_classes','evidence_refs':['Backdoor/f1']},
                'researcher':{'ids':ids},'critic':{'accepted_ids':ids[:1]}}
            value=(responses or {}).get(context['role'],default[context['role']])
            return value if isinstance(value,str) else json.dumps(value),{'status':'ok','attempts':1,'usage_complete':True,'usage':{'prompt_tokens':5,'completion_tokens':2}}
        with tempfile.TemporaryDirectory() as tmp,RunBudget(seconds,calls,tmp) as budget,patch.dict(os.environ,ENV,clear=True),patch.object(gateway,'_request_json',side_effect=transport):
            result=request_advice(request,enabled=True)
            saved=budget.snapshot()
        return result,saved,seen

    def test_default_off_has_no_gateway_calls(self):
        with patch.object(assistants,'request_json',side_effect=AssertionError('No calls')):
            self.assertEqual(assistants.propose(None).status,'disabled')

    def test_missing_shared_budget_does_not_allocate_one(self):
        with patch.object(assistants,'request_json',side_effect=AssertionError('No calls')):
            self.assertEqual(assistants.propose(fixture(),enabled=True).status,'blocked_shared_budget')

    def test_three_roles_share_ledger_and_bounded_caps(self):
        result,budget,seen=self.run_mock()
        self.assertEqual(result.status,'ok');self.assertEqual(result.roles_completed,3)
        self.assertEqual(len(result.selected_ids),1);self.assertEqual(len(result.recipe_json),1)
        self.assertEqual([s[1] for s in seen],[512,1024,512])
        self.assertTrue(all(s[2]<=30 for s in seen))
        self.assertEqual(budget['gateway_calls_started'],3);self.assertEqual(budget['prompt_tokens_reported'],15)
        self.assertTrue(budget['usage_complete']);self.assertNotIn('fixture-only',json.dumps(budget))
        self.assertEqual([e['purpose'] for e in budget['events']],['assistant_analyst','assistant_researcher','assistant_critic'])

    def test_global_call_cap_discards_partial_proposals(self):
        result,budget,seen=self.run_mock(calls=1)
        self.assertEqual(result.status,'run_call_limit');self.assertEqual(result.selected_ids,())
        self.assertEqual(len(seen),1);self.assertEqual(budget['gateway_calls_started'],1)

    def test_shared_planner_call_is_not_reset_by_helpers(self):
        with tempfile.TemporaryDirectory() as tmp,RunBudget(100,1,tmp) as budget,patch.dict(os.environ,ENV,clear=True),patch.object(gateway,'_request_json',return_value=('{}',{'status':'ok','attempts':1,'usage_complete':True})) as network:
            gateway.request_json('existing planner',{},purpose='planner')
            result=assistants.propose(fixture(),enabled=True)
            self.assertEqual(result.status,'run_call_limit');self.assertEqual(network.call_count,1)
            self.assertEqual(budget.calls_started,1)

    def test_expired_shared_deadline_prevents_transport(self):
        result,budget,seen=self.run_mock(seconds=4)
        self.assertEqual(result.status,'run_deadline_exhausted');self.assertEqual(seen,[])
        self.assertEqual(budget['gateway_calls_started'],0)

    def test_unconfigured_live_provider_is_not_mocked_as_success(self):
        with tempfile.TemporaryDirectory() as tmp,RunBudget(100,3,tmp) as budget,patch.dict(os.environ,{},clear=True):
            value=assistants.propose(fixture(),enabled=True)
            self.assertEqual(value.status,'unconfigured');self.assertEqual(budget.calls_started,0)

    def test_non_json_and_duplicate_keys_fail_closed(self):
        for value in ('```json {} ```','{"issue":"drift","issue":"rare_classes","evidence_refs":[]}'):
            with self.subTest(value=value):
                result,_,seen=self.run_mock(responses={'analyst':value})
                self.assertEqual(result.status,'invalid_response');self.assertEqual(len(seen),1)

    def test_untrusted_response_cannot_add_code_or_tools(self):
        value={'issue':'rare_classes','evidence_refs':['Backdoor/f1'],'code':'open(secret)'}
        result,_,seen=self.run_mock(responses={'analyst':value})
        self.assertEqual(result.status,'invalid_response');self.assertEqual(len(seen),1)

    def test_unknown_evidence_is_rejected(self):
        result,_,_=self.run_mock(responses={'analyst':{'issue':'rare_classes','evidence_refs':['invented']}})
        self.assertEqual(result.status,'invalid_response')

    def test_researcher_cannot_invent_new_recipe(self):
        result,_,seen=self.run_mock(responses={'researcher':{'ids':['invented']}})
        self.assertEqual(result.status,'invalid_response');self.assertEqual(len(seen),2)

    def test_critic_must_choose_subset_of_nominations(self):
        request=fixture();ids=list(assistants._catalog(request)[0])
        result,_,_=self.run_mock(request,responses={'researcher':{'ids':ids[:1]},'critic':{'accepted_ids':ids[1:]}})
        self.assertEqual(result.status,'invalid_response');self.assertEqual(result.selected_ids,())

    def test_multifactor_and_unsafe_catalogs_never_call_gateway(self):
        request=fixture()
        variants=[{'engine':'lightgbm','params':{'num_leaves':127,'reg_lambda':15}},
            {'engine':'lightgbm','params':{'num_leaves':999,'reg_lambda':8}},
            {'engine':'lightgbm','params':{'num_leaves':127,'reg_lambda':8,'change_split':True}},
            {'engine':'lightgbm','params':{'num_leaves':127,'reg_lambda':8},'feature_code':'def transform(df): return df'}]
        for candidate in variants:
            with self.subTest(candidate=candidate):
                result,_,seen=self.run_mock(replace(request,catalog_json=(json.dumps(candidate),)))
                self.assertEqual(result.status,'invalid_catalog');self.assertEqual(seen,[])

    def test_typed_input_rejects_rows_prose_and_nonfinite_evidence(self):
        for reference,value in [('raw row text',1),('score',float('nan')),('score',True)]:
            with self.subTest(reference=reference,value=value),self.assertRaises(ValueError):MetricEvidence(reference,value)
        with self.assertRaises(ValueError):replace(fixture(),evidence=({'raw_rows':[]},))
        with self.assertRaises(ValueError):replace(fixture(),catalog_json=tuple('x' for _ in range(9)))

    def test_rejection_does_not_invoke_unnecessary_critic(self):
        result,budget,seen=self.run_mock(responses={'researcher':{'ids':[]}})
        self.assertEqual(result.status,'rejected');self.assertEqual(len(seen),2)
        self.assertEqual(budget['gateway_calls_started'],2)

    def test_returned_catalog_is_immutable_json_and_not_executable(self):
        request=fixture();before=(request.incumbent_json,request.catalog_json)
        result,_,seen=self.run_mock(request)
        self.assertEqual(before,(request.incumbent_json,request.catalog_json))
        self.assertEqual(set(seen[0][0]),{'objective','aggregate_evidence','catalog','role','instruction'})
        recipe=json.loads(result.recipe_json[0]);self.assertEqual(recipe['feature_code'],'')
        self.assertEqual(recipe['params']['num_leaves'],127)


if __name__=='__main__':unittest.main()
