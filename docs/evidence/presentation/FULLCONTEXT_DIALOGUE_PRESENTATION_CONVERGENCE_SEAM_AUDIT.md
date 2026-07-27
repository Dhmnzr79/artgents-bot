# FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `7c716df` (`FULLCONTEXT_PRESENTATION_PARITY` Phase 2 complete)  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| `HEAD` == `origin/codex/stage-a` @ `7c716df` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone `FULLCONTEXT_PRESENTATION_PARITY` Phase 2 landed | ✅ (`target_presentation_*`, bone_graft demo data) |
| Target FullContext product path active (S69) | ✅ |

## Phase 2 carry-over (what landed @ `7c716df`)

| Area | Status |
|---|---|
| `target_presentation_decision.py` | **Partial** — slot caps, video/situation wiring |
| `target_presentation_source_identity.py` | **Partial** — MD ref validation + frontmatter read |
| `target_presentation_turn_projection.py` | **Partial** — semantic_context + 3/5 scenarios |
| `target_runtime_widget.py` | **Partial** — presentation decision integrated |
| `target_runtime_turn.py` | **Partial** — marketing_scenarios wired, cadence read/write |
| `target_response_verifier.py` | **Partial** — validates refs when passed in |
| bone_graft demo service/offer | ✅ |
| Gaps A–G from prior audit | **Not fully closed** — see H–N below |

## Owner decisions (binding for implementation)

### 1. Source identity for generic FAQ/info/comparison

Canonical typed contract on verified Composer output:

| Field | Role |
|---|---|
| `text` | Answer prose |
| `used_content_refs` | All MD refs Composer used (normalized `*.md`) |
| `primary_content_ref` | One validated primary MD for presentation metadata |

**Preferred direction:** structured Composer sidecar/envelope — **not** post-hoc text analysis.

Requirements:

- Refs validated against cached FullContext MD index (`md_root`); **invented refs never used** (dropped).
- No retriever, RAG, keyword routing, or second selector.
- Verifier receives and passes only validated source identity to presentation layer.
- Presentation metadata (`suggest_h3`, `video_key`, `situation_allowed`) read **only** from validated `primary_content_ref`.
- Exact-service paths (`service_id` + `content_ref` ownership) unchanged.

**Generic FAQ/info/comparison — fail semantics (owner correction):**

| Case | Answer text | Source-based UI (follow-up / video / situation) |
|------|-------------|--------------------------------------------------|
| Valid answer + valid source identity | ✅ show | ✅ show |
| Valid answer + missing/invalid source identity | ✅ show | ❌ suppress; log **warning** |
| Missing/unparseable answer | ❌ block | ❌ |
| Invented refs in sidecar | ✅ show answer if otherwise valid | ❌ dropped; never used for UI |

**Principle:** source identity is **fail-closed for presentation metadata**, **fail-open for generic answer text**.
Do **not** verifier-block the whole response solely because `source_identity` is missing or invalid.

**Verifier fail-closed (blocking) remains only for:**

- missing or unparseable `answer`;
- exact clinic/commercial claims in prose without PRIMARY_EVIDENCE support;
- contact answers without validated `clinic_contact` PRIMARY_EVIDENCE;
- existing blocking Verifier decisions (unsupported claims, personal medical conclusion, etc.).

### 2. Authoritative contact data

One canonical structured schema for: phone, WhatsApp, address, hours, parking, other exact clinic facts.

Direct questions («Какой телефон?», «Есть WhatsApp?», «Где вы?», «Как работаете?») → **PRIMARY_EVIDENCE** deterministic block, **not** free Composer generation.

No mandatory mirrors across files; authoring doc states one edit surface per fact class.

### 3. Strict UI channel separation

| Channel | Max | Contents | Must not mix with |
|---|---|---|---|
| **Choice menu** | 4 | `UiScopeAction`, `UiStageAction`, typed clarification choices | secondary, price-detail |
| **Content secondary** | 2 | video → unseen content follow-up → situation (if slot left) | choice menu, price-detail |
| **Price-detail** | 2 | authored price followups only | choice menu, content secondary |
| **CTA** | 1 | separate payload field | all QR channels |

