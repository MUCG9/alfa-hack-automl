# Промпт для следующего агента — продолжение V11–V17

Ты продолжаешь CPU AutoML-агента для Alfa Hack 2026. Цель — реальный прирост
целевой метрики универсального агента, не красивый отчёт или обещание75–85баллов.
Работай ОДИН, без дополнительных агентов. Частые логические commits и push в
рабочую ветку, не main; при15%ОСТАТКЕ пятичасового лимита (85%USED) заверши этап
и передай работу. Не используй reset credits и платные ресурсы самостоятельно.

## Первые действия

1. Клонируй https://github.com/MUCG9/alfa-hack-automl и checkout
   work/llm-upgrade-20261022; main — историческаяV2, не текущая разработка.
   Сверь HEAD/tracking ref/dirty tree. Не force push, не перезаписывай чужие правки.
2. Полностью прочитай AGENTS.md, docs/CONTINUE_HERE.md, docs/handoff/current.md,
   docs/experiments/v11_llm_review.md и актуальные release READMEs.
3. Сначала проверь финальный job и новое дополнение current.md: полный V16
   regression→class parity был запущен в test-runs/llm-upgrade-20261022/
   final-default-parity, execution15685. На другом ПК ignored artifacts не будут
   доступны: пользуйся committed assessments, не выдумывай результат.
   Не повторяй завершённые исследования по старым ACTIVE/STOP сообщениям.
   На15:10UTC V16regression completed221.052s/exactCSVparity; class11/12search
   done/exactV11traceparity, final search still running. Это НЕ fullclassPASS.
   Если local controller завершился, первым делом сохрани его assessments/report/
   finalCSVhash и сравни full selection/refit с V11; только затем новые fits.
4. Проверь реальный app usage. Все текущие действия согласуй с новой командой
   капитана; этот файл даёт контекст, не отдельное разрешение на submit/ресурсы.

Предыдущий агент завершает этап по реальному порогу:15:14:20UTC85%USED,
15%REMAINING. На этом чтении class всё ещё11/12, без fullreport/assessment.
Подтверждённый push6c27a65, затем quota-note commit; фактический HEAD сверяй вGit.
Единственный оставшийся bounded ML job — final-default-parity, не новая research.

## Что уже улучшено

Полный offline pipeline V11 featureviews1 улучшил MacroF1 mean
.6532812402233098→.6593178433614652. BOTH search/confirmation выросли:
.6538467374261537/.6527157430204659 →
.6632403174648631/.6553953692580672.
Регрессия meanRMSE35.44723155783769 и итоговыйCSV сохранены побайтово.
Full refit/export/integrity обеих задач PASS, это не только один recipe.
Полный grouped CV коллеги тоже PASS: pooled .640209809443→.645099303706.

V11 ZIP: release/solution-v11-featureviews1.zip,
SHA fbbd2511652814d7c05334ab0240f18b81e88a7b59dfc979efa617011dc84490,
230unique source+23repeated unpacked checks. Исторический архив НЕ перезаписывать.
Latest source f72c6df / V16 mean1:
SHA68e1eb0c933807720178ef4708df2c0dbf55fe9940b0dfb849d7704dbe3b2566,
258unique+23repeated PASS; новые postprocessors по умолчанию OFF.
Проверить итог latest-source full parity отдельно: unit/fixtures не full public.

V11 типизированный feature_views=categorical_te_pair: два фиксированных50/50
LightGBM представления, категории +existing fitting-group-cross-fitted target
statistics/pairs first3schema categoricals, smoothing20; свои fit iteration trees.
Selected global blend содержит две такие рецептуры и XGBoost. Не подменять primary
fixed-blend результат post-hoc более сильной standaloneTE. Не хардкодить колонки.

## Что НЕ повторять без новой мотивированной гипотезы

- V12 log-space bounded Nelder–Mead calibration: BOTH paired cuts хуже old coordinate.
- V13 pinned AutoGluon GBM+CAT procedure: BOTH хуже; inner-only preprocessing и
  refit проверены. Framework import не повод заменить сильный pipeline.
- V14 fixed13trial cached proposal: mean выше, но search ниже V11, заранее
  зафиксированный noninferiority gate FAILED.0newfits, runtime не меняли.
- V15/V16 retransformation: Duan-like moment и original-scale LS factors
  ухудшили последний forwardcut; older cuts skip с точнойCSVparity. ОставленыOFF.
- V17 leaf10 в обоих views: BOTH хуже leaf25; без CV. Не перебирать5/15 posthoc.
- Исторические ROS/compression/under/OVA/random seed blend уже имеют negative/mixed
  evidence. Сначала прочитай их протоколы, не называй комбинацию новой гарантией.

## Следующий обоснованный план, когда капитан возобновит работу

A. Проверить live Qwen ТОЛЬКО через разрешённую приватную env/secret manager, если
капитан предоставит её безопасно. В этом этапе ни одного live API вызова, env нет.
Не извлекать ключ из истории чата, не класть в command/Git/logs, не обходить отказ
защищённого ввода. Mock/localHTTP tests не равны live. Не считать600RUB остатком.
Цель smoke — JSON planner/roles/usage/error fallback, не расходовать весь бюджет.

B. Разобрать bottleneck отбора, а не добавлять ещё библиотек. В featureviews1-report
видно наследование views в fallback и global equal-thirds blend. Часть простых
fixed recipes даёт меньший runtime, но не является лучшим full-agent результатом.
Сначала fit-free анализ cached selection trace/дубликатов/подтверждений и
предъявление новой, отличной от отвергнутойV14, процедуры. Не выбирать веса или
порог по outer truth. До новых fits заморозить protocol/источники/criteria.

C. Новая ML-гипотеза должна иметь fitting-only split-aware реализацию, paired
strong control на42/43 или3forwardcuts, row/class/proba/provenance checks.
Только если заранее заданный screen PASS — exact grouped3fold73 CV with
exactly_once, foldmean+pooled/support gates. После — отдельная runtime integration,
новый immutable ZIP, unchanged-source suite/unpacked gate, FULL default обеих
задач. Слабые одиночные seed/mean gain не повод нарушать заданный keep gate.
После множества public исследований прирост public всё меньше доказывает private;
не обещать официальных баллов без результата платформы.

## Неприкосновенные ограничения

Python3.12,8CPU/32GB/noGPU/3h-task на платформе. Original requirements byte-identical
SHA9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6.
Не менять requirements, не pip изsolution, никаких внешних данных/pretrained.
Canonical src/automl, neighbor API границы, flat builder. Dummy/working CSV
публикуется до дорогого поиска; input sample_submission не перезаписывать.
data policy noop default; weighted/resampled data/calibration/encodings только
fitting rows на каждом inner/outer/fullfit. Не считать df.eval sandbox.
Local RAM ограничена: heavyfits и fixturechecks sequential,2threads/1suite,
явный watchdog/memoryguard, собственные процессы только.

Новый official submit отдельно НЕ разрешён. В текущем чате ждёт ответа ОДИН
вопрос о точномV11. При humanYES — свежие login/counter, одна попыткаV11, receipt,
не ждать server score. Не подменять архивV16 и не использовать старый счетчик.
Последний known score — со слов капитанаV9raw2187.849,1940.2s/21.87из100;
новое сообщение говорит23/100 без breakdown. Не выдавать их за scoreV11.
No extra agents/mainmerge/paid resources/reset credits. При85%USED — checkpoint.

Исходные данные и ключ передаются отдельно безопасно; Git содержит агрегаты,
протоколы, тесты и исходники, не rawCSV/NPZ/predictions/venv/models.
