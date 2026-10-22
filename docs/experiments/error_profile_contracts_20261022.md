# ERR-01 checkpoint: service boundary and contracts only

22 October 2026. Branch `work/error-profile-contracts-20261022`, based on
`work/llm-upgrade-20261022` at `300c6db`. Captain explicitly authorized implementing
and testing steps 1–2 of the agreed error-passport plan. This supersedes the old
documentation-only instruction for this scope, not for further experiments.

## Completed

1. Error Analysis ownership and public-API boundary; architecture tests cover the
   new domain and all shared contract modules. First checkpoint commit `d3559e9`.
2. Strict JSON request/profile contracts, frozen metadata, existing TaskSpec /
   DatasetRef / PredictionBundle reuse, explicit scope and model/fold provenance,
   optional group/time/probability references, bounded resource declarations,
   diagnostic-only profiles, explicit section status and evidence references.
   The public `ErrorAnalyzer` Protocol declares the backend interface; there is
   no concrete analyzer or fake successful result.

[Boundary and contract design](../architecture/error_analysis.md).

## Verification

- 20 new contract checks PASS; registered in `tools/run_checks.py`.
- 7 architecture checks PASS. These are 27 focused checks, not a rerun of the
  historical 258-check suite or 23 unpacked release checks.
- New flat modules serialize/deserialize a complete profile in an isolated
  process that rejects numpy/pandas/sklearn/learner/API-client imports.
- All 54 previously compiled files, including original requirements, match the
  pre-change build byte for byte under local Python 3.12.3. Only
  `automl_contracts_error_analysis.py` and `automl_error_analysis_api.py` are added.
- Source remained unchanged during the final focused gate. No archive written,
  model fit, ML benchmark, live call, new dependency or official upload.

An initial test run had 19/20 passes: a test helper prepended a directory to
empty/blank paths, inadvertently making them valid. The failing assertion was
analyzed and corrected to supply raw invalid paths. Contract validation was not
weakened. The final tests include nonfinite/oversized numeric values, strict JSON
fields/versions, provenance tampering, contradictory statuses, missing evidence
and absence of artifact I/O.

[Machine-readable focused receipt](error_profile_contracts_verification_20261022.json).
Local detailed logs remain ignored in `test-runs/error-profile-contracts-20261022`.

## Next checkpoint, not implemented

Step 3: a concrete read-only artifact adapter and alignment verifier. Verify actual
bytes, rows/classes, split membership and recorded metrics before emitting any
completed alignment section. The present contract only checks declared metadata;
it neither accesses paths nor establishes sandboxing or statistical correctness.

Detailed statistics, aggregate section schemas/writers, uncertainty and use by
Search/LLM are later steps requiring their own authorization and tests. Existing
V11/V16 quality evidence and historical archives remain unchanged; this checkpoint
is not a promoted release or a claim of metric improvement.
