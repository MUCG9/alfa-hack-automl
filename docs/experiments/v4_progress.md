# Статус передачи22.10.2026

Этап завершён, новые долгие jobs не запускаются. Все наши ML workers/очереди и
Qwen private processes завершены. Git credential helper закроется после последнего
push; постоянного credential в Git/config/файле нет.

Полный итог — [v4_summary.md](v4_summary.md), актуальный самостоятельный промпт —
[../prompts/next-agent.md](../prompts/next-agent.md). Source commit16987fb,
release/solution-v4-history3.zip, SHA8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f.

- 107fixed workers,3default runs,2bounded lifecycle отдельно.
- Полный v3 classification: meanMacroF1 .653714716,refit/exportok.
- Полный search2 regression: RMSE40.426939/37.723019,mean39.074979.
- Полный history3 regression: RMSE39.321110/34.229380,mean36.775245,
  refit/exportok,integrity=true,312.386s.
- 59repo +23unpacked exact ZIP passed.
- Новая classification search2/3 **не запускалась полностью**. Следующая задача —
  этот benchmark; старый frozen v3 и обе регрессии без причины не повторять.
- API реально проверен, gateway/normalizerok, неудачные гипотезы сохранены.
- Официального submit/merge не было. Score v4 неизвестен.

Подробные локальные outputs в /tmp/alfa-* и test-runs/stages/ ignored; они не
гарантируются после reboot. Рецепты,source snapshots,агрегированные metrics и
проверки сохранены в Git. Старые session IDs и run-*.sh — история завершённых runs.
