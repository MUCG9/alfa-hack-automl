# Полная CV классификации, продолжение v4

Все9 candidate-fold workers завершились exit0/statusok. Один exact ZIP v4,
одни3 group-disjoint folds, OOF покрывает все87670 строк ровно один раз.
Рецепты зафиксированы до CV. Это дополнительные проверки на повторно
используемом public train, не независимая оценка официального score.

| Фиксированный рецепт | Fold mean Macro F1 | Fold std | Pooled OOF Macro F1 |
|---|---:|---:|---:|
| Первый контроль | 0.636759 | 0.002981 | 0.636402 |
| Прежняя inner calibration | 0.637348 | 0.001729 | 0.637929 |
| OVA + inner calibration | 0.630106 | 0.006434 | 0.630416 |
| Фиксированная смесь контроль/OVA .5/.5 | 0.637040 | 0.002707 | 0.636753 |

OVA+calibration была лучшим устойчивым кандидатом по двум screening holdouts,
но проиграла обоим контролям на всех3 CV folds. Она не добавляется в default.
Это вывод о данном рецепте, а не о бесполезности one-vs-all на любых задачах.

Смесь .5/.5 была заранее объявлена до итоговых OOF (commit8aad5d8), веса не
настраивались по этим OOF. Она немного лучше первого контроля на всех3 folds,
но не лучше прежней calibration по fold mean и pooled score. Дополнительных
worker fits для расчёта смеси не было. Новым default она не становится.

Парный bootstrap500 повторов по54228 feature-hash группам, относительно прежней
inner calibration (условный интервал по фиксированным прогнозам):

| Рецепт | Разность pooled Macro F1 | Условный95% интервал |
|---|---:|---|
| Первый контроль | -0.001527 | [-0.004529, +0.001696] |
| OVA + inner calibration | -0.007513 | [-0.012402, -0.002580] |
| Смесь .5/.5 | -0.001176 | [-0.004459, +0.002438] |

Интервалы не включают неопределённость повторного обучения и адаптивного отбора
гипотез и не являются интервалами private score. OVA+calibration проиграла
сильному контролю и по этому условному сравнению. Разность двух контролей мала
и остаётся неопределённой. Default classification portfolio сохранён.

Числа/хеши/все outcomes: [v4_cv_results.json](v4_cv_results.json).
Смесь: [v4_cv_blend_summary.json](v4_cv_blend_summary.json).
Bootstrap: [v4_cv_final_bootstrap.json](v4_cv_final_bootstrap.json).
Существующие82 fixed-recipe evaluations предыдущего этапа сохранены отдельно;
эта CV добавила9 workers, суммарно91. Bounded lifecycle и default search считаются
отдельно, их нельзя смешивать с числом fixed-recipe workers.

Следующий этап — полный matched offline default benchmark v3/v4, затем Qwen
и следующие гипотезы регрессии. Релизный ZIP не менялся: после первого checkpoint
runtime source не редактировался.
