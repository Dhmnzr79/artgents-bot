# D2 S2-C12 — typed plan-focus seed

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C12 добавляет чистый `seed_d2_plan_focus()` поверх готового C11
`D2EnvelopeSessionBinding`. Он не читает C10 TTL, D1R envelope или session
snapshot повторно. Поэтому C10 остаётся только eligibility gate, а C11 —
единственным решением semantic continuation.

`ambiguous_focus` даёт code-owned `clarify_focus` без topic и carry.
`clear_continuation` переносит только уже проверенные C11 typed topic и situation.
`explicit_new_topic` даёт только явный typed topic без situation carry. Отсутствие
typed topic в otherwise clear service binding также даёт clarify: service→topic
lookup не создаётся.

## Allowlist

```text
contracts/d2_session_context.py
core/d2_session_context.py
tests/test_d2_session_context.py
docs/tasks/DEMO_D2_S2_C12_TERRA_TASK.md
```

## Приёмка

- три C11 outcomes отображаются в immutable typed seed;
- inconsistent C11 binding rejected fail-closed;
- raw `patient_text`, `assistant_text`, `patient_message`, regex и turn-age не
  участвуют в seed;
- нет catalog/service→topic lookup, resolver/materializer/session writer/store,
  runtime, HTTP/SSE, lead или provider effects.

## Stop conditions

Остановиться, если понадобятся multi-request/price policy, D1R parser/prompt,
catalog, existing resolver/materializer, persistence/replay/session writer,
runtime/HTTP/SSE, lead/privacy или provider calls.
