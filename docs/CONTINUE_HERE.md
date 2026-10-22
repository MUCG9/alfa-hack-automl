# Передача разработки: актуальная точка входа

Последняя ветка: **`work/agent-budget-20261022`**. Main — v2, не актуальный проект.

1. [Состояние, результаты, jobs и среда](handoff/current.md).
2. [Самодостаточный промпт следующему агенту](prompts/next-agent.md).
3. [План исследований](handoff/next_research_plan.md).
4. [Полностью проверенная v7](../release/v7-semantic1/README.md),
   [последний кандидат v9](../release/v9-roles1/README.md).
5. [Продолжение 22 октября](experiments/resume_20261022.md).

**V9 отправлена один раз по отдельному разрешению капитана**,22октября около
08:03UTC /11:03MSK. Принята в очередь, счётчик2→1, оценку не ждали.
Receipt: `release/v9-roles1/submission-20261022.json`. Новая отправка не разрешена.
**Ранее четвёртый submit отправлен один раз.** Read-only reload в04:25UTC показал
**2184.173** на карточке точного v4 имени и времени05:21, осталось2попытки.
Это raw score платформы, не перевод в100/hidden-final score. Старые1723.691 — v3.
Следующая отправка требует нового разрешения капитана. Main merge/force push не делать.

V6: обе полные public задачи, refit/integrity pass, mean RMSE36.775244985 и Macro F1
0.653281240. Это reused public validation, не private/official score. V7 завершила
обе public задачи с CSV parity V6. V9:169unique repo /23repeated unpacked проходят,
её полный public gate завершён: обе задачи exit0/refit/integrity pass, CSV parity
V7/V6. Тяжёлых jobs нет. Итог в current.md /release evidence. Новые модельные
гипотезы дали отрицательные результаты и НЕ продвинуты в defaults.

Предыдущая передача — `handoff/history-before-v7.md`, предыдущий prompt —
`prompts/history/next-agent-before-v7.md`. Их ветки/лимиты/пути/статусы устарели;
использовать как историю, не как активные задания.
