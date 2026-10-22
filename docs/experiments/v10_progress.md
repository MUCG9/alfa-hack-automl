# V10 research checkpoint, 22 October 2026

Current branch `work/cpu-research-20261022`, based on V9 `a95c931`.
Official best remains captain-reported V9 raw2187.849 (his21.87/100).
Read this before historical V6–V9 handoffs. New work is authorized offline
research/implementation; no further official upload or main merge.

## Completed experiments

1. Matched three-model classification ensembles, two feature-group holdouts:
   full-data mean Macro F1 .646828432; under70 mean .652199459. Strong single
   component mean .651543688. Under70 loses the second fold to that component;
   about93% of matched-control gain comes from Worms, support19/11.
2. Full three-fold StratifiedGroupKFold confirmation, frozen V9: all six jobs
   successful and every row receives exactly one OOF prediction. Full3 mean
   .638363183 / pooled .638309026; under70 mean .640222558 / pooled .640476085.
   Two folds worsen, so mixed result: no default promotion. Component/error and
   conditional bootstrap diagnostics can reuse predictions without new fitting.
3. As-of1 history fixed-recipe screen: controls RMSE40.960973/33.984412/50.924670
   versus39.051678/32.518745/51.096680. Initial all-three-cuts gate failed.
4. Support-gated asof3, minimum THREE fitting periods: same controls versus
   39.051678/31.846185/50.924670. Both recent cuts improve. Oldest validation AND
   test prediction CSV are byte-identical to control. Six workers successful.
   Full-agent comparison is still required before portfolio promotion.

Results/recipes/protocols live in this directory under v10_balanced*,
v10_history* and v10_agent_history_protocol.md. All metrics reuse public data;
they are not a private-score estimate or a conversion into official points.

## Implementation / immutable snapshots

- History helper a9cedc0, worker/normalization support gate05b2fdb and static
  contract guards0933a66. Only fitting labels, strictly earlier periods, preserved
  time semantics;21history checks. Original context TE remains cross-fitted,
  so adding as-of features does not make the whole recipe causal.
- Error-complementarity tool9591c71: aligned rows/classes/splits/fingerprints,
  conditional corrections, residual correlation, fixed blends and components;
  19tests. No raw predictions are committed.
- Release verifier c094414: owned process timeout/memory cleanup and honest
  partial-log failure receipt;3tests. First resource-contention timeout remains
  in v10_verification_timeout.json, not relabeled successful.
- asof1 SHA8f4ae2d350729a7e318ac0d21e903801424eaa6246963d9dd025161e809a89c8:
  measured original history, failed keep gate.
- asof2 SHA167663dee6fa3cfe62819859ba976976e2a9e6e333b89185dcece2dbe3639ca9:
  historical unmeasured intermediate. Do not use instead of corrected asof3.
- Current asof3 SHA32120f240f0703f0f80de4a020a9be9c3c737070774b217dcb28954bef3acf2a,
  source0933a66;51flat files,72437bytes,Python3.12.3. Defaults still unchanged.

## Active sequential gate and next stage

212unique repository checks PASSED, source_unchanged=true. Exact23unpacked checks
PASSED; automatic queue session95787 completed exit0. State test-runs/v10-followups-queue.json;
logs test-runs/v10-*.queue.log. Do not edit source or start another heavy job until
that queue completes. Check actual JSON before repeating jobs.

Exact gates and paired support evidence saved in release/v10-asof3; checkpoint commit.
Then follow predeclared v10_agent_history_protocol.md: add ONE history minimum3
candidate only where the old numeric-period metadata-history candidate is eligible;
new archive, unchanged default12trials/9900s/budget/confirmation/blend. Repeat exact
V9 default regression and new default regression sequentially, same pinned inputs
and2threads/1.7GiB guard. Keep only if BOTH search and confirmation cuts improve,
refit/export/integrity pass. Class portfolio must retain V9 parity and receive a
bounded full-size packaging lifecycle, not a claimed full quality benchmark.

## Environment / authorization

Use test-runs/venv-core/bin/python: Python3.12.3,numpy1.26.4,pandas2.2.3,
scipy1.12,sklearn1.5.2,LGBM4.6,XGB-cpu2.1.4,CatBoost1.2.8,openai1.68.2.
Organizer requirements SHA9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6
unchanged. All10public input SHA rechecked. Local8GiB RAM and full swap require
strictly sequential heavy fits AND complete fixture checks. No foreign processes
are killed. Thread envs must match benchmark arguments; no new dependencies.

No live Qwen calls in V10; no private API environment available. Historical
protected-input rejection is not bypassed. Local mock HTTP is explicitly mock.
Credentials never belong in repo, prompts, logs or argv. Preserve historical ZIPs.
Commit completed stages frequently. Stop at an actual10–15percent usage-window
reading if exposed; no account counter is exposed here, so never invent one.

## Full-agent experimental stage started

As-of3 sequential queue completed exit0, with212unique and23unpacked checks.
Checkpoint ea9cdc8. CV diagnostics committed c7f8174; no sampling promotion.
Source8f6b73e adds ONE eligible minimum3 history candidate, preserving prior
recipes and relative order, class/text policies and default search budgets.
New snapshot solution-v10-history4.zip (see manifest/README) has216checks expected,
not yet run. Frozen V9 default regression is ACTIVE in test-runs/v10-v9-default-reg,
session21276. After that completes, validate baseline integrity/CSV parity, run
8search-choice checks and frozen class/text portfolio parity, then new exact
archive default regression. Complete source/unpacked/bounded class gates remain.
Do not start another heavy fit while the baseline is running.

## History4 full-agent stage COMPLETE; captain resumed work

Captain restored limits and revoked the8% handoff pause. No new official submit.
Exact full regression control V9:39.321110258/34.229379712,mean36.775244985,
CSV parity. History4:38.902803731/31.991659384,mean35.447231558 (-3.611%).
Both cuts improve: keep gate PASSED. Selected90/10asof3-LGBM/CatBoost blend.
Final refit/export/integrity pass,CSV05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673.
216unique source checks/source_unchanged and23exact-unpacked passed.14historical
portfolio-parity cases and8search-choice checks passed. Full-size class1trial/600s
lifecycle passed; not a new full-default classification quality measurement.
Queue29369 completed exit0; no heavy work remains from it. Portable complete
evidence and technically validated archive are in release/v10-history4.

Next study is predeclared v10_extratrees_protocol.md +v10_extratrees_candidates.json:
strong calibrated LGBM vs fixed50/50 LGBM+existing ExtraTrees, unchanged fitting
rows, no new dependency/runtime change. First paired holdouts42/43; CV seed73 only
if both improve. Do not retune weights/forest size after observing these outcomes.
GitHub push first hit ownership/payload review rejection, then review could not
complete because of account usage limit. User reports limits restored; no action
was executed on either failed attempt. Keep checkpoints local until push succeeds.

Latest Git checkpoint: push SUCCESS exit0, origin/work/cpu-research-20261022 now
f25b4bc. Prior ownership/payload and usage-limit review failures are historical,
resolved after scoped payload audit and restored limits. Receipt:
docs/experiments/v10_push_checkpoint.json. New ExtraTrees paired study is ACTIVE
in test-runs/v10-extratrees-paired, session6727; no runtime source change.
