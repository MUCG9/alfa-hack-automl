# SEL-01 — fixed-third marginal selection, predeclared diagnostic screen

Declared before reading the new replay result. Control: unchanged V11 portfolio,
first two search-ranked slots, and third-family heuristic. This is NOT V14's
13th-trial/pool/trajectory proposal. Existing12 recipes/order remain unchanged.

One changed factor: third slot. Preserve first2 IDs exactly. Among remaining
existing candidates choose the one maximizing directional metric gain when its
predictions receive1/3 weight and the two fixed leaders each receive1/3; reference
pair is50/50. Use native metric/direction, no correlation proxy, learned weights,
new class weighting, transforms or recipes. Equal ties retain frozen order.
If every gain is negative still select the least damaging third: slot count and
subsequent existing blend-grid must not silently change. No per-dataset tuning.

Stage1 is diagnostic cached replay of the existing V11 trace. Verify all source,
input, row/split/class/probability/recipe/metric fingerprints with ERR-01 loader.
Separate search and confirmation; use search only to choose the third. A missing
confirmation is `needs_fit`, never reconstructed from a different cut/recipe.
If all selected IDs match the original shortlist, the replay is an identity and
no new ML-quality improvement can be claimed. Preserve this result.

The pure selector is NOT wired into runtime. It owns neither splits nor fitting;
scope labels do not certify isolation. Public search has already been reused:
it is NOT independent/outer performance, even if both cached cuts improve.
If a nonidentity cached screen is promising, before new fits define an external
group/forward comparison of the ENTIRE procedure. Every new third-slot decision
must use fitting-internal evidence, not external confirmation labels. Preserve
the original fixed blending grid after shortlist selection. Equal overall
budget, measured costs, and confirmation/refit reserve; no overlapping ML jobs.
Promotion needs improvement on both predeclared external cuts, sound support,
then CV/full-agent/refit/export/integrity/release gates. A positive cached score
alone is not enough. Failed/mixed screens stay disabled; no gate changes posthoc.
