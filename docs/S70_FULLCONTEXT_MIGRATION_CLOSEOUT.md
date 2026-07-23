# S70 — FullContext migration closeout audit

**Baseline:** `codex/stage-a` / `cdcd79f` (S69 complete) · **Audit commit:** read-only at `86ebf9b` governance HEAD  
**Mode:** READ-ONLY / NO PRODUCT CODE / NO LIVE / NO LLM / NO A9 changes

---

## A. Verdict

**`S_SERIES_COMPLETE`**

После S69 legacy product answer path физически удалён. Единственная product authority — target FullContext pipeline. Обязательных архитектурных blockers для закрытия S-series **нет**. Оставшиеся пункты — cost/performance, UX, onboarding второго клиента и hygiene мёртвого кода — классифицированы как **DEFERRED_PRODUCT_FEATURE** или **DEAD_CODE_CANDIDATE**, не как blockers.

---

## B. Простая схема итогового бота

```
POST /ask  ─┐
POST /ask/stream ─┘
        │
        ▼
  shared pre-resolver guards
  (rate/noise/ingress manual_contact · lead · booking · situation_intake · target ref nav)
        │ early exit → service_reply widget
        ▼
  TurnFrame shadow (turn_planner_llm via run_resolver_turn)
        ▼
  orchestrate_target_fullcontext_turn
        ├─ load_target_runtime_client_context (cached FullContext, once per client/process)
        ├─ load_runtime_turn_frame + session hydration (last_service_id)
        ├─ medical boundary classify (none / medical_handoff / uncertain)
        ├─ policy envelope + TurnFrame dispatch
        ├─ structured PRIMARY_EVIDENCE (pricebook · doctors · marketing)
        ├─ Composer (cached FullContext + scoped evidence + directives)
        ├─ lightweight Verifier (numeric + 3 blocking semantic kinds)
        └─ target widget / session write (follow-ups · CTA · consultation_value dedup)
        ▼
  service_reply JSON  OR  SSE batch (typing → ui → done)
```

**Источники:** `app.py:296-322`, `orchestration/pre_resolver_turn.py`, `orchestration/resolver_turn.py`, `orchestration/target_fullcontext_turn.py`, `core/target_runtime_turn.py`.

---

## C. Таблица компонентов

| Component | Responsibility | Status | Evidence |
|-----------|----------------|--------|----------|
| HTTP `/ask` / `/ask/stream` | Единая orchestration, разная упаковка | **ACTIVE** | `app.py:345-362`, `app.py:492-516` |
| Pre-resolver guards | Ingress, lead, booking, situation, ref nav | **ACTIVE** | `orchestration/pre_resolver_turn.py:134-257` |
| TurnFrame planner | Shadow frame в `request.ctx` | **ACTIVE** | `orchestration/resolver_turn.py:52-154` |
| Cached FullContext | MD corpus build once per client/process | **ACTIVE** | `core/target_runtime_client_context.py:126-163`, `core/target_cached_full_context.py:79-104` |
| Medical boundary (S42) | none / medical_handoff / uncertain | **ACTIVE** | `core/target_medical_boundary.py`, `core/target_turn_frame_policy_envelope_enforcement.py:84-103` |
| Structured evidence | Pricebook, doctors, marketing, payment stages | **ACTIVE** | `core/response_schema_loader.py`, `core/target_composer_request.py`, `core/target_marketing_selector.py` |
| Composer | Patient answer from FullContext + evidence | **ACTIVE** | `core/target_composer_executor.py`, `core/target_verified_response_pipeline.py:43-62` |
| Lightweight Verifier | Block diagnosis/eligibility/treatment choice + strict facts | **ACTIVE** | `core/target_response_verifier.py:32-38`, `622-675` |
| Target session/widget | Follow-ups, CTA, consultation dedup | **ACTIVE** | `core/target_runtime_session.py`, `core/target_runtime_widget.py` |
| Legacy ask_turn / chunk / source_routing | Product answer path | **DELETED (S69)** | `Test-Path` False; `tests/test_s69_legacy_deleted_offline.py` |
| Provider prompt caching | API-level cache for stable prefix | **NOT IMPLEMENTED** | `core/target_cached_full_context.py:17-18`, `core/target_runtime_llm_backends.py:80-86` |
| Token streaming (SSE) | Composer token-by-token | **NOT IMPLEMENTED** | `app.py:461-466` — batch `ui` only |
| A9 patient_scope | Shadow eval only | **HISTORICAL / SHADOW** | `evals/v5/run_patient_scope_shadow_eval_v2.py` |

