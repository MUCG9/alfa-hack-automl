# Файл для загрузки на платформу

Загружать **[solution-v4-history3.zip](../solution-v4-history3.zip)**.
SHA-256: `8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f`.
Размер: 51 694 байта. Код зафиксирован в `16987fb`; последующие commits содержат
результаты проверок и передачу, ZIP не пересобирался.

Архив содержит 39 корневых `.py`, включая `solution.py`, и оригинальный
`requirements.txt`. Нет вложенных папок, данных, моделей, JSON или credentials.
Содержимое побайтно соответствует текущему результату `tools/build_submission.py`.
Платформенная точка входа: `python3 solution.py task.md`.
Не загружать ZIP всего репозитория или набор корневых compatibility shims.

Итог технических проверок записан в [submission_readiness.json](submission_readiness.json).
59 repo tests и 23 повторных проверки распакованного exact ZIP прошли.
Полный offline regression завершил search, confirmation, full refit и CSV export.
Дополнительный сокращённый offline classification успешно проверил тот же ZIP
на полном объёме public данных до refit/export за97.954s, integrity=true.
На обеих задачах проверены столбцы, число строк, порядок ID, отсутствие пропусков
и допустимость предсказаний. Сохранены22449 строк regression и41166 classification.

Это техническая готовность архива к загрузке. Полный default search новой
classification ещё нужно сравнить с frozen v3; результаты сокращённого запуска
не подтверждают качество нового capacity search. Полный online Qwen search текущей
версии также не измерен. Официального score history3 нет; автоматической отправки
на платформу не выполнялось.

Продолжение исследований: [промпт следующему агенту](../../docs/prompts/next-agent.md).
Результаты этапа: [v4_summary.md](../../docs/experiments/v4_summary.md).
