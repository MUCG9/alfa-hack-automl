# Checkpoint 22.10.2026: v6 full gate и v7 semantic experiment

## Версии и факты

Последняя ветка **`work/semantic-inputs-20261022`**, опубликована в GitHub.
V7 source `b4f8db7`, freeze `12f8d20`; V6 evidence `d5b550e`.
Основа `work/autonomous-score-20261022` (v6 freeze `e783aa3`), ещё раньше
`work/pipeline-review-instructions` (`d950cb9`). Main не менялся, PR/merge не делали.

| Кандидат | Уникальные repo / повторные unpacked | Полный public цикл | Официальная отправка |
|---|---:|---|---|
| v4 history3 Python3.12.14 | 59 /23 на исходном этапе | обе задачи завершены | загружен один раз |
| v5 contract1 | 85 /23 | обе задачи, CSV parity v4 | нет |
| v5 multitarget1 | 111 /23 | обе задачи, CSV parity v4 | нет |
| v5 ranking1 | 124 /23 | отдельный full gate не запускался | нет |
| v6 universal1 | 137 /23 | обе задачи, refit/integrity pass | нет |
| v7 semantic1 | 145 /23 | regression pass, classification выполняется | нет |

Архивы:

- Загружен `release/solution-v4-history3-py31214.zip`, SHA
  `734ec4da69c7513f1896a9b528c35ae5489206df2af360c7650246d4bc0155f1`.
- V6 `release/solution-v6-universal1.zip`, SHA
  `b3b46b6a6bee7b7540fda0db22bf663a7afa090baff6e1b9ee72a3a221e3afb5`.
- V7 `release/solution-v7-semantic1.zip`, SHA
  `a31d1fc7c9bee3403f992f70467e95a446c19dbffdb4cdfea9abf2d035f79b27`.

Полный V6: regression mean RMSE **36.775244985**, тот же CSV, что v4; classification
mean Macro F1 **0.653281240** (0.653846737 /0.652715743), blend90% calibrated LGBM /
10% calibrated XGB. V4 mean0.652742609, v3 0.653714716. Лучший отдельный search trial
V6 0.658219218 — не финальный score pipeline. Прирост против v4 небольшой, против
v3 classification улучшения нет. Никакого перевода в баллы.

Компонентная XGB calibration separately: paired42/43 +полная group-CV3, pooled OOF
0.611757099 →0.617987602. Условный group bootstrap положителен, не private interval.
Evidence `docs/experiments/v5_xgb_*`; итоговые gates — `release/v6-universal1`.

## Реализация и ограничения

V5/V6: CSV/TSV, deterministic роли/пути, optional dictionary/ID, sample row order;
MAPE/MSE/RMSLE/balanced accuracy, explicit positive label; declared group/future-date
validation; независимые2..16targets; limited pointwise query NDCG. Не joint
multi-output/native ranker/произвольный natural-language task interpreter.

Runtime search/confirmation не полная K-fold OOF; development CV mode отдельный.
Joint group+time не реализован. AST-фильтр feature code — не security sandbox.
Generated feature functions могут быть трансдуктивными: жёсткой изоляции для них
не обещать. Default data policy identity/noop, прежние sampling/augmentation
эксперименты не дали основания включать увеличение данных повсеместно.

V7: bounded Qwen file-role mapping после deterministic failure, online CLI only;
3..32 CSV/TSV,≤100columns, dtype probe16rows, excerpt8k, без raw values, distinct
exact task-local paths. До2semantic calls deadline45s/output2,048tokens каждый;
gateway может повторять HTTP внутри своего deadline. Mock tests8, один с реальным
refit после подставного mapping. **Live Qwen не проверен.** Retry feedback пока
структурный/paths, не все ошибки дальнейшего TaskSpec. Время/calls этапа отдельно
от старого planner-only report.llm_calls; общий trace не считать заново по targets.

## Jobs на данном ПК

V6 completed. Сейчас один V7 full benchmark:
`test-runs/continuation-20261022/v7-public-full/`, log рядом `v7-public-full.log`.
task-00 regression уже pass, итоговый CSV byte-identical V6; task-01 classification
ещё выполняется. Default
search12/budget9900s, offline,2threads, tree guard1.7GiB, watchdog10100s/task.
Strict current-source comparison прошёл на запуске; потом менялись только docs.
Aggregate `assessments.json` означает завершение обеих задач. Проверить каждый
assessment/report на exit0, refit/integrity и SHA CSV; не дублировать job и не
объявлять full success без completion. Раздел обновляется при финальном checkpoint.

Защищённый ввод credential в диагностический terminal был отклонён policy, ключ
туда не поступил. Idle terminal может ещё ждать stdin; не утверждать, что все
credential-процессы закрыты. Не обходить отказ вводом через argv/иной канал.
Platform-provided API environment — отдельный runtime путь.

## Платформа и разрешения

Receipt `release/v4-history3/submission-20261022.json`. Read-only reload в04:25UTC:
карточка exact v4 имени, время05:21, **2184.173**, осталось2попытки. Screenshot и
accessibility state показаны в разговоре. Ранее UI смешивал имя со старым1723.691
v3; это не новый балл v4. Новый raw score не переводим в100 или hidden-final score.
Пользователь ранее сообщил v3≈16/100; формула/hidden breakdown неизвестны. Отправка
разрешена и выполнена один раз; следующие — по новой команде, даже после reset.

Разрешены автономные измерения/исправления/обычные коммиты/push рабочих веток/Qwen.
Не разрешены автоматически main merge, force push, paid GPU, новые official submits
и дополнительные AI-агенты. Managed policy выше широкого «полного доступа».

## Среда и воспроизведение

Repo на этом ПК:
`/home/mucg9/Documents/Codex/2026-10-19/referenced-chatgpt-conversation-this-is-an/outputs/team-project`.
От repo Python `../../work/ml-venv/bin/python`; tasks
`../../work/evaluation/regression/task.md`, `../../work/evaluation/multiclass/task.md`.
10 SHA сверены с `docs/handoff/public_inputs.json`. На другом ПК получить public
inputs у капитана; raw CSV/predictions/venv/secrets не в Git.

Python3.12.14,numpy1.26.4,scipy1.12.0,pandas2.2.3,sklearn1.5.2,LGBM4.6.0,
xgboost-cpu2.1.4,CatBoost1.2.8,openai1.68.2,psutil6.1.1. Новые пакеты не ставили.
Original requirements SHA в next-agent.md. Python patch влияет на ast.unparse:
3.12.3 ZIP отличается одной f-string quote style, AST совпадает. Byte-exact gate
не ослаблять; новый ZIP — новое имя, старые не перезаписывать.

15.3GiB RAM total, мало available, swap8GiB заполнен. Тяжёлые jobs последовательно,
2threads. TMPDIR/MPLCONFIGDIR — ignored `test-runs/continuation-20261022/{tmp,mpl}`:
стандартный /tmp read-only. BLAS/OMP1–2. `tools/run_checks.py --output NEWDIR` —145
проверок, source hashes до/после, owned-process guards. Exact-unpacked23 повторяют
часть145, не суммировать как168unique.

Последний записанный quota usedPercent **82% в04:25UTC** — не live остаток при
чтении. При85% used начать завершение/передачу, не начинать новые долгие этапы;
reset credits не использовать. Актуальное чтение обязательно.
