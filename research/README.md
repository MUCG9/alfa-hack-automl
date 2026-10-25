# Карта исследований

<!-- CURRENT_UAR_OBSERVATION_BEGIN -->
Current: QH3 is CLOSED FAILED. Actual main session56903 exited1 (eb10dd); its frozen negative closer exited1 (8a38cc), and collector2813 completed. They must not be polled or rerun. The first REG phase failed when gateway51 crossed its provider-call deadline after request return; the whole campaign had not exhausted its10800-second budget. Classification was not attempted. All71 startup contracts passed;24 Qwen candidates and56 successful worker callbacks were observed. Recorded HTTP entries50 are a lower bound: the failed51st gateway call did not persist usage, so whole HTTP/token totals are unknown. No QH3 metrics are independently qualified. Saved root25cadd8c records current source/temp/cleanup true and technical false; separate current-negative fresh proof is pending. Source diagnosis and a minimal separately reviewed repair are in progress. The qualified repaired standard archive eb85 remains delivered with REG RMSE34.155023394837 and CLASS MacroF1 .6557438740449282 (below historical .6593178433614652); no upload or default promotion. QH1/QH2 and all historical failures remain immutable. Linux remains human-paused.
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
QH3 is ACTUALLY RUNNING under one original 10800-second cap with equal task research windows. All 71 startup contracts passed. A genuine Qwen response and completed hypothesis worker callbacks were observed; the loop entered its next request. The request is 9621 bytes with the exact five-source gateway closure; the full immutable parent source proof remains. New independently qualified metrics and three-hour completion remain pending. QH1/QH2 failures are preserved; repaired class-fix archive qualification and delivery remain unchanged.
