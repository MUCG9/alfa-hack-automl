# Predeclared experiment: XGBoost decision calibration

The prior v4 fixed-recipe classification studies mainly calibrated LightGBM.
The completed history3 search spent eight fallback trials on XGBoost capacity
variants, none beating its first XGBoost recipe, and final two-fold ensemble mean
was slightly below frozen v3. Do not promote another capacity/default change from
this observation alone.

Hypothesis: XGBoost's existing, training-only decision-factor calibration can
improve the precision/recall balance of rare classes without changing fitting
weights, capacity or the evaluator. This is decision calibration for Macro F1,
not a claim of calibrated probabilities for log loss.

- Control and one-factor candidate: `v5_xgb_calibration_candidates.json`.
- Frozen execution archive: `release/solution-v5-contract1.zip` (existing adapter
  calibration support, before later orchestration changes).
- First compare the same feature-hash-group folds, seeds 42 and 43. Two threads,
  sequential workers, 900-second per-worker watchdog, 1.5 GiB worker RSS guard.
- Require successful workers and inspect every class, not only mean Macro F1.
  Do not add calibration to the portfolio unless direction is supported on both
  folds; if promising, confirm on full 3-fold group CV before promotion.
- Fold/CV data are already researched public rows, not a blind private estimate.
  A negative/inconsistent result is recorded and discarded, not hidden.

## Paired result

All four workers passed. Control/candidate Macro F1:

| Seed | Control | Inner decision calibration | Difference |
|---|---:|---:|---:|
| 42 | 0.650904187 | 0.652319467 | +0.001415280 |
| 43 | 0.639569586 | 0.645949771 | +0.006380185 |
| Mean | 0.645236886 | 0.649134619 | +0.003897733 |

The exact source archive SHA is
`1defe433da3fe65813b5c1cc3682991e508780dd89defefdb08b7589e17ccb5a`.
## Full 3-fold group CV

All six fixed workers completed with exact once-per-row OOF coverage and no
feature-group overlap. Control/candidate fold Macro F1:

| Fold | Control | Calibration |
|---|---:|---:|
| 0 | 0.611680839 | 0.618160438 |
| 1 | 0.616880313 | 0.618221358 |
| 2 | 0.604496346 | 0.615360714 |
| Fold mean | 0.611019166 | 0.617247503 |
| Pooled OOF | 0.611757099 | 0.617987602 |

The pooled gain is **+0.006230503**. A paired feature-group bootstrap of these
fixed OOF predictions (1,000 replicates, seed 2026, 54,228 groups) gives a
conditional 95% delta interval **[+0.003868363, +0.009158243]**. This is NOT a
private-score interval or training/refit uncertainty. All data are reused public.

Eight of ten pooled class F1 scores improved, including Shellcode/Worms/Backdoor;
Analysis and Exploits decreased. This supports adding one optional calibrated
XGBoost candidate for Macro F1, while retaining an uncalibrated control and actual
per-task selection. It does not support forcing calibration for every metric.
The portfolio change is not yet implemented at this evidence checkpoint.
