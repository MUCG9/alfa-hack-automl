# CPU research после перехода на V9, 22 октября 2026

Новая рабочая ветка `work/cpu-research-20261022` создана от `a95c931` ветки
`work/agent-budget-20261022`. Это продолжение всех V4→V9, а не main/V2.
Старый checkpoint `work/pipeline-review-instructions` сохранён. ML-код и
исторические ZIP на этом этапе не менялись; новые пункты ниже — план, не результаты.

## Официальная обратная связь

Капитан подтвердил: `solution-v9-roles1.zip`, **2187.849**,11:03,
1940.2s,«Лучшее решение»; его оценка по шкале /100 —21.87.
Предыдущая карточка2184.173,05:22,3604.9s. Разница raw score+3.676.
Это сведения пользователя, кабинет заново не открывался. Формула нормирования,
отдельные RMSE/Macro F1 и причина разницы времени неизвестны.
[Новая запись результата](../../release/v9-roles1/result-20261022.json)
дополняет прежний receipt приёма в очередь, не переписывая его историю.

## Что завершено и что запущено

По актуальному checkpoint коллеги тяжёлых ML jobs нет. Обе полные offline public
проверки V9 завершены, final refit/export/integrity проходят; CSV совпадают с V6/V7.
Mean RMSE36.775244985,mean Macro F1 .653281240. Это многократно использованные
public folds, а не отдельные private-метрики. V9 имеет169unique repo checks и
23повторных unpacked. При переносе на этот ПК завершена только проверка исходников
в текущем CPU-окружении, новых модельных экспериментов не было.

Завершённые модельные эксперименты:

| Эксперимент | Mean Macro F1 контроль → кандидат | Решение |
|---|---:|---|
| XGB: один inner holdout → training OOF3 decision calibration |.649134619 → .649029401|Discard: разные направления folds, примерно двойное время|
| LGBM: seed42 → фиксированный42/47 blend50/50 |.651543688 → .643384454|Discard: оба folds хуже|

Это не повод повторять те же гипотезы под новым названием. Простые class-weight
powers, OVA+calibration, naive pair specialists, history counts/recency и общие
Qwen ratios/logs тоже уже проверялись; их ограничения сохранены в V4 studies.
XGB inner decision calibration, прошедшая более раннюю CV, уже есть в portfolio.

V7–V9 добавляют семантические роли файлов, проверку структуры, общий deadline/API
ledger, bounded metadata/feedback, несколько независимых targets и контракты.
Новый полный live Qwen mapping→planner→worker→refit→CSV ещё не проверен: тесты V9
используют mocks/local HTTP. Старые live planner calls V4 не доказывают новый путь.

## Почему CPU достаточно для подхода autoresearch

