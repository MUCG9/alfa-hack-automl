# Единственная точка входа нового чата

Сводка 22 октября 2026; новый чат НЕ должен читать всю историю переписки.
Текущее поручение — структурировать передачу и план, БЕЗ изменения кода.
Читать: AGENTS.md → этот файл → [реестр](EXPERIMENTS.md) → [план](PLAN.md).
[Готовый стартовый промпт](../prompts/next-agent.md). Остальные отчёты — по ссылке
нужного эксперимента, не целиком. Старые ACTIVE/STOP в них — датированные снимки.

## Три разных понятия, которые нельзя смешивать

|Роль|Версия|Фактическое состояние|
|---|---|---|
|Последний отправленный архив|V11 featureviews1|Одна разрешённая отправка, принято в очередь; последнее наблюдение счётчика 1→0|
|Текущий код|V16 mean1, runtime f72c6df|258unique+23repeated checks; обе full-default задачи завершены и CSV совпали с V11|
|Предыдущая отправленная контрольная версия|V9 roles1|Raw score2187.849; локальные F1 .653281240 /RMSE36.775244985|

**Новый официальный score V11 не проверен.** Не выдавать старые 2187.849 за V11.
Нового разрешения на submit нет, даже после обновления суточного счётчика.
[Receipt V11](../../release/v11-featureviews1/submission-20261022.json).
V16 НЕ отправлялась и НЕ улучшила V11: новые postprocessors выключены.

Полный локальный V11: searchF1 .663240317465, confirmation .655395369258,
mean **.659317843361**; regression searchRMSE38.902803731335,
confirmation31.991659384341,mean **35.447231557838**.
Относительно V9: F1+.006036603; RMSE−3.611%. Это reused-public validation,
НЕ независимый private test/обещание баллов. Runtime search+confirmation ≠полная CV.
Отдельный 3fold grouped CV feature views: pooled .640209809→.645099304.

## Проверка V16 закрыта, больше не ждать старую задачу

Ранее незавершённый controller15685 завершился exit0. Регрессия 221.052s,
классификация 2703.680s, по 12search trials, finalrefit/integrity PASS.
Проверены реальные SHA обоих итоговых CSV, все 12class recipes/metrics и final
iteration tree относительно V11. Новых fits для этой сводки не было.
[Компактное доказательство](../../release/v16-mean1/full-default-parity.json),
[полные assessments](../../release/v16-mean1/public-full.json).
Тяжёлых jobs этого запуска больше нет. Не перезапускать по старым 11/12 снимкам.

Архивы:
- V11 SHA fbbd2511652814d7c05334ab0240f18b81e88a7b59dfc979efa617011dc84490.
- V16 SHA 68e1eb0c933807720178ef4708df2c0dbf55fe9940b0dfb849d7704dbe3b2566.
- Class CSV af64a22a5e9f5ff26ed817dfaa707e77e5bd9500dc63e52748521b00670efa96.
- Reg CSV 05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673.

## Git и архитектура

Repo https://github.com/MUCG9/alfa-hack-automl,
актуальная ветка **work/llm-upgrade-20261022**, НЕ ambient-ветка agent-budget.
Main — сохранённая V2, не старт разработки. Последний submit receipt в 0b482c0;
завершённая parity evidence в c95765a, документационные commits идут после.
Фактические HEAD/tracking/dirtytree проверить перед работой. Не force/mainmerge.

Поток: task understanding → неизменяемые splits → search/planner → isolated
worker/adapters → confirmation/blend → full refit → validated submission.csv.
Canonical src/automl, соседние импорты через api.py; root shims не standalone.
Это модульное приложение с subprocess, не независимо развёрнутые HTTP-микросервисы.
[Границы](../architecture/implementation.md), [сборщик](../../tools/build_submission.py).

## Неприкосновенные ограничения и доступы

Python3.12,8CPU/32GB/noGPU/3h-task, solution.py, плоский ZIP root.py+original
requirements. SHA требований:
9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6.
Никаких runtimepip, новых зависимостей, внешних данных/pretrained.
Noop default; fitting-only preprocessing/stopping/calibration/encoding/resampling.
Public имена не хардкодить, df.eval/AST не считать полной sandbox.

Работа ОДНИМ агентом, частые логические commits. При 85%USED пятичасового окна
завершать этап/передачу, не reset credits/покупки. Новое поручение здесь — только docs.
Никаких новых агентов, сообщений в другие чаты, платных GPU, submit без разрешения.

Локально Python ../../work/ml-venv/bin/python (3.12.14),2threads/1.7GiB guard;
fixture suite1thread, все heavyfits строго sequential. Данные:
../../work/evaluation/{regression,multiclass}/task.md.10inputSHA:
[public_inputs.json](public_inputs.json). Data/venv/models остаются ignored и
передаются отдельно. Капитан разрешил перенос derived public кэшей V11/V16:
[комплект и восстановление](../../transfer/README.md). После получения файлов
из актуальной ветки выполнить python tools/transfer_caches.py verify, затем
python tools/transfer_caches.py restore. BASE-01 больше не блокируется отсутствием
этих кэшей после восстановления.852 файла/485 объектов, проверен полный roundtrip
и отказ перезаписи отличающегося файла. В исходных JSON абсолютные пути сохранены;
использовать печатаемый root_mapping, не переписывать исторические fingerprint.
Обновление комплекта добавляет четыре исходных confirmation_split.npz в небольшую
шестую часть objects-005.zip; прежние848 файлов и пять частей не менялись.
Если кэши уже восстановлены, обновить tools/transfer_caches.py и transfer/,
повторить verify/restore. Недостающие разбиения теперь не надо реконструировать.

Live Qwen текущего пути НЕ проверен, privateenv здесь отсутствовала. Старые V4
livecalls и новые mocks не доказывают новый liveend-to-end. Ключ из переписки не
извлекать, обход защищённого ввода запрещён.600RUB — общий лимит, не баланс.
AutoGluon уже есть и реально испытан; Optuna/FLAML/LAMA локально отсутствовали,
хотя их pins есть в originalrequirements. Ничего не устанавливалось.

## Первый результат от нового чата

Кратко подтвердить понимание: отправленный V11, код V16, parityPASS, результаты
и 3 следующих приоритета. Сообщить недостающие данные/доступы. Не начинать
переписывание/обучение/новую отправку до отдельного поручения на реализацию.
