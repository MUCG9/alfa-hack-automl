# LONG-01 research build — opt-in, NOT submitted

Purpose: test the captain's3h/task budget hypothesis against submitted V11.
New models/features/dependencies are NOT added. Existing enabled ML policy
matches V11; legacy default12trial path is unchanged.

IMPORTANT: platform CLI defaults have NOT been promoted. This archive enables
long search only with --search-until-deadline --time-budget10800
--finalization-reserve1200 (with spaces between flags and numbers).
Do not submit it expecting3h default behaviour. Promotion requires actual results
and a separate verified build; no official upload is authorized.

First train the unchanged baseline; preserve its fully trained CSV. Continue
untried existing recipe variations until1200s remain. New confirmed candidates
must improve mean without worsening either baseline cut. Reserve final phase
for full refit/export, or retain the trained fallback on failure/no improvement.
Best observed and actually exported metrics are reported separately.

Complete unchanged-source gate PASS: 287 unique checks, including25 clock/rollback
and4 REAL source/flat classification/regression short lifecycle checks.
Exact-unpacked gate PASS: 23 repeated checks; archive matches frozen source.
Receipts: source-tests.json and unpacked-tests.json. No full public quality result
yet at this checkpoint; short fixtures are not a quality comparison.

See docs/experiments/LONG-01_protocol.md. Reused public adaptive search is NOT
private/official performance. Input hashes and requirements remain unchanged.
