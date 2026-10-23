"""One exclusive bounded offline Git suite; no model, API or worker service."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,re,sys,time,psutil
W=Path(__file__).resolve().parent;O=W/'remote-queue-checks-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def imp(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def need(v,c):
 if not v:raise RuntimeError(c)
def main():
 a=argparse.ArgumentParser();a.add_argument('--self-sha256',required=True);a.add_argument('--tool-sha256',required=True);a.add_argument('--tests-sha256',required=True);a.add_argument('--expected-checks',required=True,type=int);args=a.parse_args()
 need(not O.exists(),'exclusive_fixture_attempt_no_retry');start,mono=time.time(),time.monotonic();unix,end=start+180,mono+180;O.mkdir()
 pins={'run_lean_mvp_r2.py':'43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818','support_component_coordinator.py':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8','alfa-hack-automl/src/automl/infrastructure/processes.py':'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d','alfa-hack-automl/tools/research_lock.py':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45','awake-next-dev/awake_guard.py':'9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b','remote-experiment-queue-next-dev/remote_queue.py':args.tool_sha256,'remote-experiment-queue-next-dev/test_remote_queue.py':args.tests_sha256,Path(__file__).name:args.self_sha256,'kernel-components-next-dev/run_components.py':'3239234d7674b22a822f35f2a7e046b42c838b2b6f9c86e1e854ed7ad43d40a5'}
 refs={'kern0/terminal-root-closure.json':'e648ec50c574309edf9305f43f8ce2e5b0e25daf2f9060c417712d615b7412a7','kern01/terminal-root-closure.json':'ba402fef7aca74715e9e557e911498a054f99f18597b0d7f8b45431d87684782','ls-prep-r2-exec/terminal-root-closure.json':'ede459d1ca3416141b5d1d94a959f826bd17ddb98259ab86379d50973b751b57'}
 for n in ast.parse((W/'kernel-components-next-dev/run_components.py').read_text('utf-8')).body:
  if isinstance(n,ast.Assign):
   names=[t.id for t in n.targets if isinstance(t,ast.Name)]
   if 'HISTORY' in names:refs.update({k:v[0] for k,v in ast.literal_eval(n.value).items()})
   if 'PUBLICATION' in names:refs.update(ast.literal_eval(n.value))
 pins.update(refs);need(all(sha(W/n)==h for n,h in pins.items()),'pinned_source_changed')
 methods=[n.name for c in ast.parse((W/'remote-experiment-queue-next-dev/test_remote_queue.py').read_text('utf-8')).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
 need(len(methods)==len(set(methods))==args.expected_checks,'declared_unique_test_inventory')
 coor=imp('_remote_fixture_coor',W/'run_lean_mvp_r2.py');owner=imp('_remote_fixture_owner',W/'support_component_coordinator.py');proc=imp('_remote_fixture_processes',W/'alfa-hack-automl/src/automl/infrastructure/processes.py');lock=imp('_remote_fixture_lock',W/'alfa-hack-automl/tools/research_lock.py');awake_type=imp('_remote_fixture_power',W/'awake-next-dev/awake_guard.py').PowerRequestGuard
 me=psutil.Process();boot=[];parent=me.parent()
 while parent and any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):
  boot.append(dict(pid=parent.pid,create_time=parent.create_time()));parent=parent.parent()
 state=dict(status='starting',start_unix=start,start_monotonic=mono,absolute_deadline_unix=unix,common_deadline_monotonic=end,common_seconds=180,owned_root=dict(pid=me.pid,create_time=me.create_time()),coordinator_bootstrap_identities=boot,supervisors=[],active_supervisor=None,error_history=[],_manifest={},model_fits=0,API_calls=0,quality_metric=None,immutable_files=pins)
 def persist():coor.save(O/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
 def absent():
  known=set()
  for name in refs:
   r=read(W/name);need(r['cleanup_confirmed'] is True and r['source_unchanged'] is True and not r.get('active_owned_processes') and not r.get('uncertain_owned'),'predecessor_closure_unknown');known.update(coor.identities(r['owned_identities']+r['closure_preparer_identities']))
  ob=owner.StrictOwnedObserver();ob.remember(known);need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],'predecessor_owned_or_preparer_live_or_denied');state['fresh_predecessor_identities']=len(known)
 with awake_type('Alfa remote Git transport offline fixtures',10) as awake:
  def frozen(parent_end=None,code='fixture_parent_cap'):
   coor.cooperative_checkpoint(awake,end,unix,parent_end,code);need(all(sha(W/n)==h for n,h in pins.items()),'frozen_fixture_source_changed')
  state['_pulse']=lambda:coor.cooperative_checkpoint(awake,end,unix)
  with lock.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lease:
   lease.write_identity(state['owned_root']);absent();persist()
   cmd=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s',str(W/'remote-experiment-queue-next-dev'),'-p','test_remote_queue.py','-v']
   record=coor.supervise(cmd,W,O/'suite.json','offline_git_transport',mono,150,120,end,unix,180,state,persist,frozen,owner,proc,boot);coor.child_errors(state,record)
   text=(O/'suite.log').read_text('utf-8',errors='replace');counts=re.findall(r'Ran (\d+) tests?',text)
   passed=record['status']=='ok' and record['exit_code']==0 and counts==[str(args.expected_checks)] and 'skipped=' not in text and re.search(r'\nOK\s*$',text) is not None
   state.update(status=record['status'],passed=passed,checks_observed=int(counts[0]) if len(counts)==1 else None,cleanup_confirmed=record['cleanup_confirmed'],source_unchanged=all(sha(W/n)==h for n,h in pins.items()),elapsed_seconds=time.monotonic()-mono,owned_process_identities=record['owned_process_identities']);frozen();absent();persist()
 state.update(awake_guard=awake.record,finished_unix=time.time(),finished_monotonic=time.monotonic());persist();need(time.time()<unix and time.monotonic()<end,'original_fixture_clock_exhausted')
 print(json.dumps({k:state[k] for k in ['status','passed','checks_observed','cleanup_confirmed','source_unchanged','elapsed_seconds','model_fits','API_calls']}));raise SystemExit(0 if state['passed'] and state['cleanup_confirmed'] and state['source_unchanged'] and not state['error_history'] else 1)
if __name__=='__main__':main()
