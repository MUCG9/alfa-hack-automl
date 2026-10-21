# Alfa Hack AutoML: рабочая стартовая версия команды

Приватный репозиторий команды: [MUCG9/alfa-hack-automl](https://github.com/MUCG9/alfa-hack-automl). Первая версия реально запущена на обеих public задачах с Qwen. Один её ZIP отправлен на платформу с разрешения капитана. Последний проверенный статус хранится в `docs/platform_status.json`; пока score отсутствует, локальные метрики его не заменяют. После просьбы капитана ожидание платформенной оценки остановлено.

## Структура

```text
solution.py / agent_core.py / agent_worker.py  код v1, корневые модули
requirements.txt                             оригинальные зависимости платформы
docs/                                        материалы капитану, prompts, evidence
tests/smoke.py                               offline функциональные проверки
scripts/package_solution.py                  минимальный конкурсный ZIP
release/solution-v1.zip                       неизменённая отправленная версия
```

Первым делом открыть `docs/README.md` и презентацию. Распределение P1–P5 предварительное, реальные имена и deadline назначает капитан. Изменение агента требует измерения и review, даже если весь код написал ИИ.

## Запуск

Используйте Python 3.12 и разрешённые версии из `requirements.txt`. Устанавливайте зависимости только в среде разработки, не из `solution.py`. Секрет задавайте через менеджер секретов или переменную окружения `OPENAI_API_KEY`, без помещения в Git, файл README или общий prompt. `OPENAI_BASE_URL` и `OPENAI_MODEL` берите из инструкции организаторов. На платформе их задаёт среда.

```bash
python3 solution.py /absolute/path/to/task.md --max-experiments 3 --time-budget 1200
python3 tests/smoke.py
python3 scripts/package_solution.py --output dist/solution.zip
```

Smoke tests не обращаются к Qwen, создают маленькие synthetic задачи в `test-runs/`. Для public end-to-end скачайте разрешённые данные организаторов отдельно и передайте путь к `task.md`. CSV не входят в этот handoff. `submission.csv` и отчёты появятся рядом с условием. Выходные прогнозы проверенных public прогонов лежат в `docs/`, это примеры, а не замена агенту.

На платформе команда запуска строго `python3 solution.py task.md`. Только корневые `.py` и исходный `requirements.txt` попадают в конкурсный ZIP. Документы, tests, weights, данные и подпапки в него не включаются.

## Измеренная исходная точка

Локальный RMSE 43.60655 и Macro F1 0.60358. Один fixed holdout, не полная CV. Подробности, альтернативы, времена и ограничения — `docs/run_results.md`. Text recipe прошёл только synthetic smoke. Private не проверен. Python-процесс и AST-фильтр не являются полноценной security sandbox.

Отправленный ZIP имеет SHA-256 `dda94ac5073327140870a2f29550e50e9b841ea2937b3a9b8317b7037470aba8`. Упаковщик не перезаписывает существующий release и не отправляет его на платформу. Следующая попытка требует решения капитана.

Репозиторий создан по просьбе капитана. Issues и Project пока не опубликованы, приглашения участникам и календарные приглашения не отправлялись. Задачи подготовлены в `docs/github_issues.csv`, правила работы — в `CONTRIBUTING.md`.
