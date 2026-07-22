# TASK — S45 FullContext-grounded Service-optional Verified Response

**Branch / baseline:** `codex/stage-a` / `01dfa28 feat: wire cached FullContext into target Composer`

**Goal:** один постоянный offline vertical slice: TurnFrame + envelope → **service-optional
content response** → prebuilt cached FullContext как основной источник общих знаний → scoped
primary evidence как strict sidecar → Composer → **FullContext-aware Verifier** → verified
response. Исправить переходное противоречие S37/S38 «facts only from PRIMARY_EVIDENCE».

**No live/LLM. No runtime/UI/session/authority. No A9. No S43 changes.**

## Owner laws (source authority)

### FullContext — primary for general clinic MD content

Разрешён как основной источник для: общих информационных ответов; описаний услуг;
клинико-информационных материалов; общих медицинских фактов клиники; успокаивающих ответов
на страх лечения; другого содержательного MD-текста.

### Primary evidence — strict sidecar only

Authority только для: цен; этапов оплаты; скидок/акций/limited offers; marketing facts;
consultation_value; CTA; exact doctor fields (имя, должность, стаж, service links); other
strict/exact commercial facts.

### Conflict rule

Structured exact source wins; Composer must not mix values; Verifier fail-closed rejects
conflicting answers.

### No document routing

Composer always sees entire cached FullContext; no pre-selected MD/chunk; scoped evidence
does not hide corpus.

## Service-optional materialization (permanent, not bridge)

Allow materialize **without `service_id`** only for safe general **content-only** path:

- `response_mode`: `answer` or confident `medical_handoff`;
- `required_components == ("content",)` only;
- prebuilt `TargetCachedFullContext` injected (build once outside pipeline);
- no service-scoped price/payment/doctors/offer requirements;
- no service_id guessing.

Still forbidden without `service_id`: price; offer selection; service-specific doctor;
service-specific marketing; bypassing structured selectors.

Existing service-specific S34/S40/S41 paths **unchanged in meaning**.

## Medical semantics (materialization targets)

1. **Pain/reassurance** («Больно ли ставить имплант?»): materialize without service_id;
   grounded from demo/synthetic FullContext (`implantation__faq__pain.md`); empathy allowed;
   no personal pain-free promise; consultation close allowed; not terminal.
2. **Known topic in corpus** (e.g. diabetes): neutral grounded answer + consultation; no
   diagnosis/personal eligibility/treatment choice.
3. **Missing topic in entire MD-base**: controlled materialized «нет в материалах клиники» +
   consultation; **not** terminal defer; no model medical knowledge; no single hardcoded
   template string.
4. Only boundary **`uncertain`** → terminal defer.
5. Urgent/manual-contact hard-stop unchanged and upstream.

## FullContext-aware Verifier

- Receives same prebuilt `TargetCachedFullContext` as Composer; no rebuild; no per-turn FS.
- Checks: general claims grounded in FullContext or allowed primary evidence; strict commercial
  facts only in structured primary evidence; medical facts in clinic FullContext; no
  diagnosis/differential/personal eligibility/treatment choice; missing-base without external
  medical knowledge; topic/service-family scope; structured commercial numbers only from
  primary evidence; allowable general MD numbers present in FullContext.
- Replace misleading `grounded_in_primary_evidence` with semantically honest target contract
  (no legacy compatibility).
- No repair/retry/fallback; accept or reject only.

## Composer policy (S37)

Update system policy to match dual authority above. FullContext = primary knowledge input;
primary evidence = strict structured sidecar. Allow empty primary evidence blocks only on
verified FullContext content-only path (`service_id is None`, content-only components).

## Deliverables

1. Service-optional content materialization in S34/S41 (and minimal package/scoped path).
2. Updated Composer policy + invocation semantics (no «background only» for general facts).
3. FullContext-aware Verifier contract + deterministic checks + semantic invocation payload.
4. Pipeline propagation of `cached_full_context` into Verifier (S39/S40/S41 unchanged rebuild
   rules from S44).
5. Offline tests per acceptance below + neighbor regression.
6. ARCH/ROADMAP status for S45 only.

## Boundaries / allowlist

- `TASK.md`
- `contracts/target_response_verifier.py` (new semantic verification contract if split from core)
- `core/target_composer_executor.py`
- `core/target_composer_request.py`
- `core/target_spec_offline_response_package.py`
- `core/target_scoped_response_evidence.py`
- `core/target_response_materialization_plan.py` (only if service_id optional for content-only)
- `core/target_offline_response_assembly.py` (only if service_id optional typing)
- `core/target_offline_response_package.py` (only if minimal content-only package helper)
- `core/target_fullcontext_content_package.py` (new: minimal service-optional bound package)
- `core/target_turn_frame_dispatch.py`
- `core/target_response_verifier.py`
- `core/target_verified_response_pipeline.py`
- `tests/test_target_fullcontext_content_response.py` (new)
- `tests/test_target_turn_frame_dispatch.py`
- `tests/test_target_spec_offline_response_package.py`
- `tests/test_target_scoped_response_evidence.py`
- `tests/test_target_composer_executor.py`
- `tests/test_target_response_verifier.py`
- `tests/test_target_verified_response_pipeline.py`
- `tests/test_demo_target_turn_frame_bound_response.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `tests/test_target_cached_full_context.py` (only if shared helpers)
- `tests/test_target_policy_bound_verified_response_pipeline.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

**Forbidden:** A9; S43 artifacts/matrix; runtime/UI/session/authority; live/LLM/providers;
provider prompt caching; RAG/retriever/routing; legacy `knowledge_base.py`; hardcoded response
templates; per-turn FullContext rebuild; new thematic classifier/router table; `used_doc_ids`
product contract unless STOP escalation required.

## Minimal protected acceptance (offline, no live)

1. General service-less content: `service_id=None` materializes; Composer×1; Verifier×1.
2. Pain/reassurance demo path: verified; grounded reassurance; no personal promise; not terminal.
3. Known medical topic (diabetes): grounded passes; diagnosis/eligibility rejected.
4. Missing topic synthetic: no-information + consultation passes; external medical fact rejected.
5. Structured authority: price/marketing without evidence rejected; FullContext vs structured
   conflict rejected; existing service-specific price/doctor path stays green.
6. FullContext propagation: Composer + Verifier same prebuilt corpus; no builder/FS in pipeline.
7. Boundary: uncertain terminal; confident medical_handoff materializes without service_id;
   urgent path untouched.
8. Neighbor regression: targeted S34/S37/S38/S39/S40/S41/S44 tests green; no skip/xfail.

Run only listed targeted tests with external `--basetemp` and `-p no:cacheprovider`. **No full
pytest. No live.**

## Gates

1. Independent **PRE-CODE** checker on governance TASK.
2. Commit/push `docs: govern S45 FullContext service-optional verified response` (**TASK.md
   only**).
3. Implement allowlist; run targeted offline tests.
4. Independent **COMPLETION** checker.
5. One completion commit; push; clean/synced.

## STOP escalation (before coding)

If mandatory new `used_doc_ids` product contract or other scope expansion emerges — STOP and
report owner with minimal alternative.

## Explicitly out of scope

- A9 / message→TurnFrame planner
- Runtime / UI / session / product authority
- Live Composer/Verifier quality proof
- Provider prompt caching integration
