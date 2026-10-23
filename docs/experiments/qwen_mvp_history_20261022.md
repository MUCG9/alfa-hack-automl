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