**One response = exactly one navigation channel** among choice / content secondary / price-detail.

### 4. «Рассказать о ситуации»

Show when **all** true:

- validated `primary_content_ref` MD;
- frontmatter `situation_allowed: true`;
- situation feature enabled;
- after video + ordinary follow-up, secondary slot remains;
- not yet shown in session.

Intake flow preserved: situation → name → phone → demo_stub.

### 5. Marketing hooks

All authored typed scenarios via TurnFrame/planner semantics (no regex lists):

- `pain_fear`, `cost`, `time`, `doctor_trust`, `result_reliability`
- max 0–2 scenarios per turn; existing 3/2 fact/amplifier limits preserved
- marketing facts ≠ UI slots
- `consultation_value` rules unchanged (exact service/option only; generic FAQ N/A)

### 6. Fallback / handoff

Technical error, verifier block, nonmaterializable handoff:

- fixed human text;
- **only** confirmed phone from canonical contact authority in prose;
- no CTA, QR, video, situation, marketing facts;
- `attribution_kind=plain`
- Composer must not invent phone numbers

Global internal error/reset/plain stubs: no «по материалам клиники» attribution.

### 7. Regression coverage

Restore stale multi-turn tests after presentation session fields: vague doctors, vague price, payment follow-up, hydration, fresh clinic-wide doctors without invented `service_id`, terminal/error must not wipe focus.

## Master seam table (@ `7c716df`)

| # | Mechanism | Canonical docs | Producer | Consumer | Session | State |
|---|-----------|------------------|----------|----------|---------|-------|
| 1 | Composer source identity sidecar | ARCH §source identity; this audit §1 | `core/target_composer_executor.py` (`TargetUnverifiedComposedResponse` — text only today) | `core/target_response_verifier.py` → `TargetVerifiedComposedResponse` | meta `primary_content_ref`, `used_content_refs` | **Gap H** |
| 2 | Evidence-inferred refs (interim) | `core/target_verified_response_pipeline.py` | `_used_content_refs_from_package` from evidence blocks + plan | verifier | same | **Partial / wrong for FAQ** |
| 3 | Content-only package identity | `core/target_fullcontext_content_package.py` | `primary_content_ref=None` always | followup materializer | — | **Gap H** |
| 4 | Presentation metadata | `target_presentation_source_identity.read_doc_presentation_meta` | frontmatter of `primary_content_ref` | `target_presentation_decision._cap_secondary_content` | — | **Partial** — needs Composer primary |
| 5 | Contact authority | `clinic_policies.yaml`, `clinic__info__contacts.md` | split sources (see §Contact audit) | Composer FullContext (free gen) | — | **Gap I** |
| 6 | Contact PRIMARY_EVIDENCE | ARCH boundary detection | **missing** structured loader → evidence block | Composer | — | **Gap I** |
| 7 | Choice menu ≤4 | `target_presentation_decision._cap_choice_items` | scope/stage nav | `decide_target_presentation` | `shown_*_followup_refs` | **Partial** |
| 8 | Content secondary ≤2 | `_cap_secondary_content` | followup materializer | widget `quick_replies` | cadence | **Partial** — priority bug **Gap J** |
| 9 | Price-detail ≤2 | `_cap_price_items` | price followups | widget | cadence | **Connected** |
| 10 | Channel mutex | owner §3 | `decide_target_presentation` L278–293 | widget | — | **Gap K** — mixes channels |
| 11 | Video | `video_catalog.yaml`, MD `video_key` | `_cap_secondary_content` | widget `video` | `shown_video_ids` | **Connected** |
| 12 | Situation offer | MD `situation_allowed`, `flow_handlers.py` intake | `_cap_secondary_content` + widget | widget + pre-resolver | `situation_offered` | **Partial** — priority **Gap J**; HTTP tests **Gap L** |
| 13 | Marketing scenarios | `marketing.yaml`, `derive_marketing_scenarios` | `target_runtime_turn.py` | `target_marketing_selector` | `shown_fact_ids` | **Partial** — `time`/`result_reliability` **Gap M** |
| 14 | CTA semantic context | `resolve_target_semantic_context` | runtime turn | marketing selector + widget CTA | meta | **Connected** @ Phase 2 |
| 15 | Session cadence | `target_runtime_session.py` | write after materialize | read next turn | `shown_video_ids`, `shown_content_followup_refs`, `shown_price_followup_refs`, `situation_offered` | **Connected** @ Phase 2 |
| 16 | Fallback phone | owner §6 | `materialize_target_error_payload` | widget | — | **Gap N** |
| 17 | Plain attribution | `attribution_kind` in meta | terminal/error builders | widget/admin | — | **Partial** — `internal_error_response` missing |
| 18 | Post-widget limiter | `ux_builder.normalize_policy_payload` | app.py after widget | widget JSON/SSE | — | **Stale risk** — truncates after decision |
| 19 | `consultation_value` | `service_consultation_source.py` | exact service path only | answer text | `shown_consultation_value_refs` | **Connected** — do not widen |

