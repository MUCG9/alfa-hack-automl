# Передача разработки следующему агенту

Актуальная передача 22.10.2026: рабочая ветка `work/pipeline-review-instructions`.
[Кандидат v4](../release/v4-candidate/README.md) прошёл57 repo и23 unpacked проверки,
два bounded public lifecycle/refit/export; проведены82 fixed-recipe evaluations.
[Самодостаточный промпт](prompts/next-agent.md) содержит конкретный следующий план.
[Журнал исследования](experiments/v4_research.md) и [метрики](experiments/v4_results.json)
сохраняют keep/discard и ограничения. Полная CV финалистов и полный default поиск
ещё нужны. Ниже сохранён исторический handoff v3; его незавершённые задачи следует
сверять с текущим evidence.

Дополнение от 22.10.2026: после чтения исторического снимка ниже открыть
[`architecture/quality_plan.md`](architecture/quality_plan.md). Там уточнены
приоритет качества над скоростью в пределах платформенных лимитов, конкретные
риски inner preprocessing/обработки ошибок и этапы CV/OOF, настройки редких классов,
ансамблей и новых методов. Это план будущих экспериментов, не их результаты.
Не выполнять весь backlog автоматически при запросе только review/инструкций.

Снимок: 21.10.2026, Europe/Moscow, после отправки v3. Цель капитана — максимальный официальный score универсального CPU AutoML-агента. Презентации и распределение старых ролей сейчас не приоритет. Предыдущая реализация выполнена одним агентом; новых агентов не запускали.

## 1. Что клонировать

Приватный репозиторий: https://github.com/MUCG9/alfa-hack-automl . Нужен доступ GitHub капитана/приглашённого участника. Не передавать пароль/PAT в prompt.

```bash
git clone --branch experiment/modular-augmentation https://github.com/MUCG9/alfa-hack-automl.git
cd alfa-hack-automl
git rev-parse HEAD
git switch -c work/next-improvement
```

До этой передачи последний опубликованный commit был `8bbd038c47c62fe640a97a43b440ebace0d84537`; новая передача добавляет только документы, evidence и настройку benchmark CLI, не меняет отправленный ML-код. Фактический свежий HEAD получить из Git. Не checkout main для продолжения: там сохранена v2 (`5dd6b0f2910af7aa706d400bc28093a277ac2932`). Source checkpoint v3 — `6f0fe6bc27cab449ab9c903e701214b5395c7892`.

## 2. Что реально отправлено

`release/solution-v3.zip`, SHA-256:

```text
cba6a5aa01264c36fe67dad188e949b934557c0502bccf221e488578867032b8
```

41 593 bytes; 36 root `.py` + оригинальный requirements. В кабинете 21 октября в **23:37 МСК** появилась строка `solution-v3.zip`, статус «Проверяется»; после отправки счётчик показал **0 попыток**. Это принятие в очередь, НЕ официальный score. См. `release/v3/submission.json`. Новый сабмит только после отдельного разрешения капитана, даже после сброса лимита. Предыдущие официальные карточки по скриншоту: v2 **1694.145**, v1 **857.742**; нормирование score неизвестно.

## 3. Среда нового компьютера