---

## D. Таблица первоначальных целей

| Goal | Achieved / Partial / Not achieved | Evidence | Blocker? |
|------|-----------------------------------|----------|----------|
| Бот-продавец (лид, CTA, без меддиагноза) | **Achieved** | Composer policy + Verifier blocks personal medical conclusion; CTA via `target_marketing_selector` | No |
| FullContext (весь MD-корпус в Composer) | **Achieved** | `TargetComposerInvocation.cached_full_context`; 54 MD demo corpus cached | No |
| 150–200 небольших MD | **Partial (headroom OK)** | Demo: 54 MD, ~106k chars (~170 KB UTF-8). Target design: 150–200 MD. ~3× запас по размеру на demo scale | No — remeasure at scale |
| Точные цены / этапы оплаты | **Achieved** | `pricebook/facts.json` + `services/*.json` → PRIMARY_EVIDENCE; verifier numeric gate | No |
| Врачи из catalog | **Achieved** | `doctor_catalog.json` + MD profile refs; verifier doctor claims | No |
| Маркетинговый слой + CTA | **Achieved** | `marketing.yaml` via `response_schema_loader`; `build_target_runtime_widget_cta` | No |
| Лёгкий Verifier | **Achieved** | 3 blocking semantic kinds + numeric/commercial gates; no retry/repair loops | No |
| Медицинская граница | **Achieved** | Ingress urgent; S42 handoff/missing-base/uncertain; tests S56/S59 | No |
| Без RAG/chunk routing | **Achieved** | Legacy modules deleted; dispatch only `service_reply`; ref nav without `get_chunk_by_ref` on product path | No |
| Без legacy fallback | **Achieved** | `orchestrate_target_fullcontext_turn` fail-closed; no `TARGET_FULLCONTEXT_DEV` | No |
| Multi-client proven E2E | **Partial** | `load_target_runtime_client_context(client_id)`; only `demo` exercised in target tests | No — onboarding milestone |
| Provider prompt caching | **Not achieved** | Explicitly deferred; stable prefix candidate exists | No — cost/perf gap |

---

## E. Таблица оставшихся элементов

| Item | Classification | Why retained | Required next action |
|------|----------------|--------------|----------------------|
| `core/md_chunks.py` | OFFLINE_TOOLING | Not on target `/ask` path; tooling/tests | Optional cleanup milestone; not S-series blocker |
| `llm.py` legacy helpers (`rewrite_query_for_retrieval`, packet composer) | DEAD_CODE_CANDIDATE | No product import from target chain | Optional hygiene PR |
| `contracts/ask_orchestration.py` `kind=chunk/composer` | DEAD_CODE_CANDIDATE | Schema remnant; dispatch raises if emitted | Optional contract prune |
| `config COMPOSER_ON` / `FULLCTX_ON` | DEAD_CODE_CANDIDATE | Orphaned from product path post-S69 | Docs/flags cleanup only |
| `session.pending_clarify` API | SHARED_RUNTIME | **Active reader:** `core/turn_planner_llm.py:19,197,249` | Keep; no product writer after S69 |
| `session.last_subject` / `core/dialog_focus.py` | SHARED_RUNTIME | Legacy price/focus helpers; target hydrates via `target_runtime_state.last_service_id` | Keep for shared selectors/tests; not target read path |
| `evals/v5/s62|s63|s66_*_harness.py` | HISTORICAL_AUDIT | Frozen live replay; references deleted modules by design | KEEP_HISTORICAL; no product wiring |
| Frozen S62/S63/S66 artifacts | HISTORICAL_AUDIT | SHA-pinned regression anchors | Immutable |
| `drafts/checker_last.md` | OFFLINE_TOOLING | Checker reports | Informational only |
| `core/marketing_loader.py` | DEFERRED_PRODUCT_FEATURE | Alternate loader; target uses `response_schema_loader` | None until product needs it |
| Provider prompt caching | DEFERRED_PRODUCT_FEATURE | Cost/latency optimization | Separate milestone before production client |
| SSE token streaming | DEFERRED_PRODUCT_FEATURE | UX polish | Separate milestone |
| Admin / verifier warning viewer | DEFERRED_PRODUCT_FEATURE | Observability | Post-production |
| A9 patient_scope authority | DEFERRED_PRODUCT_FEATURE | Shadow-only per guardrails | Owner decision; not S-series |
| Second real client pack | DEFERRED_PRODUCT_FEATURE | Only `demo` validated end-to-end | Onboarding checklist per section H |

