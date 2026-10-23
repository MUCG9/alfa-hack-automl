# PIPE-02: архив для стандартного запуска платформы

По новому прямому запросу капитана23Oct разрешена ОДНА отправка улучшенного
решения. Условие локального улучшения выполнено: RMSE35.44723155783769→
35.39729814378806 на mean двух cuts, оба cuts лучше; MacroF1 сохранён
.6593178433614652. [Полный результат](../../docs/experiments/pipe02_complete_20261023.md).
Это local reused-public validation, не гарантия нового official score.

Отправлять `solution-pipe02-submit1.zip`, SHA256
`a2ca924416be9b1fc9c528b431f22123b42324b44e50402601e828c4f15056f2`.
Стандартная команда платформы:

```bash
python3 solution.py task.md
```

Entrypoint автоматически добавляет `--research-profile incumbent_mix`;
если флаг передан явно, не дублирует его. Default CPU threads2, явный внешний
AUTOML_THREADS сохраняется. Qwen file-role discovery не отключается. На known
public inputs роли определяются локально, как в qualified offline campaign;
на неподдержанном schema профиль возвращается к ordinary agent search.

ML-код, recipes, данные и метрика не менялись.67files побайтно совпадают с
полностью проверенным opt-in ZIP, изменён ТОЛЬКО `solution.py`. Original
requirements.txt сохранён. Canonical352source-check snapshot по-прежнему
совпадает с default build;3новых dispatch/entrypoint tests и3существующих
release-verifier checks PASS. Новый exact ZIP:23repeated unpacked checks PASS.
[Parity receipt](entrypoint-parity.json), [ZIP verification](exact-unpacked.json).

Текущее состояние: READY, NOT SUBMITTED. Доступный локальный desktop screen-
locked; запрос разблокировки отправлен пользователю. Session cookies/пароли
не извлекались, блокировка не обходилась. До фактической отправки нужно
прочитать текущую карточку/remaining attempts в авторизованном браузере.
Нельзя считать прежний score2187.849 результатом V11: это historical V9.
Одна отправка, затем проверить queue acceptance/имя файла/счётчик и записать
новый receipt. Не повторять upload, если результат первого действия неясен.
# Submission update,23October2026

The standard-entrypoint archive was accepted into the platform queue at09:25
Moscow. One upload, attempts3->2, official score pending; prior V11 score2309.002.
See [submission receipt](submission-20261023.json). No duplicate/replacement
upload. Later opt-in Qwen reasoning changes do not modify this immutable ZIP.

