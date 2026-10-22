# Передача V10: исследования остановлены по просьбе капитана

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
