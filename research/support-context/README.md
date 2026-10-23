Prepared only: standalone support-context component screen. No worker, model fit,
API call, experiment deadline or automatic continuation has been launched.

Frozen coordinator: `work/support_component_coordinator.py`, SHA256
`8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8`.
Launch manifest: `work/support-component-launch/manifest.json`, SHA256
`97233bd7e32b72c7d19ed0e8c1d2e100708ff30f5c06a8b84bba6d38e849bb86`.
Original `work/support-context-component-plan/protocol.json`, candidates,
generation packet, source archive and both saved NPZ files remain unchanged.

The future command is provided for root review only. The deadline placeholder
is deliberately unassigned; do not run it while2e owns any process or resource:

```
<TASK_WORK>/venv/Scripts/python.exe <TASK_WORK>/alfa-hack-automl/research/support-context/run_support_component.py --work-root <TASK_WORK> --launch --manifest-sha256 97233bd7e32b72c7d19ed0e8c1d2e100708ff30f5c06a8b84bba6d38e849bb86 --deadline-unix <ROOT_REVIEWED_ABSOLUTE_UNIX_DEADLINE>
```

Root may assign that absolute deadline only at the actual reviewed launch after
2e and its owned descendants are gone. It must be no more than4200seconds from
that launch and leave more than600seconds verification reserve. A premature
launch is rejected; the helper never waits for2e under a freshly reset clock.
An output from an earlier attempt is never overwritten or resumed.

Before any fit, the helper verifies:

- Exact PID/create_time roots6412/1792718706.779424 and24700/1792718706.768474,
  initial observed descendants and every root declared by the final2e queue.
  Recursive discovery and an orphan-parent scan are read only. Reused unrelated
  PIDs are not signalled. Any verified live descendant prevents launch.
- A terminal2e queue, confirmed cleanup and unchanged source, then exclusive
  `ResearchLock` acquisition and another resource-free check. The final2e
  supervisor cleanup receipt is required in addition to direct PID observations;
  no claim of reconstructing arbitrary unobserved historical process ancestry.
- Pinned original packet/candidate/NPZ/archive hashes, all canonical source/tool/
  test bytes and Python inventory, plus the prepared coordinator's own bytes.
- Exact archive88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0
  and all68 compiled files. The existing2e source, exact-unpacked and live
  four-stage technical gates are reused only when their saved artifact and
  current source/harness hashes match. They are not rerun, and they do not certify
  this new wrapper's own logic or the new candidates' quality.
- Pristine task/input CSV bytes and actual array equality between current
  `choose_validation(...,'auto')`/`make_split` results and both saved group42/43
  NPZ arrays. This happens before creating a benchmark process.

The sole fit entry point is the existing `tools/benchmark_candidates.py`.
Its six sequential fixed-recipe workers use600seconds,2threads and1.5GiB each,
with0API credentials and no full refit/HPO/blend search. The output is the short
`test-runs/sc1`, benchmark artifacts beneath `sc1/b`. The wrapper observes its
own plus benchmark-tree RSS under a2GiB supervisor allowance; the1.5GiB worker
cap remains the same as2e. It rechecks immutable bytes and predecessor state
every10seconds. The benchmark process stops before the final600seconds reserved
for cleanup/verification; absolute deadline checks remain active throughout.

Cleanup uses the existing identity-aware ProcessTree. If its initial constructor
fails after Popen succeeds, the wrapper retries tracking, then attempts to stop
the exact Popen root handle if tracking still fails; descendant cleanup remains
unconfirmed and the attempt fails closed. It never reports cleanup success just
because a tracker object was not created. Signals, memory/time limits and source
changes stop the owned tree; they never start another attempt.

After cleanup, the independent audit checks actual copied source bytes, evaluator
harness, worker jobs/recipes and all saved split arrays. It reconstructs MacroF1
and every class F1 directly from pristine fitting CSV labels, saved row positions
and validation probabilities; checks y_true/y_pred CSV consistency; verifies
test probability classes/order and submission schema/sample IDs/predictions; and
hashes actual JSON/NPZ/CSV artifacts including feature-view child artifacts.
Independent fitting-group support and the predeclared rarest class are recomputed.
The ex-rarest value is the mean of original per-class F1 excluding Worms, with all
validation rows retained.

Each saved proposal is compared with the exact fixed SINGLE V16 control on both
cuts, with strict positive MacroF1 and ex-rarest changes and no supported-class
F1 drop beyond0.01 (support>=100independent fitting groups). A third comparison
contrasts support with old under the same gates. Any failed/missing worker has
null metrics; no zeros, retries, cut omission or recipe repairs are inserted.
Valid negative comparisons remain evidence. Six complete verified workers are
required for a complete screen, but `promotion=false` always: this single
stochastic proposal pair cannot establish prompt superiority, full-agent quality
or an official leaderboard result.

Preparation-only evidence in `preparation-check.json`: earlier actual current/frozen
arrays match for70529/17141 and70321/17349 fitting/validation rows; every frozen
input/source/array byte and the unchanged equality-check implementation were reverified.
The earlier active2e guard refused launch. The current PID/terminal-state observation
is recorded separately; it grants no automatic launch. Popen/API/fits are0 and no
deadline was assigned. Full array equality is checked again at any future launch.
No source-gate tests or public training runs were executed to prepare this bundle.

Publication/portability: root must review and publish the byte-identical helper under research/support-context/run_support_component.py before any experiment. Use explicit --work-root <TASK_WORK> for both default preparation and --launch. The default work root is only the executing file parent, so published copies require the explicit flag. The existing current-task manifest is already prepared: invoking preparation again refuses overwrite. No private configuration or machine-specific path is embedded.

Final cleanup hardening: initial or retry ProcessTree must contain the exact owned root PID/create_time. An empty tracker returned after AccessDenied is not proof of cleanup. If exact-root tracking fails, root-handle stop is attempted, descendant cleanup remains false, and the attempt fails closed. Earlier unlaunched snapshots are preserved under work/support-component-launch-r1-preserved and -r2-preserved; the original component protocol has never changed.

Strict cleanup revision r4: the original r3 source and bundle are preserved separately. An independent read-only observer records exact PID/create_time identities and every denied identity/descendant traversal. Its historical denials remain unresolved even if the parent later disappears. Known-owned canonical cleanup is always attempted, followed by a fresh recheck of the union of observed, tracked and pending identities; any same-identity live process or verification denial keeps cleanup_confirmed=false and is fatal. A reused PID is never signalled. Unresolved receipts contain only PID/create_time/action/reason, never argv or environment. The confirmed owned_root/running receipt is written before the long loop, and safe identity counts and heartbeat are persisted at most every 10 seconds. Six synthetic mock checks passed without creating or signalling real processes. This new wrapper logic is not covered by the reused canonical 2e gates. No model parameters, learner policy, runtime bytes, input bytes, saved partitions or promotion gates changed.