## Confirmed gaps H–N (post Phase 2)

### Gap H — Composer source identity sidecar missing

| Layer | Finding |
|-------|---------|
| Composer output | `TargetUnverifiedComposedResponse` = text + spec + followups + cta only — **no** `used_content_refs` / `primary_content_ref` |
| Interim inference | `target_verified_response_pipeline._used_content_refs_from_package` copies evidence block refs + plan — works for exact service, **not** generic FAQ where plan has `primary_content_ref=None` |
| Content-only | `assemble_target_fullcontext_content_bound_package` sets `primary_content_ref=None` |
| Effect | Generic pain FAQ cannot bind `suggest_h3` / `video_key` / `situation_allowed` to Composer-selected MD |
| **State** | **Disconnected** for generic FAQ |

**Proposed contract — strict Composer JSON (owner correction @ `6eb6cee`):**

Live backend and offline recording backends must return **strict JSON** (not prose-only):

```json
{
  "answer": "...",
  "source_identity": {
    "primary_content_ref": "implantation__faq__pain.md",
    "used_content_refs": ["implantation__faq__pain.md"]
  }
}
```

Rules:

- `primary_content_ref` **must** be a member of `used_content_refs` when present.
- **Invented refs never used** — dropped during validation.
- For generic FAQ/info/comparison:
  - valid answer + valid source → answer + source-based UI;
  - valid answer + missing/invalid source → **answer shown**, follow-up/video/situation **suppressed**, warning logged;
  - **do not** block entire answer solely due to bad/missing `source_identity`.
- Executor parses JSON; semantic verifier assesses `answer` prose under existing blocking rules.
- **Requires live Composer backend + recording contract update** before cutover.

Typed Python mirror (`contracts/target_composer_source_identity.py`):

```python
@dataclass(frozen=True)
class TargetComposerSourceIdentity:
    primary_content_ref: str
    used_content_refs: tuple[str, ...]
```

Flow: Composer backend returns JSON → executor parses → validate refs against `md_root` (drop invented) → if valid primary: enable source-based UI; else: answer-only + warning → presentation never uses unvalidated refs.

**Verifier blocking (unchanged, separate from presentation metadata):** missing/unparseable answer; exact commercial/clinic claims without PRIMARY_EVIDENCE; contacts without `clinic_contact` evidence; existing semantic blocking kinds.

### Gap I — Contact authority split / no PRIMARY_EVIDENCE path

