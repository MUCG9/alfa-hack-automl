# Подготовка GitHub Issues / Project

Приватный репозиторий создан: [MUCG9/alfa-hack-automl](https://github.com/MUCG9/alfa-hack-automl). Issues и Project пока не опубликованы. `github_issues.csv` — файл для переноса задач, не доказательство их публикации. GitHub не предоставляет универсальный встроенный импорт Issues из CSV: данные можно перенести вручную либо отдельным скриптом через API после разрешения капитана.

## Поля и представления

- Status: Backlog, Ready, In progress, Review, Done, Blocked.
- Priority: P0, P1, P2. Owner: назначенное имя, не P1-placeholder.
- Track: integration, validation, regression, classification, agent, release, context.
- Due: фактическая дата после подтверждения deadline.
- Evidence: ссылка на commit, report и split hash.
- Dependency: ID блокирующей задачи.

Основная доска — по Status, таблица капитана — P0/P1 с Owner/Due, отдельный список Release. В Ready задача попадает только с критериями приёмки и владельцем. В Done — после запуска и независимого review.

## Шаблон Issue

```text
Гипотеза / проблема:
Один ожидаемый результат:
Исходная версия / split hash:
Разрешённые файлы и контракт:
Что не входит в задачу:
Проверка и acceptance criteria:
Артефакт / лог:
Reviewer:
Зависимости:
```

## Правила объединения

Одна задача — одно небольшое изменение. Reviewer проверяет факт запуска и не допускает target leakage, новые зависимости или подмену метрики. Изменение интерфейса сначала согласуют P1/P2. Капитан отдельно утверждает release/submit. Ветка и merge сами по себе не означают улучшения качества.
