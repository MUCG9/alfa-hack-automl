# BLEND-01: одна смесь готовых вероятностей с сильным control

Протокол до вычисления новой смеси. FE-01 не прошёл самостоятельный gate.
Отдельная гипотеза: выбранный Qwen MVP-кандидат может дополнять ошибки
полного qualified V11/V16 ансамбля. Это не пересмотр FE-01 или его default.

Только classification: control — сохранённые search/confirmation probabilities
полного V16, воспроизведшего V11. Candidate — selected SINGLE recipe полного
MVP, seed53/class_weight_power1/top32/two-view. У этих уже созданных артефактов
проверено точное совпадение actual split arrays. Ни один новый fit не разрешён
этим replay-протоколом. Прочитать фактические NPZ и исходные labels, проверить
row/class order, finite normalized probabilities и соответствие CSV prediction.

Ровно одна конфигурация, заранее fixed .9control + .1MVP; без grid/подбора
веса или кандидата после результата. Argmax, без новой calibration. Метрика
MacroF1 по двум сохранённым cuts; отдельно per-class delta и supported gate
>=100 independent fitting feature groups/loss<=.01, positive gain без rarest
class. Требуется улучшение ОБОИХ cuts. Regression не меняется.

Лимит120s/512MiB,0fits, без API/зависимостей, source/evaluator modifications,
official upload или automated promotion. Сохранить hashes входных reports,
probabilities и splits, aggregate scores и исход gate. Source/root_mapping
разрешает чтение исторических paths без изменения original JSON bytes.

Это posthoc development diagnostic на многократно использованном public
validation, не independent/private score. Даже положительный исход потребует
отдельной проверки всей фиксированной ensemble procedure и полного refit;
никакого нового qualified complete agent из replay не возникает. Отрицательный
исход останавливает эту конфигурацию без новых весов.

Первый replay остановился ДО новых scores: перенесённые historical artifacts
не содержат копию raw train по старому spec path. Использовать существующий
MVP train только при точном совпадении с original control provenance input:train
SHA. Original reports/splits не изменять. Исправлена только resolution исходных
данных; сохраняются та же конфигурация/gates и receipt первого отказа.
