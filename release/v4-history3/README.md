# V4 history3: контекст истории по метаданным

Source commit `16987fb`. ZIP `../solution-v4-history3.zip`,
SHA **8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f**, 51694bytes. Предыдущие ZIP сохранены.
Оригинальный requirements не менялся. Публичные feature names в код не зашиты.

## Изменение

Task Understanding распознаёт описанные в словаре числовые свойства строительства.
На fitting rows auto-history сначала находит повторяющийся числовой контекст,
затем добавляет categorical attributes и более точный статический атрибут.
Получаются coarse/fine ключи. Их поддержка проверяется между fitting periods;
при coverage<25% метод возвращается к прежним ключам. Вне fitting rows выбор ключей
не учится. Target encoding остаётся cross-fitted по независимым feature-hash группам.

Метод opt-in `target_encoding_hierarchical=true` и отдельный кандидат в time
regression portfolio, если подходящая схема есть. Нужны observation period и
повторяемость; обычные задачи не получают эти признаки принудительно. Model target
и test labels для определения контекстов не используются. Новый кандидат работает
offline и не требует pretrained моделей.

## Проверено

**59 repo checks** (18 quality) и23 повторных unpacked checks exact ZIP прошли.
Unit tests проверяют независимость от held-out X, переименование схемы, train-only
группы, нормализацию флагов, собственные labels/outer labels у target encoding.

На двух фиксированных forward cuts:

| Рецепт | RMSE периода5 | RMSE периода4 |
|---|---:|---:|
| Auto-history +log контроль |41.002541|38.062736|
| **Автоматическая иерархия по метаданным +log** |**40.960973**|**33.984412**|

Все4 worker jobs завершилисьok. Контроль точно воспроизвёл прежние значения.
Группы и split/source/input hashes — [v4_history3_results.json](../../docs/experiments/v4_history3_results.json).
Числа — repeated public validation, не private/platform score.

На предыдущем раннем inner history finer context имел мало поддержки, поэтому
автоматика использовала coarse fallback. Это дало148 iterations против100 у
ручного контекста на старшем backtest, отсюда разность33.9844 vs34.3022.
Алгоритм выбирал всё по fitting rows; внешние labels не участвовали.

## Полный поиск

Полный default regression этого exact ZIP успешно завершён:12search,
confirmation,ensemble,fullrefit/export, integrity=true,312.386s.
RMSE39.321110/34.229380,mean36.775245; regression_full.json рядом. Старый full search2 regression уже завершён успешно:
RMSE40.426939/37.723019, mean39.074979, fullrefitok/integritytrue.
Full frozen v3 classification также завершён: ensemble mean F1 .653714716.
В history3 сохраняется class capacity search из search2; **полный новый
classification benchmark ещё нужен** перед выводами о его качестве.

[Актуальный статус](../../docs/experiments/v4_progress.md),
[промпт передачи](../../docs/prompts/next-agent.md). Официальной отправки не было.
