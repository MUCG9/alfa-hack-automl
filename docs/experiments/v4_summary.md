# Итог этапа v4, 22.10.2026

Работа сохранена в ветке `work/pipeline-review-instructions`, отдельные commits
после завершённых этапов. Официальный submit/merge не выполнялись.
Кандидат: [solution-v4-history3.zip](../../release/solution-v4-history3.zip),
SHA `8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f`.

Финальная техническая проверка готовности к загрузке:
[инструкция](../../release/v4-history3/SUBMIT.md),
[receipt](../../release/v4-history3/submission_readiness.json).
Exact ZIP побайтно совпадает с source:39root `.py` +original requirements.
Дополнительный bounded classification этого ZIP завершил1search experiment,
fullrefit/export за97.954s, integrity=true, Macro F1 .646328924.
CSV обеих задач проверены по sample schema/ID/порядку/числу строк/допустимым
значениям (22449regression,41166classification). Техническая готовность
не заменяет ещё не выполненный полный default classification quality benchmark.

## Главный результат

Автоматические coarse/fine контексты повторяющихся объектов теперь определяются
по fitting rows и метаданным схемы. Составные target-статистики cross-fit;
ID/target/test labels в выбор ключей не входят, public column names не зашиты.
Признаки и остановка переобучаются в каждом inner/outer/full fit. Для будущего
периода агент использует forward validation; legacy evaluation доступна явно.

Два завершённых default offline regression pipeline на **тех же** forward cuts,
input hashes,2threads и одинаковом локальном memory guard:

| Полный агент | Search RMSE ↓ | Confirmation RMSE ↓ | Среднее ↓ | Время, s |
|---|---:|---:|---:|---:|
| v4 search2 |40.426939|37.723019|39.074979|292.920|
| **v4 history3** |**39.321110**|**34.229380**|**36.775245**|312.386|

Средний RMSE ниже на **5.89%** относительно предыдущей v4 search2.
Оба завершили12search experiments, confirmation, ensemble, full refit и export;
integrity=true. Это repeated public validation с адаптивным выбором моделей,
не независимый private/platform score. Официальный балл history3 не измерен.

Контролируемая fixed-recipe абляция подтверждает сам feature-method:
auto-history+log41.002541/38.062736 →автоматическая metadata hierarchy
40.960973/33.984412. Прежний первый LGBM forward контроль52.912918/44.564333
и ретест fixed выбранного v3 ансамбля79.475395/41.262690 приведены в журнале
с отдельным scope; их нельзя выдавать за полный v3 search на новых folds.

## Классификация

Впервые закончен полный default frozen v3 classification:12search,3confirmation,
ансамбль .9/.1,fullrefit/export, integrity=true; время2628.518s.
Search ensemble Macro F1 .654372724, mean search/confirmation .653714716.
Это законченный локальный baseline, не official score.

Полная3fold CV отсеяла OVA+calibration, которая выглядела лучше на screening:
pooled .630416015 против.637928932 у прежней calibration; проигрыш на всех folds.
Фиксированная .5/.5 смесь также не превзошла сильный контроль.
CV и bootstrap — `v4_cv.md`; новые методы не объявляются полезными без измерений.

В source2/3 отдельно изменён XGBoost fallback: сохраняет веса incumbent и
исследует depth/min_child_weight/L2 вместо повторения только весов иseed.
**Полная новая classification ещё не проверена.** Это первая следующая задача;
её качество нельзя приравнивать к завершённому frozen v3 baseline.

## Проверки и evidence

- 107 fixed candidate-fold jobs:82первого этапа +9CV +12Qwen/context +4history3.
- 3 полноценных default runs: frozen v3 class,search2 reg,history3 reg.
- 2 bounded полноразмерных lifecycle source1 и1финальный bounded history3 class
  отдельно, не называются default search.
- 59repo tests (включая18quality) +23повторных unpacked checks exact history3 ZIP.
- Реальный production Qwen planner и targeted prompt проверены; неудачные гипотезы
  также сохранены. Qwen context-группы проиграли; итоговый алгоритм использует
  схему и fitting X и работает offline. Все API credential процессы закрыты.

Рецепты/хеши/метрики: `v4_results.json`, `v4_cv_results.json`,
`v4_qwen_ablations.json`, `v4_history3_results.json`,
`v4_v3_default_full.json`, `v4_search2_reg_full.json`, `v4_history3_reg_full.json`.
Точные source snapshots и manifest находятся в release. Raw CSV, predictions,
файлы обученных моделей и credentials не включены в Git/ZIP. requirements.txt сохранён побайтно.

[Промпт продолжения](../prompts/next-agent.md) содержит конкретные команды,
приоритеты, условия, завершённые проверки и ограничения. Новые долгие эксперименты
на этом checkpoint не запускаются; все наши ML workers/очереди завершены.
