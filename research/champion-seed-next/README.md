# Champion seed: source-only next policy

This is an isolated, default-OFF proposal. Current T6, canonical source, frozen
inputs and manifests remain unchanged. No new clock, test, model fit, API call,
runtime import, archive build or publication has happened.

The factor is seeded initial policy at fixed max9. The exact complete V16
control, its original SINGLE/HPO anchor, separate broad+CatBoost32 branch and
three model families stay ahead of optional proposals. A distinct prior champion
is inserted at initial slot5; at most one initial Qwen plan then fits slot6.
HPO/followup have two remaining search slots. This optional-Qwen tradeoff and
changed feedback are part of the factor, not a free addition or a causal
hyperparameter experiment. Actual stages must still be proved after execution.

Only two existing module copies are changed. Apply changes.patch to a NEW copy
of the pinned m3dev source, not the active campaign. The existing flat builder keeps its explicit runner mapping and derives the
stages mapping from the unchanged source path; no new mapping entry, runtime
module or dependency is introduced. tests/test_champion_seed.py
contains12 UNEXECUTED pure-contract methods and has not been registered or run.
The AST default-OFF projection is static evidence, not measured output parity.

Generic interface, only in explicit preserved four-stage mode:

    --champion-recipe champion_recipe_input.json

The generic runtime never reads champion-t5-lineage.json or proposal.json as
instructions. V1 accepts <=32768-byte non-linked UTF-8 JSON containing one
selector-free tree recipe, with empty feature_code and noop data policy. It uses
existing trusted normalizer/signature/spec validators. No control/path/budget
keys or file imports are accepted. Invalid champions fail the opted-in experiment
before the first model fit rather than silently dropping the candidate; metrics
remain absent/null, never zero. Existing fallback/output semantics stay unchanged
when the option is absent.

champion-t5-regression.json is the separate local benchmark input. It pins T5's
actual selected recipe (signature959a9b8f...), with exact source/report/input/split
lineage in champion-t5-lineage.json. It is not a new general default or proof of
blind generalization. Keep both prior T5 and complete V16 artifacts.

proposal.json specifies the future matched A/B, slot/dedup rules, resource
proposal, source/ownership/technical prerequisites and promotion limits. Root
must first close actual T6, then review/commit source and freeze actual new
archives/manifest/gates/clock. Source-only preparation does not authorize launch.
