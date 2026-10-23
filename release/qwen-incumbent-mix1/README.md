# Qwen autoresearch: opt-in incumbent mixture

Новый explicit research profile в branch `work/qwen-optuna-mvp-20261022`.
Default search не меняется. Исследовательский цикл и gates:
[analysis](../../docs/experiments/research_conclusions_20261023.md),
[PIPE-02 protocol](../../docs/experiments/pipe02_protocol_20261023.md).

`solution.zip` собран `tools/build_submission.py`;68flat files, ORIGINAL
requirements.txt. SHA256:
`5584ee29c725c6fe1aca047a60414278a9660c5a7fd741683944669ff9b53d68`.
Данные/прогнозы/веса/ключи/skills/dev tools в архив не входят.

```bash
AUTOML_THREADS=2 python solution.py task.md --offline --research-profile incumbent_mix --time-budget 9900
```

Запускать из свежей рабочей копии задачи с оригинальными input files.
Это замороженные learned priors: для temporal RMSE regression profile включает
внутренний TPE8 и fixed.9complete-control+.1selected-augmentation; для group
MacroF1 classification использует полный qualified control, поскольку proposed
augmentation провалил grouped CV gate. На неподдержанном schema/kind действует
обычный baseline. У ordinary baseline Optuna/selector по умолчанию OFF; opt-in
profile сам включает свой фиксированный nested search согласно протоколу.

Локальная квалификация COMPLETE:352unique source checks,23repeated exact-unpacked,
отдельно30development harness checks. Полный sequential campaign1875.771s,
source/archive/harness unchanged, оба refits/CSV/integrity verified.
[Независимый receipt](full-procedure.json), [campaign](campaign.json),
[полный разбор](../../docs/experiments/pipe02_complete_20261023.md).

|Mean двух public cuts|MacroF1 ↑|RMSE ↓|
|---|---:|---:|
|V11/V16 control|.6593178433614652|35.44723155783769|
|Opt-in profile|.6593178433614652|35.39729814378806|

Все24inner objectives перепроверены по actual predictions; все final learners
обучены на всех training rows. Full CONTROL CSV обеих задач побайтно совпали с
V16. Итоговый regression CSV — новая fixed mixture. Reused-public metrics не
равны private/official points. Никаких новых official uploads/main merge.
Source/default search не переключается этим архивом автоматически: flag
`--research-profile incumbent_mix` необходим для активации профиля.
