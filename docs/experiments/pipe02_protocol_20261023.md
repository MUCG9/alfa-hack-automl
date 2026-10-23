# PIPE-02: исполнить найденную incumbent-mixture процедуру полностью

До новых full-procedure fits. REG-BLEND-01 прошёл три forward cuts против
сильного ПОЛНОГО control и mean-сравнения с equal-cap Random8/unchanged-anchor
mixtures. Class BLEND-01 grouped CV ещё идёт. PIPE-02 — явный opt-in research
profile; текущий default baseline и CLI defaults HPO/selector0 сохраняются.
Main/official upload не меняются. Source менять только после окончания CV.

Рецепты строятся из canonical portfolio по kind/metric/schema; без имен public
columns, task filenames, dataset hashes, сохранённых predictions/weights или
внешних данных в runtime. Regression control: qualified asof/log LightGBM+native
CatBoost (.9/.1); classification control: two-view LightGBM seed42/48 и calibrated
XGBoost с equal weights. Это frozen learned priors, не новый online LLM search.
Qwen research loop и его результаты сохраняются отдельно. Full comparison
использует offline deterministic file-role discovery, как квалификационные runs;
новых Qwen calls или незаявленных proposals при этой проверке нет.

Regression augmentation — та же nested TPE8 strongest-single procedure, seed137,
startup3, unchanged space,600s/trial/1800s study. Заново выбрать recipe ВНУТРИ
fitting rows каждого из двух outer forward cuts0/1, затем refit на этих fitting
rows canonical worker с собственным stopping/preprocessing. Смесь fixed.9/.1.
Для final deployment провести отдельный TPE8 внутри ВСЕХ доступных training
rows; full augmentation refit использует fit_iterations выбранного inner trial
этой full study. Это явное правило передачи iterations из training-only study,
не private performance estimate. Control full iterations — canonical recursive
int-median двух outer fits. Все full fits используют training rows целиком.

Classification: если ongoing grouped CV не пройдёт ВСЕ gates, использовать
только qualified complete control. Если пройдёт, добавить fixed learned MVP
two-view CW1/seed53/top32 с теми же .9/.1; selector в каждом scope заново.
Primary/confirmation group cuts42/43; full iterations каждого arm — recursive
int-median двух fits. Нет изменения веса или замены recipe по CV outcomes.
На поддерживаемом другом task profile также должен проверять paired gates;
неудачное дополнение возвращает полный control. Неподдерживаемый schema/kind
возвращается к прежнему baseline, не получает public-task shortcut.

Заранее заданное futility rule: после первого проваленного paired gate либо
неуспешного augmentation/study не тратить оставшийся бюджет на дополнительные
augmentation fits. Закончить оба control cuts и full control; сохранить actual
отрицательный mixed score и причину. Такой fallback явно отмечается в report.
Полная положительная PIPE-02 квалификация требует фактически выполненного
augmentation на обоих regression cuts, восьми успешных trials в каждой из трёх
studies и final augmentation refit. Fallback не считается проверкой этой ветви.

Оркестрировать два arms отдельными sequential workers и cached mixing.
Не расширять ради этого global ensemble worker contract. Сохранить row/class
order и actual immutable splits; source/input fingerprints и все selected
per-cut/full recipes. Full inference смешивает actual full-fit outputs; полный
control не заменяется слабым single recipe. Default data policy identity/noop.

Полный новый source/flat archive сначала проходит meaningful focused checks и
неизменённые source/exact-unpacked gates. Затем один sequential двух-task
campaign с общим10800s deadline,2threads,1536MiB per worker,900s per complete arm,
600s per HPO trial; сохранять резерв на оба full arms и экспорт. Source/archive
freeze на campaign, один owned coordinator и тот же training lock. Ни одного
fit до окончания ongoing CV. При недостатке времени сохранять valid checkpoint
и честный incomplete status, не увеличивать общий deadline.

Promotion research profile только после actual paired metrics, final refit/CSV/
integrity на обеих tasks и code gates. Это reused-public development; новый
official score не выводится из локальных means. Последняя parity стадия завершает
данный исследовательский checkpoint; не начинать после неё новые направления.
