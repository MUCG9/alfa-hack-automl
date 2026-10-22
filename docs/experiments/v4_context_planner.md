# Адресная гипотеза: составные ключи истории

Ещё один вызов Qwen через тот же gateway, со специальным planning mode для
составных context keys. Это **абляция prompt**, а не изменение production prompt.
Задача: изменить только группы target encoding относительно history+log контроля;
все ML параметры и feature_code оставить фиксированными, ID/target не использовать.

Успех с первой попытки:5.793s,11783prompt +263completion tokens, reasoning0,
raw usage.cost .1146885358554. После двух запросов нового budget-period общий
счётчик .3233491635582 из600. Ключ был только в приватном процессе, процесс закрыт.

Qwen предложил две схемы: State/building_class/facility_type (с coarse parent)
и такой же контекст с year_built (с coarse parent). Floor area он в эти ключи
не включил. Это может ограничить различение повторяющихся объектов; до измерения
мы не объявляем их лучше автоматических групп.

Дополнительно заранее добавлена человеческая гипотеза: ранее проверенные manual
context groups +log target. Она отличается от текущего лучшего auto-history+log
контроля только способом задания групп, не зашивается в runtime.

Итого набор `v4_live_planner_ablation.json` до начала обучения содержит6 рецептов:
контроль,2 generic Qwen plans,2 context plans,manual-context-log. На двух общих
forward cuts это12 workers. Все используют source1 ZIP; полный search2 позже
проверяется отдельно. Наличие предложений и успешного API не является выигрышем.

Полный контекст/ответ и нормализованные планы: `v4_context_planner.json`.
Adopted candidates: `v4_context_candidates.json`; budget: `v4_context_budget.json`.
