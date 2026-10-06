# D2 S2-C10 — TTL-проекция D2 session context

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C10 добавляет только чистую TTL-проекцию существующего typed
`ResponsePlanSessionSnapshot`. TTL обычного контекста — 30 минут бездействия по
явно переданным часам и activity record. Это не semantic continuation: helper не
читает и не разбирает `patient_text`, `assistant_text` или `patient_message`.
Решение, продолжает ли новый запрос тему, остаётся отдельным typed checkpoint.

Нет подключения к HTTP/SSE, provider, session store/writer, resolver или
existing D1R envelope. Activity timestamp будет записан будущим владельцем
сессии; чтение этой проекции его не обновляет.

## Allowlist

```text
contracts/d2_session_context.py
core/d2_session_context.py
tests/test_d2_session_context.py
docs/tasks/DEMO_D2_S2_C10_TERRA_TASK.md
```

## Приёмка

- policy defaults to 1800 seconds and rejects non-strict/non-positive values;
- injected aware clock: `< TTL` fresh, `>= TTL` expired; missing activity is
  unknown and fails closed; future/naive timestamps are rejected;
- tenant+sid bind the snapshot and activity record;
- fresh projection transfers typed ordinary state only as opaque data; expiry
  clears ordinary focus/topic/situation/options/price history/dialogue and
  `clarify_pending`, while terminal and shown IDs are retained;
- projection is immutable and has no semantic/raw-text analysis.

## Known gap / stop conditions

A10/A06/B11 end-to-end, semantic focus ambiguity, session persistence/replay,
lead/privacy and HTTP/SSE wiring are not implemented or claimed here. Stop rather
than extend this allowlist if completion requires raw-text inference, a second
session store, D1R parser/resolver changes, or runtime wiring.
