# Согласованный контракт параллельной разработки v3 — предложение 0.1

Статус: интерфейс для реализации, **не существующая функция v2**. Изменения контракта сначала согласуют три владельца в одном коротком сообщении/PR; независимо изобретать несовместимые форматы нельзя. До согласования расширений сохраняется работающий v2 fast path.

## Владельцы и стабильные границы

- Pro реализует `task_spec.py`, при необходимости `task_adapters.py`, и меняет `agent_core.py`. Он отвечает за факты о задаче, валидацию, оценку и CSV.
- Plus A меняет `model_utils.py`, `agent_worker.py`, `ensemble_cache.py`, может добавить `task_models.py`. Он отвечает за обучение по уже принятой спецификации.
- Plus B меняет `agent_runner.py`, `agent_policy.py`, `solution.py`, `scripts/` (кроме audit_task_contract.py) и интеграционные тесты. Он связывает этапы и не дублирует parser/metric/model factory.
- Никто не меняет `requirements.txt`, frozen `release/`, чужие модули или общий контракт без согласования. Свою документацию помещать в `docs/research/{task-contract,models,runner}.md`.

## TaskSpec — сериализуемый JSON, не исполняемый код

Обязательные новые поля:

```json
{
  "schema_version": "0.1",
  "task_type": "multioutput_regression",
  "kind": "regression",
  "targets": ["y1", "y2"],
  "id_columns": ["record"],
  "feature_columns": ["x1", "x2"],
  "metric": "rmse",
  "greater_is_better": false,
  "metric_params": {"aggregation": "uniform_average"},
  "prediction_type": "value",
  "output_columns": ["y1", "y2"],
  "submission_columns": ["record", "y1", "y2"],
  "output_mapping": {"y1": {"target": "y1"}, "y2": {"target": "y2"}},
  "validation": {"strategy": "holdout", "group_columns": [], "time_column": null, "seed": 42},
  "classes_by_target": {},
  "positive_class": null,
  "query_column": null,
  "paths": {"train": "actual_train.csv", "test": "actual_test.csv", "sample": null, "dictionary": null},
  "decision_evidence": ["task.md explicitly requests both targets"]
}
```

Этот пример иллюстрирует форму, не подменяет истинную схему задач. `task_type`: `regression`, `binary_classification`, `multiclass_classification`, `multioutput_regression`, `multilabel_classification`, `ranking`. Legacy `kind` остаётся `regression`/`classification`; только ranking получает `ranking`. Для одного target/ID сохраняются старые поля `target`/`id`, `classes` и остальные ожидаемые v2 поля. Для нескольких/нулевого ID старое поле может быть null: использовать новые массивы. Пример не отменяет существующие v2 пути/поля: Pro предоставляет совместимую нормализацию.

`prediction_type`: `value`, `label`, `probability`, `probability_matrix`, `ranking_score`; старое `value` для single classification сохраняется/нормализуется совместимо. `output_columns` по v2 содержит только прогнозы, `submission_columns` — весь CSV включая ID. Output mapping задаёт явный target/class для каждого prediction-столбца. Положительный класс берётся из условия/образца и метаданных, не безусловно второй лексикографический. Порядок строк восстанавливается по оговорённым ключам или исходному порядку; ключи ответа не обязаны быть признаками модели. Для ranking query ID исключается из обычных признаков по умолчанию, validation разделяет запросы; строки и group sizes согласованы для ranker.

`validation.strategy`: `holdout`, `stratified`, `group`, `time`. При неоднозначности семантики Pro обязан сохранить предупреждение/основание, не угадывать скрытые метки. План split фиксируется до сравнения моделей; менять его ради лучшей цифры нельзя. Во временном split train раньше validation, в group — нет пересечения сущностей. Возможны ограничения на сочетание времени и групп; если они противоречат — явная диагностика и консервативный вариант, не тихий random.

Метрика и направление должны быть явными; неизвестную метрику нельзя молча заменить. MAPE требует описанной обработки нулей, balanced accuracy не accuracy, NDCG@k усредняется по query с явной политикой пустой релевантности. Агрегация по target и положительный класс задаются условием; если условие не определяет — логировать принятое допущение.

## Интерфейсы для независимой работы

1. **Pro** добавляет `resolve_task(task_path, ask_llm=None)` в `task_spec.py`. Возврат — существующий 7-элементный tuple `discover`: `(spec, profile, train, test, sample, text, hashes)`; порядок проверен по v2. `ask_llm` — callback Plus B, принимающий один словарь и возвращающий JSON-словарь; Pro не создаёт второй API-клиент. Offline передаётся None: тогда детерминированный fallback и честная диагностика ограничений. Прочитанные файлы и LLM-ответ валидируются; данные/инструкции из task.md не дают права читать вне task directory или раскрывать секреты. Сохранять legacy `features` как alias `feature_columns`, а для paths — согласовать соответствие `sample`/`dictionary` прежним `sample_submission`/`data_dictionary`.
2. **Pro** сохраняет старые `discover`, `make_split`, `evaluate`, `save_submission` для v2-сценариев. Добавляет `evaluate_task(spec, y, pred, proba=None, groups=None)` для новых задач. `make_split` возвращает прежние индексы+metadata; применяет `spec.validation`, если задано. CSV writer принимает несколько целей/классов, в том числе отсутствие ID. Все новые spec-поля проходят проверку до обучения.
3. **Plus A** добавляет `make_task_model(recipe, spec, threads, iterations)` и сохраняет `make_model` для прежних callers. Поддерживаемые estimator методы и поля строго описать в своём PR. Multioutput регрессия — матрица `(n, t)` в порядке `spec.targets`; multilabel — такая же матрица меток, вероятности `(n,t)` с явными положительными классами; single classification — текущий порядок классов, ranking — вектор score. Не объединять независимые label encoders без mapping.
4. **Plus A** сохраняет JSON job/result контракт worker, `predictions.npy` и формат результатов старых задач. Новые формы/метаданные добавляет обратно совместимо; сохранение файлов без pickle, контроль finite, строк и output dimensions. Внешние validation labels не используются в stopping/калибровке. Worker не получает API-ключ.
5. **Plus B** вызывает `resolve_task` до выбора portfolio; передаёт ограниченный callback к имеющемуся Qwen-клиенту, записывает parser decision и число API-вызовов. Далее portfolio выбирается по `task_type`, worker получает spec целиком. Новый callback может оборачивать существующий `llm_plan`, но его фактическую сигнатуру нужно сначала проверить. Совместимость старой команды `python solution.py task.md` обязательна.

Заглушки новых API допустимы только в тестах с явным именем stub. Не коммитить в production фиктивно успешные модели, метрики или заглушку LLM. Каждый владелец сначала может выполнять тесты против маленького синтетического spec этой версии, затем один общий интеграционный PR проверяет реальную связку.

## Gate перед объединением

Старые 11 unit + 7 resilience + 5 smoke должны проходить. Добавить отдельные тесты каждого владельца; интеграция проверяет неизвестные имена файлов, optional dictionary, no/composite ID, reorder, multi-target, ranking, MAPE, balanced accuracy, time/group, positive-class probabilities, API fail и deadline. Не все сценарии аудита реализуются одним владельцем: Pro исправляет semantics/loader, Plus A — исполнение, Plus B — end-to-end.

Полный public benchmark проводится после фиксации интерфейсов; сравнивать одинаковые данные/split/бюджет с v2. Старый ZIP не перезаписывать. Локальное улучшение не равно официальному score; submit разрешает только капитан.
