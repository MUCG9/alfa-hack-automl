# Текущее состояние: V10, 22 октября 2026

Branch **work/cpu-research-20261022**, base V9a95c931. Main не менялся.
Капитан восстановил лимиты и отменил остановку на8%; текущий агент продолжает.
Промпт: docs/prompts/next-agent.md. Новые гипотезы требуют заранее записанного протокола.
Официальный лучший остаётся V9 raw2187.849,1940.2s (его21.87/100), не V10.

## Завершённые исследования

|Сравнение|Результат|Решение|
|---|---|---|
|Under70 vs matched3-model LGBM, paired holdouts|mean MacroF1 .646828432→.652199459|Проверили дальше; strong single .651543688, mixed folds|
|Full3fold grouped CV under70|mean .638363183→.640222558; pooled .638309026→.640476085|Два folds хуже; no default promotion|
|Fixed OOF bootstrap500|delta+.002167059,95%[-.001844234,+.006447588]|Интервал пересекает0, conditional fixed predictions|
|As-of1 history,3cuts|40.960973/33.984412/50.924670→39.051678/32.518745/51.096680|Исходный keep gate failed|
|Support-gated asof3,min3periods|39.051678/31.846185/50.924670|Recent лучше, oldest validation/test CSV byte parity; screen pass|

Полные fingerprints/recipes/метрики/ошибки: docs/experiments/v10_*.json/md.
Public folds многократно использованы, это не private/official-score estimate.

## Реализация и архивы

History helper strictly-earlier fitting targets, независимые inner/outer/full
transforms; static contexts/time semantics validated. Global min3periods не
гарантируют support каждого context. Прежний TE не стал causal.21history checks.
Diversity tool19checks, hardened release verifier3checks с partial failure receipts.

**asof3** source0933a66:212unique +23exact-unpacked pass,6support workers pass.
release/solution-v10-asof3.zip, SHA32120f240f0703f0f80de4a020a9be9c3c737070774b217dcb28954bef3acf2a.
Defaults этого архива не менялись. asof1/asof2 и их evidence сохранены отдельно.

**history4** source8f6b73e: один новый min3history portfolio entry после semantic,
только numeric-period time regression со static metadata, ranking исключён.
Class/text/старые recipes/relative order/default12trials/9900s/confirmation/blends
сохранены. Existing fallback может унаследовать history; измеряется вся процедура.
release/solution-v10-history4.zip,72537bytes,51flat files,
SHAa42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8.
14frozen-V9 portfolio-parity cases и8search-choice checks прошли.
Ожидается216unique source checks. Итог его качества/полных gates — ниже и в README;
до этого никакой автоматической рекомендации submit.

Frozen V9 full default regression повторён: search39.321110258,confirmation34.229379712,
mean36.775244985,exit0/refit/integrity pass. Итоговый CSV SHA
c1556d566cd24de3dc4bed107fbfe7f517dea14dd2c53c583545af08ed43f4e0 — точная parity.
Portable evidence release/v10-history4/v9-baseline-{assessments,report}.json.

## Последние jobs / дальнейшие действия

Последняя очередь session29369: test-runs/run-v10-agent-followups.py,
state test-runs/v10-agent-queue.json. Последовательно: full history4 regression,
216source gate,23unpacked, bounded1trial/600s full-size class lifecycle. Последний
проверяет упаковку/export, не новую full-default classification quality.
Не дублировать jobs; итог checkpoint будет дописан ниже по фактическим JSON.
Predeclared keep full agent: ОБА RMSE cuts лучше V9 +refit/export/integrity.
Если mixed — не продвигать как успешный метод, сохранить точный результат.

Следующая гипотеза **предложена, НЕ запущена**: existing ExtraTrees branch к strong
calibrated LGBM, fixed blend, paired screen→conditional grouped CV→full agent.
Сначала заморозить protocol/recipes; детали docs/experiments/v10_next_stage.md.

## Окружение и безопасность

test-runs/venv-core/bin/python: Python3.12.3,numpy1.26.4,pandas2.2.3,scipy1.12,
sklearn1.5.2,LGBM4.6,XGB-cpu2.1.4,CatBoost1.2.8,openai1.68.2. .venv не смешивать.
Локальные8GiB/full swap: тяжёлые fits И fixture checks строго последовательно;
2threads benchmarks,1thread suite, memory/watchdog; чужие процессы не трогать.
Все10input SHA сверены; ignored public_tasks и venv не входят в Git.
Original requirements SHA9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6
не менялся. ZIP только flat Python+requirements. Historical archives неизменны.

V10 offline, новых live Qwen calls нет. Local fake HTTP не live proof. Private API
окружение отсутствует; предыдущий managed protected-input rejection не обходить.
Ключи никогда не в handoff/Git/argv/logs. Нового official submit/main merge нет.

Git remote https://github.com/MUCG9/alfa-hack-automl. Последний подтверждённый remote
work/cpu-research-20261022=c46170f. Push пяти коммитов до ebd9242 отклонён auto-review:
не подтверждены remote ownership/full payload. Read-only ls-remote подтвердил ref;
аудит18outgoing blobs/17paths иZIP не нашёл credentials/raw data/row predictions.
Финальный статус отправки будет дописан ниже. Отказ нельзя обходить другим каналом.

## Актуальный завершённый checkpoint после восстановления лимитов

Очередь29369 завершилась exit0: history4 full regression +216repo +23unpacked +
bounded class1trial lifecycle PASS. Никаких оставшихся jobs этой очереди нет.
History4 RMSE38.902803731/31.991659384,mean35.447231558 против V9
39.321110258/34.229379712,mean36.775244985. Прежний both-cuts keep gate выполнен,
снижение mean3.611%; selected90/10asof-LGBM/CatBoost; CSV05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673.
Полное evidence release/v10-history4/{quality-comparison,regression-report,repo-tests,
unpacked-tests,classification-bounded-assessments,sequential-gate}.json.
Это технически проверенный кандидат, не официальный результат V10.

Следующий protocol v10_extratrees_protocol.md и candidates JSON: strong LGBM vs
fixed50/50 LGBM+existing XT; paired42/43, CV73 только при обоих улучшениях.
Не запускать дубликат; проверять test-runs/v10-extratrees-paired/results.json.
Следующий push также был не выполнен: auto-review исчерпал usage limit (review
failure, не новый unsafe verdict). Пользователь сообщает лимиты восстановлены;
повтор возможен после проверки нового конкретного исходящего payload, не обходом.
