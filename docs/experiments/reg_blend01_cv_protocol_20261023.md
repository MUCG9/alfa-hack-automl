# REG-BLEND-01: три forward cuts всей adaptive mixture procedure

До новых fits. Одна fixed .9complete-control+.1nested-TPE mixture улучшила оба
сохранённых cuts:38.902804→38.829526 и31.991659→31.965070,
mean35.447232→35.397298. Это replay, не qualification или замена HPO-01 gate.

Нужно оценить offsets0/1/2 со СИЛЬНЫМ ПОЛНЫМ control. В HPO-01 уже независимо
проверены все три TPE studies: каждый выбирал recipe только внутри outer fitting
rows, затем заново обучал selected recipe на outer fitting rows со своими
preprocessing/history/stopping scopes. Эти exact immutable artifacts повторно
не обучать. Для complete control пока отсутствует третий cut; заново выполнить
его фиксированный2-component recipe на всех трёх saved forward partitions.
Control frozen в reg_blend01_candidates_20261023.json; weights.9/.1 не менять.

Только после queue+FE-02/descendants/lock, до class BLEND-01 grouped CV, strictly
sequential. 3complete-control workers максимум,2threads,1536MiB/600s каждый,
2160s entire qualification+verification. Common MVP10800s deadline не меняется;
это отдельная стадия исследования. Source остаётся frozen через обе qualification.

Независимо проверить exact equality actual partitions controls/TPE, source/input
fingerprints, chronology, labels, row order, finite predictions, inner TPE
selection/selected outer recipes и fixed controls в jobs. Control cuts0/1 должны
воспроизвести прежние RMSE с numerical tolerance1e-9; иначе parity mismatch,
не подменять baseline более слабым. Полные fits каждого preprocessing scope
выполняет неизменённый canonical worker. Output — aggregate receipts only.

Gate: новый blend RMSE ниже complete control на КАЖДОМ из трёх forward cuts.
Отдельно mean3; он не сравнивается напрямую с mean2 старого replay. Это forward
evaluation, не full exactly-once OOF; temporal uncertainty unavailable при одном
validation period каждого cut. Negative останавливает конфигурацию без нового
веса. Positive потребует full fitting/export полной adaptive procedure и
required code/archive gates, без official upload или автоматической promotion.
