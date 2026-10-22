# Промпт для продолжения исследования v4

Продолжай работу над Alfa Hack AutoML как разработчик и исследователь ML.
Пользователь разрешил поэтапное улучшение качества, обучение и Qwen API в разумных
пределах; затем попросил закончить текущий этап, подготовить передачу и запушить
результат. Приоритет — метрика, ресурсы второстепенны в пределах платформы
8 CPU /32 GB /3 часа. Не запускай дополнительных агентов, не merge main,
не отправляй официальный submission автоматически.

Пользователь дополнительно попросил делать коммиты чаще, после завершённых
логических этапов. При приближении к10% остатка лимита останови новые долгие
эксперименты, сохрани результаты и самодостаточную передачу. Позднее пользователь
сообщил о пополнении лимита и разрешил продолжить текущую работу.

## Репозиторий и обязательное чтение

Репозиторий https://github.com/MUCG9/alfa-hack-automl . Продолжай от ветки
`work/pipeline-review-instructions`, создай собственную рабочую ветку от её HEAD.
`experiment/modular-augmentation` — прежняя интеграция `a9af568`, `main` — сохранённая
v2. Прочитай `AGENTS.md`, `docs/experiments/v4_research.md`,
`release/v4-candidate/README.md`, затем нужные исходники. Исторические
`docs/CONTINUE_HERE.md`, `docs/architecture/implementation.md` и `release/v3/README.md`
не описывают полностью v4. `docs/architecture/quality_plan.md` — backlog, не список
реализованных методов.

