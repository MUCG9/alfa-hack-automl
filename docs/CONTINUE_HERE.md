# Передача разработки: актуальная точка входа

Последняя ветка: **`work/semantic-inputs-20261022`**. Main — v2, не актуальный проект.

1. [Состояние, результаты, jobs и среда](handoff/current.md).
2. [Самодостаточный промпт следующему агенту](prompts/next-agent.md).
3. [План исследований](handoff/next_research_plan.md).
4. [Полностью проверенная v6](../release/v6-universal1/README.md),
   [экспериментальная v7](../release/v7-semantic1/README.md).
5. [Журнал 22 октября](experiments/continuation_20261022.md).

**Четвёртый submit отправлен один раз.** Read-only reload в04:25UTC показал
**2184.173** на карточке точного v4 имени и времени05:21, осталось2попытки.
Это raw score платформы, не перевод в100/hidden-final score. Старые1723.691 — v3.
Следующая отправка требует нового разрешения капитана. Main merge/force push не делать.

V6: обе полные public задачи, refit/integrity pass, mean RMSE36.775244985 и Macro F1
0.653281240. Это reused public validation, не private/official score. V7:145 unique
repo и23 repeated exact-unpacked checks pass; full public gate запущен, итог в
current.md / release evidence.

Предыдущая передача — `handoff/history-before-v7.md`, предыдущий prompt —
`prompts/history/next-agent-before-v7.md`. Их ветки/лимиты/пути/статусы устарели;
использовать как историю, не как активные задания.
