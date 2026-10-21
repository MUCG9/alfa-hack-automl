# V3: frozen candidate and evidence

Дата: 21.10.2026. Source checkpoint: `6f0fe6bc27cab449ab9c903e701214b5395c7892`, ветка `experiment/modular-augmentation`. Дальнейшие evidence-only commits не меняют конкурсный Python. Main остаётся `5dd6b0f2910af7aa706d400bc28093a277ac2932`.

Архив `../solution-v3.zip`: SHA-256 `cba6a5aa01264c36fe67dad188e949b934557c0502bccf221e488578867032b8`, 41 593 bytes, 36 корневых Python-модулей + исходный requirements. Manifest — `archive_manifest.json`. Новых зависимостей, данных, весов и credentials в ZIP нет. V1/V2 не перезаписаны.

## Gate

- `unpacked_tests.json`: 23 compatibility/fault/smoke проверки из независимого распакованного ZIP, без checkout/src.
- `data_policy_tests.txt`: 11 проверок; `architecture_tests.txt`: 7. Всего 41.
- `policy_benchmark.json`: 22 exploratory fixed-recipe запуска, seeds 42/43. Исследования шли во время механического выделения модулей; не выдавать их за единый исходный snapshot. Финальная замороженная сборка отдельно перепроверяется в `final_validation.json`.
- `policy_summary.json`: средние по двум folds, не CV estimate private score.
- `api_diagnostic.txt`: реальный Qwen proxy недоступен (`503 Insufficient credits` upstream), хотя лимит выданного ключа не исчерпан. Во время полноценного запуска фиксируется и продолжение fallback после API timeout/error. Успешных новых Qwen-гипотез не заявляем.

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

Итог отправки подтверждается отдельным `submission.json`, только после наблюдаемого принятия в кабинете. Локальные метрики не являются официальными баллами.
