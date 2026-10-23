# Alfa Hack AutoML: V11/V16 и Qwen autoresearch

Продолжение23Oct — [work/qwen-optuna-mvp-20261022](https://github.com/MUCG9/alfa-hack-automl/tree/work/qwen-optuna-mvp-20261022).
Четырёхэтапный Qwen MVP завершён с проверенными refits/CSV: Macro F1 .654485,
RMSE36.024693. Он уступил qualified V11/V16 (.659318/35.447232); default
Optuna и CatBoost selection остаются OFF. Последовательные component screens
и итерации harness описаны в [разборе](docs/experiments/research_conclusions_20261023.md),
текущие jobs — в [AGENTS.md](AGENTS.md) и фактических локальных receipts.

[Новый opt-in профиль](release/qwen-incumbent-mix1/README.md)
`--research-profile incumbent_mix` **полностью проверен**: MacroF1 .659318,
RMSE **35.397298** против35.447232 у контроля, оба regression cuts улучшились.
352source/23exact-unpacked checks и отдельно30dev checks PASS; full refit,
оба CSV/source/input integrity verified. Class augmentation отклонён grouped
CV, поэтому в профиле сохранён прежний полный classification control.
[Полный результат и ограничения](docs/experiments/pipe02_complete_20261023.md).
Это frozen learned priors, final verification offline; default search сохранён.

По запросу создан [скилл autoresearch-ml](skills/autoresearch-ml/SKILL.md) на основе
[Andrej Karpathy autoresearch](https://github.com/karpathy/autoresearch):
фиксированный evaluator, ограниченные эксперименты, проверка по метрикам,
сохранение отрицательных результатов и rollback через Git. Installed copy:
`~/.codex/skills/autoresearch-ml`. Навык не входит в конкурсный ZIP.

**Для нового чата:** [единая точка входа](docs/handoff/START_HERE.md),
[реестр экспериментов](docs/handoff/EXPERIMENTS.md),
[план](docs/handoff/PLAN.md), [готовый промпт](docs/prompts/next-agent.md).

Предыдущее продолжение — [work/llm-upgrade-20261022](https://github.com/MUCG9/alfa-hack-automl/tree/work/llm-upgrade-20261022).
`main` сохранён как v2. Новые исходники и кандидаты не означают автоматически
новый официальный submit.

Полный default pipeline **V11** улучшил оба classification cuts: средний
**Macro F1 0,653281 → 0,659318**. Регрессия сохранена: **RMSE 35,447232**,
итоговый CSV побайтово совпал с history4. Обе задачи прошли refit/export/integrity.
Это локальная reused-public validation, не официальный score или обещание75–85/100.

[Квалифицированный ZIP V11](release/solution-v11-featureviews1.zip):230unique
source checks +23repeated exact-unpacked PASS. Добавлен типизированный ансамбль
двух представлений категорий с fitting-only cross-fitted статистиками.
Последний код V16:258unique+23repeated PASS; full-default parity ЗАВЕРШЕНА,
обе итоговые CSV совпали с V11. Пороговая оптимизация, AutoGluon, две target corrections и leaf10
не дали устойчивого выигрыша и НЕ включены по умолчанию. Requirements неизменны.

[Точное актуальное состояние](docs/handoff/current.md),
[промпт следующему агенту](docs/prompts/next-agent.md),
[разбор советов LLM](docs/experiments/v11_llm_review.md),
[журнал и результаты](docs/experiments/v11_progress.md).
Капитан разрешил одну попыткуV11: архив принят в очередь22октября, счётчик1→0.
[Подтверждение отправки](release/v11-featureviews1/submission-20261022.json).
Результат сервера не ожидался; нового официального балла пока нет.

## История предыдущих этапов

Ниже сохранены исторические снимки, а не актуальные STOP/ACTIVE поручения.
Статусы «integration не начата» для feature views заменены завершённым V11 выше.

Предыдущее продолжение: `work/cpu-research-20261022`, основа`a95c931`.
Капитан подтвердил результат V9: **2187.849**,1940.2s,«Лучшее решение»
(его оценка21.87/100); [запись результата](release/v9-roles1/result-20261022.json).
[Обзор CPU autoresearch и новая очередь экспериментов](docs/experiments/cpu_research_review_20261022.md).

**Новый проверенный локальный кандидат:** [solution-v10-history4.zip](release/solution-v10-history4.zip)
([проверки и ограничения](release/v10-history4/README.md)). Признаки последнего
доступного контекста и тренда включаются при достаточной fitting-истории.
Полный regression pipeline улучшил оба reused-public cuts: RMSE
39.321110/34.229380 →38.902804/31.991659; mean36.775245→35.447232 (−3.611%).
219unique source +23exact-unpacked checks, final refit/integrity и bounded full-size
class lifecycle прошли. Последующие тесты не меняют его runtime source.
Нового официального submit нет; прежний Macro F1 не выдаётся за новый полный run.

Классификационные исследования: under70 и fixed LGBM+ExtraTrees дали mixed
результаты и не меняют defaults. Fixed 50/50 ансамбль с cross-fitted категориальными
статистиками прошёл полный 3-fold CV: pooled Macro F1 .640210→.645099, все заранее
заданные gates PASS; runtime integration ещё не начат. Капитан попросил остановиться
из-за лимитов: [передача следующему агенту](docs/prompts/next-agent.md).
[Итог CV](docs/experiments/v10_class_te_cv_results.md), [журнал](docs/experiments/v10_progress.md)
и [протоколы/метрики](docs/experiments/v10_extratrees_results.md) сохраняют также
отрицательные результаты; public scores не гарантируют private-прирост.

- **Загружен v4**: [запись отправки](release/v4-history3/submission-20261022.json).
  Свежий reload в04:25UTC показал **2184.173** у точного имени v4 и времени05:21,
  осталось2попытки. Это raw score платформы, не перевод в100 и не hidden breakdown.
  Раннее смешение карточки со старым баллом v3 1723.691 сохранено в истории receipt;
  повторного upload не было.
- **Проверена v6**: `release/solution-v6-universal1.zip`, 137 уникальных repo checks
  и23 повторных exact-unpacked. Полный public цикл обеих задач пройден: mean RMSE
  **36.775244985**, Macro F1 **0.653281240**, refit/integrity pass. Новые контракты,
  независимые targets, limited query-NDCG, positive-label probability и optional
  XGB calibration. Это локальная public validation, не официальный балл.
- **V7 полностью проверена**:145unique /23repeated checks, обе public задачи
  byte-identical V6; live Qwen не проверен.
- **V9**: `release/solution-v9-roles1.zip`,169unique /23repeated checks; общий
  deadline/API ledger от discovery до export,64KiB metadata bound, безопасный
  структурный feedback и переиспользование frames. Модельные defaults не менялись.
  Full public gate завершён: обе задачи exit0/refit/integrity pass, CSV parity V7/V6.
  **V9 отправлена одной попыткой22октября около11:03MSK**, принята в очередь,
  осталось1попытка на момент отправки. Позже капитан сообщил2187.849;
  [receipt приёма](release/v9-roles1/submission-20261022.json),
  [результат со слов капитана](release/v9-roles1/result-20261022.json).
  Итог в [передаче](docs/handoff/current.md) и
  [release evidence](release/v9-roles1/README.md). SDK/HTTP tests используют local
  mock, а не Qwen. Две новые модельные гипотезы отвергнуты по измерениям.
- V5 contract1/multitarget1 тоже завершили обе public задачи с CSV parity v4.
  [Свежий промпт следующему агенту](docs/prompts/next-agent.md),
  [следующий план](docs/handoff/next_research_plan.md). Не начинать с main/v2.
- [Текущий журнал и ограничения](docs/experiments/continuation_20261022.md),
  [контракты](docs/experiments/v5_contract_work.md),
  [валидация](docs/experiments/v5_validation_work.md),
  [несколько целей](docs/experiments/v5_multitarget_work.md).

## Сохранённая модельная основа v4 history3

Агент автоматически строит контексты повторяющихся объектов по схеме и fitting
rows, проверяет будущий период и выбирает модель/ансамбль по метрике. Public column
names в код не внесены; pretrained модели и новые зависимости не добавлялись.

На одинаковых двух forward backtests полный regression pipeline улучшился:
средний RMSE **39.074979 →36.775245** (−5.89% относительно предыдущей v4 search2).
History3:39.321110/34.229380,12search experiments,confirmation,ensemble,fullrefit,
export,integrity=true. Это повторно исследуемая public validation, не official score.

[Точный кандидат и проверки](release/v4-history3/README.md):
`release/solution-v4-history3.zip`,59repo +23повторных unpacked checks passed.
[Файл для загрузки и финальная техническая проверка](release/v4-history3/SUBMIT.md):
полный regression и bounded classification экспортировали корректные CSV.
[Итог и ограничения](docs/experiments/v4_summary.md),
[промпт передачи](docs/prompts/next-agent.md).

Полный frozen v3 classification baseline: mean Macro F1 **0.653714716**.
Полный v4 history3: **0.652742609**, full refit/export и integrity проходят.
Регрессия улучшилась, классификация — немного хуже; по public нельзя обещать
общий private-прирост. Полная CV ранее отсеяла OVA+calibration.

По умолчанию --validation-strategy auto: консервативное определение числового
observation period по схеме и будущему test; v5 расширяет это на даты и явные
семантические группы. Явный legacy режим сохранён. Фактический статус текущих
jobs указан в журнале продолжения, старые снимки других компьютеров не актуальны.

**Продолжение с другого агента/компьютера:** начать с [AGENTS.md](AGENTS.md) и [CONTINUE_HERE](docs/CONTINUE_HERE.md). Готовый [промпт передачи](docs/prompts/next-agent.md), локальный CPU setup и ограничения проверок включены в репозиторий. Данные и API-key передаются капитаном отдельно.

В ветке `experiment/modular-augmentation` реализованы сервисные границы и политики данных. [Фактический статус миграции](docs/architecture/implementation.md) отделён от [исходного плана](docs/architecture/migration_plan.md). Это локальные компоненты с общими контрактами, не сетевой кластер микросервисов. `main` и отправленная v2 сохранены без изменений.

Замороженный [выпуск v3 и доказательства проверок](release/v3/README.md), включая exact ZIP и paired ablations, сохраняются отдельно от исходников. V3 отправлена 21.10.2026 в23:37 MSK, принятие в очередь подтверждено в `release/v3/submission.json`; это не официальный score.

Приватный репозиторий команды: [MUCG9/alfa-hack-automl](https://github.com/MUCG9/alfa-hack-automl). Карточки v1/v2 показывали 857.742/1694.145, v3 перед четвёртой загрузкой — 1723.691. Капитан также сообщает 16/100 для v3; связь шкал не раскрыта. Не переводить эти значения в RMSE/F1 или прогноз private.

Текущее продолжение выполняется одним агентом по поручению капитана. Прежние `docs/parallel_work.md`, `docs/v3_contract.md` и ролевые `docs/prompts/plus-*` — исторические задания, не инструкция одновременно редактировать старые корневые файлы. Используйте границы из `docs/architecture/implementation.md` и новые stage notes. Независимые multi-target модели реализованы ограниченным контрактом; ranking, совместные модели целей и SMOTENC не реализованы. Разбор записи организаторов — `docs/webinar_20261021.md`.

## Структура

```text
solution.py                                  прежний внешний CLI
src/automl/contracts/                         версионируемые сообщения и DataPolicy
src/automl/task_understanding/                инвентаризация и схема задачи
src/automl/evaluation/                        split, метрики, калибровка
src/automl/search/                            портфель, Qwen, отбор и refit
src/automl/execution/                         worker, adapters, sampling, augmentation
src/automl/publishing/                        валидация и запись ответов
src/automl/infrastructure/                    API, лимиты, runtime, атомарная запись
src/automl/compat/                            временная совместимость v2
agent_*.py / model_utils.py                   dev-адаптеры, не canonical исходники
requirements.txt                             оригинальные зависимости платформы
program.md                                   общий протокол исследований для команды
docs/                                        материалы капитану, prompts, evidence
tests/                                       offline unit, end-to-end и fault tests
scripts/benchmark_release.py                 прогон скомпилированной копии; default sequential
tools/benchmark_candidates.py                paired recipes, full OOF или forward backtests
tools/build_submission.py                    детерминированный flat ZIP и SHA manifest
tools/verify_release.py                      23 проверки из распакованного ZIP
scripts/package_solution.py                  совместимый вызов нового сборщика
release/solution-v1.zip                       неизменённая отправленная версия
release/solution-v2.zip                       точная вторая отправленная версия
docs/prompts/                                три задания: Pro, Plus models, Plus runner
docs/webinar/                                транскрипт, SRT, аудит и HTML-разбор
```

Порядок чтения: `AGENTS.md` → `docs/CONTINUE_HERE.md` → `docs/architecture/implementation.md` → `release/v3/README.md`. Старые `program.md`, `docs/parallel_work.md` и материалы капитану использовать как историю, а не актуальное назначение владельцев. Право merge и фактический deadline утверждает капитан.

## Запуск

Используйте Python 3.12 и разрешённые версии из `requirements.txt`. Устанавливайте зависимости только в среде разработки, не из `solution.py`. Секрет задавайте через менеджер секретов или переменную окружения `OPENAI_API_KEY`, без помещения в Git, файл README или общий prompt. `OPENAI_BASE_URL` и `OPENAI_MODEL` берите из инструкции организаторов. На платформе их задаёт среда.

```bash
python3 solution.py /absolute/path/to/task.md --max-experiments 3 --time-budget 1200
python3 tests/test_v2.py
python3 tests/test_resilience.py
python3 tests/test_data_policy.py
python3 tests/test_architecture.py
python3 tests/smoke.py
python3 scripts/package_solution.py --output dist/solution.zip
```

Smoke tests не обращаются к Qwen, создают маленькие synthetic задачи в `test-runs/`. Для public end-to-end скачайте разрешённые данные организаторов отдельно и передайте путь к `task.md`. Исходные CSV не включены в репозиторий. `submission.csv` и отчёты появятся рядом с условием. Прогнозы уже проверенных public прогонов сохранены в отдельном комплекте капитана `team_handoff.zip`, но исключены из Git. Это примеры, а не замена агенту.

По умолчанию: 9900 секунд, до 12 поисковых экспериментов, до 4 обращений-планов Qwen, 4 CPU-потока. Затем — подтверждение до трёх лучших рецептов на seed 43, условный ensemble и финальное обучение. Рабочий CSV сохраняется до дорогих операций. Политика данных по умолчанию `identity/noop`; регрессионный портфель также сравнивает один bounded masking-кандидат с немодифицированным контролем. При отказе API работает детерминированный поиск; `--offline` исключает обращения к Qwen. Для полного прогона:

```bash
python3 scripts/benchmark_release.py --task /data/reg/task.md --task /data/class/task.md --output /work/check-v2
```

Каталог результата должен быть новым. Скрипт компилирует flat-модули, копирует объявленные входные файлы, сохраняет SHA и логи; не отправляет сабмит. По умолчанию задачи идут последовательно для экономии RAM, `--jobs 2` разрешает параллельный запуск, `--threads 2` уменьшает CPU на слабом ПК (default4). `results.tsv` фиксирует решения, `provenance.json` — контроль неизменности. Search и confirmation не являются независимым private test.

На платформе команда запуска строго `python3 solution.py task.md`. Сборщик преобразует импорты исходников из `src` в уникальные плоские модули. Только корневые `.py` и исходный `requirements.txt` попадают в ZIP; без документов, tests, weights, данных, JSON-конфигов и подпапок. Нельзя вручную архивировать корневые dev-адаптеры: без `src` они не работают.

## Что изменено и как проверено

В v2 исправлены неработавшие настройки глубины/row subsampling, stopping по неподходящей метрике, слишком узкий поиск и грубое балансирование классов. Добавлены inner stopping, мягкие веса классов, проверяемый ensemble, наследование рецептов, защита от старых результатов и контроль формата вероятностей. На реальном proxy проверено отключение reasoning, которое предотвращает расход всего ответа на внутренние рассуждения. Никакая настройка модели не считается улучшением без измерения.

Повтор неизменённой v1 в режиме платформы дал локально RMSE 43.61588 и Macro F1 0.61564. Ранние значения 43.60655 / 0.60358 относились к другому поисковому запуску; Qwen делает поиск стохастическим. Результаты и ограничения итоговой v2 — `docs/v2_validation.md`, решения по review — `docs/v2_review_notes.md`, обоснование адаптации autoresearch — `docs/autoresearch_decision.md`. Text проверен на synthetic, private не проверен. Python-процесс с AST-фильтром не является полноценной security sandbox.

Отправленная v2 имеет SHA-256 `b429f04a231b5fa7f5fb52d8008aa019dbc6c53cc6e5f81a6ff06999edc1602a`; manifest и запись отправки — `release/v2/`. V1 сохранена отдельно. Упаковщик не перезаписывает существующий release и не отправляет его на платформу. Следующая попытка требует решения капитана.

Для CPU-разработки используйте отдельное Python 3.12 окружение. Проверенные версии основных пакетов: numpy 1.26.4, scipy 1.12.0, pandas 2.2.3, scikit-learn 1.5.2, lightgbm 4.6.0, catboost 1.2.8, xgboost-cpu 2.1.4, openai 1.68.2, psutil 6.1.1. Полный исходный requirements содержит и неиспользуемые этим агентом пакеты; его полная установка может быть тяжёлой. `xgboost-cpu` предоставляет импорт `xgboost` для локального CPU, это не изменение платформенного requirements. Локальная среда не является официальным Docker.

Репозиторий создан по просьбе капитана. Issues и Project пока не опубликованы, приглашения участникам и календарные приглашения не отправлялись. Задачи подготовлены в `docs/github_issues.csv`, правила работы — в `CONTRIBUTING.md`.
