# Реестр исследований: что уже известно

## Новый разрешённый этап23октября2026

|ID|Состояние|Доказательство|
|---|---|---|
|MVP-01|COMPLETE/REJECT: F1 .654484535, RMSE36.024692560; оба refits/CSV/integrity verified|[receipt](../experiments/mvp01_complete_20261023.json)|
|LIVE-01|DONE: настоящий organizer API roles→planner, Optuna4, active CatBoost selector, refit/CSV/integrity|[live receipt](../experiments/mvp_verification_20261023.json)|
|FE-01/HPO-01|COMPLETE/REJECT по declared standalone paired gates; defaults OFF|[независимая сводка](../experiments/overnight_screens_20261023.json)|
|HAR-01/02|COMPLETE/REJECT по paired gates; matched prompts и typed DSL фактически проверены|[разбор](../experiments/research_conclusions_20261023.md)|
|FE-02|COMPLETE/REJECT: original+top32, better mean SINGLE, один cut потерян|[receipt](../experiments/fe02_results_20261023.json)|
|BLEND-01|REPLAY PASS, GROUPED CV REJECT: fold0 primary/Analysis loss;6/6workers, exactly-once coverage|[CV receipt](../experiments/blend01_cv_results_20261023.json)|
|REG-BLEND-01|FORWARD QUALIFICATION PASS:3cuts и mean vs Random8/anchor mixtures; full deployment выполнен в PIPE-02|[receipt](../experiments/reg_blend01_forward_20261023.json)|
|PIPE-02|COMPLETE/LOCAL QUALIFIED opt-in: F1 .659317843/RMSE35.397298144, full refits/CSV/integrity PASS,0owned jobs|[итог](../experiments/pipe02_complete_20261023.md)|
|META-REVIEW|3реальных Qwen calls: numeric/semantic ошибки даже при schema PASS;0автоматических actions|[анализ](../experiments/research_conclusions_20261023.md)|
|SKILL|DONE/INSTALLED: Karpathy-based autoresearch-ml, independent copy/hash parity|[skill](../../skills/autoresearch-ml/SKILL.md)|

Qualified default V11/V16 сохраняется. Новых official submit/main merge/extra
agents нет. Верхняя таблица заменяет исторические статусы ниже.

Статусы: KEEP=метод прошёл свой заявленный gate; REJECT=конкретный рецепт не
прошёл; MIXED=направления расходятся; DONE=инженерная возможность проверена;
PROPOSAL=обучений/результатов метода нет. Отказ относится к точной процедуре,
не ко всей библиотеке/классу алгоритмов. Числа разных scopes напрямую не сравнивать.
Это сводка семейств экспериментов, не обещание перечислить каждую из 100+workerfits;
полные recipes/outcomes/fingerprints находятся по ссылкам.

## Текущий инженерный этап без обучения

|ID|Состояние|Доказательство|
|---|---|---|
|ERR-01|DONE: отдельный компонент, строгие контракты, проверка артефактов, ошибки/срезы/парные сравнения/интервалы/отчёты; 100 focused checks PASS|[реализация](../experiments/error_passport_20261022.md), [проверки](../experiments/error_passport_verification_restored_20261022.json)|
|BASE-01|DONE: transfer97f0cf4, 852 файла, восемь search/confirmation-паспортов и фактические CSV проверены. Mean F1 .6593178433614652, RMSE35.44723155783769 совпали V11/V16; без fits|[checkpoint](../experiments/base01_complete_20261022.md), [закрывающий receipt](../experiments/base01_verified_20261022.json)|

Ни один из этих этапов не меняет обучение/отбор и не является новым приростом метрик.

## От V1 до V11: что уже вошло в проект

