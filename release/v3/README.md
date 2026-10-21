# V3: frozen candidate and evidence

Дата: 21.10.2026. **Отправлено в 23:37 MSK**, история показала `solution-v3.zip` / «Проверяется», счётчик — 0 оставшихся попыток. Серверных результатов не ждали; официальный score пока неизвестен. Подтверждение: `submission.json`.

Source checkpoint: `6f0fe6bc27cab449ab9c903e701214b5395c7892`, ветка `experiment/modular-augmentation`. Дальнейшие evidence-only commits не меняют конкурсный Python. Main остаётся `5dd6b0f2910af7aa706d400bc28093a277ac2932`.

Архив `../solution-v3.zip`: SHA-256 `cba6a5aa01264c36fe67dad188e949b934557c0502bccf221e488578867032b8`, 41 593 bytes, 36 корневых Python-модулей + исходный requirements. Manifest — `archive_manifest.json`. Новых зависимостей, данных, весов и credentials в ZIP нет. V1/V2 не перезаписаны.

## Gate

- `unpacked_tests.json`: 23 compatibility/fault/smoke проверки из независимого распакованного ZIP, без checkout/src.
- `data_policy_tests.txt`: 11 проверок; `architecture_tests.txt`: 7. Всего 41.
- `policy_benchmark.json`: 22 exploratory fixed-recipe запуска, seeds 42/43. Исследования шли во время механического выделения модулей; не выдавать их за единый исходный snapshot. Финальная замороженная сборка отдельно перепроверяется в `final_validation.json`.
- `policy_summary.json`: средние по двум folds, не CV estimate private score.
- `api_diagnostic.txt`: ранний реальный запрос получил `503 Insufficient credits` upstream, хотя лимит ключа не исчерпан. Регрессионный прогон продолжился после API timeout/error. Позднее API восстановился: `recovered_qwen_planner.json` содержит успешный JSON-план, usage и два проверенных кандидата. Успешный ответ не означает выигрыш предложенной гипотезы.
- `frozen_parent_artifact_audit.json`: проверены 4 parent-row артефакта masking из EXACT frozen ZIP — SHA/число строк/отсутствие внешних validation parents. Ранние exploratory classification-эксперименты сохраняли только provenance-хеши; полное покрытие их parent NPZ не заявляется.

## Законченные сквозные проверки до отправки

`regression_full_report.json`: exact platform CLI с default search, 12 экспериментов, повторное разбиение и финальный refit ансамбля завершились успешно, integrity true. Search RMSE **41.868106**, среднее search/confirmation выбранного ансамбля **42.010771**. Отдельный запуск без API (`regression_no_api_assessment.json`) дал тот же SHA итогового CSV.

`bounded_classification.json`: полный размер public classification, но ограниченный цикл `--max-experiments 1 --time-budget 300`; CLI, full refit и экспорт успешно завершены, integrity true. Это проверка жизненного цикла, не итог 12-experiment search. Базовый Macro F1 этого ограниченного прогона 0.646329.

`validation_progress_at_submission.json`: 6 фиксированных перепроверок exact ZIP (оба noop-контроля и mask25 на seeds42/43), все совпали с эталонными predictions. На момент отправки extended default classification search ещё выполнялся; его текущий best 0.650904 не выдаётся за итоговый результат. Локальные jobs имеют заранее установленные watchdogs, новых сабмитов автоматически не делают.

Эффект masked-copy policy не разложен на отдельный эффект повторения строк и собственно маскирования: контроль copy-only остаётся полезной следующей абляцией. Это не повод менять уже отправленный frozen ZIP.

## Решение по данным

Чистый перенос с noop воспроизводит v2 по предсказаниям на обоих разбиениях обеих задач. Контрольные single-component recipes не равны окончательному ансамблю v2; сравнивать их с ensemble-метриками как один эксперимент нельзя.

Классификация: mean Macro F1 контроля 0.651544. Duplicate beta .5 — 0.638282; ROS1.5 — 0.646347; compression — 0.650926; cap20 — 0.651038. Under85 даёт mean 0.653204, но ухудшает seed43 (0.652109 против 0.652794); обязательной политикой не становится. Гибрид ухудшающих методов не добавлялся.

Регрессия: mean RMSE контроля 42.226950; mask15 — 42.220636 (разнонаправленно по folds); mask25 — 42.164774, улучшение на обоих folds. Для mask25: копии 25% fitting rows, вероятность маски .15, вес копии .5, только частично пропущенные continuous columns; максимально +25% rows. Остальные задачи/модели сохраняют noop, а masked-кандидат должен пройти обычный отбор. Это небольшой локальный эффект, не обещание прироста официального score.

## Повторение

Из корня репозитория, с внешними разрешёнными CSV и новым каталогом результата:

```bash
python tools/benchmark_data_policies.py --task /data/class/task.md --task /data/reg/task.md --output /work/paired-check --seeds 42 43
python tools/verify_release.py --archive release/solution-v3.zip --output /work/release-check.json
python scripts/benchmark_release.py --archive release/solution-v3.zip --task /data/reg/task.md --task /data/class/task.md --output /work/full-check
```

Первый скрипт замораживает compiled source, исключает API-secrets у worker и проверяет noop parity. Второй сверяет archive bytes с текущим source, затем 23 старые проверки. Третий использует команду платформы с default search и копиями task inputs; сетевое поведение зависит от переменных API. Нельзя помещать ключ в команду, Git или этот документ; используйте приватное окружение процесса.

Локальные метрики не являются официальными баллами. Основной migration scope выполнен; добровольные M6-расширения (SMOTENC, pseudo-labeling, multi-target/ranking) не реализованы. CI оставлен неактивным шаблоном из-за отсутствия workflow scope у GitHub credential; main не merge-ился.
