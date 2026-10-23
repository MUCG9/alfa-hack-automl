# Autoresearch: подтверждённые lessons tm1 и Stage0, 23 октября 2026

Факты и точные SHA/JSON pointers собраны в [evidence](autoresearch_lessons_tm1_20261023.evidence.json).
Это запись наблюдений. Она не разрешает запуск, не описывает текущие PID и не
превращает результат одного exploratory pipeline в общий закон о методе.

## Исполнение, качество и независимый аудит — разные gates

Настоящий tm1 подтвердил pre-fit Qwen EDA, broad features с фактическим CatBoost
selection, LightGBM/CatBoost/XGBoost, inner Optuna и свежий полный refit/CSV/source
integrity. Это технически исполненная процедура, но не улучшенный baseline. [L1]

Selected regression RMSE:38.919029055/37.289046752, mean38.104037904 против
сохранённого V16 mean35.447231558. Selected class MacroF1:
.649307250/.650516192, mean.649911721 против V11/V16 .659317843.
Оба cut каждой задачи хуже; class также не проходит ex-rarest и supported-class
limits: Analysis/Backdoor теряют более.01 на обоих cut. Это сравнение с
сохранённым квалифицированным контролем, без нового matched control refit;
historical raw confirmation predictions не пересчитывались. [L2,L3]

Class independently-read closed API ledger:2gateway calls,16492prompt и1826
completion tokens, usage_complete=true. У regression независимые calls/tokens/
usage остаются null из-за PermissionError; известный отказ не повторялся и ACL
не обходился. Parent-reported2calls хранятся отдельно. Нельзя суммировать их как
независимо проверенный общий usage или назвать весь audit PASS. [L6]

## Cost прежде увеличения pipeline

В class записано80teacher receipts и4252.255s selector time из7204.438s solver
report (59.02%); regression52receipts/164.192s из449.109s (36.56%). Это время
всего selector, включая подготовку/ranking/slicing, а не pure CatBoost fit и не
экономия будущего кэша. Metadata-identical scopes не доказывают actual prepared
X/y/weights equivalence. Полный pipeline менял несколько факторов, поэтому его
ухудшение не устанавливает причину в broad FE, selector, Qwen или Optuna. [L4]

Class HPO:8planned,3attempted,2successful,1timeout,5unattempted; guided TPE0.
Regression:8successful, из них5guided. Наличие Optuna или planned8 не означает,
что выполнен adaptive search. Эти наблюдения не являются matched random-vs-TPE
comparison. Стоимость/preprocessing и startup feasibility проверять до дорогой
серии; не объявлять TPE победителем или причиной провала без отдельного опыта. [L5]

## Component и whole agent

Fixed-half SC1 blend прошёл свой component gate против сильного SINGLE recipe:
cut42 .655863466→.658024378; cut43 .653724308→.656119589. Это не full-agent
V11/V16 control и не default promotion. Оценка процедуры выбора требует
повторного inner selection в каждом frozen outer grouped fold, complete OOF,
затем both-task full-agent/refit/export qualification. R3 сохраняет AB/BA/AB,
отрицательный early stop и null aggregate при incomplete matrix; component
nonselection само по себе не заменяет quality gate. [L8]

## Expected registry и actual gate

Манифест A451/B468 — ожидание, не PASS. В первом Stage0 sourceA фактически
наблюдались451checks/0skips;435 — script-counted passes. Один16-check script,
test_error_preparation.py, дал2FileNotFoundError, а не16численных ML failures.
SourceA exit1; B и exact-unpacked не были достигнуты. Cleanup/source unchanged
подтверждены, inference о качестве модели отсутствует. [L9]

395 immutable hashes и Python inventory не доказали transitive fixturemetadata
closure: isolated A deployment не содержал docs/handoff/public_inputs.json,
который читают tests через audit_baseline. Preflight должен проследить реальные
read dependencies fixtures/callees, включая docs/release metadata, и проверить
замкнутый isolated deployment. Runtime archive bytes не менялись. Старые failed
receipts и deadline сохраняются; будущий harness repair — отдельный объявленный
attempt, не исправленный задним числом PASS и не обнуление его часов. [L10]

## Frozen clock и знания агента

tm1 завершился внутри исходного3h clock:7664.906s monotonic elapsed, исходный
absolute deadline1792735776.7207654; UTC residual3135.133s записан отдельно.
Обе задачи достигли14outer slots; plateau rule или posthoc extra training для
расходования остатка не вводились. Residual не доказывает, что больше trials
улучшит качество. Scheduler/cache/admission — отдельные prospective factors
с резервом на confirmation/refit/export и неизменяемым общим deadline. [L7]

Эта запись не меняет runtime Qwen context: локальный AGENTS/skill не читается
моделью автоматически. Передача знаний в planner и её влияние требуют своего
bounded context/protocol и измерения. Не повторять отрицательный combined
pipeline без нового механизма; сохранять V11/V16 как qualified control.
