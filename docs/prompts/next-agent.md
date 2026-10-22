# Промпт для продолжения AutoML V10 — checkpoint 22 октября 2026

Ты продолжаешь исследование и разработку CPU AutoML-агента для Альфа-Будущее
Хакатона 2026. Качество целевой метрики приоритетно в пределах лимитов платформы.
Последняя просьба капитана: **остановиться и подготовить передачу из-за лимитов**.
Предыдущий агент завершил checkpoint без новых обучений после этой просьбы.
Этот файл — контекст для нового агента, а не команда старому продолжать работу.

## Сначала проверь состояние

Рабочая ветка **work/cpu-research-20261022**, основа V9 `a95c931`.
Remote: https://github.com/MUCG9/alfa-hack-automl. Main сохраняет V2.
Последний push до финальной передачи подтвердил `10e4ee5`; финальный handoff-коммит
идёт после него в этой же ветке. Проверь фактические HEAD, tracking ref и clean tree.
Исторические отказы push устранены успешными отправками; это не текущая блокировка.
Не помещай credentials в команды, Git или prompt.

Читать: AGENTS.md, docs/CONTINUE_HERE.md, docs/handoff/current.md,
docs/experiments/v10_progress.md, docs/architecture/implementation.md.
Старые ACTIVE/partial статусы в журнале — история, итог ниже их заменяет.

Все6workers классификационной CV завершились успешно, controller session46586
вернул exit0. Scoped host-аудит не нашёл оставшихся процессов этого запуска.
Анализ готовых прогнозов тоже завершён. **Незавершённых ML jobs этой передачи нет.**
Не запускай повторный CV по старому сообщению о частичных4/6 результатах.

## Проверенная версия для платформы

**release/solution-v10-history4.zip**, runtime source `8f6b73e`:

- SHA256 `a42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8`.
- 72537bytes,51root files:50Python+оригинальный requirements.txt.
- Полные219unique source checks и23repeated exact-unpacked checks PASS.
  Первоначальные216checks сохранены, новый receipt добавлен отдельно.
- Full regression lifecycle exit0,final refit/export/integrity PASS.
- Classification bounded full-size1trial/600s lifecycle PASS: проверка упаковки,
  **не новая full-default оценка MacroF1**.
- При передаче заново проверены SHA/структура/компиляция Python и точное совпадение
  всех51flat files с текущей сборкой исходников. Архив не меняли.

Evidence: release/v10-history4/README.md,quality-comparison.json,
additional-repo219-tests.json,unpacked-tests.json,docs/handoff/v10-stop-checkpoint-20261022.json.

Полные default regression сравнения в одинаковой среде:

|Метрика|Frozen V9 control|History4|
|---|---:|---:|
|Search RMSE|39.32111025790986|38.902803731334785|
|Confirmation RMSE|34.229379711674525|31.991659384340597|
|Среднее RMSE|36.775244984792195|35.44723155783769|
|Время pipeline, секунды|336.888|389.131|

Оба cuts лучше,mean RMSE ниже на3.611%. Выбран90/10blend asof3-LGBM/прежнийCatBoost.
Final CSV SHA history4:
`05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673`.
V9 repeat воспроизвёл исторический CSV побайтово, SHA
`c1556d566cd24de3dc4bed107fbfe7f517dea14dd2c53c583545af08ed43f4e0`.

History4 добавляет один numeric-period regression candidate с историей контекста
и minimum3fitting periods после прежнего semantic/log candidate. Только строго
предшествующие fitting targets; inner/outer/full transforms отдельные. Static
context/time validation действует и ниже support gate. Minimum3периода не
гарантирует поддержку каждого контекста. Прежний context TE — GroupKFold, поэтому
весь recipe не стал causal. Ranking исключён. Старые recipes/relative order,
class/text policy,default12trials/9900s,confirmation/global blend сохранены.
Fallback может наследовать history от incumbent — измерена вся процедура.

Лучший **официальный** результат пока V9 solution-v9-roles1.zip: со слов капитана
raw2187.849,1940.2s,его21.87/100. V10 не отправлялся. Техническая готовность
history4 не означает разрешение на официальный submit: оно нужно отдельно.

## Новое: feature-view ансамбль прошёл полный фиксированный CV gate

Существующий multiclass target encoder, без изменения runtime. Control — strong
calibrated LightGBM seed42. Вторая ветка: тот же learner/rows/weights/seed/calibration
плюс categorical singles и пары первых3categorical columns в порядке schema,
smoothing20. Публичные имена есть только в dev recipe JSON; не хардкодить runtime.
Fitting rows получают3fold GroupKFold encodings без всей собственной feature-hash
группы; outer validation/test используют только fitting labels. Inner fitting
перестраивает статистики. Исходные категории/colsample.9 сохранены, дополнительные
колонки меняют фактические feature masks.

**Primary endpoint заранее зафиксирован:50/50probability blend двух веток.**
Не заменять его post-hoc более сильной standalone TE веткой и не подбирать веса.

Paired holdouts42/43:control .650292961/.652794416 против fixed blend
.655863466/.653724308;mean .651543688→.654793887. Оба лучше.

Полный3fold StratifiedGroupKFold seed73,87670rows exactly_once,6jobs exit0:

|MacroF1|Control|Fixed50/50blend|
|---|---:|---:|
|Fold0|.641237770212|.648007875526|
|Fold1|.633295603768|.638038833502|
|Fold2|.647188887692|.649725432942|
|Fold mean|.640574087224|.645257380657|
|Pooled OOF|.640209809443|.645099303706|

