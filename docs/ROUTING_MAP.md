# Карта маршрутизации

**Статус:** синхронизировано с post-RAG runtime.  
**Обновлено:** 2026-07-06.  
**Парный документ:** `CURRENT_ARCHITECTURE.md`.

---

## 1. Целевой порядок `/ask`

```text
request
→ pre-resolver guards / flow handlers
→ resolver + source routing
→ ask_turn hard routes
→ composer / deterministic service reply
→ finalize_turn
```

Фактический порядок post-resolver в `orchestration/ask_turn.py`:

1. contacts overlay;
2. patient playbook overview для content-ситуаций;
3. situation price overview;
4. doctor route;
5. composer overlay;
6. catalog facts;
7. price flow;
8. composer fallback.

---

## 2. Pre-resolver

| Случай | Route | Где |
|---|---|---|
| reset command | reset session | `session.mem_reset` |
| rate limit / duplicate / burst | service reply | `orchestration/pre_resolver_turn.py` |
| obvious noise / offtopic | ingress route | `ingress_gate.py` |
| lead refs and pending lead | `lead_flow` | `flow_handlers.py` |
| explicit booking | `lead_flow` | `flow_handlers.explicit_booking_intent` |
| ref in body | direct chunk/service reply | `orchestration/pre_resolver_turn.py` + `core/md_chunks.py` |
| short continuation without context | `continuation_clarify` | pre-resolver guards |

`get_chunk_by_ref` is a direct md resolver, not search.

---

## 3. Resolver and planner

`resolver.py` returns `DecisionFrame`. `core/turn_planner_llm.py` may add a one-turn plan:

- `route`;
- `aspects`;
- `service_id`;
- `followup_of`;
- `patient_situation`;
- `brand_filter`.

Planner does not replace price-scope regex routing. The cancelled 5.5a-2 experiment proved that method-price questions such as “сколько имплантация” need deterministic dental price-scope routing.

---

## 4. ask_turn hard routes

| Order | Condition | Result |
|---|---|---|
| 1 | contacts intent | contacts chunk |
| 2 | content situation with playbook options | `patient_options_overview` |
| 3 | price intent + patient situation + `SITUATION_PRICE_ON=1` | `situation_price_overview` |
| 4 | doctor source route | doctors list or doctor ref |
| 5 | composer can answer | composer service reply |
| 6 | catalog facts source route | deterministic facts reply |
| 7 | price lookup / concern | price flow |
| 8 | content fallback | composer fallback |

---

## 5. Price routing

Price routing is deterministic and intentionally still uses dental regex scope helpers.

| Query shape | Typical route |
|---|---|
| “сколько имплантация” | group overview from pricebook manifest |
| “сколько all-on-4” | specific protocol |
| “сколько один имплант” | one-tooth scope |
| “нет всех зубов сколько” | situation price overview when flag is on |
| “почему дорого” | price concern |
| widget `price:{service_id}` | deterministic service price |

Inline money comes only from pricebook/price views. Composer may write framing text, but not prices.

---

## 6. Content routing

Content answers go through the full-context composer.

The composer receives:

- current question and dialog context;
- whole client md knowledge base;
- deterministic answer packet/cards when applicable;
- service/catalog/price context prepared by code.

Direct md refs are still used for exact snippets and materialized cards. There is no separate vector search layer in the current runtime.

---

## 7. Patient situation routes

| Situation path | Trigger | Output |
|---|---|---|
| `patient_options_overview` | content intent + playbook options | living answer over ordered clinic options |
| `situation_price_overview` | price intent + playbook options + flag | hero price inline + option buttons |

Data source:

- `core/patient_situation.py` detects semantic situation;
- `core/patient_playbook.py` selects ordered options;
- `core/answer_lens.py` projects options to service nodes;
- `core/service_node.py` loads catalog + pricebook view.

---

## 8. Smoke route labels

Common route labels used by tests/evals:

| Label | Meaning |
|---|---|
| `contacts_chunk` | contacts answer |
| `lead_flow` | lead collection/booking path |
| `price_lookup` | deterministic price path |
| `price_concern` | cost concern answer |
| `patient_options_overview` | situation options content |
| `situation_price_overview` | situation price overview |
| `doctors_list` | doctor cards |
| `catalog_facts` | service facts without md narrative |
| `composer` / `composer_fallback` | full-context content answer |
| `guided` | clarify/menu fallback |

Route inference in evals is a test helper, not the source of runtime truth.

---

## 9. Open TODOs

> TODO(review): keep this map synced when content “what fits” is rewired from legacy playbook flow onto `SituationView` rendering.

> TODO(review): if `core/claim_gate.py` is deleted in code, remove remaining roadmap references to that cleanup item.
