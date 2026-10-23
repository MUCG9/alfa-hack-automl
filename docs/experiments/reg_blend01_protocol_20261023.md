# REG-BLEND-01: fixed no-fit дополнение сильного регрессионного ансамбля

До новой оценки. Одна конфигурация .9qualified complete V16+.1inner-selected
TPE8 history LightGBM, offsets0/1. TPE recipe выбран отдельно внутри fitting
rows каждого cut в уже завершённом HPO-01; outer labels не используются для
выбора его параметров. Это adaptive inner-HPO arm, а не один fixed recipe
для всех cuts. Полный control — actual сохранённые V16 search/confirmation.

Ноль fits/API, один вес без grid. Проверить original train provenance SHA,
actual saved partitions, row order, source labels/finite predictions и scores.
Gate: RMSE строго ниже полного control на ОБОИХ cuts. Negative останавливает
конфигурацию без других weights. Positive потребует3forward cuts всей
адаптивной процедуры с complete control, затем full refit/export и code gates;
исходный HPO-01 standalone gate остаётся отрицательным и не пересматривается.

Лимит120s/512MiB, CPU1, source/splits/evaluator не менять. Это posthoc reused
public diagnostic, не private/official score и не новая qualification. Временная
uncertainty по одному validation period остаётся unavailable. Сохранить hashes,
aggregate metrics и status; predictions остаются ignored.
