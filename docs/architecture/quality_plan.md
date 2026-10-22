# План следующей итерации: качество модели

Актуальный backlog и статус на этапе v7: [next_research_plan](../handoff/next_research_plan.md)
и [current](../handoff/current.md). Этот документ — исторический план. Nested
preprocessing, fit-error isolation, owned-process watchdog и полная development CV
уже реализованы. Runtime full OOF selection по-прежнему не реализован. Не повторять
исправления, не сверив код, тесты и stage evidence.

Дата review: 22.10.2026, Europe/Moscow. Основа: integration commit `a9af568`.
Это исходный план экспериментов. Фактически реализованное и измеренное описано
в [v4_research.md](../experiments/v4_research.md); пункты backlog не являются
заявлением о готовности методов.
Первый запрос разрешал review и обновление инструкций. Следующим сообщением
22.10.2026 капитан разрешил реализацию по этапам, обучение, измерения и использование
командного Qwen API. Официальный submit этим сообщением не запрошен.

## Цель и порядок работ

Приоритет капитана — качество целевой метрики, ресурсы второстепенны.
Официальные 8 CPU / 32 GB / 3 часа остаются ограничениями исполнения.
Не отбрасывать качественный вариант только потому, что он медленнее baseline,
если весь финальный pipeline укладывается в лимит. Не снимать guardrails.

Разделять runtime-исправления, изменение оценки и новые методы. Для каждого
эксперимента сначала записать гипотезу, контроль, единственный изменяемый фактор,
способ выбора и критерий keep/discard. Отсутствие убедительного выигрыша означает
«не продвигать в default», а не доказательство бесполезности семейства методов.

## P0. Воспроизводимость и границы fit

1. Поднять отдельную Python 3.12 CPU-среду из `requirements-dev-cpu.txt`.
   Не устанавливать пакеты в системный Python. Зафиксировать версии и результаты
   всех пяти test scripts и unpacked verification. Отдельно завершить default
   classification benchmark; прошлые прерванные runs не являются baseline полного цикла.
   Зафиксировать также patch-версию/build Python сборщика: на Python 3.12.3 в этом
   review `ast.unparse` дал другое оформление кавычек f-string в `automl_runner.py`
   относительно frozen ZIP; byte-exact verification остановился до тестов.
   AST исходников обоих вариантов нужно сравнивать как диагностику, не как замену
   обязательной проверки точного release. Для новых кандидатов собирать и проверять
   архив в одной закреплённой среде; исторический ZIP не пересобирать поверх оригинала.
2. Починить watchdog отдельным изменением. Проверить fixture: coordinator запускает
   worker с `start_new_session=True`, worker запускает потомка; timeout/interrupt
   завершают все принадлежащие этому запуску процессы. Не искать процессы только
   по имени и не завершать чужие jobs. Сохранять timeout как failure с checkpoint.
3. Разделить fit/transform preprocessing внутри каждого fit. Сейчас в
   `execution/worker.py` `generic_features` и `prepare_frames` вызываются по outer
   fitting rows до создания inner split. Частоты/медианы ExtraTrees, словарь
   категорий и выбор generic features поэтому могут использовать inner validation X.
   Это не прямое чтение outer validation labels, но inner оценка не полностью
   изолирована. Inner pipeline должен учиться на inner train, outer pipeline —
   заново на outer train, full pipeline — на всех training rows.
   Fixture: меняем только inner-validation значения и проверяем неизменность
   fitted preprocessing state для фиксированного inner train.
4. Убрать молчаливую деградацию: `except ValueError` вокруг inner fit сейчас
   может скрывать ошибку adapter/policy под статусом rare-class fallback.
   Отдельно проверять ожидаемую нехватку классов/групп; прочие ошибки сохранять
   с phase/exception type, не называть их rare classes без диагностики.

## P1. Полная CV и OOF для финалистов

Существующие search seed42 и confirmation seed43 — два повторно используемых
holdout, не полная CV. `evaluation/service.py` берёт только `next(splitter.split(...))`.
Сохранить v3 evaluation как baseline. Добавить новую стратегию отдельным режимом,
не подменять исторические split hashes и не менять определение метрики.

- Сначала определить смысл групп/времени по task contract. Feature hashes защищают
  лишь от точных дубликатов; они не заменяют client/session/time groups.
- Для независимых объектов использовать stratification, для групп — grouped split.
  Не выбирать более выгодное разбиение по полученному score. Порог duplicate rate
  .05 и редкий-group fallback нынешней версии требуют явной диагностики overlap.
- Для финалистов пройти все допустимые 3–5 folds. Выбирать K с учётом числа
  независимых групп каждого класса; проверять присутствие классов и отсутствие
  запрещённого group overlap. Не обещать идеальный баланс StratifiedGroupKFold.
