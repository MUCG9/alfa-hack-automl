# Experimental support-gated history with static contract guards

Source0933a66; archive ../solution-v10-asof3.zip,
SHA32120f240f0703f0f80de4a020a9be9c3c737070774b217dcb28954bef3acf2a,
72,437bytes,51flat files,Python3.12.3. Original requirements unchanged.

Same min-period support algorithm as asof2, with static context validation even
below the gate and immutable observation-period semantics under feature code.
21history checks pass (13helper +8worker). No default/portfolio promotion.

Support-gated fixed-recipe screen passed: recent-cut RMSE39.051678170/31.846185167
against40.960973097/33.984412055 control; oldest50.924669513 and both prediction CSV
byte-identical to control. All6workers exited0. Evidence paired-support.json.
212unique repository checks passed with source_unchanged=true;23repeated exact
unpacked checks passed. Evidence repo-tests.json and unpacked-tests.json.
This opt-in archive does NOT change default portfolio; full-agent evaluation is
next under docs/experiments/v10_agent_history_protocol.md. No official upload.
