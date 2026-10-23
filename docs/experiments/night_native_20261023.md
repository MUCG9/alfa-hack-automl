# Ночной autoresearch на Windows, 23 октября 2026

Рабочая ветка `work/night-research-20261023` продолжает `7202aba`, а не устаревший main.
Прямое поручение капитана разрешает ML-эксперименты, использование выданного Qwen,
публикацию кода в указанном GitHub и условный submit после подтверждённого улучшения.
Исторические documentation-only и запреты новых fits не описывают текущее поручение.
Новых платных ресурсов и внешних обучающих данных не используется.

## Контроль и данные

Сильный complete-agent контроль V11/V16: regression RMSE 38.902803731335 / 31.991659384341,
mean 35.44723155783769; classification MacroF1 .663240317465 / .655395369258,
mean .6593178433614652. Эти reused-public cuts не являются private test.
Старый ordinary selector32 MVP regression уже дал отрицательные 36.02469255996805.
Новая Windows кампания — проверка переноса и воспроизводимости, а не обнуление истории.

Все десять public CSV/task.md скачаны по ссылке из предоставленного PDF. SHA совпали
с `docs/handoff/public_inputs.json`. Исходный requirements из вложения имеет SHA
`9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
Windows Git автоматически менял его LF на CRLF, ломая существующий build gate;
`.gitattributes` сохраняет этот файл побайтно. Pins не изменены.
Локально установлены используемые пакеты из исходного списка в отдельный Python3.12
venv, без полного тяжёлого AutoGluon/Torch. Это не официальный Docker.

## Замороженный MVP

`../frozen-mvp` — отдельная копия source7202aba. Изменения до её фиксации:
только переносимый учёт peak RSS и явное UTF-8 чтение job JSON. Координатор
передаёт `PYTHONUTF8=1`; это исправляет чтение кириллицы в Windows paths.
ML policy, original selector, evaluator и partitions сохранены.
Archive SHA: `8dd04d8da7b93f0440dbabea22d9a84aff399f049659200ffd24e5d2b30a935f`.

Live smoke3: organizer roles + planner, active CatBoost teacher, Optuna4,
full-refit/CSV/input-integrity — PASS, exit0,44.359s. Первые две проверки
сохранены: первая обнаружила неправильное чтение JSON; во второй selector
не понадобился при двух input columns/top2. Это не успешный active-selector test.

Public MVP запускает две задачи последовательно в общем10800s. Фиксированы
top32, Optuna8/900s, staged prompt, максимум14 search recipes и2 planner calls,
2 threads и2GiB local process guard. Он не делает Git writes, promotion или upload.
Фактические completed trials/timeouts/CSV необходимо читать из итоговых receipts.

## Следующие заранее объявленные проверки

1. FE-BROAD: bounded row-local broad features против тех же SINGLE controls;
   regression forward offsets0/1/2 и classification group cuts42/43. Сохранять
   raw inputs, не менять target/ID/evaluator. Отдельно off/broad/broad+protected32.
   Улучшение каждого cut требуется для продвижения компонента; для classification
   дополнительно gain без rarest class и loss<=.01 на классах с>=100 fitting groups.
2. REASONING: одинаковые staged prompt/context, terminal token ceiling16384,
   по одному call на off иxhigh. До обучения фиксировать source/candidates/splits;
   сравнить принятые предложения на одинаковых cuts и limits. Это exploratory
   сравнение двух стохастических calls, не статистическое доказательство effort.
3. HPO: исправить defaults sparse anchor по реальным adapters, не меняя searchspace;
   явно считать anchor/startup/guided/random и failed work. При полном component
   screen сравнивать TPE с equal-budget random; startup-only не называть guided TPE.
4. Полный агент с победившими компонентами: обе задачи, final-refit/CSV/integrity,
   source и exact-unpacked checks. До этих gates defaults и qualified release
   не продвигаются. Составное изменение маркировать exploratory procedure.

Каждый worker ограничен временем/памятью; expensive fits и fixture suites
выполняются последовательно. Пока frozen MVP работает, разрешена независимая
разработка следующего дерева и no-fit проверки; frozen execution source не менять.
Ошибки/timeout/OOM сохраняются без числового objective и не исключаются из набора задач.

## Qwen и внешние доступы

Малый live probe подтвердил alias `qwen/qwen3.8-27b`; default вернул311 reasoning
tokens, explicit xhigh174, high245, disabled0. Все четыре дали корректный terminal
JSON. Порядок и prompts/backend токенизация различались; superiority xhigh не доказано.
`reasoning_effort=xhigh` принят прокси, effective hidden effort не сообщён.
Текущий production defaultoff сохраняется до измеренного выигрыша ML-процедуры.
Shared budget endpoint показал spend2.4480768 из600 при ранней проверке; это snapshot,
не гарантия последующего остатка. Ключи находятся только вне Git в private coordinator.

GitHub API подтвердил аутентификацию MUCG9 и право push. Секреты не публикуются.
Открытие Changellenge браузером отклонено origin approval gate с причиной user
declined. Этот отказ не обходить другим транспортом/браузером. Локальная работа
продолжается; отправленный ZIP и официальный score нельзя заявлять без реального
успеха upload/evaluation.

## Вычислительная проверка кода и единиц измерения

Сгенерированный xhigh weather recipe создал полностью NaN `avg_daily_range`:
pandas вычитал две таблицы с разными именами колонок и выравнивал их по labels.
Fitting-X preflight подтвердил ноль пригодных значений на фиксированных2048 rows.
Отдельный code-only Qwen repair за3.875s явно переименовал правую группу колонок;
все пять derived features стали конечными на том же sample. Параметры модели,
исходный proposal и sample не менялись. Это проверка вычислений, не ML gain;
исходный и repaired recipes объявлены отдельными линиями для paired screens.

Ещё один семантический дефект старого generated recipe — вычитание календарного
года из ordinal period code. На public fitting CSV период имеет диапазон1..5,
календарный столбец0..2014 (ноль также требует трактовки missing/sentinel).
После clip(lower=0)99.9903% из51581 nonmissing значений равны нулю; это почти,
а не полностью constant feature. Общее правило: единицы и representation времени
проверять по dictionary, не выводить calendar age из порядкового индекса периода.
В будущем dominant-value fraction полезен как описательная диагностика; редкие
значения нельзя автоматически отбрасывать, поскольку они могут нести сигнал.

Новая four-stage реализация явно вызывает Qwen EDA до fits, сохраняет валидность
структуры assessment отдельно от attempted/error, изолирует несовместимые initial
proposals, оставляет raw columns в protected-selector arm и выбирает успешный
поддерживаемый HPO anchor, даже если лучший overall learner — ExtraTrees.
По результатам static review исправлена передача fatal cleanup failure через
multi-target recovery. Archive2b SHA:
`3084727f9fc84d40e025bac3d0ae56b063661a7571b0f37ecd851c47114fa117`.
Полные source448/exact-unpacked/live gates и ML screens на момент записи pending.
Предварительный79bccf archive сохранён без ML запусков, как и отрицательные receipts.
