# V4: проверенный кандидат исследования, 22.10.2026

Дополнение: [полная CV финалистов после этого checkpoint](../../docs/experiments/v4_cv.md)
завершена; OVA+calibration не продвигается. Runtime source/ZIP не менялись.
Текущие default benchmark — [статус](../../docs/experiments/v4_progress.md).

Рабочая ветка `work/pipeline-review-instructions`, база `a9af568`.
Текущий этап закончен по просьбе пользователя для передачи следующему агенту.
Официальной отправки и merge интеграции/main не было.

`../solution-v4-candidate.zip`: **27d29e38e0ae16df5bb436b51e484801cbb57a9f21e2179b6c67d3b6e3a72afb**, 50974 bytes,
39 root Python-модулей и исходный requirements.
Build Python3.12.3; manifest — `archive_manifest.json`. В ZIP нет данных, ключей,
предобученных моделей или новых зависимостей. V1/V2/V3 сохранены.

## Что проверено

- Все57 repo проверок:11 legacy,7 resilience,11 data-policy,7 architecture,
  5 smoke,16 quality. Exit codes и время — `repo_tests.json`, логи рядом.
- Этот exact ZIP совпал с canonical source и прошёл23 распакованные
  compatibility/fault/smoke проверки: `unpacked_tests.json`. Это повтор части
  repo тестов в независимой упаковке, не80 разных тестов.
- Два полноразмерных public lifecycle: `bounded_lifecycle.json`. Offline,
  по1 search recipe, budget600sec,2 потока, локальный guard1.7GiB, watchdog780sec.
  Оба завершили confirmation/full refit/export, exit0, integrity=true.
- 82 последовательных fixed-recipe evaluations, paired seeds42/43 и forward
  backtests: [рецепты и результаты](../../docs/experiments/v4_results.json).
  Все82 завершились ok. Восемь точных снимков source — `research_sources/`,
  их hashes связаны с evidence через `research_sources/index.json`.

| Bounded lifecycle | Search metric | Время всего, s | Full refit | Integrity |
|---|---:|---:|---|---|
| Регрессия, forward val5 | 43.148597 RMSE | 14.814 | ok | true |
| Классификация, legacy seed42 | 0.646329 Macro F1 | 90.994 | ok | true |

**Это проверка полного размера данных и жизненного цикла одного рецепта, а не
полного default поиска из12 экспериментов.** Полная CV финалистов, полный v3
classification и matched offline/online default search нового агента ещё нужны.
Ни официальный score v4, ни улучшение всего агента этими проверками не установлены.

## Измеренный эффект и что включено

Runtime исправления изолируют preprocessing во всех fit и завершают только
принадлежащие запуску процессы. Default auto-validation консервативно обнаруживает
документированный будущий период; legacy split доступен явно. Для time-регрессии
добавлены auto-history smoothing2 и отдельный history+log кандидат. Новые методы
классификации доступны opt-in; прежний default classification portfolio сохранён.

На общих forward cuts первый LGBM контроль52.912918/44.564333RMSE против
43.148597/37.749473 у автоистории, среднее ниже на17.01%. Это сравнение fixed
рецептов на повторно исследованных public backtests, не прирост official score.
Ретест фиксированного выбранного v3 ансамбля дал79.475395/41.262690; scope и
ограничения сравнения описаны в [журнале](../../docs/experiments/v4_research.md).
В классификации пока найден только небольшой paired прирост, полного CV ещё нет.

Qwen API реально проверен feature-only запросами, предложения измерены и не дали
устойчивого выигрыша. Usage — `api_usage.json`, приватный процесс с ключом закрыт.
Полный online запуск нового агента не выполнялся.

## Продолжение

[Самодостаточный промпт следующему агенту](../../docs/prompts/next-agent.md)
содержит данные/среду, конкретные команды и следующий порядок исследований.
[Готовые три рецепта CV классификации](../../docs/experiments/v4_class_cv_candidates.json)
включают первый контроль, сильную прежнюю inner calibration и OVA+calibration.
Не переносить выводы из public holdouts на независимые баллы без проверки.
