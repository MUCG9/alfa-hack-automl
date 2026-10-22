# Промпт передачи: продолжение Alfa Hack AutoML

Продолжай ML-исследование и разработку по поручению капитана. Цель — максимальная
целевая метрика универсального CPU AutoML-агента. Капитан разрешил обучение,
поэтапные эксперименты, Qwen API и push рабочих веток. Ресурсы второстепенны внутри
лимита платформы8CPU/32GB/3часа. Он просит чаще коммитить завершённые этапы и
при приближении к10% резерва лимита сохранять передачу, не начинать новые долгие
эксперименты. Точный процент счётчика не выдумывать, если интерфейс его не показывает.

Работа приостановлена на логическом checkpoint после успешного полного regression
history3. Все наши ML jobs, очереди и Qwen credential-процессы завершены. Ничего
не нужно «дожидаться» или запускать параллельно старым jobs. Официальный submit,
merge main и дополнительные AI-агенты не разрешены. GitHub push разрешён.

## С чего начать

Репозиторий https://github.com/MUCG9/alfa-hack-automl . Клонируй ветку
`work/pipeline-review-instructions`, проверь HEAD и создай свою рабочую ветку.
`main` — сохранённая v2; `experiment/modular-augmentation` — прежняя интеграция
`a9af568`. Не начинать с main. Прочитай AGENTS.md, docs/experiments/v4_summary.md,
release/v4-history3/README.md и этот промпт. Старые migration/handoff v3 — история.

