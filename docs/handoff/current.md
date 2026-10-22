# Актуальное продолжение:22октября, v9

Последняя ветка **`work/agent-budget-20261022`**; основа `b11debf` из
`work/semantic-inputs-20261022`. Main по-прежнему v2 (`5dd6b0f`), не менялся.
Промпт `docs/prompts/next-agent.md`; журнал `docs/experiments/resume_20261022.md`.
Не клонировать main как актуальное решение; новая работа — от HEAD рабочей ветки.

## Что проверено

|Версия|Уникальные repo /повторные unpacked|Полный public цикл|Отправлена|
|---|---:|---|---|
|V4 history3 Python3.12.14|59 /23 на том этапе|обе задачи|да, один раз|
|V6 universal1|137 /23|обе задачи, refit/integrity pass|нет|
|V7 semantic1|145 /23|обе задачи, CSV parity V6|нет|
|V8 budget1|163 /23|отдельно не запускался|нет|
|V9 roles1|169 /23|запущен, финальный результат пока не подтверждён|нет|

V7 сначала прервалась: owned execution вернул143, прогресс остановился на4trials.
Частичный прогон НЕ засчитан. Новый classification-only завершён за1358.099s:
mean Macro F1 **0.6532812402233098**, итоговый CSV
`58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326`, идентичен V6.
Регрессия V7 тоже byte-identical V6/V4: mean RMSE **36.775244984792195**, CSV
`c1556d566cd24de3dc4bed107fbfe7f517dea14dd2c53c583545af08ed43f4e0`.
Evidence `release/v7-semantic1/public-full.json`. Это reused public validation,
не official/private score. V3 classification0.653714716 немного выше V6/V7.

## Точный последний архив

`release/solution-v9-roles1.zip`,69,565bytes,50flat root files, source `41cae86`.
SHA **`297647239badde608d349d053a89f9d7f98e8fffceb4a09633f675f99ebd7291`**.
169checks source-unchanged прошли за167.251s, плюс23повторных unpacked.
Оригинальный requirements SHA
`9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
Python3.12.14. Старые ZIP/manifests/evidence не перезаписаны.

V8 SHA `2522f6ef47194d92410ceffff22835610c1820ea4c330a2d6ad8c7b0b0ebaa07`;
V7 SHA `a31d1fc7c9bee3403f992f70467e95a446c19dbffdb4cdfea9abf2d035f79b27`.
V8 имеет отдельные unit/unpacked gates, не свой полный public run.

## Изменения после V7

- Один deadline от начала CLI, включая discovery, и общий API ledger для semantic
  mapping/planner/всех targets. `--max-llm-calls`0..16, default planner limit+2;
  HTTP retries и неизвестный usage учитываются отдельно. Это не дневной RUB cap.
  Детали: `docs/experiments/v8_run_budget.md`.
- Метаданные semantic mapping≤65,536UTF-8bytes, включая feedback. Ключи, сырые
  строки и error messages не попадают в общий ledger; неполный usage не называется
  нулевой ценой. Deadline перепроверяется после client setup и перед retries.
- Структурно неверные file roles дают один безопасный feedback retry в рамках
  прежних2attempts. Проверки row counts,targets/features,ID/dictionary; валидные
  frames переиспользуются. Parse/runtime/unsupported-metric ошибки terminal,
  никакого подбора «удобной» новой задачи. `v9_role_feedback.md` описывает scope.
- Модельные defaults/weighting/augmentation/outer splits НЕ менялись.

## Модельные исследования: не продвигать отвергнутое

|Гипотеза|Контроль mean Macro F1|Кандидат|Решение|
|---|---:|---:|---|
|XGB training OOF3 calibration вместо одного inner holdout|0.649134619|0.649029401|discard, mixed folds, медленнее|
|LGBM fixed50/50 seeds42/47|0.651543688|0.643384454|discard, хуже на обоих folds|

Парные данные/ошибки/recipes/source/input/split hashes сохранены в
`docs/experiments/v8_xgb_oof_calibration*` и `v9_lgbm_seed_blend*`.
Оба исследования использовали frozen V7 workers и завершились; CV/default
promotion не делали, так как predeclared keep criteria не выполнены.

## Текущий выполняющийся gate

Единственный тяжёлый job: `test-runs/resume-20261022/v9-public-full`, log рядом
`v9-public-full.log`; started около10:35MSK. Сначала regression task-00, затем
classification task-01. Offline, default12trials,2threads,1.7GiB tree guard,
10100s/task outer watchdog. Strict exact-archive/current-source gate пройден на
старте. Последующие правки пока docs only. До завершения не дублировать job.
Проверять aggregate `assessments.json` и report каждого task: exit0, refit,
integrity, CSV SHA. Не называть running/partial успешным и не завершать turn,
обещая, что незаконченный процесс обязательно переживёт передачу.

## API и разрешения

Live Qwen **не проверен**. Переменных organizer API в среде нет. Попытка hidden
stdin была policy-denied до ввода ключа; waiting terminal без ключа может ещё
существовать. Не обходить отказ или помещать ключ в argv/Git/prompts/logs.
`tools/live_smoke.py` принимает private environment/hidden input; loopback только
с fixed dummy key. Проверки real SDK→LOCAL FAKE HTTP→CLI→refit→CSV проходят,
но явно `local_mock_http`, не live Qwen. Расход/баланс реального API не установлен.

V4 загружен один раз; карточка показала raw **2184.173**,2попытки оставались.
Наблюдение: **07:25MSK (04:25UTC)**, upload time05:21MSK.
Receipt `release/v4-history3/submission-20261022.json` хранит точное наблюдение.
Не переводить в /100/hidden-final score. Новых submits не было; следующая загрузка
требует новой команды капитана. Нельзя main merge/force push/paid GPU/extra agents.

## Среда /лимит

Repo `/home/mucg9/Documents/Codex/2026-10-19/referenced-chatgpt-conversation-this-is-an/outputs/team-project`.
Python `../../work/ml-venv/bin/python`; public tasks в
`../../work/evaluation/{regression,multiclass}/task.md`,10SHA сверены с
`docs/handoff/public_inputs.json`. Raw CSV/predictions/venv/secrets не в Git.
numpy1.26.4/scipy1.12/pandas2.2.3/sklearn1.5.2/LGBM4.6/XGB-cpu2.1.4/CatBoost1.2.8.
Новые зависимости не ставили. Low-memory: heavy jobs последовательно,2threads;
TMPDIR/MPLCONFIGDIR внутри ignored `test-runs/resume-20261022/{tmp,mpl}`.

На07:37UTC primary used75%, осталось25%; при85% начать финализацию, не начинать
новые долгие этапы. Reset credits не тратили. Это историческое чтение, проверять live.