---

## F. Must-fix blockers

**None.**

---

## G. Deferred features

| Feature | Why deferred | Blocker for S-series? |
|---------|--------------|----------------------|
| Provider prompt caching | Not implemented; corpus prefix is stable candidate only | **No** — cost/performance |
| Token-by-token SSE streaming | Batch `typing→ui→done` works; product parity on authority | **No** — UX |
| Admin / runtime log viewer for verifier warnings | Planned admin layer | **No** |
| A9 authority / re-audit | Shadow-only; guardrails forbid A9 changes in S70 | **No** |
| Onboarding реального второго клиента | Architecture supports `client_id`; not live-proven | **No** — product ops |
| Additional quality evals (S57-style live) | Measurement separate from architecture completion | **No** |
| Dead code / schema hygiene (`md_chunks`, contract kinds, orphan flags) | No runtime impact on target path | **No** |

---

## H. Real-client readiness

### Уже универсально (shared core)

- `client_id` → `load_target_runtime_client_context` + `ResponseSchemaBundle`
- Cached FullContext from `clients/{id}/md/`
- Pricebook: `clients/{id}/target_response/pricebook/`
- Doctor catalog: `clients/{id}/target_response/doctor_catalog.json`
- Marketing: `clients/{id}/target_response/marketing.yaml`
- Policies/features: `clients/{id}/features.yaml`, ingress templates
- `allowed_topics` / service IDs — client-configurable via pack + schema loaders

### Что нужно подготовить для нового клиента

1. Validated MD corpus (`md/`, target 150–200 small docs)
2. `pricebook/facts.json` + `pricebook/services/*.json` (staged payments per service)
3. `doctor_catalog.json` (position, experience, services, selling profile — per agreed schema)
4. `marketing.yaml` (consultation facts, CTA keys)
5. `features.yaml` / policy flags
6. Offline target tests + optional live gate (owner-approved)

### Что ещё проверить перед первым реальным подключением

- Corpus size/token budget at 150–200 MD (remeasure; demo ~54 MD ≈ 106k chars)
- Provider prompt caching decision (cost)
- Live eval under owner approval
- Widget/embed CORS for client domain
- Lead/booking integration with real CRM (out of S-series scope)

**Честно:** end-to-end multi-client **не доказан** — только `demo` pack exercised in target acceptance tests.

---

## I. Final protected boundaries

| Boundary | Status |
|----------|--------|
| No legacy product authority | ✅ S69 deleted modules; `app.py` unconditional target |
| No RAG/chunk answer routing | ✅ No `source_routing`, `chunk_responder`, `ask_turn` on disk |
| No medical diagnosis / treatment choice | ✅ Verifier `personal_medical_conclusion`; boundary S42 |
| Structured commercial authority | ✅ PRIMARY_EVIDENCE + numeric verifier gates |
| A9 shadow-only | ✅ No product wiring |
| Frozen artifacts immutable | ✅ `frozen OK` at audit time |
| No kill-switch / legacy fallback | ✅ `TARGET_FULLCONTEXT_DEV` removed from `config.py` |

---

## J. Recommendation

