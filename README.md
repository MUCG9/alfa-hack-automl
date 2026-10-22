# Alfa Hack AutoML: исследовательская v4

Свежая [history3 сборка](release/v4-history3/README.md): автоматические контексты
по схеме,59repo +23unpacked checks. Fixed forward RMSE40.960973/33.984412;
полный regression run проверяется. [Статус](docs/experiments/v4_progress.md).

В рабочей ветке v4 добавлены исправления исполнения, полная CV/OOF как отдельный
режим измерений и новые методы обучения. Главный измеренный результат — перенос
регрессионной проверки на будущий период и train-only исторические признаки:
автоматический вариант снизил RMSE с 52.9129/44.5643 до 43.1486/37.7495 на двух
forward backtests. Это public validation, не официальный score. Подробности,
контроли и ограничения — [журнал исследования](docs/experiments/v4_research.md).

[Кандидат v4 и evidence](release/v4-candidate/README.md): 57 repo проверок,
23 проверки распакованного ZIP, два успешных полноразмерных bounded lifecycle
с refit/export. [Полная CV финалистов завершена](docs/experiments/v4_cv.md): OVA+calibration
не подтвердила выигрыш и не включена в default. Полный default поиск продолжается. [Следующая сборка search2](release/v4-search2/README.md)
исследует capacity XGBoost при сохранённых весах, прошла58repo и23unpacked
проверки; прирост её метрики ещё не измерен.

По умолчанию `--validation-strategy auto`: только при однозначном документированном
числовом периоде и полностью будущем диапазоне test применяется forward validation;
остальные задачи сохраняют прежний split. `--validation-strategy legacy` позволяет
явно воспроизвести старую стратегию. Для временной регрессии в портфеле есть
cross-fitted история автоматически обнаруженных повторяющихся контекстов.

**Продолжение с другого агента/компьютера:** начать с [AGENTS.md](AGENTS.md) и [CONTINUE_HERE](docs/CONTINUE_HERE.md). Готовый [промпт передачи](docs/prompts/next-agent.md), локальный CPU setup и ограничения проверок включены в репозиторий. Данные и API-key передаются капитаном отдельно.

В ветке `experiment/modular-augmentation` реализованы сервисные границы и политики данных. [Фактический статус миграции](docs/architecture/implementation.md) отделён от [исходного плана](docs/architecture/migration_plan.md). Это локальные компоненты с общими контрактами, не сетевой кластер микросервисов. `main` и отправленная v2 сохранены без изменений.

Замороженный [выпуск v3 и доказательства проверок](release/v3/README.md), включая exact ZIP и paired ablations, сохраняются отдельно от исходников. V3 отправлена 21.10.2026 в23:37 MSK, принятие в очередь подтверждено в `release/v3/submission.json`; это не официальный score.

Приватный репозиторий команды: [MUCG9/alfa-hack-automl](https://github.com/MUCG9/alfa-hack-automl). По скриншоту капитана **v2 получила 1694.145**, v1 — 857.742. Это значения карточек, не RMSE/F1 и не прогноз private. Официальный результат v3 не известен до проверки платформой.

Текущая реализация сделана одним агентом по поручению капитана. Прежние `docs/parallel_work.md`, `docs/v3_contract.md` и `docs/prompts/` — исторические задания, не инструкция одновременно редактировать старые корневые файлы. Для новой работы используйте границы из `docs/architecture/implementation.md`. Multi-target/ranking не реализованы. Разбор записи организаторов — `docs/webinar_20261021.md`.

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
