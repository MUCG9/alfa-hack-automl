# Следующий план: общий score, а не только public F1

Актуализация22октября после V9: V7 и V9 full gates завершены успешно, CSV parity
V6; тяжёлых jobs нет. Общий startup/API ledger,64KiB metadata cap и bounded
структурный feedback уже реализованы в V8/V9 — НЕ делать их заново. XGB OOF3
calibration и fixed LGBM seed42/47 blend проверены и отвергнуты; не повторять без
новой гипотезы. V9 отправлена одной разрешённой попыткой; позже капитан сообщил
2187.849,1940.2s,«Лучшее решение», оценка21.87/100.
Новая предложенная очередь1→selection shortlist,2→adaptive CPU HPO,
3→strictly-as-of history находится в
[`cpu_research_review_20261022.md`](../experiments/cpu_research_review_20261022.md).
Она ещё не запущена. Предыдущие исследования и доказательства сохранены.

Следующий приоритет: bounded LIVE Qwen end-to-end только через разрешённую
private environment (SDK/local fake HTTP уже проверены, это не live). Затем одна
предобъявленная модельная гипотеза, paired folds и CV только после keep gate.
Старые пункты ниже — исторический backlog; сверять с current.md и кодом, не
принимать описание старого недостатка за актуальный баг. Новая отправка требует
отдельного разрешения. При15% остатка не начинать долгие этапы.

## 1. Проверка реально работающего AI-агента

Гипотеза: unknown schemas/имена/описания проваливаются до обучения, хотя две public
задачи проходят. V7 закрывает только file roles.

- Bounded live end-to-end fixture в private API environment: нестандартные имена,
  mapping/planner→worker→refit→CSV, gateway status/retries/usage, без secrets/raw rows.
- Schema/metric/positive-label ambiguity — отдельные fixtures и контракты; LLM не
  может менять path/security ограничения или придумывать unsupported objective.
- Общий deadline/API accounting должен охватывать pre-discovery+planner+targets;
  сейчас file-role trace отдельный от planner report.
- Следующая отдельная итерация: bounded downstream schema-validation feedback,
  не бесконечный поиск «удобной» трактовки после структурно верного JSON.
- Добавить serialized metadata cap: count bounds не ограничивают длину имён.
  Не усекать silently точные paths так, чтобы ответ больше нельзя было валидировать.

Keep: корректные TaskSpec/CSV и bounded traces на заранее новых fixtures, offline
regression сохранён. Один public F1 не проверяет эту гипотезу.

## 2. Валидация, не меняя исторический контроль

Nested preprocessing/fit-error isolation/owned-process watchdog уже реализованы;
старый quality_plan описывал их до исправления. Сверить код/tests/test_quality.py,
не делать заново то же «исправление». Runtime search+confirmation не полная OOF.

Для финалистов сравнить отдельную bounded CV стратегию с legacy control. Всё
preprocessing/augmentation/weights/stopping/calibration внутри fitting folds.
Проверять exactly-once OOF/classes/positions/groups/time. Joint unseen-group+future
пока не реализован. Нельзя выбирать split по более высокому score.

## 3. Классификация: одна гипотеза за раз

Компонентный CV3 прирост calibration дал полному V6 лишь+0.00054 к v4, а v3
classification выше. Гипотеза: отбор/смешивание ограничивают перенос улучшения.

- Зафиксировать контроль V6 и небольшую predeclared альтернативу: например,
  OOF-calibration2/3fold ИЛИ иной weight power, не оба одновременно. Fit price
  должен укладываться в платформенные3часа/task.
- Paired folds/полная CV, per-class/group analysis, fold mean/pooled OOF отдельно.
  Настройку weights на OOF оценивать снаружи, не на тех же fitted OOF.
- ROS/SMOTENC не default без нового устойчивого результата; прежние
  compression/oversampling/underweight эксперименты были неоднозначны.
- Нельзя обещать прирост по одному seed; exact ZIP full-agent refit обязателен.

## 4. Регрессия/универсальность

Сохранить V6 forward RMSE36.775244985. Context encoding выводит группы из schema/
fitting rows, без public column names. Отдельные гипотезы — универсальные dates/
categorical или history для новых observation contracts; сначала leakage checks.
Ranking pointwise baseline ≠native ranker; улучшать только отдельным экспериментом.

## Протокол

До: hypothesis/control/one factor/selection/keep-discard, source/input/split hashes,
ресурсы/deadline. После: ошибки, честные scores, full lifecycle, unchanged-source
tests, новый ZIP/manifest, commit/push/handoff. Official test labels недоступны.
Это применимый autoresearch-цикл CPU AutoML, не исходный GPU LLM проект и не повод
покупать GPU. Следующая официальная отправка — только по новой команде капитана.
