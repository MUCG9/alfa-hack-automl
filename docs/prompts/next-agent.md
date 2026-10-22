# Готовый промпт для нового чата

Последний checkpoint: `work/error-profile-contracts-20261022`, основа `300c6db`.
По отдельной команде капитана реализованы только пункты 1–2 паспорта ошибок:
граница Error Analysis, JSON-контракты и интерфейс backend; 20 новых +7 architecture
checks PASS. Читать docs/experiments/error_profile_contracts_20261022.md первым.
Чтение артефактов/статистики/интеграция с поиском не реализованы. Контекст V11/V16
и ограничения ниже сохраняются; старый documentation-only scope заменён только
для завершённых пунктов 1–2. Новых обучений, релизов или submit не было.

Ты продолжаешь Alfa Hack AutoML:
https://github.com/MUCG9/alfa-hack-automl,
ветка work/llm-upgrade-20261022. Main и ambient-ветка agent-budget — не основа.
Всю старую переписку и все отчёты читать не нужно.

Сначала проверь HEAD/origin/dirty tree и прочитай:

1. AGENTS.md.
2. docs/handoff/START_HERE.md.
3. docs/handoff/EXPERIMENTS.md.
4. docs/handoff/PLAN.md.
Доказательства отдельных экспериментов открывай только по необходимости.

Отправлена V11 featureviews1: очередь принята, последний счётчик 1→0,
официальный score ещё не проверен. Не повторять upload.
Текущий код V16 mean1: 258 unique +23 repeated checks. ОБЕ full-default задачи
уже завершены, CSV и метрики совпали с V11. Старое «11/12 running» устарело.
Незавершённых ML jobs этого запуска нет.
Локально V11: F1 .659317843, RMSE35.447231558.
Относительно V9: F1+.006036603, RMSE−3.611%. Это reused public, не private баллы.

Первый ответ — только краткая сверка состояния, три следующих приоритета,
блокеры доступа и критерии успеха. Не переписывай код, не запускай обучение,
новые релизы или сабмиты до отдельной команды на реализацию.

Дальнейший план: анализ отбора без новых fits; универсальность/live Qwen при
безопасном доступе; ОДНА новая budget-aware CPU-гипотеза с сильным контролем,
screen → CV → full-agent gates. Не повторять отвергнутые рецепты без новой причины.

Original requirements неизменны: Python3.12/8CPU/32GB/noGPU/3h-task,
solution.py и flat root Python. Никакого runtime pip, внешних данных/pretrained.
Canonical src/automl, соседние api.py, не root shims; не перезапуск архитектуры.
Private env и данные отдельно; ключи из истории/команд/Git не использовать.
Mock ≠ live. Работать одному, делать частые commits.
При85% USED окна (15% остатка) — checkpoint/передача.
Никаких reset credits, платных GPU, extra agents, force push/main merge
или новых submit без отдельного разрешения.
