# C1 — Legacy residue report (post-cleanup)

**Baseline:** `c9598ee` → C1 implementation on `codex/stage-a`  
**Mode:** offline `rg` classification — no product behavior change intended

## Summary

| Metric | Value |
|--------|------|
| Files deleted | 15 modules + 8 legacy-only test files |
| Net lines removed (product+tests) | ~5,200 |
| Collect-only tests | 2451 (was 2524) |
| Frozen S62/S63/S66 | byte-identical ✅ |

## Deleted as provably dead (C1)

- `core/catalog_resolution.py`, `core/knowledge_base.py`, `core/living_frame.py`
- `core/price_brand_money.py`, `core/price_symptom_consult.py`, `core/price_group_overview.py`
- `core/rewrite_policy.py`, `contracts/answer_packet.py`
- Legacy `llm.py` packet/retrieval rewrite (~1,090 lines)
- Legacy `ux_builder.py` price/catalog/clarify payloads (~870 lines)
- `orchestration/helpers.py` retrieval/chunk telemetry (~250 lines)
- `app.py` `/__debug/retrieval` endpoint
- Orphan flags: `COMPOSER_ON`, `FULLCTX_ON`, `ANSWER_PACKET_*`, `QUERY_REWRITE_*`, `LIVING_OVERVIEW_ON`, `SITUATION_PRICE_ON`, `PRICE_SYMPTOM_CONSULT_ON`

## Remaining hits (classified)

### active — product meaning

| Pattern | Examples | Why kept |
|---------|----------|----------|
| `shadow` | `turn_frame_shadow.py`, `record_planner_attempt_shadow` | Active planner shadow bridge → target TurnFrame (C2) |
| `legacy_plan` | `turn_planner_llm.py` | Active planner strict branch (C2) |
| `fallback` | `resolve_with_fallback`, `LLM_FALLBACK_ANSWER`, ingress fail-closed | Active safety/resolver (C2 for resolver) |
| `chunk` | `core/md_chunks.py` (`get_chunk_by_ref`, tooling) | Offline index + tests; not product answer path |
| `composer` | `target_composer_*`, docs | Target FullContext composer — not legacy packet composer |
| `retrieval` | `metadata_first_observability` pool keys, log event names | Telemetry vocabulary; no embed retrieval path |

### shared — selectors/tests

| Pattern | Examples |
|---------|----------|
| `legacy` | `legacy_intent` in resolver telemetry, `finalize_turn` |
| `chunk` | `md_chunks` tests, eval harness references |
| `fallback` | price resolution reason strings in `query_selector` |

### historical — frozen/evals

| Pattern | Examples |
|---------|----------|
| `retrieval` / `chunk` | `evals/v5/s62|s63|s66_*_harness.py` pinned replay |
| `composer` | deleted-module names in harness allowlists |

### planned C2

| Pattern | Examples |
|---------|----------|
| `legacy_plan`, `shadow`, `turn_frame_adapter` | See `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` |
| `last_subject`, `pending_clarify` | Session readers in planner/focus |

### false positive

| Pattern | Examples |
|---------|----------|
| `RAG` | comments in `md_chunks.py` header only |
| `composer` | `target_composer_executor` (target product) |

## Post-C2e residue (2026-07-24)

| Group | Examples |
|-------|----------|
| **Deleted** | `aspect_arbitration`, `consult_nudge`, `retrieval_candidate`; `build_answer_plan` API |
| **Active** | `md_chunks` (kb_ref), `detect_aspects`, `metadata_first_observability`, `routing_loader`, target FullContext stack |
| **Historical** | A9 `turn_frame_shadow*` meta aliases, eval harness fields, `pg_sink.retrieval_candidates` column |

## Explicitly unchanged

- TurnFrame planner semantics (`legacy_plan`/shadow behavior)
- FullContext target runtime path
- Frozen audit artifacts
- A9 shadow-only evals
