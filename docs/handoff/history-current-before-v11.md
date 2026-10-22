# ACTIVE V11–V12 continuation after colleague handoff

Captain renewed implementation after colleague6aefbd9. Branch
`work/llm-upgrade-20261022`, not main. See v11_llm_review.md/v11_progress.md in
docs/experiments. New official submit NOT authorized; previous V10 STOP below
is historical. Main and older artifacts preserved; no extra agents/API-key bypass.

V11 featureviews1 sourcee11409e,SHAfbbd2511652814d7c05334ab0240f18b81e88a7b59dfc979efa617011dc84490:
230source/23unpacked PASS. Full history4 baseline class reproduced CSV58f52...,mean
.6532812402233098,exit0/refit/integrity. Frozen V11 full class→regression is ACTIVE
in test-runs/llm-upgrade-20261022/featureviews1-full (owned execution11039).

V12 threshold2 sourceeafdd6a,SHA12dc0f0ee49eaea085851ee98d309f1b86154e2be4d5a026212aa4d6806bb9a1,
new method dormant; default old coordinate unchanged.244source checks queued AFTER
V11 (execution15143). That older queued verifier still names superseded threshold1
and should refuse current-source mismatch, not a passed archive gate. Correct
threshold2 unpacked verification separately queued after source results (98344).
Do not edit runtime/tests during these unchanged-source gates. No threshold public
fits yet. V13 AutoGluon dev-only extension/synthetic checker prepared, not run;
V14 independent search-anchor policy is a conditional protocol, not implementation.

Primary26% used observed12:48UTC; cutoff85% used. Heavy jobs sequential2threads,
fixture suite1thread. No new dependencies, live Qwen or official upload this turn.

## Historical V10 handoff (superseded status)

22октября2026. Branch **work/cpu-research-20261022**,base V9a95c931. Последняя
команда — остановиться из-за лимитов и передать работу; она заменяет предыдущее
возобновление. [Самодостаточный промпт](../prompts/next-agent.md).
Main не менялся,официального V10 submit нет.

## Jobs и новый CV результат

Grouped classification CV73 завершилась:session46586exit0,все6workers успешны.
Scoped host-аудит не нашёл owned CV процессов. Анализ готовых прогнозов завершён.
Новые обучения/integration после STOP не запускались. Старые ACTIVE/partial4/6
сообщения superseded. Незавершённых ML jobs этой передачи нет.

Primary fixed50/50calibrated LGBM/LGBM+cross-fitted categorical statistics,
schema-order pairs,smoothing20. Существующий encoder,не новый runtime метод.
Paired screen42/43 улучшил оба folds. Full3foldCV73:

|MacroF1|Control|Fixed blend|
|---|---:|---:|
|Fold0|.641237770212|.648007875526|
|Fold1|.633295603768|.638038833502|
|Fold2|.647188887692|.649725432942|
|Fold mean|.640574087224|.645257380657|
|Pooled OOF|.640209809443|.645099303706|

87670rows exactly_once; все predeclared gates PASS,включая supported-class
F1drop≤.01 и gain без редчайшего класса+.004943201374.
[Итог/методика](../experiments/v10_class_te_cv_results.md),JSON results/diversity/
gate рядом. StandaloneTE сильнее blend на этом CV,но не primary endpoint:
не менять promotion path после результата. Public reused,не private estimate.

Следующий этап:[замороженный full-agent protocol](../experiments/v10_class_te_agent_protocol.md).
Один кандидат с корректными per-view iterations/nestedrefit,tests/newarchive,
полный baselineclass→candidateclass→regressionparity sequential. Интеграция не
начата,нового full-agent class score нет. Исторический mean .653281240 — ожидание
baseline,не результат TE-агента. Under70/ExtraTrees mixed,defaults не изменили.
Support-awareXTblend — резервный proposal без fits/метрик/реализации.

## Проверенный release

[solution-v10-history4.zip](../../release/solution-v10-history4.zip),source8f6b73e,
SHA `a42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8`,72537bytes,
51flatfiles. **219unique source+23repeated exact-unpacked checks PASS**.
Full default regression refit/export/integrity и bounded full-size class lifecycle
PASS. При handoff заново проверены byteparity всех51compiledfiles,original
requirements,ZIPstructure/Pythoncompile. [Receipt](v10-stop-checkpoint-20261022.json),
[полные gates](../../release/v10-history4/README.md).

RMSE39.321110258/34.229379712→38.902803731/31.991659384;
mean36.775244985→35.447231558,−3.611%,оба cuts лучше. Final90/10asof-LGBM/CatBoost.
History strictly-earlier fittinglabels,minimum3periods,отдельные inner/outer/full
transforms. Старый contextTE не стал causal. Classdefaults сохранены,bounded
lifecycle — не новая full-default qualityevaluation. Нового TE-ансамбля в ZIP нет.

Официальный лучший со слов капитана:V9raw2187.849,1940.2s,его21.87/100.
Новыйupload требует отдельного разрешения; техническая готовность его не заменяет.

## Git, среда, ограничения

Последний подтверждённый push до финального handoff —10e4ee5,эта же ветка origin.
Финальный commit добавляет эту передачу/CVагрегаты; HEAD сверять в Git. Старые
отказы push устранены успешными отправками. Credentials/rawCSV/predictions/NPZ/
venv в Git не сохранять.

Использовать test-runs/venv-core/bin/python,Python3.12.3,sklearn1.5.2,LGBM4.6,
XGB-cpu2.1.4,CatBoost1.2.8. Original requirements неизменны. На8GiBRAM тяжёлые ML
и fixturechecks строго sequential,2threads benchmark/1suite,watchdog.
Ignored data/venv/predictions на другом ПК отсутствуют;10inputSHA в public_inputs.json.
No liveQwen/newdependencies/officialsubmit/extraagents/mainmerge. Частые commits;
соблюдать новые указания капитана об остатке лимита,не выдумывать appreading.
