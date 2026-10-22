# Error Analysis: boundary and message contract

Scope authorized on 22 October 2026: complete the error-passport implementation
and prepare BASE-01. The component verifies artifacts, computes descriptive and
paired statistics, slices and conditional uncertainty, and writes aggregate
reports. It does not train or change model selection. Steps 1–2 are preserved as
the historical error_profile_contracts_20261022.md checkpoint.

## Ownership

Error Analysis accepts references to frozen artifacts and returns a diagnostic
profile. Execution owns training and predictions; Evaluation owns metric
definitions and split semantics; Search owns experiment/model selection;
Publishing owns submission export. Error Analysis owns only its output directory.
It cannot train, tune weights/thresholds, change splits or publish predictions.

Consumers import only `automl.error_analysis.api`. Shared messages live under
`automl.contracts` and have no pandas, numpy, learner or API-client dependencies.
The public synchronous interface is `analyze(request) -> ErrorProfile`, with a
concrete local backend and guarded subprocess CLI. `summarize(profile)` supplies
up to 8 KiB of scalar evidence for a future coordinator. No automatic planner
integration or use of outer labels for selection is enabled.

Initial deployment is a local component, optionally a subprocess. Independently
deployed HTTP services are not implemented. Message semantics do not depend on
the future transport. No network stack or new dependency is required.

## Request

An analysis request identifies its task, original fitting dataset, control model,
protocol artifact, prediction scope, model/fold artifacts, optional groups/time,
output directory and analysis resource budget. Model references reuse the existing
`PredictionBundle`; dataset references reuse `DatasetRef`. New references add
content SHA256 and recipe/source/row-order provenance without changing either
legacy contract. Schema 2.0 adds the recorded-result reference needed to verify
recipe and metric. Version 1.0 is rejected explicitly: adding a field to a strict
JSON format changes its wire compatibility and canonical request digests. Legacy
TaskSpec/DatasetRef/PredictionBundle stay at 1.0. A split file's content hash and the logical split SHA in a
prediction bundle are distinct identifiers and must not be conflated.

Scope distinguishes inner, search, confirmation, OOF and forward diagnostics.
Model/fold identifiers are unique within a request. Optional probability artifacts
declare whether values are raw or decision-adjusted; F1 decision adjustment is
not evidence of probability calibration. References contain no prediction arrays,
labels, credentials or data-frame objects. Paths are declarative: this contract
does not resolve them, access files or establish a filesystem sandbox.

## Profile

The profile retains the full request, its canonical digest and the analyzer's
source SHA256. Five named
sections describe alignment, individual models, comparisons, slices and
uncertainty. Each section is complete, unavailable or failed. Complete sections
reference aggregate artifacts by path and content hash. Aggregates embed section
name, schema version and request digest; other sections explain their status and
cannot carry an apparently successful result.

Overall status is derived from section states: complete only when all sections
are complete, partial when alignment is complete but a later section is
unavailable/failed, and failed when alignment fails. An unavailable alignment
allows only an entirely unavailable profile. Downstream completed results cannot
coexist with failed/unavailable alignment. This is metadata consistency, not
verification that alignment was actually performed.

Findings cite completed sections. Profiles are always diagnostic-only; they are
not selection instructions, validation certificates or private-score estimates.
The initial contract requires an explicit limitations list. Unknown fields and
schema versions are rejected at JSON boundaries. Defaults are not silently
applied to incompatible versions. Source/input hashes describe provenance; their
presence does not prove that artifact bytes have been verified.

## Implemented analysis

1. Verified-byte reads and bounded NPZ expansion; rows/classes/splits, original
   targets and recorded recipes/metrics checked. Full-fit/test predictions cannot
   be declared diagnostics. Forward fitting periods strictly precede validation.
   OOF requires complete exactly-once coverage. Inputs and analyzer source are
   hashed again before the manifest is published.
2. Regression bias, variance, residual quantiles, error tails and paired
   covariance/Pearson/Spearman. Classification confusion/precision/recall/F1,
   fitting-group support, confidence bins, joint errors, Q and classwise changes.
   Decision-adjusted scores do not establish probability calibration.
3. Fixed pairwise half blends, protocol-declared ensembles and leave-one-member-out
   diagnostics with renormalized fixed remaining weights; no optimization/refit.
4. Fitting-derived numeric bins, missingness, categorical/context support,
   chronological context-coverage proxies and period slices. Small independent
   support is flagged. Slice sets can overlap.
5. Seeded paired cluster bootstrap for Macro F1 and RMSE/MSE/MAE. Forward requests
   resample period blocks, never rows in place of too few periods. Missing support
   yields unavailable uncertainty. Intervals condition on fixed predictions and
   do not cover refit/private uncertainty or multiple-comparison corrections.
6. Immutable JSON sections, error_profile.json, error_profile.md and a bounded
   planner_summary.json. Existing output directories are refused. Failed integrity
   invalidates completed references; insufficient optional evidence produces an
   explicit partial profile. A CLI watchdog failure returns nonzero; unfinished
   files are not a successful passport.

`tools/error_passport.py --request PATH` runs an owned, credential-stripped child
with wall-clock/process-tree RSS guards. Library limits are cooperative, not a
security sandbox. The budget includes imports and is separate from training.

`tools/prepare_error_baseline.py --output DIRECTORY [--cache-root DIRECTORY]`
audits frozen V11/V16 reports/archives, local input hashes and environment. Only
an explicit cache root is relocated; no V10 fallback/refit is allowed. Original
JSON files are preserved. Run provenance and saved model results must match;
requests retain the selected ensemble and available two-view components.
An explicit `--root-mapping-file` preserves original absolute paths across hosts.
With `--analyze`, the CLI runs available passports sequentially; missing split
artifacts are recorded per scope, never reconstructed or replaced. Exit2 means
baseline incomplete even when all available passports succeeded.
`finalize_baseline` closes the baseline only after all four original runs have
search and confirmation passports with complete required sections, verified
artifact/section bytes, reproduced selected scores and matching actual final CSVs.
Unavailable temporal uncertainty is allowed explicitly; failed sections are not.
It writes a separate immutable receipt, preserving the initial inventory.

Old diversity/OOF tools and their outputs remain unchanged. Policy changes based
on diagnostics require separate experiments: outer labels must not become fitting,
tuning or routing data. Network deployment and learned routing remain out of scope.

Each stage gets focused tests and a commit. Historical archives remain immutable;
this stage does not promote a release or rerun public benchmarks.
