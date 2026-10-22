# V7 semantic file-role experiment (not submitted)

Branch: `work/semantic-inputs-20261022`; source checkpoint `b4f8db7`.
Archive: `../solution-v7-semantic1.zip`, 66,096 bytes, 48 flat root files.
SHA-256 `a31d1fc7c9bee3403f992f70467e95a446c19dbffdb4cdfea9abf2d035f79b27`.
Builder Python 3.12.14; original platform requirements are byte-identical.

Passed: **145 unique repository checks**, unchanged compiled sources, 156.158
seconds. The exact unpacked archive also passes the 23 compatibility checks;
these repeat tests included in 145, not additional unique checks. Evidence is
`repo-tests.json` and `unpacked-tests.json` in this directory.

Adds bounded Qwen selection of file roles ONLY after deterministic resolution
fails, ONLY in online CLI mode. Accepts only distinct task-local catalog paths;
sends schema metadata, not raw rows; at most two 45-second/2,048-token attempts.
No generated loading code or arbitrary paths. Multi-target children reuse the
resolved input cache. Canonical names, offline and library defaults do not call
this stage. See `docs/experiments/v7_semantic_inputs.md` for scope and limitations.

The eight semantic tests use a mock gateway; one continues into real model
training/refit/export. **No live Qwen session was established in this continuation.**
Do not interpret mock usage as HTTP success or assume a live API balance/spend.

Full default public regression for this exact v7 archive completed: exit0,
refit/integrity pass, final CSV SHA
`c1556d566cd24de3dc4bed107fbfe7f517dea14dd2c53c583545af08ed43f4e0`,
byte-identical to v6/v4, harness215.622s. See `regression-full.json`.
The earlier classification was interrupted (exit143); its partial evidence is
preserved in `interrupted-classification.json`, not counted as full success.
The NEW classification-only run completed on22October about10:19MSK: exit0,
full refit/integrity pass, mean Macro F1 **0.6532812402233098**, final CSV SHA
`58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326`.
Harness1358.099s; output is byte-identical to V6. See `classification-full.json`.
**Both V7 public full lifecycles now pass**; combined evidence in `public-full.json`.
This establishes offline parity/correctness, not live Qwen or a new official score.
The v6 ZIP and historical releases remain immutable. Do not describe v7 as the
best measured model or automatically submit it. Only v4 was authorized/uploaded.