Canonical код — src/automl, root agent_*.py/model_utils — shims. Между компонентами
импорты через соседний api.py. Flat ZIP собирает tools/build_submission.py, проверяет
соответствие текущему source и распакованный запуск tools/verify_release.py.
Исходный requirements.txt сохранён, SHA
`9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
Нельзя менять runtime dependencies, zip-ить root shims или добавлять pretrained
модели: кейс их запрещает. TF-IDF/LSA с нуля допустимы; готовые embeddings — нет.

Текущий кандидат: release/solution-v4-history3.zip, source commit16987fb,
SHA `8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f`,51694bytes.
59repo checks (включая18quality) +23повторных unpacked checks прошли.
Архивы v1/v2/v3, v4-candidate/source1 и v4-search2/source2 сохранены отдельно.
Не перезаписывай их. Для следующих изменений делай новый архив/manifest/evidence.

## Данные, среда и авторизация

На текущем ПК cwd `/home/dima/Документы/ml/alfa-hack-automl`.
Оба public task.md и все8CSV уже в ignored public_tasks/classification/ и
public_tasks/regression/. Все10 SHA совпали с docs/handoff/public_inputs.json.
На другом ПК нужны эти разрешённые public inputs из папки организаторов/архива
капитана; raw CSV в Git отсутствуют. Не выдумывать метрики до получения данных.

Измерения делались через test-runs/venv-core/bin/python: Python3.12.3,
numpy1.26.4,scipy1.12.0,pandas2.2.3,sklearn1.5.2,LGBM4.6.0,
xgboost-cpu2.1.4,CatBoost1.2.8,OpenAI1.68.2. Venv с system-site-packages и
локально закреплёнными core versions. Отдельная .venv подготовлена, но её результаты
не смешивались. На новом ПК создай CPU venv по requirements-dev-cpu.txt с constraints
исходного requirements. Фиксируй реальные версии; не ставь пакеты в system Python.

У этого ПК8GiB RAM, мало доступной памяти, swap почти заполнен. Тяжёлые jobs строго
последовательно,2threads, local whole-tree memory guard1.7GiB. Это локальный лимит,
а не платформа32GB. Экспериментальный worker watchdog1200s и full watchdog10100s
различать; штатный полный budget9900s. Не объявляй interrupted run успешным.

Авторизация GitHub использовалась через временный private process, без credential
в URL/config/файле; после передачи процесс закрыт. На новом ПК настрой свой
credential manager/GitHub CLI. Токен не копировать в prompt/логи/репозиторий.

Qwen капитан разрешил, ключ в Git отсутствует, private API процессы закрыты.
Настрой приватное окружение, не проси прислать ключ в открытый prompt:
OPENAI_BASE_URL=https://changellenge.up.railway.app/v1,
OPENAI_MODEL=qwen/qwen3.8-27b. Общий командный budget600/день, reset03:00МСК;
проверяй актуальный /key/info. Endpoint/model реально отвечали через SDK, reasoning0.
Без API продолжай offline задачи. Workers ключ не получают.

## Что достигнуто

Главная проблема регрессии: public train периодов1–5, весь test периода6.
Случайный holdout скрывал переход в будущее. Runtime default auto-validation
консервативно распознаёт документированный числовой observation period, исключая
construction year, и применяет forward validation. Старый режим доступен через
--validation-strategy legacy. При невозможности split записывается warning/fallback.
Time confirmation — предшествующий период с исключением будущих строк.

Исправлены owned-process watchdog/cleanup (включая detached workers), exit-code
validation, изоляция preprocessing внутри каждого inner/outer/full fit, сокрытие
fit errors под rare-class fallback, выбор собственного worker из flat ZIP.
P0 воспроизвёл validation/submission CSV побайтно на первых фиксированных рецептах
двух задач/seeds42/43. Primary Macro F1/RMSE не переопределялись.

Добавлены cross-fitted target encoding, автоматические recurring context groups,
composite groups/counts/recency, OVA, training OOF factors и pair specialists opt-in,
TF-IDF+logistic/LSA opt-in. Не все дали выигрыш. Полная CV и bootstrap реализованы
как dev инструменты, runtime по-прежнему использует search/confirmation, не K-fold.

History3 распознаёт из data_dictionary статические числовые construction properties.
На fitting rows строит coarse/fine ключи: лучший повторяющийся числовой контекст +
категории + статическое свойство. Coverage проверяется на fitting periods, порог25%;
при недостатке истории возвращается к старым ключам. Ни y, ни outer/test X не выбирают
ключи. Target-статистики cross-fit, ID/target исключены. Имена public колонок в src
не зашиты, rename/held-out isolation tests есть. Opt-in
`target_encoding_hierarchical=true` включает auto groups и target encoding;
в time regression portfolio добавлен отдельный metadata+log кандидат при наличии
подходящей схемы. Для остальных задач метод не принудителен.

## Завершённые результаты, не повторяй их без причины

Полные default offline pipelines,2threads,original inputs,fullrefit/export,
integrity=true:

- Frozen v3 classification:2628.518s, search ensemble Macro F1 .654372724,
  mean search/confirmation .653714716. Рецепт .9LGBM-cal/.1XGB. Это впервые полностью
  завершённый v3 class baseline, прежние interrupted runs остаются историей.
- V4 search2 regression:292.920s, RMSE40.426939/37.723019,mean39.074979.
- **V4 history3 regression:312.386s, RMSE39.321110/34.229380,mean36.775245.**
  Та же пара forward split hashes/input hashes; mean ниже на5.89% против search2.
  Итоговый CSV SHA c1556d566cd24de3dc4bed107fbfe7f517dea14dd2c53c583545af08ed43f4e0.

Search/confirmation многократно использовались для выбора рецептов и весов.
Это public validation, НЕ unbiased private estimate и не официальный score.

Fixed controlled history3:41.002541/38.062736 контроль →40.960973/33.984412.
Первый LGBM forward control52.912918/44.564333. Fixed selected_recipe старого v3
ансамбля, повторно обученный из frozen ZIP на тех же outer cuts,79.475395/41.262690;
это НЕ независимый полный v3 search на каждом новом cut. Scope сравнения не менять.

Полная3-fold class CV: pooled control .636401856, старая calibration .637928932,
OVA+calibration .630416015. Последняя проиграла на всех3folds, хотя screening
seeds42/43 обещал небольшой выигрыш. В default она не включена. Фиксированный
OOF blend .5/.5 также не победил сильный контроль. Bootstrap500 по54228 feature
группам условный по сохранённым predictions, не интервал private score.

Qwen generic feature/schedule hypotheses дали разнонаправленные результаты;
адресные Qwen context keys оказались хуже. Manual-context+log помог, затем его
механизм обобщён в автоматический history3. Суммарно107 fixed candidate-fold jobs
(82+9CV+12Qwen/context+4history3), отдельно3full default и2bounded lifecycle.
Не суммируй23unpacked с59 как82 различных теста:23 — повтор в иной упаковке.

В source2/3 отдельно изменён XGBoost class fallback: сохраняет веса incumbent,
исследует глубину,min_child_weight,L2 плюсseed; раньше менял почти только веса.
Тест подтверждает реально разные effective configurations и границы, но
**полный новый classification benchmark ещё НЕ выполнен**. Нельзя приписывать
ему F1 завершённого v3. Это первая следующая задача.

## Следующие действия

1. Проверь git/status/manifest, прочитай полный summary. Существующих живых jobs нет.
   На этом ПК подробные outputs в /tmp/alfa-* и ignored test-runs/stages/, но /tmp
   может исчезнуть после reboot. Portable recipes/aggregated metrics/source ZIPs
   сохранены в Git. Старые run-*.sh больше не являются активной очередью.
2. Полный default **history3 classification offline**, последовательно, новая папка:

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLCONFIGDIR=/tmp/alfa-mpl \
test-runs/venv-core/bin/python scripts/benchmark_release.py \
  --archive release/solution-v4-history3.zip \
  --task public_tasks/classification/task.md \
  --output /tmp/alfa-next-history3-class --offline \
  --jobs 1 --threads 2 --memory-gb 1.7 --watchdog-seconds 10100
```

