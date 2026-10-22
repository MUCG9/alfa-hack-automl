# One last bounded rare-class learner-capacity hypothesis, before fits

Source exact frozen V16 (target/numeric refinements OFF), existing fixed two-view
MacroF1 learner. Control min_child_samples25, candidate10 in BOTH internal views.
All other params/seed42/soft class weights.5/calibration/splits/encoding20/rows/
fixed internal.5/.5 weights unchanged. No new feature, sampling or dependency.
This is one learner parameter shared by the two views, not an isolated claim
about one view or a guaranteed rare-class boost. Smaller leaves can also overfit
conflicting groups. Do not change num_leaves/weights/bounds after seeing results.

Paired feature-group holdouts42/43,2threads,1.7GiB,1200s/worker; all preceding
owned jobs must finish first. Control expected fixed-view F1 .655863465996 /
.653724307927. Keep for CV only if BOTH cuts improve and all supported classes
(>=100independent fitting feature groups per cut) lose<=.01 F1. Source/input/split/
prediction/recipe fingerprints recorded and metrics independently recomputed.

If positive: complete SAME control/candidate3fold grouped CV73, exactly_once,
all folds/mean/pooled improve; pooled supported-class drop<=.01, gain excluding
minimum-supported class positive. No pooled overlapping holdouts or posthoc
mixture weights. Only then replace the one qualified view's minchild25 with10,
keeping old ordinary learner25, portfolio order/trial/deadline/selection unchanged.
New immutable source/archive/full unique/unpacked gates, full default class
procedure versus qualified V11. Require BOTH search/confirmation F1 improve,
refit/export/integrity and regression history4 full CSV parity. Otherwise keep
evidence and V11; do not broaden search to5/15 or run CV on a negative screen.

At85%used stop starting long stages, checkpoint. No official submit without the
separate captain reply; one V11 permission question is already pending. No extra
agents/API-key bypass/paid resources. Reused public, not private/official score.