| Source | Fields today |
|--------|--------------|
| `clients/demo/clinic_policies.yaml` | `contact.phone_display` only — **incomplete structured schema** |
| `clients/demo/md/clinic__info__contacts.md` | **duplicate** phone, address, hours, WhatsApp, parking in MD body |
| `core/clinic_hours.py` | expects `hours.weekly` in policies — **demo pack has none** |
| `core/clinic_policies_loader.py` | phone for `manual_contact_template` |
| `policy.contacts_intent` | legacy regex — **forbidden on target path** |
| Target FullContext | contact Q → Composer + FullContext — **free generation** |

**Proposed canonical authority (owner correction):**

| Fact class | Canonical file | Notes |
|------------|----------------|-------|
| phone, whatsapp, address, parking, structured hours | `clients/{id}/clinic_policies.yaml` → `contact:` block | **единственный** источник правды |
| MD contact duplicates | **forbidden** | не дублировать телефон, адрес, часы в `md/` |

**Removal plan:** expand structured `contact:` in `clinic_policies.yaml`; remove or strip factual contact fields from `clinic__info__contacts.md` (no dual-edit surfaces). `clinic_hours.py` reads structured hours from same block.

**Contact question routing (no regex):**

- Add typed `contacts` to `AspectKind` / TurnFrame.
- Turn Planner (same LLM call) sets `primary_aspect=contacts` or `aspects` contains `contacts` for direct contact questions («Какой телефон?», «Есть WhatsApp?», «Где вы?», «Как работаете?»).
- Target runtime branches on validated TurnFrame — **not** `policy.contacts_intent` regex.

**PRIMARY_EVIDENCE path:**

`TurnFrame` with `contacts` aspect → `materialize_clinic_contact_primary_evidence(client_id)` → evidence block:

| Field | Value |
|-------|-------|
| `kind` | `clinic_contact` (**not** `commercial_fact`) |
| `must_preserve_exact` | `true` |
| `text` | structured fields from `clinic_policies.yaml` only |

Composer must not invent or paraphrase contact numbers/address/hours.

### Gap J — Situation priority inverted

`target_presentation_decision._cap_secondary_content` inserts situation **before** content follow-up queue (L218–226 before L228–234).

Owner rule: **video → content follow-up → situation (if slot remains)**.

Effect today: situation can displace `suggest_h3` follow-up; acceptance rows 5–6 fail.

### Gap K — Navigation channel mixing

`decide_target_presentation`:

- when `choice_qr` non-empty: `quick_replies = choice_qr + price_qr` (L278–279)
- else: `quick_replies = secondary_qr + price_qr` (L293)

Owner rule: **one channel per response**. Price-detail must be suppressed when choice or content secondary is active.

### Gap L — Situation HTTP tests missing

Intake wired in `flow_handlers.py` (`situation_action` start/back, `situation_pending`, PII in `core/observability_pii.py`).

**No** dedicated HTTP offline tests for: start, back, submit, SID isolation, interrupt/resume, PII withholding on `/ask` path.

### Gap M — Marketing scenarios: heuristic projection wrong; TurnFrame field missing

**Owner correction:** `time` and `result_reliability` **cannot** be inferred from `duration`/`warranty` aspects or direct informational questions. A direct question is **not** a marketing objection.

| Anti-pattern | Why wrong |
|--------------|-----------|
| `primary_aspect == "duration"` → `time` | «Сколько длится имплантация?» = informational, not objection |
| `primary_aspect == "warranty"` → `result_reliability` | «Какая гарантия?» = direct fact question |
| `topic == "doctors"` → `doctor_trust` | «Кто врач?» = informational |

**Current interim (to remove):** `derive_marketing_scenarios` maps `emotion`/`price` heuristically — **superseded**.

**Canonical contract — add to `TurnFrame`:**

```python
marketing_scenarios: list[
    Literal["pain_fear", "cost", "time", "doctor_trust", "result_reliability"]
]  # 0–2 values, from Turn Planner same LLM call
```

Rules:

