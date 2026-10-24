# Карта исследований

<!-- CURRENT_UAR_OBSERVATION_BEGIN -->
Current: repaired standard archive eb85 is independently qualified and delivered as solution-br-rmse34.15502-class-fix.zip (81flat). Both standard tasks exit0, four cuts and two full-refit CSV artifacts verified. Actual reused-public REG RMSE34.155023394837 and CLASS MacroF1 0.6557438740449282; CLASS remains below historical0.6593178433614652. Original RQ6 and RA1 failed procedure records remain unchanged. Separate RA2 main46536/524167 exit0, atomic1efed4 exit0, finitepostbf9346 exit0;26checks/current source/temp/cleanup PASS;8071known including post observers. No model replay or upload. Qwen current source: coreR7, typed qualification auditR4, outerR6 final and metadata producerR3+utilityR2 independently reviewed. Two pure metadata contracts actually passed;66 prospective QH setup checks are not yet run. One10800 second cycle, equal nominal5400/task, awaits actual working binding/READY/preflight/launch. No Qwen runtime or metric gain claimed.
<!-- CURRENT_UAR_OBSERVATION_END -->

Начните с нужного направления. Исходные пути, manifests, receipts, имена веток и ZIP не переименовываются: они участвуют в SHA-привязках. Суффикс `next` означает название каталога, а не подтверждение готовности или запуска.

| Направление | Материалы |
|---|---|
| Полный агент и сохранение сильного anchor | [Champion A/B](champion-pair-next/README.txt), [checkpoint supervision](lean-supervision-next/README.md) |
| Выбор функции потерь, L1 | [Реестр](loss-selection-next/experiments.json), [component screen](loss-selection-next/component-screen/README.txt), [L1 seed](loss-selection-next/l1-seed/README.txt), [технический gate](loss-selection-next/l1-seed-stage0-r2/README.txt) |
| Ядерные представления | [Реестр](kernel-methods-next/experiments.json), [full Stage0](kernel-methods-next/full-stage0-recovery/README.txt), [component screen](kernel-methods-next/components/README.txt) |
| Другие модели и фиксированные blends | [Component screen](method-expansion-next/component-screen-r1/README.txt), [linear recovery](method-expansion-next/linear-recovery-r1/README.txt), [90/10 blend](method-expansion-next/cache-blend-r1/README.txt) |
| Кэш, HPO, контекст поддержки классов | [Кэш](cache-pilot-launch-r2/README.md), [HPO admission](hpo-admission/README.md), [support context](support-context/README.md), `hpo-memory-next/`, `class-support-bounded-r3/` |
| Следующие протоколы и исторические неудачи | [Outer validation](outer-validation-next-r3/README.txt), `prepared-prototypes/`, `fullagent-cv-r3/`, `fullagent-cv-r4/` |
| Удалённая работа через Git | [Начальная инструкция](remote-experiments/REMOTE_AGENT_START.txt), [транспорт](remote-experiments/transport-README.txt), [READY jobs](remote-experiments/jobs/), [reviews](remote-experiments/reviews/) |
| История первых MVP | [True four-stage](true-four-stage/README.md), `repaired-mvp-r1/`, `lean-mvp-r1/`, `lean-mvp-r2/` |

Для статуса отдельного опыта читать в таком порядке: объявленный protocol/manifest → actual campaign/supervisor → terminal root closure → независимый audit. Сохранённый `experiments.json` может быть только preregistration; отсутствие чисел в нём не доказывает, что опыт не выполнялся. Старый сводный [отчёт 23 октября](progress-20261023/research-progress-20261023.txt) — исторический срез, он не является единственным актуальным статусом.

Технический gate проверяет код и жизненный цикл, component screen — один фактор на объявленных срезах, whole-agent A/B — полный агент. Ни один из них сам по себе не равен official score или разрешению автоматически продвигать релиз. Неудачи и пустые метрики сохраняются.

Крупные сырые данные, predictions, веса, приватные конфигурации и локальные environments сюда не публикуются. Замороженные источники активного опыта не редактируются. Новая реализация создаётся отдельно и получает собственные pins.

Для изменений навигации предлагаются append-only [remote notices](remote-experiments/notices/). Они не изменяют действующий job, caps, sources или исходный clock. Пока этот путь не опубликован и не добавлен в стартовую инструкцию, queue CLI сам его не опрашивает.

<!-- CURRENT_UAR_OBSERVATION -->
QH1 is CLOSED FAIL before model/API execution because its immutable union omitted the development worker entrypoint. All 66 startup contracts passed; the failure remains. QH2 uses a reviewed four-literal output relocation and the exact missing worker pin; two targeted entrypoint metadata contracts passed. The two-task 10800-second research campaign is prospective until its actual launcher. The repaired class-fix archive remains independently qualified at REG RMSE 34.155023394837 / CLASS MacroF1 0.6557438740449282, below historical CLASS 0.6593178433614652; no upload or default promotion.
