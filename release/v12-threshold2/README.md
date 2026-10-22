# V12 bounded threshold experiment, corrected snapshot — NOT submitted

Sourceeafdd6a,Python3.12.14,branch work/llm-upgrade-20261022.
Archive `../solution-v12-threshold2.zip`,77216bytes,53flat root files.
SHA `12dc0f0ee49eaea085851ee98d309f1b86154e2be4d5a026212aa4d6806bb9a1`.
Original requirements unchanged; no new dependencies/model assets/raw data.

Same dormant positive bounded MacroF1ThresholdOptimizer as threshold1, with
acceptance evaluated AFTER numeric bound clipping. This matters for discontinuous
argmax/F1 at ties. A regression fixture forces a slightly outside-bound solver
result and verifies preservation of the stronger coordinate warm start.
Default calibration still calls the unchanged old callback. Explicit numerical
method is not in default portfolio; no quality gain or promotion claimed.

Source suite intended244unique checks and23repeated exact-unpacked, PENDING until
the independent frozen V11 full class→regression finishes. An earlier queued
verifier points to threshold1, so current threshold2 verification is separate;
never call that historical source mismatch a passed gate. V11 archive unchanged.
Protocol/candidates in docs/experiments/v12_threshold*. No public threshold fit yet.
