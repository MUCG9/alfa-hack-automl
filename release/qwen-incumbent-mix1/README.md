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

Qualification stages: исходники352unique checks, exact unpacked23repeated,
затем полный sequential двух-task campaign и независимая проверка actual
metrics/inner scope/full refit/CSV/lineage/integrity. Итоговые receipts появятся
после завершения. Reused-public metrics не равны hidden/official points.
Новых official uploads или main merge нет.
