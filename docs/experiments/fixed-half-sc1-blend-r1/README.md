Prepared fixed-alpha complementarity screen. No mixture or new score computed.

Freeze: protocol.json SHA256
c3c879fd9a5fb0a6cd55cc38ff84555a6347943c61c727fd02fdabad0df3d227.
Root must commit this card/protocol before any blend scoring. This is separate
from true four-stage MVP and the selector-cache prototype; neither changes.

Candidate is fixed in advance: P=.5*exact historical SINGLE control probability
+ .5*SC1 support probability, on both original group42/43 cuts. The support
parent differs only in num_leaves63→98. Each parent is a two-view .5/.5 model,
giving four effective leaf weights of .25. No alpha grid, threshold adjustment,
class-factor change, refit, API request or post-score recipe change is allowed.

Mechanism to test: probability averaging might smooth the support parent's
supported-class DoS loss while keeping complementary confidence information.
This follows inspection of SC1 and is an adaptive reused-public hypothesis.
It cannot establish prompt superiority, private quality or an official score.

Frozen now: exact source/archive/parent recipes;50 file SHAs;24 parent/child
validation/test probability artifacts; both original and actual saved splits;
pristine inputs; canonical class order; fitting independent-group support.
Only NPZ classes and row-position metadata were read. Probability arrays were
not averaged, new labels/predictions/scores were not computed, and the declared
alpha remains .5. All stored parent class orders and validation rows matched.

After root's publication, a separate no-fit audit may use120seconds, one thread
and1.5GiB: reverify hashes, rows/classes/probability contracts; compute the fixed
mixture once; independently reconstruct MacroF1/per-class F1 from pristine
labels and verify fitting support. Primary comparator is exact SINGLE. Require
strictly positive MacroF1 and ex-Worms deltas on each cut, with no class having
>=100 independent fitting groups losing more than.01 F1. Ex-Worms is the mean
of the original other nine class F1 values with all validation rows retained.
Missing/invalid results remain null; both cuts remain mandatory. Comparison to
the support parent is descriptive and cannot select another alpha.

Even if these component gates pass, promotion=false. Any operational four-model
recipe needs separate full-agent selection/confirmation/refit/export, resource/
Windows path checks and exact-release verification. Saved test probabilities
provide schema checks only and no unseen-label quality estimate.

Prepared: blends0, new scores null, fits0, API0, no deadline or launch assigned.
