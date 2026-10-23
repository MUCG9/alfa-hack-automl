# PIPE-02: реализация и обязательная полная проверка

Preregistered protocol: [pipe02_protocol_20261023.md](pipe02_protocol_20261023.md).
Class CV завершён отрицательно; freeze снят после проверки process identities
и lock. Прототип перенесён в canonical source. Шесть no-fit checks проверили fitting-only study
scope, передачу full iterations, пересчёт по исходным labels вместо доверия
worker scores, futility fallback и порядок классов/строк при экспорте.

Модуль в canonical `src/automl/search/incumbent_mix.py`, подключается
явным `--research-profile incumbent_mix`. Без флага остаётся исходный search.
Профиль — замороженные learned priors, не online Qwen search; новая полная
проверка использует `--offline` и0API calls. Рецепты выбираются по kind/metric/
schema, не public filenames/columns. Global worker ensemble остаётся2/3 простых
components. Control и augmentation исполняются разными sequential workers;
итоговый report содержит логический граф, который не передаётся nested worker.

Контроль времени: один common campaign deadline10800s, regression task максимум
3600s, classification получает оставшееся время, максимум9900s. Каждый arm
максимум900s; adaptive trial600s/study1800s, восемь trials. Отдельный final
reserve; full-study callbacks защищают оставшийся refit reserve вместо
повторного вычитания outer-search reserve. RAM1536MiB включает coordinator и
его worker tree (строже простого worker RSS); campaign supervisor2GiB.

Проверки новой canonical source и exact ZIP выполняются до первого profile fit.
`tools/run_profile_campaign.py` проверяет qualification receipts, реальные
process identities, exclusive training lock, source/check/archive fingerprints.
Работает из свежих копий данных и exact unpacked source, без доступа worker
к credentials. Запуск сохраняет source/input hashes и actual per-task reports.

`tools/verify_profile_campaign.py` независимо проверяет фактические predictions,
immutable outer/inner partitions, каждый successful inner objective и выбранный
recipe, unchanged complete control, fixed mixture, source fingerprints,
full-iteration provenance, lineage всех final learners на полных training rows,
actual full outputs, final CSV/schema/ID order/hash. Regression fallback не
считается завершённым опытом новой ветви. Public cuts не являются private/official
score, а три forward cuts не означают exactly-once OOF.

Code gates завершены:352unique source checks/266.083s,23repeated exact-unpacked
checks. Archive68files/SHA5584ee29c725c6fe1aca047a60414278a9660c5a7fd741683944669ff9b53d68.
Полная кампания из этого exact ZIP завершена за1875.771s. Независимые
actual metrics/partitions/24inner objectives/full refits/lineage/CSV/integrity
PASS; [результат](pipe02_complete_20261023.md). Owned jobs0. Code gates отдельно
от ML qualification; default search не менялся.
