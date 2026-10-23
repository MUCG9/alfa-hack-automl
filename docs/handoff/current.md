# Ночное продолжение23Oct — текущий checkpoint

[START_HERE.md](START_HERE.md) и [research conclusions](../experiments/research_conclusions_20261023.md)
содержат актуальный статус. MVP завершён и отрицателен; qualified V11/V16 сохранён.
Полный MVP и все component screens завершены; standalone gates отрицательны.
REG-BLEND-01 прошёл3forward cuts и обе mean-comparisons. Class BLEND-01
прошёл6/6workers, но ALL-fold gate FAIL: fold0 ухудшил primary и Analysis F1.
Классификационная добавка отклонена, новые веса не подбираются. Все прежние
координаторы/descendants exited, lock проверен свободным.

Freeze снят. Sparse HPO anchor corrected вa708b1c (3checks PASS); explicit
measured controls не меняются. Canonical opt-in PIPE-02 integrated в2ddaf10:
`--research-profile incumbent_mix`, fixed complete class control и nested-TPE
regression augmentation. Default baseline/HPO0/selector0 сохранён.
Сейчас выполняется352-check source gate в
`test-runs/qwen-optuna-20261022/pipe02-source-checks/`; новых public fits ещё нет.
После gates: exact ZIP verification, затем один sequential PIPE-02 campaign
по `docs/experiments/pipe02_protocol_20261023.md`; не дублировать jobs.

Ниже историческое состояние V16, сохранённое для provenance.

---

# Актуальное состояние

Полная компактная сводка — [START_HERE.md](START_HERE.md).
[Реестр исследований](EXPERIMENTS.md), [план](PLAN.md),
[стартовый промпт](../prompts/next-agent.md).

Последняя отправка: V11 featureviews1, одна разрешённая попытка, принята в очередь;
последний наблюдавшийся счётчик 1→0. Score V11 не проверен.
[Receipt](../../release/v11-featureviews1/submission-20261022.json).

Последний код: V16 mean1/runtime f72c6df, 258 unique +23 repeated checks.
Ранее ожидавшийся full-default прогон ЗАВЕРШИЛСЯ: controller15685 exit0,
regression221.052s, classification2703.680s. Обе CSV точно совпали с V11,
refit/integrity PASS.
[Доказательство](../../release/v16-mean1/full-default-parity.json).
V16 не отправлена; нового прироста относительно V11 нет.
Незавершённых ML jobs этого запуска нет; не повторять старый 11/12 checkpoint.

Исторические подробные снимки сохранены в Git и checkpoint JSON.
На текущем этапе передачи код, requirements и ZIP не изменяются.
