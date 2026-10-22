# Источник и границы адаптации

Изучен upstream [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
23 октября 2026, commit
[`228791fb499afffb54b46200aca536f79142f117`](https://github.com/karpathy/autoresearch/commit/228791fb499afffb54b46200aca536f79142f117).
Это фиксация прочитанной версии, не зависимость нашего ML-кода.

[README](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md)
разделяет исследуемый `train.py`, фиксированную подготовку/оценку и `program.md`,
задающий поведение исследователя. Основная идея — сопоставимые ограниченные
запуски, решение по измерению и развитие исследовательских инструкций.

[program.md](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md)
задаёт baseline, отдельную ветку, коммит перед запуском, журнал и решение
о сохранении изменения. Учитывается сложность решения. Автономный цикл
рассчитан на работу без постоянного участия человека.

[prepare.py](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py)
содержит training budget и evaluation utilities, а
[train.py](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py)
использует их и печатает измерения. В оригинале обучается GPT на одной GPU,
training budget — пять минут, метрика — validation bits per byte.

Следующие решения принадлежат нашей адаптации, а не автору upstream:

- CPU/RAM/API budgets выбираются для задачи; пять минут не универсальный лимит.
- ML использует собственные метрики, group/time splits, inner HPO и gates.
- История отрицательных commits сохраняется при rollback.
- Ошибка не получает нулевой objective; журнал агрегатов можно версионировать.
- Автономность ограничена действительными deadline, ресурсами и scope.
- GPU-код, зависимости и внешние данные upstream не импортируются.

Код upstream не скопирован; инструкции написаны заново для ML skill.
