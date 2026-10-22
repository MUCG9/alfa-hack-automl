# History screen result and train-only support hypothesis

Six workers passed, exact asof1 snapshot, matched splits/inputs. No other recipe
parameters changed. Control exactly reproduced earlier two metadata-history cuts.

|Forecast period|Metadata control RMSE|As-of last/trend RMSE|
|---|---:|---:|
|5|40.960973097|39.051678170|
|4|33.984412055|32.518744902|
|3|50.924669513|51.096679815|

Initial predeclared keep gate required all THREE cuts to improve. It failed;
do not promote asof1 into defaults. The two recent cuts improve, oldest worsens.

## New hypothesis declared before the next run

With only TWO fitting periods, no fitting row can have two strictly prior period
means, so the trend feature is entirely missing in training; at prediction it may
appear. Sparse history also changes feature subsampling. This is a structural
support hypothesis, not proof of the cause of the observed change.

Add opt-in history_min_periods=3: each inner/outer/full fit independently checks
the number of observation periods in ITS fitting rows (no y/held-out/test X).
If insufficient, omit the entire history block and retain exact metadata control.
Original history_asof default remains min2 for reproducibility; new candidate
explicitly asks min3. Keep no other changes. On oldest public cut, candidate should
be prediction-identical to the control; recent periods still require measurement,
because the gate can change inner stopping and chosen iteration count.

Recipes: v10_history_support_candidates.json. New immutable source archive asof2;
same three forward cuts0/1/2,2threads,1200s/worker,1.5GiB guard, sequential after
the ongoing frozen V9 classification CV. Support check, cutoff and decision must
be recorded per fit. Test insufficient-support baseline parity and held-out-X
invariance, validate integer min periods and unsupported contracts.

Keep: both recent cuts improve and the oldest remains byte-identical control,
all workers/gates pass; then full-agent comparison before portfolio promotion.
This follow-up was motivated by observed reused public outcomes and does not
create an unbiased holdout. No silent replacement of first negative evidence.
