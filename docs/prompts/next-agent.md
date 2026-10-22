# Готовый промпт для нового чата

Актуальное поручение: полный паспорт ERR-01, затем BASE-01.
Ветка `work/error-profile-contracts-20261022`, основа `300c6db`, код диагностики
`b2a5ad4`, перенос `813af42`, закрытие baseline `68775f2`. ERR-01 и BASE-01 ЗАВЕРШЕНЫ. Читать
docs/experiments/base01_complete_20261022.md первым. Transfer97f0cf4 восстановлен:
852 файла проверены, прежние 848 bytes/mtime сохранены. Все восемь паспортов
search+confirmation и фактические итоговые CSV проверены, V11/V16 совпали:
mean F1 .6593178433614652, RMSE35.44723155783769. Это прежний baseline, не gain.
Четыре regression-паспорта partial только из-за uncertainty unavailable (один
временной validation-блок на cut); обязательные разделы complete, failed нет.
Текущие canonical compiled source и test scripts совпадают с ранее пройденным
100-check gate. После добавления split выполнены только недостающие confirmation
паспорта, search не пересчитывался. Применять root_mapping без правки исходных
JSON. Не подменять V10, не реконструировать splits и не переобучать.
Модельная политика, обучение и submit не разрешены. Текущих jobs нет.
Следующий этап — отдельный протокол SEL-01; не повторять закрытый V14.
Результаты анализа reused public не являются полной CV или новым private score.
Коммиты этапа, включая 813af42 и 68775f2, локальны; итоговый push снова завершился
exit128 из-за отсутствия GitHub Git auth
(could not read Username, terminal prompts disabled). Не заявлять синхронизацию.
Исторические пункты 1–2: docs/experiments/error_profile_contracts_20261022.md.
Ниже — исходный контекст; ограничения documentation-only заменены разрешением
на ERR-01/BASE-01, остальные ограничения сохраняются.

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
