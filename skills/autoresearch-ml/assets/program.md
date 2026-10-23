# Research program

Перед первым fit записать конкретные значения из запроса и состояния проекта.
Не изменять действующую кампанию из-за наличия этого шаблона.

## Контракт

Указать run_id, branch, qualified control SHA/receipt, input fingerprints,
метрику и направление, разрешённые изменения, защищённые evaluator/data/splits,
библиотеки, общий/per-worker/per-study deadline, RAM, threads, API call cap,
резерв на confirmation/refit/export и required acceptance gates.

Если нужен ранний futility stop после невыполнимого обязательного gate, задать
его ДО запуска. Остановленный screen остаётся rejected/incomplete, с отсутствующими
scores; его mean и work counts нельзя приравнивать к завершённому сравнению.

## Цикл

Продолжать от qualified incumbent. До запуска записывать гипотезу и критерий её
опровержения, comparator, механизм, split IDs, фактор, ожидаемую стоимость и
candidate commit. Проверять контракт до дорогого fit. Запускать только owned jobs
в пределах общей очереди.

Пересчитать метрику по сохранённым строкам. Записать scores каждого cut, wall time,
peak RAM, completed trials, source/input/split hashes и статус артефактов.
Применить заранее заданные gates. Различать keep-for-confirmation, qualified,
discard, crash, timeout, OOM и incomplete; при ошибке метрика отсутствует.
Сохранять commits и отрицательные результаты, обновлять ссылку на лучший
qualified SHA. Комбинацию победителей проверять новым опытом.

## Разбор агента

Отдельно измерять schema acceptance, полезность гипотез, стоимость поиска и
качество. Менять prompt/tool/harness по одному фактору на сопоставимом feedback.
Подкреплять learned knowledge receipts; предположение LLM оставлять гипотезой.
Не повторять отрицательную конфигурацию без нового основания.

## Завершение

Продолжать автономно в scope, пока хватает действительного бюджета. Сохранить
лучший qualified вариант, журнал, точный статус owned jobs и Git rollback.
Отделить development scores от private/official performance. Внешние действия
выполнять в пределах существующих разрешений.