- Turn Planner emits 0–2 scenarios in the **same** planner invocation; no extra classifiers, no regex.
- Scenario only on **expressed fear, doubt, or objection** — not on neutral/direct questions.
- Examples:
  - «Боюсь, что это слишком долго» → `time`
  - «А вдруг имплант не приживётся?» → `result_reliability`
  - «Не доверяю врачу без опыта» → `doctor_trust`
  - «Сколько длится имплантация?» → **no** `time`
  - «Какая гарантия?» → **no** `result_reliability`
  - «Кто врач?» → **no** `doctor_trust`
- Runtime uses **only** validated `TurnFrame.marketing_scenarios`; delete `derive_marketing_scenarios` after cutover.
- Malformed/unknown values → sanitized to empty list.
- Implementation requires: contract field, sanitization, planner prompt update, blast-radius tests.

`marketing.yaml` already authors amplifiers for all five scenarios.

### Gap N — Fallback without canonical phone

`materialize_target_error_payload` — fixed text, **no phone**, empty QR/CTA/video/situation ✅, `attribution_kind=plain` ✅.

`ux_builder.internal_error_response` — no `attribution_kind`, no phone.

Composer system policy forbids contact from FullContext alone — but fallback path does not inject authoritative phone.

## Proposed presentation channel scheduler

```text
Inputs: navigation_followups, selected_followups{content, price}, primary_content_ref,
        cadence, allow_situation, client_id, md_root

1. Classify refs: choice | content | price (classify_followup_ref)

2. If navigation has unseen choice refs:
     channel = CHOICE
     quick_replies = cap_choice(≤4)
     video = None; situation.show = False
     suppress content + price QR entirely

3. Elif selected_followups.content non-empty OR primary has presentation meta:
     channel = CONTENT_SECONDARY
     slots = 2
     if video_key valid and not shown → video sidecar; slots -= 1
     fill slots from unseen suggest_h3 followups (validated primary)
     if slots > 0 and situation_allowed and feature on and not offered:
         situation.show = True; slots -= 1
     quick_replies = content caps only
     suppress price QR

4. Elif selected_followups.price non-empty:
     channel = PRICE_DETAIL
     quick_replies = cap_price(≤2)
     video = None; situation.show = False

5. Else:
     channel = NONE (CTA/text only)

CTA: always separate field; never consumes QR slots.
Post: normalize_policy_payload must NOT re-truncate governed decision.
Session: write cadence only on materialized success.
```

## Contact audit — target path (@ `7c716df` + owner correction)

| Question | Current path | Target path |
|----------|--------------|-------------|
| «Какой телефон?» | Composer + FullContext | TurnFrame `contacts` aspect → PRIMARY_EVIDENCE `clinic_contact` |
| «Есть WhatsApp?» | Composer + FullContext | same |
| «Где вы?» | Composer + FullContext | same |
| «Как работаете?» | Composer + FullContext | same |
| Manual-contact hard-stop | `clinic_policies.yaml` templates | same canonical `contact:` phone |
| Fallback/error | fixed text, no phone | fixed text + canonical phone only |

**Authoring:** edit **only** `clinic_policies.yaml` `contact:` — never duplicate phone/address/hours in MD.

## consultation_value — preserve (unchanged from prior milestone)

| Rule | Status |
|------|--------|
| Automatic close only on exact service/option `selected_content_ref` | ✅ |
| Generic FAQ/info/comparison — no automatic `consultation_value` | ✅ intentional |
| Direct consultation question = primary content, not automatic close | ✅ normative |
| Source identity must not widen applicability via `used_content_refs` | binding |

## Acceptance matrix (implementation)