1. **Закрыть S-series** — архитектурная миграция на FullContext-only product path завершена.
2. **Не создавать S71 автоматически.**
3. Следующие этапы — отдельные product-направления по выбору владельца:
   - provider prompt caching + cost measurement;
   - token streaming UX;
   - второй client pack + onboarding playbook;
   - optional dead-code hygiene;
   - live quality eval (owner-approved).

---

## Audit area notes (detail)

### 1. Единственная product-цепочка

Подтверждено для: обычный вопрос, follow-up ref, price/doctors/payment aspects, medical_handoff, missing-base, uncertain defer, lead/booking, ingress manual_contact, target error fail-closed. Нет legacy branch, RAG, chunk/composer dispatch, automatic fallback, per-document routing. Ref-click → `resolve_target_followup_navigation` → тот же FullContext pipeline.

### 2. FullContext — три разных понятия

| Concept | Status |
|---------|--------|
| **A. Corpus build/cache** | ✅ `build_target_cached_full_context` once; `load_target_runtime_client_context` process cache per `client_id` |
| **B. Stable provider prefix** | ✅ `cached_full_context` identical across turns; turn-varying JSON separate; system role = policy only (`core/target_runtime_llm_messages.py`) |
| **C. Provider prompt caching** | ❌ Not implemented; passive `cached_tokens` logging only |

**Demo corpus:** 54 MD files, ~106,374 chars, ~170 KB UTF-8, SHA256 `ee6cc28b…`. Headroom to 150–200 MD: likely OK at similar doc size; **requires remeasurement** before claiming production scale.

### 3–4. Structured + content authority

Prices/payment stages from pricebook JSON; doctors from `doctor_catalog.json` + MD sections; marketing/CTA from structured selectors. FullContext is primary knowledge input; PRIMARY_EVIDENCE supplements for strict commercial facts — not hidden retrieval. `shown_consultation_value_refs` dedupes consultation_value (`core/target_runtime_session.py`).

### 5. Lightweight Verifier

Blocks: `unsupported_clinic_claim`, `personal_medical_conclusion`, `material_external_medical_claim` + numeric/commercial gates. Does not block: empathy, minor external detail, missing-base honest response, consult CTA. No disease blocklists, regex tables, voting, retry loops.

### 6. Medical boundary

Urgent → ingress before target (`pre_resolver_turn.py:134-159`). Confident `medical_handoff` → materialize. Missing-base → controlled response. Only `uncertain` → terminal defer.

### 7. Session continuity

Target hydrates `service_id` from `target_runtime_state.last_service_id` for vague price/doctor follow-ups (`core/target_runtime_turn_frame_hydration.py:38-72`). `pending_clarify` read by planner only — not legacy orphan on hot path. Target path does not depend on `current_doc_id`.

### 8. UI/runtime

`/ask` and `/ask/stream` share `_orchestrate_ask_turn`. SSE = batch only. CTA/follow-up refs active. Legacy widget compatibility not required.

### 9. Multi-client

Shared core is client-pack driven; demo is example, not hardcoded schema for all clinics.

### 11. Test confidence (verified at audit)

| Check | Result |
|-------|--------|
| S69 Checkpoint A | **80/80** (`248b6c6`) |
| S69 completion suite | **112/112** (`cdcd79f`) |
| Full collect-only | **2524** tests |
| S69 closeout targeted | **19/19** (`test_s69_checkpoint_a` + `test_s69_legacy_deleted`) |
| Frozen S62/S63/S66 pins | **frozen OK** |
| Product import audit | **clean** (comments only in `doctors_lookup.py`, `query_selector.py`, `pg_sink.py`) |
| Legacy files absent | `chunk_responder`, `ask_turn`, `source_routing`, `composer_flow` → False |

---

## Commits referenced

| Commit | Milestone |
|--------|-----------|
| `248b6c6` | S69 Checkpoint A — unconditional FullContext authority |
| `cdcd79f` | S69 Checkpoint B — legacy modules/tests deleted |
| `86ebf9b` | S70 governance (this audit) |
