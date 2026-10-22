# Актуальная передача: V10, 22 октября 2026

Рабочая ветка **work/cpu-research-20261022**. Main сохраняет V2.
Капитан восстановил лимиты и поручил продолжить работу. Предыдущая передача
на8% сохранена как checkpoint; пауза отменена.

1. [Самодостаточный промпт следующему агенту](prompts/next-agent.md).
2. [Точное текущее состояние](handoff/current.md).
3. [Журнал и результаты V10](experiments/v10_progress.md).
4. [Архив экспериментального полного пайплайна](../release/v10-history4/README.md).
5. [Следующая предложенная, ещё не запущенная гипотеза](experiments/v10_next_stage.md).

V9 остаётся официальным лучшим: captain-reported2187.849,1940.2s,его21.87/100.
V10 на платформу не отправлялся. Новая отправка требует отдельного разрешения.
Новый агент сначала сверяет завершение jobs/gates и Git; pending не означает pass.
Исторические V6–V9 handoffs и прежние queued статусы не заменяют новые evidence.

History4 полностью завершил local gate: оба RMSE cuts лучше V9,mean36.775→35.447,
216unique/23unpacked pass, bounded class lifecycle pass. Следующий активный протокол:
experiments/v10_extratrees_protocol.md (fixed LGBM+ExtraTrees vs strong single).