- Сохранять OOF с row positions, class order, split/source/recipe hashes.
  Каждая строка должна иметь ровно один прогноз от не видевшего её fit.
  Preprocessing, weights, augmentation и stopping учатся заново в каждом fold.
- Отчитывать отдельно среднее/разброс метрики по folds и метрику объединённых OOF.
  Для Macro F1/RMSE эти величины не обязаны совпадать. OOF пригодны для анализа
  и blending; сами по себе они не являются независимой оценкой после настройки.
- Подбор class factors, ensemble weights и meta-model проводить внутри отдельного
  training/OOF уровня; проверить выбранную процедуру на нетронутом outer fold.
  Не называть score на тех же OOF после настройки unbiased validation.

## P2. Редкие классы и поиск моделей

LightGBM не заменять XGBoost без измерений: XGBoost уже есть в portfolio v3.
CatBoost/ExtraTrees также уже реализованы. Сначала на общей стратегии сравнить
настроенные семейства, затем их комбинации. Результат одной конфигурации не
закрывает семейство. Использовать установленную Optuna при доступности в среде;
сохранить детерминированный поиск как fallback, не менять requirements.

1. Подбор `class_weight_power` (например 0/.25/.5/.75/1), мощности модели,
   регуляризации и минимального размера листа. Разделить эти абляции, затем
   комбинировать лучшие. Не сравнивать weighted training metric с unweighted
   целевой Macro F1; проверять actual effective parameters и выбранные итерации.
2. Сохранять per-class precision/recall/F1/support, confusion matrix и число
   независимых групп; оценивать, какие именно пары классов путаются.
3. Расширить inner decision-factor tuning на другие adapters только после
   проверки class order и validation isolation. Это decision calibration,
   а не доказательство калиброванных вероятностей для log loss.
4. Новые кандидаты: one-vs-rest classifiers для редких классов и ансамбль моделей
   с разными весами/seed/семействами. Проверить качество на всех классах и расход
   времени refit. Для OVR отдельно определить совместное правило выбора класса.
5. Затем ограниченный stacking: простая регуляризованная meta-model на OOF,
   отдельный уровень оценки и сравнение с обычным probability blend.
   Не обучать meta-model на in-sample predictions.

## P3. Новые политики данных и текст

| Метод | Контроль и условие продвижения |
|---|---|
| Copy-only против masking | Одни parents, seed, число копий и веса; отдельно от noop. Разделить эффект дублирования и маскирования. Если API политики не допускает copy-only, добавить явный метод с тестами, не маскировать его под noop. |
| Balanced-subset ensemble | Несколько training-only подвыборок большинства с сохранением редких классов; сравнить с тем же числом моделей без undersampling. |
| SMOTENC | Только после аудита типов/допустимых значений и train-only neighbour graph; не интерполировать номинальные категории как непрерывные. Noop/ROS — обязательные контроли. |
| TF-IDF + TruncatedSVD (LSA) | Обучать vocabulary/SVD на fit rows; сравнить с текущими word/char TF-IDF и проверить полезность для смешанного text+tabular ансамбля. Доступно в sklearn, внешние weights не нужны. |

Нейросетевые embeddings — отложенный вариант: сначала проверить правила доступа
к pretrained weights и их наличия на платформе. Не скачивать модели во время
solution и не предполагать интернет/GPU. LSA не называть pretrained neural embedding.
Pseudo-labeling и генеративную аугментацию не включать по умолчанию: нужны отдельный
контракт использования test X, проверка уверенности и независимая абляция.

## Приёмка изменения

Для runtime/docs достаточно соответствующих проверок; не требовать public-метрики
для чистой документации. Для изменения training policy/model/selection нужны:

- контроль и кандидат из зафиксированных source/archive snapshots;
- общие splits и seed schedule, API mode/replies либо offline mode;
- paired fold metrics и per-class diagnostics, полный refit/export;
- runtime/peak memory, input/source/split hashes, artifact SHA и failures;
- последовательный benchmark с watchdog длиннее внутреннего бюджета + запас;
- решение keep/discard с ограничениями: reused public ≠ private/official score.

Не задавать универсальный минимальный прирост: подтверждать направление по folds,
устойчивость редких классов и пользу относительно сложности. Новое разбиение
сравнивать отдельной абляцией, а не объявлять рост его score улучшением модели.

## Источники методики

- [sklearn: preprocessing и leakage](https://scikit-learn.org/stable/common_pitfalls.html)
- [sklearn: CV, OOF и ограничения cross_val_predict](https://sklearn.org/stable/modules/cross_validation.html)
- [sklearn 1.5: StratifiedGroupKFold](https://scikit-learn.org/1.5/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html)
- [sklearn: TruncatedSVD и LSA](https://scikit-learn.org/1.8/modules/generated/sklearn.decomposition.TruncatedSVD.html)

Ссылки объясняют методы; совместимость реализации проверять на закреплённых
версиях платформы, а не по наличию API в свежей документации.
