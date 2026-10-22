# Experimental semantic input-role mapping

Branch: `work/semantic-inputs-20261022`, based on the frozen v6 checkpoint.
The already checked v6 ZIP is immutable and its full public run is independent of
this source work. This stage is not a claim of live Qwen/API success.

## Why

Canonical names and aliases cannot cover every possible input filename. Before
this stage, arbitrary `alpha/beta/gamma.csv` files could fail before the agent's
first meaningful Qwen call. Add one bounded semantic decision at this boundary,
not arbitrary generated loading code.

## Implemented

- The CLI first uses exact paths/names and deterministic aliases. Only when these
  fail, and the CLI is not offline, ask the existing authorized gateway to map
  file roles from the task text and actual local table schemas.
- Library `discover`/`load_inputs` default to network-free operation. Canonical
  inputs do not trigger a decorative API request even in online mode.
- Present 3..32 local CSV/TSV tables, at most 100 columns per table, at most 16
  rows for dtype probing, and bounded task text. Never send raw row values.
- Accept only three required distinct paths plus an optional dictionary, all
  exact members of the validated task-local catalog. Reject URLs, outside paths,
  unknown response fields and duplicate roles. No model-generated code is run.
- Security/path-escape rejection is terminal, never sent to an LLM for a workaround.
- At most two semantic mapping attempts; each uses the existing gateway's 45-second
  total deadline and 2,048-token completion cap. One bounded validation-feedback
  retry is allowed. A gateway failure stops this stage instead of retrying forever.
- Save one audit trace with schemas, choices, validation outcomes and honest usage
  status. A resolved input cache is reused for multi-target dispatch, avoiding a
  second file-role request. Per-target reports may reference the SAME trace; do
  not double-count its tokens across children.
- Existing dictionary/schema/target/output validation still runs after selection.
  The model cannot override a target, metric, grouping constraint or path boundary.

## Tests and limitations

Eight targeted tests use a **mock gateway**, including privacy of raw rows, no-call
offline/canonical behavior, malicious/duplicate mappings, bounded feedback, path
escape rejection, multi-target cache reuse, and one real model refit/export after
a mocked role decision. Initial tests caught a missing audit-directory creation;
that was fixed and the targeted tests rerun. These are NOT live HTTP/API evidence.

The current developer environment still rejects protected interactive credential
entry. No key is stored in this branch, and no real development Qwen mapping was
tested. The platform's supplied environment is a separate execution path.

Only file roles are interpreted by this stage. Arbitrary file formats, unsupported
metric formulas, semantic target/positive-label aliases, multiple query/group
ambiguities and full natural-language task contracts remain future work.
The metadata bounds and UTF-8 CSV/TSV support are explicit limitations.

The benchmark wrapper's read-only preflight stays deterministic; unknown-name
online tasks should be exercised through the CLI on a writable private task copy.
Full repository gate: **145 unique checks passed**, source unchanged, 156.158
seconds (`test-runs/continuation-20261022/v7-checks/results.json`). The eight
semantic tests are included in 145, not additional checks. The exact-unpacked
gate subsequently passed23 repeated checks, and a source-hash audit matches the
frozen ZIP to all145 checks. Full public regression passes with byte-identical
V6 CSV; classification remains pending at the85%-usage handoff. See
`release/v7-semantic1`. Do not promote an unfinished full gate as passed.
