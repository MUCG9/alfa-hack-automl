# REVIEW-02: явный evidence/qualification contract для Qwen

Протокол до второго вызова. Первый skill-guided review завершён live:16481tokens,
6.712s,1attempt,usage_complete. Аудит сохранён в review01_audit_20261023.json.
Qwen ошибочно связал supported-class gate с Worms (46groups); фактический
supported violation — Analysis (695groups,delta−.011701). Numeric gate100/.01
не был явно передан: ссылка на локальный профиль/протокол не загружает его
в plain API context. Формат evidence paths тоже был недостаточно определён.
Не приписывать эти ошибки только модели и не применять её предложения автоматически.

Новая итерация review-harness: те же замороженные числовые receipts из
review01/input_snapshot.json и тот же skill; concise evidence cards с уникальными
ID, tools вычисляют gates, отдельный явно переданный исходный numeric contract.
Qwen генерирует объяснения как ГИПОТЕЗЫ и планы новых проверок; factual summary
остаётся результатом инструментов. control_id ограничен qualified controls,
acceptance_contract_id фиксирован, IDs и ресурсные caps проверяются кодом.

Один дополнительный organizer Qwen call,4096outputtokens/180s/210s total.
Без fits, новых пакетов, изменения source/evaluator/gates или автоматического
применения. Замерить tokens/wall time, разрешимость ID и фактические ошибки
по исходным receipts. Заранее перечисленные FE/HPO/HAR probes уже запланированы;
review не должен порождать их дубли.

Это последовательная итерация интерфейса с уточнённым контрактом, не строгий
изолированный A/B-тест формата: добавление явных правил и смена схемы меняются
вместе. По одному стохастическому ответу на вариант; результаты не доказывают
общую надёжность Qwen или ML gain. Сохранять исходные ответы и ошибки.
