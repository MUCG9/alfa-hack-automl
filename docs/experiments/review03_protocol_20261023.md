# REVIEW-03: Qwen-разбор новых marginal-contribution результатов

Один read-only call до дальнейших fits,4096outputtokens/180s/210s total,
без retry и automatic application. Использовать существующий evidence-card
review harness с typed IDs/control/gates/resource validation. В контекст дать
компактные MVP aggregates и новые class/reg fixed replay receipts, явно указав,
что обе qualification ещё pending и новых fits reviewer не запускает.

Цель — получить проверяемые архитектурные гипотезы из факта, что standalone
MVP/HPO не прошли gates, но fixed marginal addition улучшил complete control
на обоих saved cuts. Не считать это общей полезностью FE/HPO или готовым release.
Сохранять ID resolution, schema rejection, фактические ошибки, tokens и wall time.

Это новый вопрос с новыми фактами, более коротким контекстом и обновлённым skill,
не retry REVIEW-02 на тех же данных и не изолированный A/B-test. По одному
ответу нельзя утверждать, что context compression улучшает Qwen вообще.
Протоколы class/reg qualification и fixed weights остаются прежними.
