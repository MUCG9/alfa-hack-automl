# V4 search2: отдельная гипотеза поисковой политики

Source commit `e8458fe`, база — первый v4 checkpoint с полностью завершённой CV.
ZIP `../solution-v4-search2.zip`, SHA **53bb47d3e05adc44477cd8cd7a87802367209b554a5355bfff75992f4673d685**, 51206bytes.
Оригинальный requirements сохранён. Предыдущие ZIP не изменялись.

Изменён только fallback классификации при incumbent XGBoost: вместо повторения
class weights исследуются меньшая/большая глубина, min_child_weight и reg_lambda.
Весовая политика incumbent сохраняется; seed по-прежнему меняется. Это сравнение
поисковых политик, не single-factor абляция отдельных гиперпараметров.
Базовые4 classification portfolio recipes, regression search и обучение worker
не менялись. Неуспешная на CV OVA+calibration в default не добавляется.

Проверки: **58 repo** (включая17 quality) +23 повторных unpacked проверки exact ZIP.
`repo_tests.json`, `unpacked_tests.json` и логи рядом. Тест подтверждает4 различных
реальных capacity-конфигурации XGBoost, сохранение весов и допустимые границы.
Первая промежуточная проверка была аннулирована integrity guard из-за правки
исходника одновременно с CLI тестом; после заморозки все проверки повторены и прошли.

**Прирост метрики этого изменения пока не установлен.** Полный frozen v3
classification продолжает считаться с прежней политикой. После него в очереди:
Qwen ablations на source1 →полная regression на search2 →полная classification
на search2. Последняя задача запускается при наличии локального флага
`test-runs/stages/allow-default-v4-class`, чтобы можно было остановить новые долгие
этапы при переходе к резерву токенов. Источник состояния — reports/progress,
не предположение о завершении очереди.

[Статус](../../docs/experiments/v4_progress.md),
[промпт продолжения](../../docs/prompts/next-agent.md).
Официальной отправки не было.
