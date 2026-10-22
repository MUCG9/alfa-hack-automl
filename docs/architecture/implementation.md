# Реализация модульной архитектуры, 21.10.2026

Ниже scope первоначальной миграции, не перечень возможностей v7. Позднее добавлены
CSV/TSV/file contracts, multiple targets, declared groups/dates, limited NDCG и
semantic input-role experiment. Актуальные реализованные ограничения и gates:
[current](../handoff/current.md); этот исторический текст их не отменяет.

Работа выполнена одним агентом в `experiment/modular-augmentation`. Main не менялся, другие агенты не привлекались. Исходный migration_plan — исторический документ; этот файл описывает реализованный scope.

## Поток исполнения и границы

```text
Task Understanding → TaskSpec + profile + ссылки на входы
Evaluation → immutable outer/confirmation split
Search → ExperimentRequest + recipe + DataPolicy
Execution subprocess → private predictions + fit/provenance metadata
Evaluation → измеренная метрика
Search → подтверждение / ensemble / SelectionPlan по смыслу
Execution → full refit
Publishing → проверенный финальный submission.csv
```

Соседний функциональный компонент импортируется только через `api.py`; это проверяет architecture test. Контракты не импортируют pandas, модели или API-клиент. Конкретные ML-библиотеки скрыты в пяти adapters и едином capabilities registry. Разработка остаётся в одном репозитории и окружении, транспорт — локальные вызовы и JSON/NPZ/CSV для subprocess. Это сервисные границы модульного приложения, а не независимо развёрнутые HTTP-сервисы.

Canonical code — `src/automl`. Корневые старые файлы — временные compatibility shims. Worker пишет только свои частные артефакты; официальный CSV выбирает и публикует координатор. Credentials доступны только gateway; из окружения worker удаляются ключи, токены и auth/proxy-переменные.

Версия сообщений `1.0`: TaskSpec, DatasetRef, SplitPlan, ExperimentRequest, DataPolicy, PredictionBundle, EvaluationResult, SelectionPlan. Это локальный контракт, не отдельный внешний стабильный SDK. Legacy payload сохраняется для совместимости; не все внутренние словари уже заменены dataclass. DatasetRef/SelectionPlan пока предусмотрены и тестируются как контракт, но legacy transport ещё не полностью переведён на них.

## Политики данных

- `identity/noop`: не менять строки, цели и уже существующие class weights. Это точный контроль v2.
- Weighting: source class counts до resampling, мягкие class weights, cap относительного веса, множитель кратности дубликатов `m^-beta`.
- Sampling: compression одинаковых `(features, label)` с суммой весов; diverse majority undersampling; умеренный oversampling редких классов.
- Augmentation: копии fitting-строк с пропусками только в частично пропущенных непрерывных признаках. Категории, ID, target и полностью наблюдаемые признаки не маскируются.

Каждый inner/outer/full fit заново применяет выбранную политику к своим fitting rows. Источники synthetic-строк записываются в `fit-parents-N.npz`, проверяется отсутствие пересечения с validation. Масштаб роста ограничен 25%; смесь методов имеет общий row budget. SMOTENC, генеративные модели и pseudo-labeling не реализованы и не выдаются за noop-успех.

Проверены два фиксированных разбиения public. Дубликатное снижение веса, ROS, compression, under85 и cap20 не дали устойчивого улучшения классификации на обоих folds; по умолчанию там noop. Masking 15% неоднозначен. Masking 25%, probability .15, synthetic weight .5 дал RMSE 41.9350/42.3946 против 41.9684/42.4855 у фиксированного контроля. Это небольшое локальное улучшение, не доказательство private-преимущества. В портфеле есть отдельные deep-XGB noop и masked варианты, выбор по измерениям, а не обязательная аугментация всех моделей. Новая глубина портфеля и model-specific fallback — отдельные изменения Search, не эффект чистого рефакторинга.

## Проверки и сборка

M0: неизменённый ZIP v2 повторно прошёл 23 старые проверки. M1–M4: сообщения, API boundaries, registry, flat compiler, политики данных, fault fallback, provenance. Новые тесты: 11 data-policy + 7 architecture; старые 11 + 7 + 5 выполняются также из распакованного ZIP. Итоговые результаты и точный SHA выпуска сохраняются в `release/v3/` после финального gate. GitHub отверг push активного `.github/workflows/ci.yml`: у текущего PAT нет scope `workflow`. Поэтому сохранён неактивный шаблон `ci-workflow.example.yml` рядом с этим документом. Локальные проверки выполнены, но GitHub Actions и branch protection не настроены. Расширение прав токена автоматически не запрашивалось.

`tools/build_submission.py` строит deterministic flat ZIP, проверяет уникальность имён, запрещённые импорты, компиляцию, исходный requirements и секретоподобные строки. `tools/verify_release.py` сравнивает байты с canonical source и запускает старые проверки в независимой распакованной папке. CLI не зависит от checkout/src или JSON/YAML-ресурсов.

Память ограничивается по process tree + controller (28 GiB), threads 1..8, учитываются время, свободный диск и размер артефактов. Это best-effort guardrails, не hard cgroup/RLIMIT sandbox. Локальные измерения на CPU не доказывают поведение официального Docker при предельной нагрузке.

## Git и дальнейшая независимая работа

Не редактировать корневые shims вместо canonical code. Одна рабочая ветка на задачу, PR только в experimental integration branch, один логический слой на PR. Контракты меняются перед потребителями; несовместимое изменение повышает major. Никакого force push и автоматического merge main. CODEOWNERS содержит только известный аккаунт капитана, не вымышленные назначения команде.

M6 сознательно отложен: SMOTENC, balanced-subset ensembles, псевдоразметка, произвольные форматы/имена файлов, multi-target/ranking и автоматическое time/group понимание. Текущий Task Understanding наследует CSV/один target/один ID. Text поддерживает только noop. AST-фильтр feature-code не является security sandbox. Исправление этих ограничений — отдельные функциональные ветки и тесты, не часть доказательства noop parity.

На 22:53 MSK реальный Qwen proxy вернул HTTP 503 с `Insufficient credits` у upstream OpenRouter. Key-info при этом показывал расход 63.35075 при лимите 600. Это внешняя недоступность, не исчерпание лимита данного ключа. Gateway имеет ограниченные повторы, журналирует отказ без ключа, затем поиск продолжает fallback. Расход API после ошибок нельзя считать полностью известным без usage ответа.
