# Карта исследований

<!-- CURRENT_UAR_OBSERVATION_BEGIN -->
Current repair: RQ5 is closed FAIL before contracts/models (dependency bootstrap callback falsely treated native import time as an observation gap; technical child also bound previous output). Actual terminal 9c4f4d exit1, negative closer 1f0b7d exit1; current-negative observer f0a7ad and post3423df both exit0, finite next union7937, source/temp/cleanup true, technical false. No new metrics.
RQ6 source ce829991 independently reviewed34cb7aae: current output binding plus clock-only technical-child callback under independently sampled parent full guard, unchanged strict resource/gap caps.119 prepared contracts,0 executed. New6000 clock unassigned, repaired archive not ready. Qwen time-driven R6 source/outer reviewed; new10800 actual campaign not yet launched. Linux remains human-paused; no upload authorization.
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
