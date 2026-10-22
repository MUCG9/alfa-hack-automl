# V12 threshold infrastructure — dormant experiment, NOT submitted

SUPERSEDED before any public fit by threshold2 (sourceeafdd6a): numeric clipping
must precede the discontinuous-objective acceptance check. Historical ZIP is
preserved, not promoted. A prequeued verifier still names this archive and will
correctly refuse source mismatch after the fix; use threshold2 for current gates.

Runtime source0973de0,Python3.12.14,branch work/llm-upgrade-20261022.
Archive `../solution-v12-threshold1.zip`,77208bytes,53flat root files.
SHA `b44feb1094cc2d4063e3e1d6dc629c8b8bc5f227b794a58ea1619025e264585f`.
Original requirements unchanged, no new dependencies/pretrained assets.

Adds MacroF1ThresholdOptimizer with explicit class/probability/positive bounds,
existing coordinate warm start and optional bounded log-space Nelder–Mead400fev.
Same .004regularized objective, [.4,2.5] weights, explicit .15log-space simplex.
Invalid/unavailable optimizer preserves old factors and records failure type.
The worker default still calls the original coordinate implementation directly;
new method is explicit `decision_optimizer=nelder_mead`, NOT a default candidate.
No quality gain claimed. Protocol and frozen two-recipe screen in docs/experiments.

Also lets the planner explicitly clear inherited feature_views with JSON null
before proposing ordinary LightGBM feature code. Worker raw malformed flags still
fail closed. No default ML behavior intended to change from frozen V11.

Eleven initial pure tests passed; added import-failure check and real worker test
await full suite. Intended total243unique source checks plus23repeated unpacked,
all gates PENDING. Frozen V11 full class→regression is independently running;
V12 model screen will not start concurrently. No official upload authorized.
