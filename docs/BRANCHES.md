# Назначение веток

Снимок read-only inventory: 24 октября 2026. SHA ниже — наблюдавшиеся указатели, не обещание неизменного tip. Старые ветки и release ZIP сохраняются; удаление, переименование и force push не предлагаются.

| Ветка | Роль | Наблюдавшийся tip |
|---|---|---|
| `work/night-research-20261023` | Основное локальное исследование и публикация evidence | `cbd758be` |
| `research/remote-dispatch` | READY jobs, проверенные sources, primary reviews и навигация второго агента; обычное продвижение | `cbd758be` |
| `research/remote-claims/<job-id>` | Неизменяемый atomic claim отдельного job; это пакет с собственным небольшим tree, не ветка разработки | В снимке remote heads не обнаружены |
| `research/remote-results/<job-id>` | Неизменяемый sealed result с parent=claim; не merge в основной код | В снимке remote heads не обнаружены |
| `main` | Сохранённая основная линия | `5dd6b0f2` |
| `work/llm-upgrade-20261022` | Историческая V11/V16 development/evidence | `97f0cf43` |
| `work/qwen-optuna-mvp-20261022` | Историческая ветка Qwen MVP; fresh remote отличается от локального tracking ref | remote `1320e79d`, tracking `7202aba4` |
| `experiment/modular-augmentation` | История архитектурного разделения | `a9af568b` |
| `work/agent-budget-20261022`, `work/autonomous-score-20261022`, `work/cpu-research-20261022`, `work/pipeline-review-instructions`, `work/semantic-inputs-20261022` | Предыдущие направления; сохранять для lineage и исходных материалов | Точные remote SHA проверяются read-only `ls-remote` |
| `experiment/v11-long-budget-20261023` | Дополнительная удалённая ветка: владелец/текущий статус здесь не проверялись | `7b071aba` |
| `work/error-selection-20261023` | Дополнительная удалённая ветка: владелец/текущий статус здесь не проверялись | `8d87f3d7` |

Ветки `main`, `llm-upgrade` и `night-research` не взаимозаменяемы. Для контрольного runtime открывайте [release V11](../release/v11-featureviews1/README.md) или [V16](../release/v16-mean1/README.md) и точный manifest/ZIP; название ветки не является release-квалификацией.

Локально обнаружены только `main` и `work/night-research-20261023`. Origin tracking refs — кеш, поэтому текущий список remote heads проверен отдельно read-only `ls-remote`; fetch/reset/checkout не выполнялись. Транспорт ready не означает, что второй агент уже подключён. Подключение подтверждается фактическим валидированным claim, приём изменений — отдельным acknowledgement.
