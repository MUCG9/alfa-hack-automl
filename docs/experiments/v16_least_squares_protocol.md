# Separate original-scale squared-error correction, before implementation/fits

V15 empirical log-residual moment worsened eligible outer period5. Do NOT rescue
its result by resizing bounds. New one-factor hypothesis changes the ESTIMATOR,
not support/bounds/training: choose the scalar inverse factor minimizing RMSE on
the same training-only inner held-out rows, rather than averaging residual ratios.

For z=exp(prediction_log), inverse prediction=s*z-1. Minimize
sum((y+1)-s*z)^2: s=dot(z,y+1)/dot(z,z), projected to the SAME[.8,1.25] bounds.
Compute with scaled vectors to avoid overflow. This is original-scale least-
squares calibration, NOT the Duan estimator or probability calibration. It can
still overfit/shift and has no guarantee of outer improvement.

Control: exact asof-min3 history4 recipe. Candidate adds target_smearing=true and
target_smearing_method=least_squares. Old omitted method remains the V15 empirical
moment, off by default. Preserve>=20rows, matching-iterations fitting-only inner
split, actual enabled calibration history, identity inverse and original flags.
No new model/features/weights/data policy/default candidate/trial/dependency.

Required: scalar-optimum and scale-stable math, typed enum/disable/signature,
actual outer-label isolation tests; complete unchanged-source suite/new archive/
exact-unpacked checks. Then same forward cuts0/1/2,2threads,1.7GiB,1200s/worker.
Require control reproduction, eligible cut5 STRICTLY lower RMSE, all cuts no
worse and validation/test CSV byte parity where inactive. Fail means discard;
no further bound/selection rescue. If positive, separate one-candidate portfolio
addition after asof and full-agent regression comparison: search strictly better,
confirmation no worse, mean strictly lower, refit/export/integrity and full
classification CSV parity. Do not claim a component score is the whole agent.

New model experiments only after preceding owned jobs complete. Frequent commits,
15%-remaining cutoff, no new official upload/extraagents/paid resources. Reused
public validation, not independent/private/official score. No source runtime change
is authorized by a document alone; captain's current implementation request applies.
