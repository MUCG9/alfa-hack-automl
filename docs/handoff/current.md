# Завершённый checkpoint23Oct2026

Ночное поручение ЗАВЕРШЕНО. [Полный PIPE-02](../experiments/pipe02_complete_20261023.md),
[анализ autoresearch](../experiments/research_conclusions_20261023.md).
Ветка `work/qwen-optuna-mvp-20261022`, canonical code `src/automl`; main V2 сохранён.

MVP COMPLETE и отрицателен: F1 .6544845346080569/RMSE36.02469255996805.
Все9основных component screens и FE-02 complete/rejected по standalone gates.
Class BLEND-01:6/6workers, grouped CV FAIL fold0; не искать новые weights.
REG-BLEND-01:3forward cuts и mean vs Random8/anchor mixtures PASS.
PIPE-02 explicit `--research-profile incumbent_mix`: F1 .6593178433614652,
RMSE35.39729814378806 против35.44723155783769 у control; оба reg cuts лучше.
Default baseline/HPO0/selector0 сохранены; profile — frozen learned priors,
final offline/0API, не online Qwen search/hidden performance/official points.

352unique source/23repeated exact-unpacked/отдельно30dev checks PASS. Полный
sequential campaign1875.771s завершён:24inner objectives, actual partitions,
полные refits/lineage/CSV/source/input integrity verified. Full CONTROL CSVs
обеих задач byte-identical V16. Archive/receipts: `release/qwen-incumbent-mix1/`.

Owned ML jobs0:100146/92500/91931/37960/49264 exited, lock free. Не перезапускать
старые campaigns и не продолжать новые направления после final parity.
Karpathy-based skill versioned/installed independent copy,5file hash parity;
[откат](../experiments/qwen_mvp_history_20261022.md), verified local tag
`qwen-incumbent-mix-verified-20261023`. `.env` mode600/ignored, не выводить.
Public branch publication authorized; remote SHA читать из actual Git/ignored
push receipt. Новых official uploads/main merge/force push/paid compute/extra
Codex agents не было. Исторические разделы ниже не являются текущим scope.

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
