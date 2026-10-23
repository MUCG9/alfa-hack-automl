# Isolated legacy launcher deprecation

Prepared for review only. Canonical and active campaign files were not changed.

`run_mvp_campaign.legacy.py` preserves the original tool bytes. The isolated replacement changes its misleading docstring and adds unconditional fail-fast guards for direct CLI use and imported `main()` use. CLI rejection precedes project imports, dotenv loading, input copying, API use and Popen. The original implementation remains historical unreachable code; no new command builder, stage validator or launch bypass is introduced.

The old tool omitted `--four-stage`; it accepted successful refit/integrity as campaign completion without proving EDA, broad CatBoost selection, model-stage execution or HPO. Adding that flag alone would still leave resource, shared reserve, ownership and actual-stage supervision gaps. The replacement therefore refuses execution and names the separately reviewed supervisor and its frozen-manifest preconditions. It does not certify or duplicate that supervisor, validate the active campaign, or change any historical result.

The mock-only checks verify rejection with no arguments, formerly valid launch arguments and help/explicit-four-stage arguments; they also verify the imported entry point, absence of dependency/private-environment/process activity, unchanged historical bytes, and an unchanged canonical tool. Missing-stage cases do not produce any completion receipt because execution is categorically unsupported.

Root may promote the patch after active tm1 is terminal and its source guard is released. No current source integration, fits, API calls or heavy fixtures are authorized by this preparation.