[Исходный autoresearch](https://github.com/karpathy/autoresearch#platform-support)
обучает небольшую LLM на NVIDIA GPU. Его зависимости (torch2.9.1,NumPy≥2.2.6,
pandas≥2.3.3) расходятся с платформенными pins. Не устанавливать его requirements
поверх окружения соревнования и не переносить CUDA/FlashAttention pipeline.

Полезный принцип: baseline → одна гипотеза → bounded fit → неизменяемый evaluator
→ сравнение → keep/discard → журнал/commit. Для нас Qwen предлагает признаки и
направления поиска; CPU обучает LightGBM/XGBoost/CatBoost. Текущий program.md уже
описывает такой цикл. Нужны улучшения механизма поиска и экспериментальная проверка.

Эмуляция не добавляет CPU физической мощности GPU. Например,
[Numba CUDA Simulator](https://numba.readthedocs.io/en/stable/cuda/simulator.html)
предназначен для отладки CUDA Python, а не универсального ускорения PyTorch.
Пакеты этого примера не предлагаются для установки на платформу.

## Разрешённые инструменты: приоритет применения

Версии ниже присутствуют в оригинальном requirements.txt. Это разрешённый список,
не подтверждение успешной установки всех AutoML пакетов на текущем ПК.

| Инструмент | Что проверять | Условия интеграции |
|---|---|---|
| **Optuna4.2.1** | TPE для существующих CPU adapters, раннее завершение слабых trials | Явный startup budget; core report/should_prune, без отсутствующего optuna-integration |
| **FLAML2.3.6** | CFO как отдельный bounded CPU кандидат/контроль поиска | `auto_augment=False`, точная метрика, наш outer split, whitelist моделей, память/watchdog |
| **AutoGluon Tabular1.3.1** | CPU bagging и один stacking level как отдельный кандидат | `num_gpus=0`, allowed model whitelist, sequential fitting, внешняя оценка и hard memory guard |
| **LightAutoML0.4.2** | Независимый CPU baseline из lgb/cb/linear_l2 | Явные use_algos/метрика/splits; собственный memory watchdog |
| sklearn1.5.2 / imbalanced-learn.12.4 | ExtraTrees, controlled balanced subsets | Fit-only preprocessing/resampling, исходные class counts и корректный перенос весов |

Primary references: [Optuna TPE4.2.1](https://optuna.readthedocs.io/en/v4.2.1/reference/samplers/generated/optuna.samplers.TPESampler.html),
[Optuna core pruning](https://optuna.readthedocs.io/en/v4.2.1/tutorial/10_key_features/003_efficient_optimization_algorithms.html),
[integrations](https://optuna.readthedocs.io/en/v4.2.1/reference/integration.html),
[FLAML2.3.6 source](https://github.com/microsoft/FLAML/blob/v2.3.6/flaml/automl/automl.py),
[AutoGluon1.3.1 fit](https://auto.gluon.ai/1.3.1/api/autogluon.tabular.TabularPredictor.fit.html),
[LightAutoML0.4.2 source](https://github.com/sb-ai-lab/LightAutoML/blob/v.0.4.2/lightautoml/automl/presets/tabular_presets.py).

TPE4.2.1 по умолчанию делает10startup trials: при общем лимите12 почти весь поиск
будет стартовым. FLAML использует `macro_f1`, AutoGluon — `f1_macro`; RMSE scorer
AutoGluon имеет обратный знак внутри higher-is-better API. Нельзя молча заменить
метрику на accuracy/logloss. AutoML нельзя отдавать бесконтрольный внутренний split:
feature groups и forward constraints должны соблюдаться внутри процедуры.
Foundation/pretrained models запрещены; runtime pip и новые зависимости запрещены.
Torch2.5.1 CPU разрешён, но обучение собственной нейросети — отдельная гипотеза,
не необходимая инфраструктура исследовательского цикла.

## Предлагаемая очередь — пока не запущена

1. **Аудит и абляция отбора финалистов.** Контроль — frozen V9 pool12trials,
   те же3confirmation slots. Кандидат — лучший представитель каждого из трёх
   семейств вместо top2+условного третьего. Сейчас runner.py260–264 ищет новую
   family только когда первые два из одной family. Сначала cached replay при
   наличии всех нужных predictions, затем отдельная внешняя проверка процедуры.
   Не объявлять такую диагностику независимой оценкой качества.
2. **Более широкий адаптивный поиск.** Runtime default12trials, hard cap14;
   public class закончил около1250s при9900s budget (в snapshot оставалось≈8650s),
   regression≈215s. Гипотеза: подбор параметров и ограничение числа trials
   оставляют полезный CPU-budget неиспользованным. Сравнить отдельно расширенный
   deterministic/random контроль и TPE при одинаковом deadline, с зарезервированным
   временем для confirmation/refit. Инициализировать сильными существующими
   controls; один bounded диапазон параметров за исследование. Pruning через
   fitting-only промежуточные оценки. Tuning внутри outer fitting rows; финальные
   outer folds не превращать в optimizer objective. Число trials — результат
   budget manager, не обещание успеть сотни моделей на любых private данных.
3. **Новый history block регрессии.** Frozen metadata-history/log контроль
   против strictly-as-of last-period context value +trend. Группы/модель/smoothing
   сохранить. Это новые признаки относительно прежних mean/counts/half-life.
   Для каждой fitting строки используются только периоды<её периода; контекст
   определяется по fitting X. Нужны perturb-future-label invariance и проверка
   минимум двух прежних cuts +одного заранее выбранного старшего cut.
4. **CPU AutoGluon bagging/stacking.** Как отдельная альтернативная процедура,
   сначала классификация:3bag folds,одинstack level,whitelistGBM/CAT/XGB/XT,
   sequential,hard RAM/time guards. Сравнить с V9 на одинаковых outer folds и
   resource budget. Нельзя использовать обычные IID folds поверх duplicate groups
   или будущих периодов; без контроля splits такой результат не сопоставим.
   Сначала проверить pinned install/import/API в отдельной CPU-среде.
5. **ExtraTrees diversity / balanced subsets.** Два независимых будущих
   исследования: заменить один объявленный fallback на ExtraTrees (adapter уже
   есть) ИЛИ3-model balanced subsets против3-model no-sampling control с теми же
   model seeds. Fixed ensemble и per-component under уже поддерживаются;
   автоматическая новая политика пока не внедрена. Не смешивать эти изменения.
6. **Calendar features для универсальности.** Declared datetime → calendar/cyclic
   block без ID/target. Datetime split уже существует, а систематических календарных
   признаков нет. Нужны заранее новые датированные fixtures/labelled задачи;
   на текущих двух public задачах применимость ограничена.

Порядок1→2→3 выбран для начала;4–6 — альтернативы после результатов, не запуск
всего backlog. На этом ПК heavy fits последовательно,2threads и local memory guard;
платформа даёт8CPU/32GB/3h на задачу. Не путать локальные ограничения с платформой.

Keep: все jobs/refit/export исправны, направление поддержано paired outer cuts,
затем подходящая CV/дополнительный time cut; fold mean и pooled OOF отдельно.
Изменение selection/stacking требует внешней оценки всей процедуры, не только
повторного веса на её же OOF. При сомнительном результате discard; никакого
прогноза прироста официальных баллов по reused public данным.

## Проверка переноса на этот ПК

169unique checks прошли на Python3.12.3 с неизменённым source. Первый общий запуск
дал167checks в полностью прошедших scripts и ошибку HTTP script: sandbox запрещал
socket127.0.0.1. Оба HTTP checks отдельно повторены с разрешённым loopback и прошли
за31.321s; используются только mock и фиксированный dummy key. Первый неуспешный
общий run не назван passed. [Combined evidence](../../release/v9-roles1/local-transfer-check-20261022.json)
сохраняет исходный статус и retry, хеши source/tests и реальные package versions.

V9 ZIP сохранён с прежним SHA. Имена50flat файлов совпадают;49Python AST совпадают
с текущим compiled source. Побайтное сравнение на нашем Python3.12.3 отличается
от Python3.12.14 коллеги только кавычками одного f-string в automl_runner.py
(ast.unparse); AST одинаковый. Не объявлять exact-byte gate пройденным на этом ПК
и не перезаписывать V9 ради форматирования. Его прежний3.12.14 exact gate сохранён.
После будущих изменений src собирать отдельный новый candidate под своей средой.

Новой официальной отправки не было. ML-код/requirements/старые артефакты сохранены.
