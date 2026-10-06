# D2 S2-C13 — typed persisted situation identity and facts

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C13 расширяет только typed `PersistedSituationState`: optional opaque
`situation_owner_id` и D1R-parity `tooth_count`. C10 уже переносит typed state
как opaque value при fresh projection и скрывает его при expiry, поэтому его code
не меняется.

Старые snapshots без новых полей валидны, но не дают основания для будущего
cross-topic carry. D1R `subject_id` (`sN`) уникален только внутри одного turn и
не используется как durable owner. C13 не создаёт owner lifecycle, не связывает
его с envelope и не реализует A08. Он запрещает silent loss: conversion к legacy
`ResponseSituationState` reject'ится, если C13 fields заполнены.

## Allowlist

```text
contracts/response_plan_session.py
tests/test_d2_session_context.py
docs/tasks/DEMO_D2_S2_C13_TERRA_TASK.md
```

## Приёмка

- owner — opaque exact nonblank string; tooth count strict и согласован с extent;
- fresh C10 сохраняет оба typed field без semantic interpretation; expired их
  скрывает вместе с ordinary situation;
- old ownerless state remains valid and legacy conversion leaves C13 fields absent;
- populated C13 fields не теряются в legacy conversion молча;
- raw dialogue/envelope text, regex, turn-age, HTTP/SSE/runtime/store/writer,
  resolver/materializer, D1R parser/prompt и provider не участвуют.

## Stop conditions

Остановиться, если нужно populate/bind owner, сравнить его с D1R `sN`, реализовать
cross-topic A08, менять D1R parser/prompt, session writer/store, runtime model,
resolver/materializer, HTTP/SSE или provider calls.
