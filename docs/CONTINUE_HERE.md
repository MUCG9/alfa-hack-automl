# Актуальное продолжение V11–V12 — 22 октября 2026

Новая команда капитана возобновила работу после V10 STOP. Текущая ветка
`work/llm-upgrade-20261022`,base6aefbd9. Читать `experiments/v11_llm_review.md`,
`experiments/v11_progress.md`,`handoff/current.md`. V11 source/unpacked PASS,
full class→regression идёт; V12 threshold2 — dormant corrected snapshot, full
source/unpacked ждут завершения V11. Не запускать параллельные тяжёлые jobs.
Официальная отправка не разрешена. Следующие исследования предобъявлены отдельно.
Ниже неизменённый исторический V10 checkpoint; его STOP не отменяет новую команду.

## История: передача V10

Ветка **work/cpu-research-20261022**,main сохраняет V2. Капитан попросил остановиться
из-за лимитов и подготовить передачу. Новая команда STOP заменяет предыдущее
возобновление. Все ML jobs текущего checkpoint завершены.

1. [Готовый промпт следующему агенту](prompts/next-agent.md).
2. [Точное состояние](handoff/current.md),[технический receipt](handoff/v10-stop-checkpoint-20261022.json).
3. [Завершённая feature-view CV](experiments/v10_class_te_cv_results.md).
4. [Проверенный history4 release](../release/v10-history4/README.md).
5. [Следующий full-agent protocol](experiments/v10_class_te_agent_protocol.md).
6. [Исторический журнал V10](experiments/v10_progress.md).

History4:оба полных RMSEcuts лучше V9,mean36.775245→35.447232;219unique source/
23repeated unpacked checks,refit/integrity,boundedclasslifecycle PASS. ZIP технически
проверен для платформы; официально V10 не отправлялся.

Fixed50/50feature-view ensemble прошёл полный3foldgroupedCV73:pooledMacroF1
.640209809→.645099304,все folds/дополнительные gates PASS. Он **не включён в runtime**.
Дальше одна интеграция и полный baseline/candidateagent comparison по записанному
протоколу. Не повторять CV по историческим ACTIVE/partial сообщениям.

Официальный лучший — captain-reportedV9raw2187.849,1940.2s,его21.87/100.
Новыйupload/mainmerge/дополнительныеагенты не разрешены. Public метрики — повторно
используемая validation,не private или официальный прирост.
