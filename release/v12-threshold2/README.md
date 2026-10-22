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

Source suite244unique checks PASS unchanged-source (169.873s), plus23repeated
exact-unpacked PASS. The independent frozen V11 full gate passed. An earlier queued
verifier points to threshold1, so current threshold2 verification is separate;
never call that historical source mismatch a passed gate. V11 archive unchanged.
Public paired threshold screen completed: BOTH cuts worse, mean .651543688→
.650925929. NoCV/default promotion; details in v12_threshold_results.md/gate.json.
Default still original coordinate, not this rejected refinement. No official upload.
