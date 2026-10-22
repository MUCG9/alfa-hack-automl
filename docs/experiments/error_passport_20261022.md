# ERR-01 / BASE-01 implementation checkpoint

Latest continuation: [restored-cache checkpoint](base01_restored_20261022.md).
100 focused checks PASS; four actual search passports and four final CSVs verified.
BASE-01 remains incomplete: the transfer omitted all four confirmation_split.npz.
The 95-check receipt below is the preserved earlier implementation gate.

22 October 2026. Working branch `work/error-profile-contracts-20261022`, based on
`300c6db`; scope expanded by the captain from contract steps 1–2 to the complete
passport implementation and BASE-01 preparation. No model training, optimizer,
new representation, decision policy, release promotion or submission authorized.

## Implemented

- `automl.error_analysis.api`: lazy local analyzer, interface, bounded summary and
  explicit full-run cache preparation. Neighbor domains are accessed through APIs.
- Verified original dataset/protocol/prediction/result/split bytes, rows/classes,
  held-out labels and primary metrics. Forward chronology and declared exactly-once
  OOF are checked. Artifact and analyzer-source mutation invalidates the profile.
- Regression residual distribution/bias/variance/tail concentration and paired
  Pearson/Spearman/covariance; classification class/confusion/confidence/support
  diagnostics, shared errors, corrections, Q and probability correlation.
- Fixed half blends, declared fixed ensembles and component removal diagnostics.
  No fitted weights, thresholds, learned routing or selection instructions.
- Missingness, fitting-derived numeric bins and category/context support slices,
  period diagnostics and fitting-only temporal context coverage proxies.
- Conditional paired cluster bootstrap for Macro F1 and RMSE/MSE/MAE. Forward
  uncertainty uses period blocks; too few blocks/groups yields explicit
  unavailable uncertainty. No private/refit uncertainty or multiplicity claims.
- Versioned aggregate sections, JSON/Markdown passport and at most 8 KiB planner
  summary. Fresh output directories only. Guarded credential-stripped CLI child.
- BASE inventory of portable V11/V16 reports/archives, original input hashes,
  selected recipes/iteration parity and local package versions. An explicit cache
  root is required; original absolute paths inside JSON are never rewritten.

Schema 2.0 explicitly replaces the initial strict diagnostic 1.0 wire format:
recorded-result references are needed to verify metrics/recipes, and silently
adding serialized fields would invalidate old request digests. Legacy shared
TaskSpec/DatasetRef/PredictionBundle stay at 1.0. Old messages fail clearly.

## Tests and limits

[Focused verification receipt](error_passport_verification_20261022.json):
20 contract +38 backend +11 preparation/supervisor +7 architecture +19 existing
diversity checks = **95 PASS**, sequential, one thread, owned watchdog/RSS guards.
The backend also runs from flat compiled modules without checkout imports.
All 54 previously compiled baseline files remain byte-identical under local
Python 3.12.3. Only diagnostic modules are added. Original requirements preserved.

This is not a new full 258-source/23-unpacked release gate. No historical ZIP is
changed and no new release ZIP is created. Source stayed unchanged during the
focused gate. No ML fit was needed for synthetic fixtures or the independent
portable baseline audit.

During development a test expected ValueError where the existing-output guard
correctly raised FileExistsError, and a generic fixture used predictions.csv
instead of the pipeline's validation_predictions.csv. Both fixtures were corrected
without weakening production checks. Versioning was corrected explicitly as above.

Library memory/time guards are cooperative; the CLI monitors the owned process
tree. It returns nonzero after a supervisor kill, and unfinished files are not a
successful profile. The component is not a security sandbox. Correlations, slices
and bootstrap intervals are exploratory diagnostics, not causal explanations.

## Reproduction

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  test-runs/venv-core/bin/python tools/prepare_error_baseline.py \
  --output test-runs/base01-new \
  --cache-root test-runs/llm-upgrade-20261022

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  test-runs/venv-core/bin/python tools/error_passport.py \
  --request test-runs/base01-new/v11-featureviews1-classification-search/request.json
```

Each invocation needs a NEW output directory. Without `--cache-root`, the audit
verifies portable evidence and marks raw caches blocked; it never substitutes V10
or starts training. The environment inventory records missing optional packages
and the Python 3.12.3 versus recorded 3.12.14 difference rather than claiming exact
model-replay equivalence. The diagnostics use the existing pinned CPU environment.

## Actual BASE-01 evidence

The independent run in `test-runs/error-passport-20261022/base01-independent`
verified all 10 public input SHAs, every member of both frozen V11/V16 archives,
portable assessment parity and all 12 classification recipes/metrics/iterations.
It did not certify unavailable final CSV bytes. No V10 evidence was relabelled.

Captain subsequently supplied transfer commit `7276ec6` on
`work/llm-upgrade-20261022`: `transfer/v11-v16-caches`, manifest plus five ZIP parts,
848 original files, now restored and verified by tools/transfer_caches.py.
Raw artifacts remain outside the diagnostic aggregate reports. The linked latest
checkpoint records actual search diagnostics and missing confirmation splits.
The independent receipt and historical evidence were preserved.

## Remaining work beyond this scope

Changing Search based on the passport is SEL-01, a separate measured experiment.
Optuna/FLAML, embeddings, LightAutoML and self-created LLM assistants remain the
discussed future queue. No improvement to current RMSE/F1 is claimed by this
engineering stage.