Все predeclared criteria PASS: каждый fold/mean/pooled лучше; у классов с minimum
100independent fitting feature-hash groups во всех folds pooled F1 не упал больше
.01. Minimum support Worms41; исключение Worms из среднего pooled class F1
оставляет gain+.004943201374. Это среднее остальных class F1 при всех строках и
неизменных прогнозах, не фильтрация строк перед пересчётом. Наибольшее падение
среди поддержанных классов DoS−.002776829.

Standalone TE diagnostic mean .647623143531/pooled .647349395776. Это не отдельный
promotion path. **Full-agent class evaluation не начат**; history4 ZIP не включает
новый feature-view ансамбль.

Portable evidence без row predictions:

- docs/experiments/v10_class_te_protocol.md — замороженный протокол.
- v10_class_te_{candidates,cv_candidates,results,diversity}.json — recipes/screen.
- v10_class_te_cv_{results,diversity,gate}.json и v10_class_te_cv_results.md — CV.
- Ignored local artifacts:test-runs/v10-class-te-cv3,controller46586 завершён.
- tests/test_class_te.py:3meaningful isolation checks PASS, входят в219.

## Следующий конкретный этап

1. Прочитать уже записанный **до integration**
   docs/experiments/v10_class_te_agent_protocol.md. CV gate теперь пройден;
   дальше одна ограниченная реализация + сравнение **полного агента**.
2. Один schema-driven fixed two-view candidate после прежнего calibrated LGBM;
   сохранить recipes/relative order/default budget. Сначала решить nested global
   ensemble/refit. run_ensemble сейчас запрещает child engine ensemble: наивная
   вложенность сломает refit. Typed learner flag — возможный дизайн, ещё НЕ
   реализован. Per-view iteration lists должны пройти confirmation,recursive
   median,nested global fullrefit; не терять вторую ветку или её iterations.
3. Meaningful tests eligibility/rename invariance,fitting-only isolation,per-view
   iteration shapes,прежний portfolio order,реальный nested fullfit. Новый архив,
   полный source gate/exact-unpacked23. Не перезаписывать history4. Не совмещать
   с новой data policy,tuning и рефакторингом.
4. Последовательно повторить full-default history4 class baseline,новый default
   candidate и regression parity по protocol. Исторический mean .653281240 и CSV
   SHA `58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326` —
   ожидание, сначала проверить реальный baseline. Keep только если **оба** search/
   confirmation MacroF1 лучше,refit/export/integrity исправны. Regression full
   lifecycle/portfolio должны сохранить history4 CSV parity.
5. При mixed/failure сохранить evidence,не менять критерии после результата.
   Коммит каждого законченного этапа.

## Что уже проверяли — не повторять как новые идеи

- Under70 diverse-data ensemble:mixed full3fold CV,mean .638363183→.640222558,
  pooled .638309026→.640476085,но2folds хуже. Bootstrap50095%gain interval
  [−.001844234,+.006447588] включает0. Defaults не изменены.
- Fixed50/50LGBM+ExtraTrees:.644409878/.658312670 против .650292961/.652794416,
  mean чуть хуже. Первый fold теряет редкий Worms,хотя accuracy/logloss лучше.
  Нет продвижения/CV. Original session исчезла,причина неизвестна; exact candidate-
  only retry завершён,child-control CSV parity обоих folds. Partial/retry сохранены.
- Support-aware XT blend:только docs/experiments/v10_support_blend_proposal.md,
  без fits/метрик/runtime/tool. Теперь резерв; приоритет TE full-agent этапу.
- Seed/under/OOF-calibration/ранний asof1 уже изучены,часть результатов отрицательна.
  CPU HPO/shortlist backlog в cpu_research_review_20261022.md — предложения,
  не установленные библиотеки и не реализованные возможности.

## Среда и ограничения

Python:test-runs/venv-core/bin/python,3.12.3,numpy1.26.4,pandas2.2.3,scipy1.12,
sklearn1.5.2,LGBM4.6,XGB-cpu2.1.4,CatBoost1.2.8,openai1.68.2. Не смешивать с.venv.
Optuna/FLAML/AutoGluon/LightAutoML/torch в этой среде не установлены.

ПК8GiBRAM/full swap:тяжёлые fits **и full fixture checks строго sequential**,
2threads benchmarks/1suite,matching BLAS envs,явные tree watchdog/RSS guards.
Локальные1200s/1.7GiB не лимиты платформы8CPU/32GB/3h. Полный pipeline protocol
задаёт10100s watchdog. Не трогать чужие процессы/не менять source при integrity
gate. PIDs sandbox могут отличаться от host PIDs.

Ignored public_tasks/*/task.md+8CSV:10SHA в docs/handoff/public_inputs.json.
Данные/venv/weights/predictionCSV/NPZ не в Git,на другом ПК получить отдельно.
Агрегаты/fingerprints уже portable,не повторять старые fits ради обзора.
V10 offline,live Qwen не проверен;fake HTTP tests не live API proof. Исторический
protected-input отказ не обходить. Секреты только в private process env/manager,
никогда не в prompt/Git/argv/logs. Бюджет Qwen общий у команды.

Canonical src/automl,root shims не standalone submission. Imports через api.py/
contracts. Сборка tools/build_submission.py,ZIP только rootPython+original
requirements,без runtime pip/pretrained assets/неразрешённых пакетов.
Requirements SHA `9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.

Никаких official upload/main merge/force push/paid resources/extra agents без
отдельного разрешения. Не писать в другие чаты. Public folds переиспользуются:
screen/CV не дают unbiased/private/официальный score estimate. Частые commits;
при фактических15%остатка5hокна прекратить длинные jobs и подготовить handoff.
Если app reading не показан,не выдумывать процент и не сбрасывать лимиты.
