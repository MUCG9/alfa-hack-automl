# Профиль alfa-hack-automl

Применять только в репозитории с `src/automl` и этими receipts. Текущее состояние
читать из корневого `AGENTS.md`, последнего поручения и фактического Git/process
state. Исторические STOP/PID/статусы не заменяют проверку.

От корня проекта прочитать:

- `docs/experiments/hpo01_protocol_20261022.md`: FE-01/HPO-01/HAR-01 и gates.
- `docs/experiments/har02_protocol_20261023.md`: декларативные признаки Qwen.
- `docs/experiments/overnight_20261023.md`: действующая очередь и ограничения.
- `docs/experiments/qwen_mvp_history_20261022.md`: checkpoints/rollback tags.
- `docs/handoff/START_HERE.md`: qualified baseline и evidence.

Canonical code — `src/automl`, root-файлы — compatibility shims. Contest ZIP
собирает `tools/build_submission.py` с побайтно исходным `requirements.txt`.
Dev tools/skills в flat ZIP не входят. Во время кампании не менять её конкретные
frozen execution paths/source hashes. Разработку следующей версии можно вести
в отдельном дереве, которое исполняющийся worker не импортирует. После переноса
между компьютерами перепроверять доступность процессов и артефактов на новом host;
старый PID или running receipt не доказывает наличие локальной job.

Qualified complete control — сохранённый V11/V16. Component controls сильные
SINGLE recipes: categorical two-view LightGBM для classification, asof/history
LightGBM для regression. Это разные единицы сравнения. Optuna/selector по
умолчанию OFF; exploratory MVP не означает default promotion.

Действующие screens: classification group cuts42/43, regression forward offsets
0/1/2. FE/HAR требуют улучшения каждого cut; classification также ограничивает
провал поддержанных классов и требует gain без rarest class. TPE должен обойти
equal-cap random. Точные gates читать из протокола и не ослаблять после результата.
Positive class screen требует grouped CV всего inner selection, затем полной
проверки агента/refit/export. Reused-public scores не равны official points.

Heavy fits/fixture suites строго последовательны на host. Public fits2threads,
core checks1thread. Читать identity receipts, PID+create_time, descendants и
`test-runs/.owned-research.lock`; не завершать посторонние процессы. Local guards
не доказывают соблюдение platform timeout.

Инструменты доступны из корня проекта:

```bash
.venv/bin/python tools/benchmark_hpo.py --help
.venv/bin/python tools/benchmark_candidates.py --help
.venv/bin/python tools/compare_planners.py --help
.venv/bin/python tools/propose_feature_dsl.py --help
.venv/bin/python tools/summarize_mvp.py --help
.venv/bin/python tools/summarize_research.py --help
```

`overnight_research.py` умеет вести последовательную очередь; сначала проверить
существующий `queue.json` и host/process identity, а не запускать дубль. Manifests содержат actual
source/input/split hashes. Перед promotion выполнить действующий source gate и
exact-unpacked verification; repeated checks не складывать с unique checks.

Qwen-ключ доступен только приватному окружению координатора. `.env` игнорируется
Git, его содержимое не выводится; workers credentials не получают. Не коммитить
raw rows, predictions, weights, окружения и секреты. Публикация рабочей ветки
имеет отдельное разрешение; из него не следуют official upload/main merge/paid
compute.

## Подтверждённые lessons tm1 и isolated gates

Перед повтором broad FE/selector/HPO или отчётом о tm1 прочитать от корня
проекта `docs/experiments/autoresearch_lessons_tm1_20261023.md` и его SHA-bound
evidence. tm1 исполнил четыре стадии, но не улучшил сохранённый V11/V16;
class HPO не дошёл до guided TPE. Не превращать combined negative outcome в
причинный запрет отдельной технологии. У class закрытый API ledger проверен
независимо, у regression usage null после известного PermissionError; parent
usage не заменяет независимый аудит.

Expected source registry, статические hash/inventory checks и component gain
не равны actual full gates или whole-agent CV. Первый Stage0 показал незамкнутую
fixturemetadata dependency при неизменных395hashes; проверять реальные test
reads через callees, включая docs/release metadata, в isolated deployment.
Детали, исходные часы и неудачные attempts сохранять по evidence, а текущий
execution state всегда читать отдельно из свежих receipts.
