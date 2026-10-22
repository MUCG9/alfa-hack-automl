# Начать здесь — актуальный этап V11–V17

Ветка **work/llm-upgrade-20261022**, основа коллеги6aefbd9; main сохранён как V2.

1. [Точное состояние, результаты и текущий job](handoff/current.md).
2. [Самодостаточный промпт следующему агенту](prompts/next-agent.md).
3. [Разбор советов LLM](experiments/v11_llm_review.md).
4. [Проверенный улучшающий V11](../release/v11-featureviews1/README.md).
5. [Последний код и 258 проверок V16](../release/v16-mean1/README.md).
6. [Архитектура и границы](architecture/implementation.md).

V11 внедряет уже прошедший CV фиксированный ансамбль двух представлений категорий.
Полный default pipeline улучшил оба classification cuts: mean Macro F1
**0,653281 → 0,659318**. Регрессия RMSE **35,447232** и итоговый CSV сохранены.
Это reused-public validation, не официальный балл и не обещание75–85/100.

V12 numeric thresholds, V13 AutoGluon, V14 cached search proposal,
V15/V16 target corrections и V17 smaller leaves проверены и НЕ продвинуты.
Подробности/протоколы/отрицательные результаты сохранены в experiments/.
Поздние возможности выключены по умолчанию; V11 остаётся квалифицированным ZIP.

Заключительный полный прогон defaults актуального V16 запущен последовательно
regression→classification в test-runs/llm-upgrade-20261022/final-default-parity.
Проверить current.md и assessments перед любым новым запуском. Pending не PASS.
Капитан разрешил и выполнена ОДНА отправкаV11: принята в очередь, счётчик1→0.
[Receipt](../release/v11-featureviews1/submission-20261022.json), score pending;
новые отправки не разрешены. Не путать прежние2187.849(V9) с результатомV11.

Частые commits, без новых зависимостей/ключей/CSV в Git. При85%USED завершить
текущий этап и передачу; никаких дополнительных агентов или покупок ресурсов.
Исторические V10 STOP/ACTIVE статусы сохранены отдельно, не текущее поручение.