| # | Criterion |
|---|---|
| 1 | Generic pain FAQ + valid source → answer + source-based UI |
| 1b | Generic FAQ + valid answer + missing/invalid source → answer only, no follow-up/video/situation, warning logged |
| 2 | FAQ follow-up from `suggest_h3` on validated primary MD |
| 3 | FAQ with video + follow-up → video + one follow-up (two secondary slots) |
| 4 | Video already shown → next unseen follow-ups available |
| 5 | Existing follow-up → situation does not displace it |
| 6 | One follow-up + free slot → situation may show |
| 7 | Choice menu contains no price-detail refs |
| 8 | Price-detail response contains no content secondary |
| 9 | Direct phone / address / hours / WhatsApp → PRIMARY_EVIDENCE exact answer |
| 10 | Marketing `time` scenario selectable (0–2) via TurnFrame |
| 11 | Marketing `result_reliability` scenario selectable (0–2) via TurnFrame |
| 12 | Exact-service `consultation_value` preserved |
| 13 | Generic FAQ without neighbor `consultation_value` |
| 14 | Technical fallback → fixed text + canonical phone only |
| 15 | Verifier block → fixed text + canonical phone only |
| 16 | Internal error → `attribution_kind=plain`, no clinic-material attribution |
| 17 | Situation start / back / submit HTTP offline tests |
| 18 | No-repeat cadence for video, followups, situation |
| 19 | `/ask` and `/ask/stream` parity on all above |
| 20 | AC1–AC3, typed UI, explicit service price lookup, pricebook paths — no regression |

## Multi-turn regression tests (implementation allowlist)

| Test theme | Existing anchor | Gap |
|------------|---------------|-----|
| Vague doctors + session focus | `tests/test_vague_doctor_followup.py` | extend for `shown_*` cadence fields |
| Vague price follow-up | `tests/test_attribute_followup.py`, `test_c2c_session_migration_offline.py` | re-wire to target session |
| Payment follow-up hydration | `tests/test_s62_correction_offline.py` | presentation session fields |
| Service focus hydration | `tests/test_c2c_service_focus_age_offline.py` | terminal must not wipe |
| Fresh clinic-wide doctors | `tests/test_s63_correction_offline.py` | no invented `service_id` |
| Terminal/error focus | scattered S61/S62 tests | unified assertion |

## Implementation seam (target — not in this commit)

```text
TurnFrame (marketing_scenarios 0–2 from planner; contacts aspect when applicable)
  → clinic_contact PRIMARY_EVIDENCE branch (deterministic, pre-Composer)
  → Composer strict JSON { answer, source_identity }
  → Verifier (answer blocking rules unchanged; source identity gates UI only for generic FAQ)
  → decide_target_presentation (single channel mutex, correct situation priority)
  → widget (CTA separate)
  → fallback injector (canonical phone from clinic_policies.yaml only; plain attribution)
  → session cadence write (materialized only)
```

## Governance correction (@ post-`6eb6cee`)

Binding clarifications from owner (docs/tests only in this commit):

1. **Contacts** — only `clinic_policies.yaml`; no phone/address/hours duplication in MD.
2. **Contact routing** — typed `contacts` aspect from Turn Planner; no regex on target path.
3. **Composer** — strict JSON sidecar; `primary_content_ref ∈ used_content_refs` when present.
4. **Evidence** — `kind=clinic_contact`, not `commercial_fact`.
5. **Marketing** — `TurnFrame.marketing_scenarios` from planner; remove `derive_marketing_scenarios` heuristics; direct questions ≠ scenarios.

## Governance correction — source identity fail-open (@ post-`f91fc04`)

For generic FAQ/info/comparison:

- valid answer + valid source → answer + source-based UI;
- valid answer + missing/invalid source → answer shown, UI suppressed, warning logged;
- invented refs never used;
- do **not** block entire answer solely for source-identity sidecar.

Fail-closed (blocking) only for: missing/unparseable answer; exact clinic/commercial claims without PRIMARY_EVIDENCE; contacts without `clinic_contact` evidence; existing Verifier blocking decisions.

**Principle:** fail-closed for presentation metadata; fail-open for generic answer text.

## STOP

This audit + TASK governance authorize **governance PRE-CODE only**.
Implementation begins only after independent PRE-CODE checker ✅ and explicit owner GO.
**NO PRODUCT CHANGE / NO LIVE / NO LLM** in governance commit.