Canonical код — `src/automl`; root agent_*.py/model_utils — shims. Импорты соседних
компонентов проходят через api.py. ZIP собирается `tools/build_submission.py`;
только плоские .py и исходный requirements. `requirements.txt` менять нельзя,
SHA `9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
V1/V2/V3 архивы и evidence сохранены. Новый ZIP:
`release/solution-v4-candidate.zip`, manifest и проверки в `release/v4-candidate/`.
Это кандидат исследования, не официально отправленный/подтверждённый победитель.

## Официальная обратная связь пользователя

22.10 пользователь сообщил: общий балл второго решения1694.145, около16% по уточнению пользователя, RMSE43.62 →41.99,
Macro F1 .6156 →.6534. Позже получен скриншот: первое857.742 (~8%), второе1694.145 (~16%);
v3 ещё «Проверяется». Точная привязка к SHA архива не подтверждена. `docs/experiments/official_scores_20261022.json` сохраняет запись.
Нельзя называть эти значения метриками нового v4 или переводить локальный прирост
в официальный score: baseline нормирования на независимом тесте неизвестен.

## Среда, данные, ключ

На этом ПК cwd `/home/dima/Документы/ml/alfa-hack-automl`.
Данные уже в ignored `public_tasks/classification/` и `public_tasks/regression/`;
все десять SHA совпали с `docs/handoff/public_inputs.json`. На другом ПК получи
разрешённые public inputs из официальной папки кейса, проверь SHA. Raw CSV,
предсказания, веса и virtualenv в Git отсутствуют.

Среда реальных измерений: `test-runs/venv-core/bin/python` (Python3.12.3,
system-site-packages включены, core ML локально закреплён), numpy1.26.4,
scipy1.12.0,pandas2.2.3,sklearn1.5.2,LGBM4.6.0,xgboost-cpu2.1.4,CatBoost1.2.8.
`.venv` отдельно установлена, но в измерениях не использовалась. На новом ПК
подними CPU venv по `requirements-dev-cpu.txt`; исходный runtime requirements
не заменять. Зафиксируй фактические версии.

У ПК 8 GiB RAM, мало доступной памяти, swap почти заполнен. Тяжёлые jobs строго
последовательные, AUTOML_THREADS=2, OPENBLAS/OMP/MKL_NUM_THREADS=2, memory-gb1.7.
Полноценному search нужен внешний watchdog10100sec, штатный budget9900.
Watchdog1200sec в отдельном recipe benchmark — локальный guard, не лимит платформы.
Все наши фоновые benchmark и приватный API-процесс должны быть закрыты к передаче;
не рассчитывай на оставшиеся jobs или сохранённый ключ.

Qwen API пользователь разрешил. Рабочие параметры из инструкции организаторов:
OPENAI_BASE_URL=https://changellenge.up.railway.app/v1,
OPENAI_MODEL=qwen/qwen3.8-27b. Ключ ранее передавался в беседе; в Git/файлах его нет.
Настрой приватное окружение/secret manager; не вставляй ключ в prompt, shell history,
логи, исходники, CSV, README или workers. Общий командный лимит600/день, reset03:00МСК.
Проверяй /key/info и usage; разность общего spend включает возможную работу команды.
На ключе уже проверены реальные feature-only вызовы Qwen. Свежий полный online
прогон итогового агента ещё нужен. Без приватного ключа выполняй offline часть.

Кейс запрещает предобученные модели. Используй только предоставленный train для
обучения. LSA/TF-IDF с нуля допустимы; pretrained sentence embeddings не добавлять.

## Что реализовано

P0: watchdog отслеживает принадлежащие Popen процессы вместе с detached workers,
cleanup при исключениях, проверка worker exitcode; inner/outer/full preprocessing
учатся отдельно; ошибки fit не скрываются как rare-class fallback; распакованный
release выбирает собственный worker даже внутри checkout. P0 дал побайтную parity
validation/submission CSV для обеих public задач на seeds42/43.

Evaluation: make_folds с exactly-once OOF и защитой от exact-hash group overlap;
запись отсутствующих validation классов (SGKF не гарантирует идеального баланса),
запрет missing fitting classes. make_time_split с whole-period forward backtests.
Метрики дополнены per-class precision/recall/support/confusion matrix.

Runtime default `--validation-strategy auto`: консервативно выявляет документированный
числовой период, если весь test лежит позже train; built-year/age не считаются
периодом наблюдения. Проверяет допустимость split, записывает warning/fallback.
Старый режим `--validation-strategy legacy` сохранён. Для time confirmation использует
предыдущий период. Полная K-fold CV — dev инструмент, не runtime search по умолчанию.

Новые opt-in: cross-fitted target encoding, composite groups, автопоиск повторяющихся
контекстов только по fitting X, smoothing/counts/recency; LGBM one-vs-all;
training OOF decision factors; до3 парных специалистов редких классов; TF-IDF +
logistic/TruncatedSVD. Новые зависимости и pretrained модели не добавлялись.
Для time-регрессии portfolio начинается с auto-history smoothing2 и отдельного
history+log-target кандидата, затем консервативный/прежние модели. Default
classification portfolio сохранён: новых методов по paired screening недостаточно
для заявления об улучшении всего агента.

## Измеренные результаты

`docs/experiments/v4_results.json` содержит все завершённые рецепты, исходные hashes,
input/split hashes, primary/per-class F1, время/RSS/статусы. В
`release/v4-candidate/research_sources/index.json` восемь точных source ZIP снимков
с source-manifest hashes, без данных/ключей. Они позволяют воспроизвести этапы,
которые предшествовали последним изменениям. На этом ПК подробные outputs остались
в `/tmp/alfa-*`, configs/logs — ignored `test-runs/stages/`. После reboot /tmp может
исчезнуть, поэтому опирайся на tracked evidence/recipes/snapshots.

Регрессия, одни forward outer cuts (train<5→val5; train<4→val4):
- Первый fixed LGBM control: RMSE52.912918/44.564333.
- Auto-history smoothing2:43.148597/37.749473, MAE тоже лучше на обоих.
  Средний RMSE ниже на17.01% против первого рецепта; это НЕ17% official score.
- History+log:41.002541/38.062736; добавлен отдельным кандидатом, не принудительно.
- Явно заданные вручную группы:43.115491/34.373065 — диагностическая гипотеза,
  public имена не захардкожены в продукт. Есть резерв улучшить универсальное
  выявление постоянного контекста или запросить такие группы у Qwen.
- CatBoost600/1600/depth8, XGB+history, counts/refinement не выиграли устойчиво.
- Fixed selected_recipe старого полного v3 ансамбля (XGB8/XGB10/LGBM255,
  .5/.25/.25), повторно обученный из frozen ZIP на тех же outer cuts:
  79.475395/41.262690. Это ретест фиксированного ансамбля с прежним inner stopping,
  НЕ полный повтор всего v3 search на каждом backtest и НЕ официальный score.

Классификация seeds42/43:
- Первый control .646329/.648113; уже существующая inner calibration
  .650293/.652794 — более сильный fixed control.
- OVA .651574/.649883; OVA+calibrate .649378/.656524;
  OVA+target encoding .650943/.653535. Улучшения небольшие.
- Сильнее class weights, больше листьев, minimum300/600trees, Qwen features,
  OOF decision factors и парные специалисты не дали устойчивого выигрыша.
- Полная CV финалистов и полный default classification search ещё НЕ выполнены
  в этом этапе. Bounded lifecycle не считать полным поиском.
- В train есть1458 одинаковых feature-групп с разными labels,14829/87670строк.
  В них70.9% Analysis и72.6% Backdoor; см. v4_class_ambiguity.json. Это описательная
  диагностика, не оценка обобщения и не повод удалять конфликтные validation rows.

## Что делать дальше по порядку

1. Проверь git/status, manifest и итоговые tests/lifecycle в release/v4-candidate.
   Сначала завершай нижеуказанные проверки качества; не добавляй новый стек сразу.
2. Полная 3-fold CV классификации: первый контроль, сильный v3 inner-calibration,
   лучший устойчивый новый рецепт. Готовый набор `docs/experiments/v4_class_cv_candidates.json`.
   Команда (новый output):

   OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLCONFIGDIR=/tmp/alfa-mpl \
   test-runs/venv-core/bin/python tools/benchmark_candidates.py \
     --archive release/solution-v4-candidate.zip \
     --task public_tasks/classification/task.md \
     --candidates docs/experiments/v4_class_cv_candidates.json \
     --output /tmp/alfa-next-class-cv --folds 3 --threads 2 --memory-gb 1.7

   Сравни все folds, fold mean/std и pooled OOF, class order/coverage/group overlap.
   Не донастраивай factors/weights на этих же OOF с заявлением unbiased score.
   При близких результатах оцени разброс и оставь сильный контроль в portfolio.
3. Закончи полный default v3 classification **offline** (ранее были лишь interrupted
   runs) и полный v4 offline на обеих задачах, последовательно, одинаковые лимиты.
   Для старого ZIP у benchmark_release нужен явный trusted SHA:
   `--archive release/solution-v3.zip --expected-archive-sha256 cba6a5aa01264c36fe67dad188e949b934557c0502bccf221e488578867032b8`.
   Остальное: `--offline --jobs 1 --threads 2 --memory-gb 1.7 --watchdog-seconds 10100`,
   `--task .../task.md --output /tmp/NEW-DIR`. **Не ставь --max-experiments1**, если
   называешь это default search. Для v4 не указывай historical SHA: требуй совпадения
   с текущим canonical source. После изменения src сначала собери новый архив.
4. Затем с приватным API окружением проведи полный Qwen run нового кандидата на
   обеих задачах; offline и online сравнения разделяй. Сохрани планы, effective
   parameters, usage/cost, failures, search/confirmation, full refit и SHA CSV.
   Наличие успешного ответа Qwen не означает полезности предложенного метода.
5. Проверяй регрессию на forward cuts; legacy random holdout используй только для
   исторической parity. Для новых context/history алгоритмов обучай обнаружение
   групп и статистики заново внутри каждого inner/outer/full fit. Добавь ещё один
   ранний временной backtest для оценки устойчивости, если хватает history.
6. Если качество подтверждено, исследуй ограниченный OOF probability blend/stacking
   с отдельным уровнем проверки, semantic context groups от Qwen и копирование
   vs masking отдельной абляцией. Balanced-subset и SMOTENC остаются гипотезами,
   не реализованными возможностями. Не применяй всё одновременно.
7. После изменения src: шесть test scripts, новый flat ZIP, verify_release (23
   unpacked compatibility/fault/smoke), публичные lifecycle/метрики, обнови evidence
   и handoff. Сохраняй честно ошибки и неполные runs. Требуемая изоляция — fitting
   rows в каждом fit, включая веса, preprocessing, augmentation и calibration.

Пуш рабочей ветки разрешён пользователем. Автоматический merge/main/official
submission не разрешены. Отчитывайся по проверенным локальным результатам,
не обещай скачок официальных баллов без независимой проверки.
