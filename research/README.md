# Карта исследований

<!-- CURRENT_UAR_OBSERVATION_BEGIN -->
Current: RQ6 both standard tasks completed solver exit 0, all 119 technical contracts passed. Its original procedure remains FAIL because independent artifact audit accessed terminal_resource_observation=None. Current negative source/cleanup proof and post-tool observation confirmed; no models need to be repeated. A separate no-fit RA1 audit source and caller R2 are independently reviewed; 22 changed contracts are prepared, not executed. READY, actual RA1 clock and new qualified metrics remain pending. Qwen core R7 is reviewed; typed postfailure admission source is being finished before one actual 10800-second iterative run. No new archive delivered or upload performed.
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
