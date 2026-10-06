# D2 S2-C15 — isolated cross-topic candidate consumption

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C15 потребляет только optional typed `D2PlanFocusSeed` на изолированной
границе `resolve_d2_envelope_response`. Для первой price-part C14 candidate
может отфильтровать цены explicit destination topic по `source_situation.extent`.
Это допустимо лишь при `resolve_topic`, exact session-key, exact destination
topic у seed/candidate/current price request, non-null current subject,
`continuity=same`, non-reset ситуации, owner-bearing source и разных source/
destination topics. Собственная typed situation текущей price-part сохраняет
прежний приоритет; source situation не меняется и не подменяет destination.

При отсутствии или любом несовпадении candidate result остаётся обычным C2/C3
overview. C15 не перечитывает C10 TTL и не меняет C14/C12 contracts.

## Allowlist

```text
core/response_plan_materialization.py
tests/test_d2_price_scope_selection.py
docs/tasks/DEMO_D2_S2_C15_TERRA_TASK.md
```

## Приёмка

- valid C14 carry фильтрует только destination topic prices по source extent;
- missing, stale/wrong-session, ownerless, source=destination, wrong destination,
  null subject, missing/non-same/reset situation и multi-topic absence fail closed;
- existing overview и own typed situation сохраняют поведение;
- mutation raw D1R text не меняет результат; source situation immutable;
- нет semantic inference из текста, service→topic inference, C10 TTL reread,
  runtime/HTTP/S3/provider wiring.

## Stop conditions

Остановиться, если нужны изменения C10/C14 contracts, D1R parser/prompt,
session writer/store, runtime/HTTP/SSE, service→topic lookup, owner lifecycle,
raw-text semantics или provider/live calls.
