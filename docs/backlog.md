# Приоритетные задачи после первой отправки

Имена владельцев назначаем на встрече. Done означает проверенный артефакт, а не обещание ИИ.

| ID | Приоритет | Владелец | Задача | Приёмка |
|---|---|---|---|---|
| INT-01 | P0 | P1 Pro | Адаптивный output budget и исправление JSON после truncation | 5 записанных planner-traces, включая length/timeout, без потери best |
| VAL-01 | P0 | P2 Pro | Независимая проверка selection bias и leakage | минимальные воспроизводимые тесты + review итогового diff |
| TXT-01 | P0 | P2 Pro | Сильный универсальный текстовый рецепт | реальные локальные текстовые holdout из разрешённых материалов либо явно synthetic smoke test и documented gap |
| CLS-01 | P1 | P4 ML | Сравнить balanced weights, threshold/prior effects и per-class F1 | 4–6 экспериментов на фиксированном split, macro/per-class/time/RAM |
| CLS-02 | P1 | P4 + P2 | Измерить оптимизм random split против grouped split | один recipe и два подписанных split, отдельные строки метрик |
| REG-01 | P1 | P3 ML | Подтвердить пользу generated features | 3 folds/seed или обоснованный дешёвый аналог, исходная шкала RMSE |
| REG-02 | P1 | P3 + P2 | Проверить missingness/time robustness | диагностика по Year_Factor и основным группам, без заявления temporal leakage без доказательства |
| AGT-01 | P1 | P5 аналитик | Укоротить общий context и убрать повтор словаря | actual tokens/latency при сохранении качества планов |
| AGT-02 | P1 | P1 + P5 | Улучшить обработку API ошибок и 429 | bounded backoff с deadline и наблюдаемым статусом |
| GEN-01 | P1 | P2 Pro | Неизвестные метрики и схемы | задачи с новыми target/id, binary probability contract, явный отказ от unsupported |
| REL-01 | P0 | Капитан | Дождаться первой официальной оценки | score/status/время + SHA-256, без дублирующей отправки |
| REL-02 | P1 | P1 | Единый CI и release checklist | плоский ZIP, те же requirements, smoke на обеих задачах |
| CTX-01 | P0 | P5 + капитан | Подтвердить deadline и назначения | реальные имена, срок freeze, единая версия контекста |

Не тратим следующий submit на изменение, которое нельзя отличить от предыдущей версии и оценить локально. На платформе сейчас отправлена ровно одна разрешённая попытка; новые попытки требуют согласованного решения капитана.
