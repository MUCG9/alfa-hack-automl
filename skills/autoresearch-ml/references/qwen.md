# Qwen: настройка reasoning и доказательства

Официальный [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B)
документирует default thinking и `reasoning_effort=low/medium/xhigh`, где xhigh —
default. Сопоставление полей зависит от backend; OpenAI-compatible прокси может
принять неизвестное поле и проигнорировать его. HTTP200 не доказывает эффективный
скрытый budget или превосходство максимального режима.

В alfa gateway маленький probe23Oct принял top-level `reasoning_effort=xhigh`.
Default/xhigh/high вернули ненулевые reasoning_tokens, disabled —0. Сохранён
только terminal validity/usage/timing, внутренний текст рассуждений не записывается.
По одному последовательному запросу на режим качество ML и отличие xhigh от
default не установлены. Исторический fast mode явно задаёт
`extra_body={"reasoning":{"enabled":false}}`, а не полагается на default.

Проверять режим на одинаковых ML inputs/prompt/context/output cap, затем одинаковых
фиксированных training/evaluation budgets. Считать truncated/no-final ответы,
валидные новые рецепты, LLM costs и итоговые метрики/завершённые fits. Больший
reasoning budget может оставить меньше времени на обучение. Отклонённый xhigh
не заменять молча default. Секрет передавать только авторизованному endpoint
через приватное окружение координатора; не включать его в command line или worker.
