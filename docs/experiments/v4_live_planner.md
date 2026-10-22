# Реальный production planner Qwen

После daily reset выполнен один реальный запрос через текущие `planner_context`
→ `llm_plan` → `llm_gateway.request_json` → normalize. Не через fake-response test.
Qwen получил схему/словарь, агрегированный профиль и реальные завершённые forward
backtests. Raw CSV строки и credentials не отправлялись в prompt.

HTTP/API успешен с первой попытки, без compatibility retry:12.163s,
11691prompt +648completion tokens, reasoning0. Raw usage.cost .2086606277028.
Shared spend в отдельном новом budget-period:0 →.2086606277028, max600,
next reset2026-10-23T00:00:00Z. С первым budget-period этот delta не смешивается.
Приватный процесс с ключом закрыт; ключ в файлы и Git не записывался.

Два нормализованных рецепта:

1. На лучшем history+log контроле learning_rate .035 →.02 и cap1600 →2500.
   Это **составной schedule trial**, не чистая абляция одного параметра.
2. Те же параметры контроля, плюс5 простых row-wise признаков: отношения
   площади к heating/cooling degree days, climate balance, commercial indicator,
   interaction с energy_star_rating. Feature code и гипотеза сохранены точно.

Исходный контекст, call usage, нормализованные планы: `v4_live_planner.json`.
Кандидаты: `v4_live_planner_candidates.json`; полный набор с контролем:
`v4_live_planner_ablation.json`. Budget receipt: `v4_live_planner_budget.json`.

**Это пока предложения, а не доказанное улучшение метрик.** После полного v3
classification очередь выполнит6 candidate-fold workers: контроль +2 plans на
forward cuts5 и4. Используется тот же exact v4 ZIP и те же input/split hashes.
Затем продолжится полный default offline v4 на обеих задачах.

Дополнение до старта worker: набор расширен адресными context-группами и
manual-context-log; теперь6 рецептов и12 workers, см.v4_context_planner.md.
