# PIPE-02 завершён: полный opt-in profile

[Протокол](pipe02_protocol_20261023.md) зафиксирован до fits. Code checkpoint
984ec2e, canonical implementation2ddaf10; narrow sparse-HPO-anchor correction
отдельноa708b1c. Новый default/main/official submit не создавался.

|Полная процедура, mean двух cuts|MacroF1 ↑|RMSE ↓|
|---|---:|---:|
|Qualified V11/V16 control|.6593178433614652|35.44723155783769|
|Четырёхэтапный Qwen MVP|.6544845346080569|36.02469255996805|
|PIPE-02 opt-in|.6593178433614652|35.39729814378806|

Regression: fixed.9complete-control+.1separately inner-TPE-selected single arm.
Оба actual cuts улучшились:38.902803731334785→38.82952590212054 и
31.991659384340597→31.965070385455594. Предварительная3forward qualification
также улучшила все cuts и mean против Random8/unchanged-anchor mixtures.
Standalone HPO-01 по-прежнему rejected; это другая единица сравнения.
В PIPE-02 заново выполнены3studies×8successful trials, seed137/startup3,
включая отдельный inner search ВНУТРИ всего training set для deployment.
Full iterations: control[160,350], augmentation201 из selected full-study trial.
Все3final learners заново обучены на53308строках; final CSV22449строк.

Classification: proposed.9control+.1MVP прошёл первоначальный replay, но
провалил grouped CV fold0, включая Analysis F1 loss>.01. Среднее/pooled улучшение
не заменяет ALL-fold gate. Поэтому PIPE-02 использует прежний complete control,
без augmentation. Оба cuts и final CSV полностью воспроизведены. Recursive
median iterations:[[100,111],[100,138],339],5final learners на87670строках;
final CSV41166строк.

**Независимая проверка PASS**: фактические сохранённые partitions побайтно по
массивам совпали с qualified control; исходные labels, row/class order,
все24inner objectives/выбранные recipes, fixed mixture, full-iteration provenance,
lineage каждого final learner, actual full outputs, CSV/schema/ID/hash и
source/input integrity. Full CONTROL CSV в обеих задачах byte-identical V16.
Regression FINAL mixture CSV отличается от control по заданной формуле.
[Portable receipt](pipe02_complete_20261023.json),
[независимый verifier receipt](../../release/qwen-incumbent-mix1/full-procedure.json).

Один owned sequential coordinator,2threads,1536MiB worker+parent limit,
900s/complete arm,600s/trial/1800s study, общий10800s deadline. Actual campaign
1875.771s, regression324.811s, classification1548.236s. Source/archive/harness
unchanged; coordinator100146 и descendants завершены, training lock свободен.
Все прежние coordinators также exited. Никаких новых направлений после этой
финальной стадии не запускалось.

Проверки352unique source/23repeated exact-unpacked PASS; отдельно30development
harness checks PASS. Archive68files, ORIGINAL requirements.txt:
[solution.zip](../../release/qwen-incumbent-mix1/solution.zip),
SHA5584ee29c725c6fe1aca047a60414278a9660c5a7fd741683944669ff9b53d68.
[Запуск профиля](../../release/qwen-incumbent-mix1/README.md).

Это frozen learned priors после реальных Qwen research runs, не новый online
LLM search: final campaign offline/0API calls. Ordinary baseline и default
HPO0/selector0 сохранены; unsupported schema/kind возвращается к baseline.
Метрики — reused-public development, mean двух outer holdouts, не full OOF,
private performance или official normalized points. Полный трёхчасовой MVP и
последующие ночные screens/campaign имеют отдельные заранее заданные budgets;
старый deadline не обнулялся. Отсутствует основание обещать такой gain на новых
датасетах или hidden test.

Скилл [autoresearch-ml](../../skills/autoresearch-ml/SKILL.md) основан на
[Karpathy autoresearch](https://github.com/karpathy/autoresearch), установлен
независимой копией. Rollback: qwen-mvp-frozen-research-20261023,
qwen-incumbent-mix-tested-20261023, qwen-incumbent-mix-verified-20261023.
Данные/прогнозы/веса/env/secrets в Git и ZIP не включены.