Python **3.12**; GPU не нужен. Для Linux (проверенная платформа):

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev-cpu.txt
python tests/test_v2.py
python tests/test_resilience.py
python tests/test_data_policy.py
python tests/test_architecture.py
python tests/smoke.py
python tools/verify_release.py --archive release/solution-v3.zip --output test-runs/clone-release-check.json
```

На Windows активация `.venv\Scripts\Activate.ps1`; доступность этих package wheels на Windows/macOS не проверялась. При отсутствии wheel согласовать подходящий локальный CPU пакет, не менять платформенный requirements. Это CPU subset для разработки; весь тяжёлый organizer requirements локально не переустанавливался. Отправляемый `requirements.txt` НЕ заменять. SHA оригинала `9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`. Verification требует соответствия ZIP текущему canonical source; после изменения кода проверять уже новый кандидат, а не требовать совпадения со старым ZIP.

Ключ Qwen в Git отсутствует. Попросить капитана настроить приватное окружение, не присылать ключ в общий prompt. `.env.example` — пустой шаблон; автоматического dotenv-loader нет. Без ключа продолжать offline tests. Endpoint/model в шаблоне были проверены на реальном proxy; при изменении инструкции организаторов перепроверить. Key-info на 23:45 MSK показывал spend **64.15851869319712**, max_budget **600**, reset `2026-10-22T00:00:00+00:00` (=03:00 MSK). Это снимок сырых API-полей, не текущий остаток и не новое подтверждение валюты. НЕ путать с reset submit-слотов в **00:00 MSK**.

## 4. Данные и исходные материалы

В Git нет исходных CSV, API-ключа, MP4 и локального окружения. На другом компьютере капитан должен отдельно дать архив `data_for_participants-20261019T184005Z-1-001.zip` или распакованные public задачи. До получения данных не выдумывать public-метрики; fixtures и упаковку можно проверить без них.

Нужны два `task.md` и по четыре CSV (`train`, `test`, `data_dictionary`, `sample_submission`) с сохранёнными относительными путями. В исходном архиве каталоги называются `Многоклассовая классификация` и `Регрессия`; task-копии могли ссылаться на вложенные `multiclass/` и `regression/`. Не смешивать разные варианты task.md. `docs/handoff/public_inputs.json` содержит размеры/хеши именно проверенных копий, не сами данные. Пути задаются аргументами CLI, не хардкодятся в решении.

Старый компьютер, только если продолжение на нём:

- Workspace: `/home/mucg9/Documents/Codex/2026-10-19/referenced-chatgpt-conversation-this-is-an`.
- Repo: `outputs/team-project`; Python: `work/ml-venv/bin/python`.
- Public task copies: `work/evaluation/multiclass/task.md`, `work/evaluation/regression/task.md`.
- Original extraction: `work/archive_inspect/data_for_participants/`.
- Detailed local artifacts: `work/v3-migration/`, summaries `outputs/v3-migration/`.
- Исходный MP4: `/home/mucg9/Downloads/AI-агент для разработки ML моделей.mp4`; повторно транскрибировать не нужно: разбор/транскрипт уже в `docs/webinar_20261021.md` и `docs/webinar/`.
- Telegram export: `/home/mucg9/.var/app/org.telegram.desktop/data/TelegramDesktop/tdata/temp_data/ChatExport_2026-10-21/messages.html`; нужные уточнения уже в `docs/organizer_clarifications.md`.

## 5. Пайплайн и архитектура

`solution.py` → Task Understanding (`discover`) → Evaluation (`split`) → Search (portfolio/Qwen/fallback) → отдельный Execution subprocess (train-only preprocessing/features/DataPolicy/adapters) → Evaluation metrics → confirmation seed43 → cached ensemble → full refit → Publishing итогового CSV. Worker не получает API credentials. Координатор держит рабочий checkpoint при сбоях.

Canonical код: `src/automl/{contracts,task_understanding,evaluation,search,execution,publishing,infrastructure,compat}`. Корневые старые файлы — shims. Это локальные сервисные границы с проверяемыми API, НЕ развёрнутые сетевые микросервисы. Контракты v1.0 частично оборачивают legacy dicts; DatasetRef/SelectionPlan ещё не полностью внедрены в transport.

По умолчанию 9900 секунд, 12 search experiments, 4 planner calls, 4 CPU threads. На платформе 8 CPU /32 GB /3 часа, запуск `python3 solution.py task.md`, CSV рядом с task. Только root `.py` и original requirements копируются из ZIP. `tools/build_submission.py` компилирует `src` в flat-модули; ручная упаковка shims сломает запуск.

## 6. Проверено и НЕ проверено

- **41 проверка**: 11 legacy +7 resilience +5 smoke из распакованного exact ZIP, 11 DataPolicy +7 architecture в repo. Evidence в `release/v3/`.
- 22 exploratory paired runs на seeds42/43; часть шла при механическом переносе модулей. Затем **6 случаев перепроверены из exact ZIP**, включая noop parity на обеих задачах и mask25 на регрессии. Parent lineage аудирован для 4 frozen masking fit artifacts, пересечений с outer validation нет.
- Noop воспроизводит v2 predictions. Это fixed single-component comparison, НЕ сравнение с финальным ансамблем v2.
- Regression: контроль RMSE mean **42.226950**, mask15 **42.220636** (неоднозначно), mask25 **42.164774** (оба folds лучше). Policy: copies .25, mask_probability .15, synthetic_weight .5, только частично пропущенные continuous columns. Рост до25%; политика применяется заново внутри каждого fit.
- Classification: beta .5, ROS, compression, cap20 не дали устойчивого улучшения. Under85 улучшил среднее, но ухудшил seed43; mandatory policy не включён. Noop сохраняет существующие мягкие class weights.
- Полный default regression search/refit успешен: search RMSE **41.868106**, ensemble mean42/43 **42.010771**. Повтор без API дал тот же итоговый CSV SHA. См. `regression_full_report.json`.
- Полноразмерный classification прошёл сокращённый цикл (1 experiment/300sec), full refit и CSV: F1 **0.646329**. Это lifecycle test, не максимум поиска.
- **Длинный default classification не завершён полностью**: наш внешний локальный watchdog остановил его в23:45, после примерно1163sec, ради резерва на submit. Это НЕ официальный 3-hour timeout. Сохранено 10 search outcomes, best **0.6517757640545693**, без итогового confirmation/refit. См. `local_validation_final.json` и `classification_interrupted_progress.json`. Не объявлять весь full validation passed.
- Отдельный default classification без API тоже остановлен внешним watchdog1200sec в23:49, с11 сохранёнными experiments и best0.650904187; full refit не подтверждён. Оба coordinator-запуска закончились, но их kill-process-group не гарантирует очистку отдельной worker process group; это известный runtime gap, не доказательство, что сейчас остался живой worker.
- Qwen сначала отвечал timeout/503 upstream insufficient credits, позже восстановился: получены реальные JSON-plans с reasoning0. Более сильный class weighting от Qwen ухудшил F1 до0.61866 и занял350sec; успех вызова не означает полезность гипотезы.
- Official v3 score неизвестен в этом snapshot. Все приведённые RMSE/F1 — повторно исследованные public folds, не private estimate.

## 7. Что делать следующим — по приоритету

1. Проверить git/status, прочитать AGENTS и свежий release evidence. Уточнить у капитана официальный score v3, но не ждать его пассивно и не делать повторный submit самостоятельно.
2. Закончить **один последовательный** full-size classification run с достаточным watchdog и безопасной RAM. Зафиксировать full refit, export, runtime/RSS, provenance. Не запускать несколько тяжёлых benchmarks одновременно: на прежнем ПК было около2GB свободной RAM и почти заполненный swap.
3. Отдельный небольшой PR: научить внешний benchmark-watchdog останавливать всё дерево, включая workers в отдельных process groups. Сейчас kill coordinator group может оставить worker до конца его fit. Не завершать чужие процессы.
4. Для качества: matched-budget v2/v3 full-agent comparison с сохранёнными planner replies/одинаковыми splits; посмотреть per-class precision/recall, особенно редкие группы. Не менять evaluator ради score. После базовых результатов — class weight power/decision calibration и diversity-aware ensemble. Смешивать улучшения по одному фактору.
5. Augmentation: copy-only control для отделения дублирования от masking, затем при необходимости один гибрид. Не включать SMOTENC/генеративные методы без измерений. Неподдерживаемый метод должен явно отклоняться, а не становиться молчаливым noop.
6. Далее отдельная ветка Task Understanding: произвольные input names/formats, MAPE/balanced accuracy, time/group interpretation, multi-target/ranking — ограничения из вебинара, пока НЕ реализованные возможности. Не смешивать с чистым refactor.

GitHub CI не активирован: PAT не имеет scope `workflow`. Готовый шаблон — `docs/architecture/ci-workflow.example.yml`; расширение прав требует отдельного решения капитана. CODEOWNERS не равен branch protection. PR/Issues/Projects/приглашения автоматически не создавались.

## 8. Команды воспроизведения

```bash
# Новый flat-кандидат, имя должно быть новым:
python tools/build_submission.py --output dist/solution-v4-candidate1.zip
python tools/verify_release.py --archive dist/solution-v4-candidate1.zip --output test-runs/v4-verification.json
# Public data остаются внешними. Последовательный запуск, CPU ограничен:
python scripts/benchmark_release.py --archive release/solution-v3.zip --task /data/reg/task.md --task /data/class/task.md --output test-runs/full-v3 --jobs 1 --threads 2
# Paired fixed-recipe policy ablation; это не full agent search:
python tools/benchmark_data_policies.py --task /data/class/task.md --task /data/reg/task.md --output test-runs/policies --seeds 42 43 --threads 2
```

Запуски создают новые каталоги, не переиспользуют stale checkpoints. Финальный артефакт изменения: diff, tests, exact ZIP+SHA, data/split/source manifests, measured quality/runtime/memory, решения keep/discard и ограничения. Замороженную v3 не перезаписывать.