Не добавляй --max-experiments1 или300-second budget к проверке, которую называешь
полным default search. После изменения src сначала собери новый archive; новый
ZIP по умолчанию должен побайтно совпасть с canonical source. Historical trusted
SHA override нужен только для точного старого archive, не для обхода несоответствия.

3. Сравни classification с завершённым v3 по обеим legacy folds/mean и статусу
   refit/export. Если новый capacity search переобучается, проверь сохранение сильных
   исходных portfolio controls при confirmation: top3 по одному search могут вытеснить
   устойчивую LGBM множеством похожих XGB. Попробуй family diversity/резерв controls
   отдельной измеряемой политикой, не меняй metric/splits ради числа.
4. Фиксированные новые финалисты проверь полной CV с сильным контролем, все splits,
   fold mean/std и pooled OOF отдельно. tools/benchmark_candidates.py --folds3;
   tools/compare_oof.py — парный bootstrap и заранее заданные blends. Не тюнь веса
   по тем же OOF с заявлением unbiased результата.
5. Затем полный online Qwen lifecycle history3, обе задачи последовательно, отдельно
   от matched offline comparison. В новой папке benchmark без --offline и с private
   env. SDK/planner реально проверены, но полного online search текущего агента ещё нет.
   Сохрани реальные plans/effective params/usage/failures/CSV SHA, не только HTTPok.
6. Следующие регрессионные идеи: ещё один ранний forward cut; лучше сообщать Qwen
   фактически найденные training context groups и feature importance (они уже есть
   в worker result). В текущем context mostly params/schema, поэтому targeted Qwen
   предложил слишком coarse ключи. Не отправляй raw labels/maps. Не зашивай public
   feature names или готовые case-specific recipes в submission.
7. После этого можно проверять OOF blending/stacking отдельным outer уровнем,
   inner-OOF выбор пар rare specialists (сейчас пары выбирались in-sample и не помогли),
   copy-only vs masking и balanced subsets. SMOTENC,stacking,pseudo-labeling,
   multi-target/ranking НЕ реализованы; pretrained embeddings запрещены кейсом.
8. При каждом изменении src: appropriate tests, новый flat ZIP, unpacked gate,
   реальный metric/lifecycle, truthful evidence и отдельный commit/push. Не редактируй
   source одновременно с CLI integrity tests: guard правильно аннулирует такой run.
   Не прерывай owned long run незаметно и не называй partial успешным.

## Где evidence

- docs/experiments/v4_summary.md — итог.
- v4_results.json — первые82fixed workers и8точных source snapshots в release.
- v4_cv.md, v4_cv_results.json, v4_cv_final_bootstrap.json — полная CV.
- v4_live_planner*.json, v4_context*.json, v4_qwen_ablations.json — реальные API/абляции.
- v4_history3_results.json —4paired workers и fitting group metadata.
- v4_v3_default_full.json, v4_search2_reg_full.json, v4_history3_reg_full.json —3default runs.
- release/v4-history3/ — exact manifest,59+23tests,full regression evidence.

Официальная обратная связь пользователя/скриншот: первое857.742 (~8%),
второе1694.145 (~16%, ранее округлял17%). RMSE43.62→41.99, Macro F1 .6156→.6534
сообщены текстом. На снимке v3 ещё «Проверяется», итогового официального v4 нет;
точная привязка metric-чисел к archive SHA не подтверждена. Не конвертировать
локальные улучшения в платформенные баллы: baseline нормирования неизвестен.

Работай самостоятельно без subagents. Push рабочих веток разрешён, force-push,
merge main и официальный submit — нет. Подготовь конкретный проверенный результат
и согласовывай отправку только когда пользователь действительно её запросит.
