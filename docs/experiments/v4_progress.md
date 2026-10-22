# Продолжение v4 после первого checkpoint

Первый проверенный checkpoint: `3bbbb38` (код), `ba63e30` (82 эксперимента,
кандидат, handoff). Затем `17cacdc` добавил парное OOF сравнение с bootstrap групп;
проверка одинаковых predictions на87670 строках дала точную разность0 и интервал[0,0].
Эти коммиты опубликованы в GitHub, ветка `work/pipeline-review-instructions`.

Пользователь пополнил лимит и разрешил продолжить. Просьба: коммитить после
завершённых этапов, при приближении к10% остатка лимита сохранять передачу и
приостанавливать дальнейшие эксперименты. Официальный submit не разрешался.

## Текущий этап

Полная3-fold CV на exact `release/solution-v4-candidate.zip`, два потока,
локальный guard1.7GiB, watchdog1200s на candidate-fold. Рецепты:
`v4_class_cv_candidates.json`. Это первый контроль, сильная старая inner calibration
и OVA+calibration. У всех одни group-disjoint folds. Входные SHA совпадают.

Полная CV всех трёх рецептов завершена:9/9workersok, exactly-once OOF.
Pooled Macro F1: контроль .636401856, прежняя calibration .637928932,
OVA+calibration .630416015, фиксированная смесь .636753388. OVA проиграла
на всех3 folds, default classification portfolio сохранён.
[Полный разбор](v4_cv.md), source/input/split hashes и интервалы сохранены.

Локальные outputs: `/tmp/alfa-next-class-cv/results.json`, OOF в подкаталогах
рецептов; лог `test-runs/stages/next-class-cv.log`. Процесс был запущен через
exec session22569. Очередь session87405 / `run-default-v3.sh` запустила полный default offline v3 classification с
watchdog10100s. Очередь session46282 / `run-default-v4.sh` ждёт окончания v3 и затем выполнит
полный default offline v4 regression + classification. Логи — default-v3.log и
default-v4.log в test-runs/stages. Не запускайте конкурирующие тяжёлые jobs. Состояние нужно проверить
по существующим reports и процессам: session ID относится только к этой сессии.

GitHub credentials предоставлены пользователем и использованы через приватный
процесс, без записи в Git/config/URL/файл. Не рассчитывайте на сохранённую
авторизацию после завершения процесса. Ключи и токены в handoff не копировать.

Текущая задача — закончить полный default offline v3 classification и matched
v4 на обеих задачах. Затем commit/push результатов, полный online Qwen lifecycle
и следующие train-only гипотезы. Полную CV повторять только после новых кандидатов.

Дополнительная заранее фиксированная гипотеза для этих же OOF: смесь вероятностей
первого контроля и OVA+calibration с весами .5/.5. Веса не подбираются по итоговым
OOF; сравнить её с обоими отдельными рецептами. Это новая исследуемая комбинация,
не независимая private-оценка. Сохранить отдельную метку derived OOF, не считать
расчёт смеси новым обучением или дополнительными worker fits.
