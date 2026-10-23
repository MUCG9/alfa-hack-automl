# BLEND-01 qualification: fixed grouped CV после положительного replay

До первых CV fits. Replay одной заранее fixed смеси .9V16+.1MVP прошёл оба
paired/support gates: .6632403175→.6639909034 и .6553953693→.6561163362;
mean .6593178434→.6600536198. Worms F1 не меняется; gain без rarest положителен.
Это reused-public posthoc screen, не qualified improvement или significance.
Frozen recipes: `blend01_candidates_20261023.json`, никаких новых weights/trials.

Следующая проверка —3fold GROUPED CV fixed ensemble procedure, seed42,
auto validation strategy, original feature hashes. В каждом fold заново обучить
оба arms: qualified complete3-component recipe и selected MVP two-view recipe.
CatBoost selection, categorical statistics, stopping и decision calibration
каждый раз заново на собственных fitting scopes. Никакого outer selector cache,
исходных fit_iterations, переподбора рецептов, Qwen proposals или HPO в CV.
Проверяется фиксированная процедура выбранных recipes, не переигрывается весь
первоначальный exploratory search, изменивший несколько факторов.

После этих fits смешать их probabilities с теми же .9/.1. Это та же fixed
ensemble procedure; второй раз учить control внутри blend не требуется.
Сравнение — со всем qualified complete control, не с отдельно слабым recipe.
Raw rows/predictions/NPZ остаются ignored, экспортировать aggregate receipts.

Только после завершения queue PID37960 И FE-02 PID49264 и всех известных
descendants, проверки process create_time и exclusive training lock. Не
запускать параллельно. Canonical source и recipes остаются frozen до окончания
этой проверки. Guards:2threads,1536MiB/900s на один complete-arm worker,
6workers максимум,6000s на CV+verification. Это отдельный CV budget после
первоначального10800s MVP, не изменение старого deadline и не новый official run.

Независимая проверка читает фактические сохранённые splits и probabilities:
полное exactly-once row coverage, train=дополнение validation, отсутствие
пересечения feature groups, одинаковые partitions у arms, соответствие исходным
labels, row/class order, finite normalized probabilities и сохранённым CSV.
Проверить неизменные recipes в jobs, source/input fingerprints и2threads.
Отдельно fold mean и pooled MacroF1, per-class deltas и actual costs.

Advance только если ВСЕ3folds проходят исходный paired/support/rarest gate
и pooled score также улучшается с теми же ограничениям классов. Для pooled
eligibility использовать минимум independent fitting groups по трём folds
(консервативный scope), не число validation rows. Неполный CV не проходит gate.
При отрицательном результате прекращается эта конфигурация без новых весов.

Положительный CV ещё потребует отдельной integration/полной проверки агента
на двух tasks, refit/CSV/integrity и source/exact-unpacked gates. Runtime сейчас
ограничивает global ensemble тремя ненестированными components, а эта смесь
фактически содержит четыре. Не менять runtime limit до positive qualification;
CV исполняется каноническими3-component control +1MVP arm и cached mixing.
