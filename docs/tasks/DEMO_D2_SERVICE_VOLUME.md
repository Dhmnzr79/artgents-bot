# D2 — service and treatment scope

Baseline: merged D1R, `141ce91fb1731cd990fcf8391550150016c73e7f`.
Branch: `codex/demo-d2-service-volume` in `C:\Cursor Projects\artgents-bot`.

## Agreed behavior

- Keep the service being discussed separate from a patient's stated need. A price question about implants does not establish missing teeth or a treatment recommendation.
- Scope can be unknown, one tooth, several teeth, or a full jaw. Preserve an explicit count and upper/lower/both jaw when supplied; do not infer an implant count or treatment method.
- An explicit correction replaces the prior stated fact. A hypothetical comparison does not change it.
- A short follow-up uses clear current context. A new service becomes the discussed service; unrelated old scope does not transfer to it.
- Keep one current situation in D2. An unrelated clinic question does not erase it. A new patient does not inherit it; do not implement parallel patient histories. Old booking permission is not revived by memory.
- Ask only when missing or ambiguous scope prevents a correct answer. General service information can be answered without a full intake. A small set of clarification options should appear as buttons, with free-text entry always available.
- Choosing “Не знаю” leaves scope unknown, offers a way to describe the situation or seek consultation, and does not repeat the same question or invent a personalized calculation.
- Demo full-jaw prices are per one jaw. For both jaws, retain both-jaw scope and explicitly quote the catalog's one-jaw price as such; do not calculate an automatic total. Do not ask upper/lower merely to give an identical one-jaw price.

Free-text understanding uses the existing single D1R model envelope. Code validates structured facts and applies catalog, pricing, memory, and booking rules. No parallel dictionary or regex semantic classification.

## First implementation checkpoint

Handle one current service/situation across a short conversation: stated scope, correction, hypothetical variant, service change, follow-up, ambiguity, and clarification buttons. Extend existing D1R structures and session behavior. Preserve D1R policy, lead, and booking gates.

Focused offline tests cover these conversation examples, unknown scope, both-jaw per-jaw pricing, stale/foreign button handling, JSON/SSE parity, and D1R regressions. No live model/provider calls. One independent Checker review at a coherent checkpoint; no full audit repetition.
