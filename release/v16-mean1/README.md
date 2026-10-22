# V16 metric-matched inverse correction — dormant, NOT submitted

Runtime sourcef72c6df,Python3.12.14,branch work/llm-upgrade-20261022.
Archive `../solution-v16-mean1.zip`,79054bytes,54flat root files.
SHA `68e1eb0c933807720178ef4708df2c0dbf55fe9940b0dfb849d7704dbe3b2566`.
Original requirements unchanged; no new dependencies, data or pretrained assets.

Adds typed target_smearing_method=least_squares as a SEPARATE estimator from the
rejected empirical log-residual moment. Scaled dot products avoid overflow;
same fitting-only support, [.8,1.25] bounds and exact-identity path. Method omitted
still means dormant V15 estimator, default correction remains OFF. No portfolio
or classification policy change yet; no quality gain claimed.

258unique source/23repeated exact-unpacked gates running; includes original-scale
optimum, numerical scale stability, method/signature/disable and actual outer-label
isolation tests. Public screen has not begun. Protocol/candidates in docs/experiments.
V11 is still the fully qualified score-improving archive. No upload authorized.
