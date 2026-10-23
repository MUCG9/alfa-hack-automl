# Профиль alfa-hack-automl

Применять только в репозитории с `src/automl` и этими receipts. Текущее состояние
читать из корневого `AGENTS.md`, последнего поручения и фактического Git/process
state. Исторические STOP/PID/статусы не заменяют проверку.

От корня проекта прочитать:

- `docs/experiments/hpo01_protocol_20261022.md`: FE-01/HPO-01/HAR-01 и gates.
- `docs/experiments/har02_protocol_20261023.md`: декларативные признаки Qwen.
- `docs/experiments/overnight_20261023.md`: действующая очередь и ограничения.
- `docs/experiments/qwen_mvp_history_20261022.md`: checkpoints/rollback tags.
- `docs/experiments/research_conclusions_20261023.md`: полный MVP, component screens
  и ограничения meta-review. Статусы проверять по actual receipts.
- Если продолжается blend qualification: `blend01_cv_protocol_20261023.md` и
  `reg_blend01_cv_protocol_20261023.md` в `docs/experiments/`.
- `docs/handoff/START_HERE.md`: qualified baseline и evidence.

Canonical code — `src/automl`, root-файлы — compatibility shims. Contest ZIP
собирает `tools/build_submission.py` с побайтно исходным `requirements.txt`.
Dev tools/skills в flat ZIP не входят. Canonical source не менять во время
frozen-source campaign.

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
.venv/bin/python tools/run_blend_cv.py --help
```

`overnight_research.py` и followups могут вести последовательную очередь; сначала
проверить существующие receipts/identities, а не запускать дубль. Manifests содержат actual
source/input/split hashes. Перед promotion выполнить действующий source gate и
exact-unpacked verification; repeated checks не складывать с unique checks.

Положительный fixed replay означает только measured screen для новой единицы
сравнения. Не отменять отрицательный standalone gate FE/HPO, не называть replay
полным refit или qualified release. Grouped CV class и forward qualification reg
имеют разные coverage semantics; полностью повторять inner selection, либо
переиспользовать её exact verified artifacts с совпавшими source/input/split hashes.

Qwen-ключ доступен только приватному окружению координатора. `.env` игнорируется
Git, его содержимое не выводится; workers credentials не получают. Не коммитить
raw rows, predictions, weights, окружения и секреты. Публикация рабочей ветки
имеет отдельное разрешение; из него не следуют official upload/main merge/paid
compute.
