# Локальная история MVP

Ветка: `work/qwen-optuna-mvp-20261022`. По просьбе капитана этапы сохраняются
отдельными локальными коммитами; исторические архивы не перезаписываются.

|Коммит / метка|Состояние|
|---|---|
|`f3c8aba` / `baseline-before-qwen-optuna-20261022`|Исходный checkpoint BASE-01 / ERR-01, проверенные прогнозы V11/V16|
|`c3a63f5` / `qwen-optuna-core-20261022`|Optuna inner-only, CatBoost fitting-only selector, компонентный benchmark; 342 source checks с HTTP-повтором вне sandbox, 23 exact-unpacked checks|
|`b486a4f`|Явный CLI-флаг отбора признаков, matched сравнение промптов Qwen; selector OFF при отсутствии явного разрешения координатора|
|`bc51d88`|Последовательный полный MVP с общим deadline и live-smoke четырёх этапов|
|`37d1cca`|Независимая проверка MVP; сохранён отрицательный результат regression|
|`1e689c6`|Декларативные признаки Qwen и trusted compiler с preflight|
|`f46c997`|Последовательная ночная очередь с process identity и exclusive lock|
|`ad7e472`|Независимый пересчёт component screens и диагностика class tradeoffs selector32|

Чтобы посмотреть старый вариант и работать с ним в новой ветке, сохранив
историю текущей ветки:

```bash
git switch -c recovered-baseline baseline-before-qwen-optuna-20261022
```

Возврат к текущей исследовательской ветке:

```bash
git switch work/qwen-optuna-mvp-20261022
```

Перед переключением сохранить незакоммиченные изменения. История исходников
не восстанавливает игнорируемые данные, локальные результаты и окружение.
Приватный `.env` создан по отдельному прямому указанию капитана, имеет права600
и исключён из Git. Ключ в документацию, коммиты и конкурсный архив не входит.
Публичная публикация рабочей ветки разрешена капитаном отдельно. Push `ad7e472`
проверен через remote SHA; main не менялся. Это история кода и технических
отчётов, а не резервная копия игнорируемых данных/моделей/прогнозов/секретов.


Продолжение23Oct: c396932 — Karpathy-based skill;804d407 — независимая installed
копия;7202aba — FE-02 trusted prototype;070b8cd — sequential followup;
a1b1b39 — frozen FE-02 identity;6d85647/0b37c89/86b5dd0 — read-only Qwen review
и агрегированный контекст. Последний проверенный remote SHA перед очередным
push:a1b1b39. Полный MVP завершён и отрицателен; V11/V16 остаётся qualified.
Обновлённый installed skill совпадает с versioned copy, включая наблюдение
о разной history availability внутри/снаружи HPO.


Позднее ночное продолжение23Oct:

|Checkpoint|Состояние|
|---|---|
|`b886593`|Последний подтверждённый public push до full-profile stage|
|`4f43e68` / `qwen-mvp-frozen-research-20261023`|Frozen research source до narrow HPO/profile integration; все отрицательные screens сохранены|
|`a708b1c`|Исправлены sparse HPO anchor defaults; реальные adapter constructors,0fits,3checks PASS|
|`2ddaf10`|Opt-in incumbent profile; class blend отвергнут по grouped CV, reg blend forward qualified|
|`984ec2e` / `qwen-incumbent-mix-tested-20261023`|352unique source/23repeated exact-unpacked/30dev harness checks PASS; exact68file ZIP до full campaign|

PIPE-02 campaign ACTIVE PID100146/create_time1792730294.41; immutable identity
`test-runs/qwen-optuna-20261022/detached-pipe02.json`. Пока нет independent full
verification receipt, tested tag не означает verified full model/refit. Во время
frozen fitting не переключать checkout; пользоваться историей после завершения.


Финальный checkpoint: PIPE-02 COMPLETE, independent verification PASS на обеих
задачах;[итог](pipe02_complete_20261023.md). Campaign1875.771s,0owned jobs.
Локальная метка`qwen-incumbent-mix-verified-20261023` сохраняет полный проверенный
вариант и технические receipts. Прежние ACTIVE/PID выше — история, не инструкция
перезапуска. Public branch SHA подтверждать через actual push receipt/Git.
