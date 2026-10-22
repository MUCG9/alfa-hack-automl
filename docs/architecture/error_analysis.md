# Error Analysis: boundary and message contract

Scope authorized on 22 October 2026: steps 1–2 of the error-passport plan,
component responsibility and versioned request/profile contracts. Artifact
reading/verification, statistics, report writing and search integration are later
steps. No training or changed model-selection policy is part of this stage.

## Ownership

Error Analysis accepts references to frozen artifacts and returns a diagnostic
profile. Execution owns training and predictions; Evaluation owns metric
definitions and split semantics; Search owns experiment/model selection;
Publishing owns submission export. Error Analysis owns only its output directory.
It cannot train, tune weights/thresholds, change splits or publish predictions.

Consumers import only `automl.error_analysis.api`. Shared messages live under
`automl.contracts` and have no pandas, numpy, learner or API-client dependencies.
The public interface will be a synchronous `analyze(request) -> ErrorProfile`
operation, transportable across a process boundary using JSON. Its interface is
declared separately from a concrete implementation: no successful empty profile
or fake analysis is returned while the backend is absent.

Initial deployment is a local component, optionally a subprocess. Independently
deployed HTTP services are not implemented. Message semantics do not depend on
the future transport. No network stack or new dependency is required.

## Request

An analysis request identifies its task, original fitting dataset, control model,
protocol artifact, prediction scope, model/fold artifacts, optional groups/time,
output directory and analysis resource budget. Model references reuse the existing
`PredictionBundle`; dataset references reuse `DatasetRef`. New references add
content SHA256 and recipe/source/row-order provenance without changing either
legacy contract. A split file's content hash and the logical split SHA in a
prediction bundle are distinct identifiers and must not be conflated.

Scope distinguishes inner, search, confirmation, OOF and forward diagnostics.
Model/fold identifiers are unique within a request. Optional probability artifacts
declare whether values are raw or decision-adjusted; F1 decision adjustment is
not evidence of probability calibration. References contain no prediction arrays,
labels, credentials or data-frame objects. Paths are declarative: this contract
does not resolve them, access files or establish a filesystem sandbox.

## Profile

The profile retains the full request and its canonical digest. Five named
sections describe alignment, individual models, comparisons, slices and
uncertainty. Each section is complete, unavailable or failed. Complete sections
reference aggregate artifacts by path and content hash; other sections explain
their status and cannot carry an apparently successful result. Detailed statistic
schemas will be introduced with their implementations, rather than guessed here.

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

## Later implementation

1. Validate artifact bytes, prediction rows/classes, split membership and recorded
   metrics; distinguish exactly-once OOF from overlapping holdouts/backtests.
2. Add per-model statistics, paired diagnostics, predefined slices and uncertainty.
   Reuse Evaluation through its API and migrate existing analysis tools gradually.
3. Write aggregate JSON/Markdown under the assigned output directory, preserving
   frozen inputs. Send only aggregate evidence to a future planner.
4. Evaluate any policy using these diagnostics as a separate experiment. Outer
   labels must not become fitting, tuning or routing data. Unchanged training
   behavior remains the control.

Each stage gets focused tests and a commit. Historical archives remain immutable;
this stage does not promote a release or rerun public benchmarks.
