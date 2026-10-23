# Measured research results

All numbers below are reused-public local validation. They are not official
scores, hidden-test estimates or a new release qualification.

| Experiment / scope | Control | Candidate | Decision |
|---|---:|---:|---|
| Historical V11/V16 whole regression RMSE | — | 35.4472315578 | Preserve |
| Historical V11/V16 whole classification Macro F1 | — | 0.6593178434 | Preserve |
| CP1 whole regression A/B RMSE | 35.2075921769 | 34.8662208787 | B verified; tie with T5, research flags/external JSON required |
| LA2 saved whole regression A/B RMSE | 34.8662208787 | 34.1550233948 | Both cuts better; retain research best, original procedure FAIL preserved |
| LA2 saved whole classification A/B F1 | 0.6555664858 | 0.6569242333 | Below historical V11/V16; preserve historical classification |
| LOSS01 component three-forward-cut mean RMSE, L2 versus L1 | 40.6075109499 | 39.7392276554 | All three improve; whole-agent confirmation pending LA2 |
| LOSS01 Huber component mean RMSE | 40.6075109499 | 40.9820986264 | Reject; two of three worsen |
| Fixed class 90/10 SINGLE + ExtraTrees component mean F1 | 0.6547938868 | 0.6556723826 | Promising on both cuts/support gates; full agent unconfirmed |
| KERN01 regression component matched linear / RBF | 40.6075109499 | 68.7343280066 / 67.3162534620 | Both worsen every cut; do not repeat fixed recipes |

Fresh whole class control 0.6530048969 failed to reproduce historical
0.6593178434. Same recipe lineage is established; exact matrix/native stopping
cause is not proven. KERN01 classification candidates have no metric following
Windows Unicode/joblib failure. T5 and T6 remain failed procedures permanently.
T7 was technically complete without quality promotion.

LA2 completed all four model arms, then exited 1 when the independent audit
compared two meanings of `kind`: task kind versus task kind plus arm. A separate
reviewed audit-only correction reused the saved artifacts inside the original
10,800-second clock, exited 0 and passed all four artifact checks. Fresh absence
of 4,386 known identities was confirmed. The original LA2 remains FAIL.

Regression improved on both cuts: 2.04% versus matched CP1 and 3.65% versus
historical V16. Classification remains below historical V11/V16; the primary
supported-class and ex-rarest gates regressed. Both classification arms had the
L1 flag OFF, so their stochastic difference is not an L1 classification effect.
No dual-task default or generic official release is promoted.

Linux packets 01 through 05 are portability/contract work with zero model fits and
zero API calls. Packet 05 reports 69 unique pure/mock/inert methods, including 43
inherited methods re-executed, not 69 new historical checks. Source review accepts
the two targeted guard repairs; exact private six-job authority still precedes any
model admission. No Linux quality improvement has been measured yet.

UAR-v1 metric, publication, router and process patches passed 48 meaningful unit
methods under one serial guarded lease. They are integrated as libraries; caller
hooks and full source/build checks remain pending. No ML quality is attributed
to those unit results. HPO cache is not integrated and
measured savings remain zero.
