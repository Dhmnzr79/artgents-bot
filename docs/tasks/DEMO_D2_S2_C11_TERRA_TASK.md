# D2 S2-C11 — typed D1R/session continuation binding

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C11 добавляет чистое typed-решение `bind_d1r_envelope_to_d2_context()`. Оно
связывает уже разобранный D1R `OneCallEnvelope` с C10
`D2SessionContextProjection` и возвращает один из outcomes:
`clear_continuation`, `ambiguous_focus`, `explicit_new_topic`.

C10 TTL — только допуск к чтению typed ordinary state. Истёкший или отсутствующий
activity record запрещает carry, но не превращает явно заданный D1R `topic_id` в
другой semantic outcome. Решение читает только `requests[].topic_id`,
`service_id`, `situation.continuity` и typed active topic/service/situation/shown
options. Оно не читает `patient_text`, `assistant_text`, `patient_message`,
dialogue history, regex или turn-age.

Situation переносится только при fresh `clear_continuation`, точном совпадении
typed topic и явном D1R `continuity="same"`. `new`/`unknown`/reset и любой
неоднозначный focus ничего не переносят. Отдельного service→topic вывода нет.

## Allowlist

```text
contracts/d2_session_context.py
core/d2_session_context.py
tests/test_d2_session_context.py
docs/tasks/DEMO_D2_S2_C11_TERRA_TASK.md
```

## Приёмка

- exact typed topic/service/shown-option refs дают clear continuation только при
  fresh C10 ordinary state;
- conflicting/multiple/absent focus даёт fail-closed ambiguous focus;
- explicit new topic остаётся explicit-new и при expired context;
- same-situation carry требует только совпадающих typed refs и `continuity=same`;
- изменение raw dialogue/envelope text при неизменных refs не меняет outcome;
- helper immutable, без provider/network/runtime/HTTP/SSE wiring.

## Stop conditions

Остановиться, а не расширять checkpoint, если понадобятся person identity across
turns, catalog service→topic inference, отдельная multi-request policy, raw-text
semantic inference, D1R parser/prompt changes, session persistence/writer,
resolver/materializer или HTTP/SSE wiring.
