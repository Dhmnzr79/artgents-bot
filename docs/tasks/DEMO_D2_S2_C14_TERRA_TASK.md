# D2 S2-C14 — code-bound cross-topic situation candidate

Дата: 2026-09-18. Статус: implementation checkpoint.

## Граница

C14 реализует вариант 1: pure code-bound candidate для будущего переноса
ситуации между topics. Он не создаёт owner и не связывает D1R turn-local `sN` с
owner. Единственный semantic signal модели — существующий typed
`situation.continuity="same"` на request с explicit destination topic.

Candidate возможен только при fresh C10 ordinary state, единственном owner-bearing
source situation и точном согласии source topic в active topic, shown options и
situation. Destination обязан быть другой explicit topic; request обязан иметь
non-null current-turn subject, `continuity=same` и не-reset situation. Candidate
содержит source situation отдельно от destination topic: имплантация не
притворяется состоянием протезирования.

При expiry, ownerless legacy state, ambiguous/multiple topics, missing or
inconsistent refs, `new`/`unknown`/reset — candidate отсутствует. Explicit new
topic остаётся explicit-new; C14 не меняет C10 TTL classification, не выбирает
услугу по topic и не реализует A08 в resolver/runtime.

## Allowlist

```text
contracts/d2_session_context.py
core/d2_session_context.py
tests/test_d2_session_context.py
docs/tasks/DEMO_D2_S2_C14_TERRA_TASK.md
```

## Приёмка

- fresh owner-bearing implant situation + explicit prosthetics + typed `same`
  produces immutable cross-topic candidate with source owner/facts and destination;
- all missing, stale, legacy, reset, multi-focus or mismatched typed guards fail
  closed without carry;
- raw dialogue/envelope text, regex и turn-age не влияют;
- нет D1R parser/prompt, owner lifecycle, session store/writer,
  resolver/materializer, runtime, HTTP/SSE, lead или provider effects.

## Stop conditions

Остановиться, если нужно создавать/bind owner, сравнивать людей между turns,
выбирать среди situations, выводить связь service→topic, менять D1R parser/prompt,
session writer/store, resolver/materializer, runtime/HTTP/SSE или provider calls.