|Этап|Работа|Статус/вывод|Доказательство|
|---|---|---|---|
|V1→V2|Stopping по целевой метрике, мягкие class weights, inner calibration, ensemble/fallback|KEEP; ранняя рабочая основа, main остался V2|[v2 review](../v2_review_notes.md)|
|V3|Модули/API/contracts/flat compiler, fitting-only data policies и fail-safe|DONE; не переписывать архитектуру заново|[архитектура](../architecture/implementation.md)|
|V3 sampling|ROS1.5, compression, duplicate downweight/cap, under85|REJECT/MIXED для class; noop остался default|[V3 evidence](../../release/v3/README.md)|
|V3 masking|mask25/prob.15/syntheticweight.5 на частично missing continuous columns|KEEP как отдельный regression candidate, небольшой paired gain; не обязательная политика|[V3 evidence](../../release/v3/README.md)|
|V4 OVA|OVA+calibration и fixed50/50 смесь|REJECT: OVA pooled .630416 против .637929; смесь не сильнее calibration|[полная CV](../experiments/v4_cv.md)|
|V4 feature screens|Ratio/log, context/count/recency и Qwen hypotheses, class-weight/специалисты|Уже исследованы; не повторять под новым названием без прочтения точного recipe|[V4 summary](../experiments/v4_summary.md),v4_results.json,v4_qwen_ablations.json рядом|
|V4 history3|Metadata-derived hierarchy/context statistics для регрессии|KEEP: full meanRMSE39.074979→36.775245 против тогдашнего search2; будущий период в validation|[V4 summary](../experiments/v4_summary.md)|
|V5→V7|Форматы/roles, несколько независимых targets, groups/dates, limitedpointwiseNDCG, binarypositive probability|DONE с ограниченным контрактом; не native/listwise ranker и не jointmultioutput|[V6](../../release/v6-universal1/README.md),[V7](../../release/v7-semantic1/README.md)|
|V5 XGB calibration|Одна inner decision calibration для MacroF1|KEEP:3fold pooled .611757→.617988; optional candidate уже в portfolio|[исследование](../experiments/v5_xgb_calibration.md)|
|V8→V9|Shared startup/deadline/API ledger,64KiB metadata, structural feedback/frames reuse|DONE,169unique/23repeated, ML CSVparity с V6/V7|[V9](../../release/v9-roles1/README.md)|
|V8 XGB OOF3|Calibration на 3trainingOOF вместо одного innerholdout|MIXED/REJECT: mean .649134619→.649029401,~2x время|[результат](../experiments/v8_xgb_oof_calibration.md)|
|V9 seed blend|LGBM42/47 fixed50/50|REJECT: mean .651543688→.643384454,оба хуже|[результат](../experiments/v9_lgbm_seed_blend.md)|
|V10 under70|Matched3model ensemble с majority undersampling|MIXED: CV pooled .638309→.640476,но 2folds хуже; gain сосредоточен на Worms|[V10 log](../experiments/v10_progress.md)|
|V10 asof1/2/3|Strictly earlier lastperiod/trend, затем minimum3fittingperiods|asof1 REJECT; asof2 unmeasured intermediate; asof3 KEEPscreen с identity на старшем cut|[V10 log](../experiments/v10_progress.md)|
|V10 history4|Встраивание support-gated history в полный агент|KEEP: full meanRMSE36.775245→35.447232,оба cut лучше|[release](../../release/v10-history4/README.md)|
|V10 ExtraTrees|Fixed50/50 calibratedLGBM+XT|MIXED/REJECT: mean .651544→.651361,первый cut хуже; retry успешно завершён после interruption|[результат](../experiments/v10_extratrees_results.md)|
|V10→V11 feature views|Fixed50/50 originalcategoricals +cross-fittedcategoricalsingles/pairs|KEEP: paired+3foldCV+fullagent; pooledCV .640210→.645099; fullF1 .653281→.659318|[CV](../experiments/v10_class_te_cv_results.md),[V11](../../release/v11-featureviews1/README.md)|

