# Ночная очередь исследований

Капитан23октября разрешил продолжать автономно ночью без вопросов. Это
продолжение прежнего поручения: MVP, затем анализ и несколько измеренных
итераций. Работа на своей ветке; публичный push кода/технических отчётов разрешён
отдельно. Main, official submit, платные ресурсы и дополнительные Codex agents
не задействуются.

Актуально03:40МСК: полный MVP завершён на обоих tasks; PID33136 exited.
meanF1 .6544845346080569 и RMSE36.02469255996805 хуже V11/V16. Итоговые
CSV/refits/integrity и все четыре actual partitions независимо проверены:
`mvp01_complete_20261023.json`, `mvp_comparison_partitions_20261023.json`.
Posthoc cached blend без fits даёт .6572695988152342, тоже ниже control;
это не новый полный refit и не изменение первоначального результата.
Ночная очередь PID37960/create_time1792705065.83 проходит classification HPO;
FE-02 followup PID49264 ждёт. До завершения ОБОИХ source заморожен.
Process identity/receipt/lock проверять перед любым новым fitting.

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

До HAR-01 генерации общий feedback обоих prompt modes также дополнен числами
independent fitting feature groups/validation rows по классам из сохранённого
outer split и actual HPO work. Group overlap отклоняется до API call. Три dev
проверки PASS, включая duplicate rows vs independent groups. Это одинаковый
обогащённый контекст для двух промптов; эффект самого support tool отдельно не
изолирован. Не выдавать такое сравнение за исходный полный baseline агента.

HAR-01 также сохраняет raw terminal JSON в ignored artifacts до нормализации,
отдельно считает raw/supported/rejected proposals и причины contract rejection.
Это observer вокруг того же `llm_plan`, без изменения prompt/parser/API cap;
source MVP остаётся прежним. Четыре dev проверки PASS, включая отклонённый
feature_code при унаследованном feature_views и восстановление gateway callback.
Raw ответы не коммитить. У двух текущих MVP вызовов осталось по одному supported
recipe; сырой ответ тогда не сохранялся, причину отсутствия второго не выдумывать.

Подготовлен отдельный FE-02 протокол и trusted dispatcher сохранения исходных
features: `fe02_protocol_20261023.md`. Пока новых fits нет. Три dev-проверки
union/order/rows/weights/skip PASS. Actual flat worker import и expected rejection
неподходящего task kind проверены до fitting (0 model fits). Этот тест не является
live ML smoke. FE-02 запускать только после завершения текущей ночной очереди и
проверки training lock; canonical source до этого остаётся замороженным.

FE-02 уже автоматически запланирован: followup PID49264/create_time1792709589.83,
receipt `fe02-identity.json`, статус `fe02-20261023/followup.json`. Сейчас он
waiting_for_overnight, lock по-прежнему принадлежит PID37960. Не запускать
ручной дубль. Wait+screen21600s, fitcap3600s; canonical source нельзя менять
также между завершением основной очереди и этим followup. Проверка busy-lock
и сохранения чужого lock PASS, без task discovery/fits.

`summarize_mvp.py` теперь независимо пересчитывает также per-class F1, проверяет
group disjointness/forward chronology и сохраняет fitting/validation group
support. Проверен на реальных regression artifacts (прежняя mean неизменна)
и текущем class search leader: F1 .6577309532263398, Analysis .29333333333333333,
Worms fitting46/validation19 independent groups. Это search result, не final mean.

Подготовлен `tools/review_autoresearch.py`: один organizer Qwen call с созданным
skill и snapshots metadata-only receipts, максимум4096 output tokens/180s.
CLI/help проверен, реальный review ещё не запущен. Ответ — untrusted analysis/
гипотезы, без автоматического применения, новых прав или ML-quality claim.


REVIEW-01 live завершён:16481tokens,6.712s. Числовой supported-class contract
не был явно включён (ссылка на локальный файл не загружает его в API), Qwen
ошибочно назвал Worms причиной gate. Реальная violation — Analysis695groups;
Worms46groups исключён из >=100 gate. Аудит:review01_audit_20261023.json.
REVIEW-02 preregistered: те же frozen facts/skill, явные contracts и evidence IDs,
код вычисляет gates; ответы только гипотезы, не automatic actions. Три no-fit
проверки ID/control/gate/resource bounds PASS. Это interface iteration, не
изолированный A/B или ML gain.


REVIEW-02 выполнен live на тех же frozen фактах и том же skillSHA:5.691s,
14158tokens (14155prompt/3completion),1attempt. HTTP ok, но returned `{}`;
схема отклонена, без retry/actions/fits. Причина пустого ответа неизвестна:
общий gateway использует json_object без ограничительной schema. Ни улучшение
review, ни ML gain не установлены. Аудит:review02_audit_20261023.json.
В skill добавлен проверенный operational lesson: локальные ссылки не загружаются
plain API, critical contracts нужны в контексте, числовые gates/валидация — код.
Installed copy синхронизирована с guard против чужих изменений; validation PASS.
FE-01 classification также COMPLETE: .6547938868310776→.654200887190105 mean
сильного SINGLE control/selector. Cut42 хуже (.655863→.650262),cut43 лучше
(.653724→.658140); paired gate FAIL. Это не mean полного V11 ансамбля.


Подготовлен отдельный no-fit regression test `tests/test_hpo_anchor.py`.
Real adapters construction + actual Optuna с injected worker (0 model fits)
воспроизводит drift первого trial для sparse LGBM/XGB recipes: defaults63/5
против adapter31/3 и XGB6/5 против adapter8/8. Explicit measured controls PASS.
Тест пока RED, исправление canonical source ОТЛОЖЕНО до завершения queue+FE-02.
Добавлена также проверка legacy XGB depth alias и явного max_depth precedence.
Эти sparse recipes не использованы в измеренных screens; прежние scores и
source343/exact-unpacked23 относятся к зафиксированному исходнику.
