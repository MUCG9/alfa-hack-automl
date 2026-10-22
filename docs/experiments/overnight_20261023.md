# Ночная очередь исследований

Капитан23октября разрешил продолжать автономно ночью без вопросов. Это
продолжение прежнего поручения: MVP, затем анализ и несколько измеренных
итераций. Работа на своей ветке; публичный push кода/технических отчётов разрешён
отдельно. Main, official submit, платные ресурсы и дополнительные Codex agents
не задействуются.

Текущий полный MVP выполняется отдельным owned coordinator PID33136. Ночной
координатор PID37960/create_time1792705065.83 **ждёт** его и известных дочерних
процессов. Прежде чем начать новый fit, проверить обе identity receipts и
`queue.json`; не дублировать запуски. Теперь filesystem/network sandbox выключен,
обычный process inspection видит owned jobs; при возвращении sandbox учитывать
ранее обнаруженную разницу видимости PID.

Последовательность после завершения MVP:

1. Независимая проверка финальных CSV/двух validation артефактов.
2. FE-01 regression: qualified asof control против selector32, три forward cuts.
3. HPO-01 regression: control/random/TPE, восемь inner trials на каждый sampler
   и cut, три forward cuts; startup3.
4. HAR-02 regression: ровно пять уже сгенерированных декларативных признаков
   против qualified asof control, selector OFF в обеих ветвях.
5. HAR-01 regression: одинаковая measured feedback, baseline/staged промпты,
   затем отдельные forward benchmarks их кандидатов.
6. FE-01 и HPO-01 classification на paired group cuts42/43.
7. HAR-01 classification: matched prompts и paired benchmarks.

Все fits строго последовательны: два потока,1536MiB/600s per benchmark worker,
максимум1800s на inner study, максимум10800s на HPO matrix. Общий ночной
координатор ограничен21600s вместе с ожиданием; каждый subprocess имеет watchdog
и memory guard. Это локальные guards, не platform timeout. Source/input/split
fingerprints и отдельные immutable directories сохраняются. Межпроцессная
блокировка отклоняет второй coordinator; две проверки lifecycle PASS.

Ночной runner не делает Git writes, uploads или default promotion. Каждый этап
пишет JSON и log. Ошибки не подменяются нулевым objective, пропуски не считаются
успешными экспериментами. Canonical source заморожен на исходном343+23 gate;
новые dev tools и документы не меняют исполняемый контестный код.

Четыре отдельных проверки DSL-компилятора PASS; один настоящий Qwen-план дал
пять признаков. Ошибка trusted template с неподдерживаемым np.inf исправлена
до ML fits, исходные JSON сохранены; использовать candidates-checked.json.
Это подтверждение валидности генерации, не качества модели.

Первый измеренный итог MVP regression:39.755603137589205/32.2937819823469,
mean36.02469255996805 против35.44723155783769. Оба cuts хуже; baseline V11/V16
сохранён. Classification ещё выполняется. Positive component screen не равен
готовому улучшенному релизу: нужны заявленные CV/full-agent gates.

Артефакты: `test-runs/qwen-optuna-20261022/overnight-20261023/queue.json`.
Реальный процент остатка app quota доступными tools не предоставляется;
проценты не выдумываются, reset credits не используются.

Независимый `tools/summarize_research.py` пересчитывает primary/per-class metrics
по фактическим source labels и immutable split arrays. Проверяет row order,
disjoint fitting/validation feature groups или forward chronology, nesting HPO
внутри outer fitting rows, совпадение random/TPE inner partitions, выбранный
inner recipe и его outer refit, исходные input/frozen-source SHA. Применяет
заявленные paired/support/rarest-class gates; неполный screen не проходит gate.
Четыре отдельных проверки artifact corruption/gates PASS, без обучения моделей.
Это дополнение к dev tools, не новый canonical source gate.

Промежуточная диагностика classification сохранена в
`selector32_class_diagnostic_20261023.json`: фактические старый/новый search
split arrays совпадают. У single two-view control MacroF1 .6558634659956402,
у selector32 .6502622584145485. F1 Worms .6842105263157895→.5625,
Analysis .3375796178343949→.3258785942492013; supported-class gate уже нарушен
на этом cut. Это descriptive comparison сохранённых runs, не новый independent
screen и не доказательство механизма изменения. FE-01 остаётся отдельной парной
проверкой. Не подбирать top_k задним числом по этому validation.

По прямому поручению капитана создан `skills/autoresearch-ml/SKILL.md` на основе
karpathy/autoresearch, изученный commit228791fb499afffb54b46200aca536f79142f117.
Локальная установка: `~/.codex/skills/autoresearch-ml` содержит независимую копию
versioned каталога с проверенным совпадением SHA, чтобы rollback проекта не
удалял навык. Entry, upstream attribution, профиль alfa-hack и
шаблон `program.md` проверены quick_validate. Новая программа не меняет уже
запущенную очередь и не является измеренным улучшением runtime Qwen.
Сохранение истории вместо destructive reset, inner/group/time validation,
paired gates и отсутствие objective при ошибке — явные адаптации для ML.
Skill/source fingerprints не входят в contest ZIP; canonical hashes неизменны.

Classification experiment05 (CatBoost + selector32) завершился watchdog timeout
900.497s, метрики нет; другой owned worker продолжил очередь. Это отказ по
стоимости/лимиту, не числовая оценка качества CatBoost на полном fit.

Source inspection: отложен узкий дефект HPO anchor для sparse recipes без явно
заданных параметров. `hpo.py` defaults: LightGBM leaves63/reg_lambda5 против
adapter31/3; XGBoost max_depth6/reg_lambda5 против adapter8/8, дополнительно
учесть legacy depth alias. Поэтому bare recipe anchor может менять контроль.
У текущих qualified controls эти параметры заданы явно: measured MVP/screens
этот случай не используют. Не менять frozen canonical source до завершения
owned campaigns. После них исправить engine-specific defaults и проверить
семантическое равенство anchor/control через model construction без fitting.

Classification HPO завершён:900.6s,2 successful из8 maximum trials, ещё один
timeout34.465s. Два successful trials заняли412.532s и425.991s. Startup3 не
пройден: guided TPE attempts0. Inner MacroF1 .6293967027246721→.6296331435097767;
это другие строки, не сравнивать с outer F1. Selected recipe сейчас проходит
outer evaluation. `mvp_cost_diagnostic_20261023.json` сохраняет агрегаты и
observational timing comparison со старым control; это не isolated causal
замер стоимости selector. Архитектурная гипотеза на следующий цикл: условное
включение FE после gate и распределение бюджета по измеренной стоимости вместо
обязательных дорогих стадий. Она пока не проверена как новая полная процедура.

До первых HAR-01 вызовов/fit уточнён dev harness `compare_planners.py`: явный
cap двух distinct proposals после dedup, reject незаявленного selector с receipt
вместо молчаливого изменения рецепта. Общий runtime parser поддерживает3, поэтому
одной инструкции в prompt недостаточно для declared limit2. Две отдельные
проверки cap/factor boundary PASS, без API/fits. Это выполнение исходного
протокола, не смена условий после scores; новый harness SHA будет записан очередью.