Положительный component/CV результат ≠ прирост полного агента. В V11 сохранены
iteration trees nested ensemble. Исторические plain-LGBM screens не равны
полной выбранной смеси V11; нельзя сравнивать их как один и тот же контроль.

## V12–V17: что проверено, но НЕ включено по умолчанию

|ID|Гипотеза|Результат/решение|Доказательство|
|---|---|---|---|
|V12|Bounded positive log-space Nelder–Mead class factors|REJECT: pairedmeanF1 .651543688→.650925929,оба cut хуже; oldcoordinate unchanged|[результат](../experiments/v12_threshold_results.md)|
|V13|PinnedAutoGluon1.3.1 GBM+CAT, nonbagged/nonstacked, inner-only featuregen|REJECT: mean .651543688→.627271597,оба cut хуже; frameworkfit/refit и isolation PASS|[результат](../experiments/v13_autogluon_results.md)|
|V14|Cached13trial selection preserving ordinary control trace|REJECT без fits: гипотетический mean .660102396,но search ниже V11; predeclaredgatefail; не runtime|[результат](../experiments/v14_search_anchor_results.md)|
|V15|Inner log-residual moment smearing|REJECT: latestforwardRMSE39.051678→40.160774,oldercutsidentity; OFF|[результат](../experiments/v15_smearing_results.md)|
|V16|Inner original-scale least-squares inverse correction|REJECT: latestforwardRMSE39.051678→39.354053,oldercutsidentity; OFF|[результат](../experiments/v16_least_squares_results.md)|
|V17|min_child_samples25→10 в обоих featureviews|REJECT: pairedmean .654793887→.646085495,оба cut хуже; CV не запускалась|[результат](../experiments/v17_leaf_results.md)|
|V16 default repeat|Проверить поздний код с экспериментальными флагами OFF|DONE: full обеих задач, фактические CSV/metrics/selectedrecipe/iterations совпали V11; НЕ новый gain|[закрывающий gate](../../release/v16-mean1/full-default-parity.json)|

Threshold tuning уже работает в контроле; «добавить thresholds» не новая гипотеза.
Нельзя принудительно balanced поверх уже существующих sampleweights или log1p по
одному skew. Inner optimum может ухудшать outer/forward качество — это измерено.
Включение dormant capabilities без нового gate отменило бы смысл этих результатов.

## Что ещё НЕ сделано / лишь предложено

|Направление|Настоящий статус|Условие продолжения|
|---|---|---|
|Новый live Qwen roles→planner→worker→refit→CSV|Не проверен в текущем gateway; mocks есть, старые V4livecalls не тотпуть|Безопасная privateenv, ограниченный smoke; никаких секретов изистории|
|Adaptive CPU HPO с Optuna/FLAML|PROPOSAL, полного сравнения нет; локально отсутствовали|Допустимый pin/import и контракт splits/metric/budget, equal-budget контроль|
|Support-aware classwise LGBM/XT shrinkage|PROPOSAL, не fittingresult|[заранее описанный метод](../experiments/v10_support_blend_proposal.md), новый strongcontrol/gates|
|AutoGluon bagging/stacking|Не испытывался этим V13; V13 не bagged|Контроль групп/time на внутренних folds, memory/time feasibility; низкийприоритет|
|Calendar/cyclic block для declared datetime|PROPOSAL|Есть подходящие заранее labelled задачи, fitting-only transform|
|LightAutoML backend|Нет локального import/fit proof|Не заменять архитектуру по одному import, сначалаконтракты/ресурсы|
|SMOTENC/generative augmentation/pseudolabels|Не реализованы|Не приоритет, отсутствует evidence; никаких externaldata/pretrained|
|Независимая private оценка|Недоступна|Официальный сервер/новые неизвестные задачи, не новый seed на томже public|

[Порядок дальнейших действий](PLAN.md). Библиотеки/методы изрезерва не составляют
автоматическую очередь «запустить всё». У каждого отдельный новый protocol.
