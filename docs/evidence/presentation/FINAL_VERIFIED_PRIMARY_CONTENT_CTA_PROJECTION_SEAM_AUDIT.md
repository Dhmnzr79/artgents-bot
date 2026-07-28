# FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION — seam audit

**Дата:** 2026-07-28  
**Baseline:** `codex/stage-a` @ `ce256c5`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM / NO Verifier policy change**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch `codex/stage-a` | ✅ |
| `HEAD` == `origin/codex/stage-a` @ `ce256c5` | ✅ |
| Working tree clean at governance start | ✅ |

## Defect (confirmed offline @ `ce256c5`)

**Turn:** «Я боюсь боли» (starter prompt `clients/demo/widget_config.json` and free-text equivalent).

| Stage | Actual | Expected |
|---|---|---|
| Composer | Valid answer from `implantation__faq__pain.md` | ✅ |
| Verifier | `primary_content_ref=implantation__faq__pain.md` validated | ✅ |
| MD frontmatter | `cta_key: consult`, `cta_action: lead` | ✅ authored |
| Policy / package | `allow_cta=False`, `selected_cta_key=None` | generic FullContext by design |
| Widget `cta` | `null` | CTA `consult` from validated primary only |

**Root cause:** CTA is wired only through planner/service/marketing package paths (`allow_cta` + `plan.cta_key`). Generic FullContext intentionally sets `allow_cta=False` and never projects authored MD CTA after Verifier validates `primary_content_ref`. Presentation layer already reads the same primary for `video_key` / `situation_allowed` / `suggest_h3`, but **not** for CTA.

## Owner decisions (binding for implementation)

### 1. Verified-primary CTA projection rule

If **all** true after successful Verifier pass on a materialized response:

- `validated primary_content_ref` is present and file-valid under `md_root`;
- response is not terminal / error / medical handoff / verifier-blocked;
- `selected_cta_key` is **not** already set by explicit service/price/marketing path;
- validated primary MD frontmatter contains allowed CTA metadata;

→ project `selected_cta_key` (and widget CTA payload) **only** from that primary MD.

**Do not** set `allow_cta=True` globally for generic FullContext specs. Projection is a **post-Verifier typed side-effect** on the verified response, not a policy widening.

### 2. Forbidden CTA sources (fail-closed)

Never derive CTA from:

- arbitrary `used_content_refs` (non-primary);
- neighboring / guessed service or topic;
- `marketing_scenarios` or marketing selector;
- answer prose or Composer hallucination;
- `CACHED_FULL_CONTEXT` scan without validated primary file read.

### 3. Validation and fail semantics

- `cta_action` must be `lead` (only supported widget action today).
- `cta_key` must resolve via `load_lead_cta_variants(client_id)` (existing lead config).
- Missing / invalid primary ref, missing frontmatter, unknown `cta_key`, or non-`lead` action → **suppress CTA**, log **warning**, **do not** block answer text.
- Existing explicit service/price CTA (`selected_cta_key` already set upstream) **wins**; primary MD CTA must not replace it.

### 4. UI channel invariants (KEEP)

CTA remains separate payload field (`payload.cta`). Does not occupy choice / secondary / price-detail slots. Presentation caps unchanged.

### 5. Parity and ingress

- Starter prompt «Я боюсь боли» (`widget_config.json` / `ui.yaml`) and manually typed same question → identical CTA behavior.
- `/ask` and `/ask/stream` share `widget_payload_from_runtime_result` → parity when projection sits on verified pipeline output.

### 6. Implementation constraints (KEEP)

- No regex routing, no new selector, no new routes, no service hardcodes.
- **No Verifier policy / prompt change** — projection after `verify_target_composed_response`.
- No global `allow_cta=True` for generic mode.
- Terminal, error, medical handoff, verifier-blocked paths: `cta=None` (unchanged).

## Master seam table (@ `ce256c5`)

| # | Seam | Producer | Consumer | Gap |
|---|---|---|---|---|
| A | `selected_cta_key` upstream | `target_spec_offline_response_package.assemble_target_spec_bound_package` — service `plan.cta_key` when `effective_include_cta`; broad_family_price `marketing_selection.cta_key` | Composer request → unverified response passthrough | **Connected** for service/price |
| B | Generic `allow_cta` | `build_generic_fullcontext_content_policy_request` L183; `_materialize_fullcontext_content_policy_request` L305 | `TargetResponseSpec.allow_cta=False` | **By design** — must not flip globally |
| C | Generic package CTA guard | `assemble_target_fullcontext_content_bound_package` L108–109 rejects `selected_cta_key` | bound package always `None` | **By design** until post-Verifier projection |
| D | Composer CTA validation | `target_composer_executor._validate_request` L306–310 — rejects `selected_cta_key` when `!allow_cta` | blocks upstream CTA on generic | **Correct gate** — projection must be **after** Composer |
| E | Composer output passthrough | `execute_target_composer` L433 `selected_cta_key=validated_request.selected_cta_key` | unverified response | **Connected** |
| F | `primary_content_ref` validation | `target_response_verifier._resolve_validated_source_identity` + `verify_target_composed_response` L774–791 | `TargetVerifiedComposedResponse.primary_content_ref` | **Connected** @ dialogue convergence |
| G | MD frontmatter read | `target_presentation_source_identity.read_doc_presentation_meta` | `target_presentation_decision._cap_secondary_content` (video, situation) | **Partial** — no CTA |
| H | Lead CTA validation | `client_config_loader.lead_cta_dict_from_meta` + `load_lead_cta_variants` | legacy + `build_target_runtime_widget_cta` | **Connected** — reuse for projection |
| I | Widget CTA build | `target_runtime_widget.build_target_runtime_widget_cta` | `materialize_verified_widget_payload` L211–217 | **Connected** — consumes `verified.selected_cta_key` only |
| J | Verified pipeline terminus | `target_verified_response_pipeline.run_target_offline_verified_response_pipeline` | `TargetTurnFrameBoundMaterializeResponse.verified` | **Gap** — no primary CTA projection |
| K | Runtime widget parity | `orchestration/target_fullcontext_turn` + `app.py` `/ask` + `/ask/stream` | same `widget_payload_from_runtime_result` | **Connected** once J fixed |
| L | Starter prompt ingress | `clients/demo/widget_config.json`, `clients/demo/ui.yaml` | same `q` string as free text | **Connected** — no separate CTA path |

## Seam detail — `selected_cta_key` selection today

```text
dispatch_target_turn_frame_response
  → policy_request (generic: allow_cta=False)
  → assemble_target_spec_bound_package / assemble_target_fullcontext_content_bound_package
      → selected_cta_key = None (generic)
      → selected_cta_key = plan.cta_key (exact service, include_cta)
      → selected_cta_key = marketing_selection.cta_key (broad_family_price)
  → materialize_target_composer_request(selected_cta_key=...)
  → execute_target_composer (passthrough)
  → verify_target_composed_response (passthrough selected_cta_key, validate primary_content_ref)
  → materialize_verified_widget_payload → build_target_runtime_widget_cta
```

**Gap:** step after Verifier — no read of `cta_key` / `cta_action` from `validated primary_content_ref`.

## Seam detail — `primary_content_ref` validation

1. Composer JSON sidecar: `source_identity.primary_content_ref` + `used_content_refs`.
2. `parse_composer_backend_output` → `TargetUnverifiedComposedResponse.source_identity`.
3. Verifier `_resolve_validated_source_identity`:
   - normalizes via `validate_used_content_refs`;
   - drops invented refs;
   - ensures primary ∈ used when present;
   - for generic FAQ does **not** block answer on missing source (presentation fail-closed only).
4. Output on `TargetVerifiedComposedResponse.primary_content_ref`.

Example primary: `clients/demo/md/implantation__faq__pain.md`:

```yaml
cta_key: consult
cta_action: lead
video_key: pain-doctor-explains
situation_allowed: true
```

## Seam detail — MD frontmatter and CTA config

| Function | File | Role |
|---|---|---|
| `read_doc_presentation_meta` | `core/target_presentation_source_identity.py` | strict YAML frontmatter read for validated ref |
| `lead_cta_dict_from_meta` | `core/client_config_loader.py` | `{text, action, key}` from `cta_key`/`cta_action`; validates against `load_lead_cta_variants` |
| `build_target_runtime_widget_cta` | `core/target_runtime_widget.py` | maps `selected_cta_key` → widget CTA dict; fail-closed on unknown key |
| `load_lead_cta_variants` | `core/client_config_loader.py` | client lead variants (`consult`, `plan`, `price`, `doctor`, …) |

**Reuse target:** shared pure helper — do not duplicate variant lookup logic.

## Seam detail — widget payload

`materialize_verified_widget_payload` (`core/target_runtime_widget.py`):

- `cta = build_target_runtime_widget_cta(client_id, selected_cta_key=verified.selected_cta_key)`
- `meta.cta_key` / `meta.cta_action` when key present
- CTA separate from `quick_replies`, `video`, `situation`

Terminal/error/handoff builders hardcode `cta: None` — unchanged.

## Minimal typed projection (implementation design)

**Name (proposed):** `project_verified_primary_content_cta`

**Location (proposed):** new module `core/target_verified_primary_content_cta_projection.py`, invoked from `core/target_verified_response_pipeline.py` immediately after `verify_target_composed_response` (or thin wrapper in `target_policy_bound_verified_response_pipeline.py`).

**Signature (conceptual):**

```python
def project_verified_primary_content_cta(
    verified: TargetVerifiedComposedResponse,
    *,
    client_id: str,
    md_root: Path,
) -> TargetVerifiedComposedResponse:
    ...
```

**Algorithm (fail-closed, warning on suppress):**

1. If `verified.selected_cta_key` already set → return unchanged (service/price priority).
2. If `verified.primary_content_ref` missing/invalid → warning `primary_cta_projection_skipped`; return unchanged.
3. If `verified.spec.response_mode` not materializable (`terminal` paths never reach here) → skip.
4. Read frontmatter via `read_doc_presentation_meta(md_root, primary_content_ref)`.
5. Resolve via `lead_cta_dict_from_meta(client_id, meta)` — requires `cta_action=lead` and known `cta_key`.
6. On success → `replace(verified, selected_cta_key=variant.key)`.
7. On failure → warning with reason; leave `selected_cta_key=None`.

**Explicit non-goals:**

- Do not mutate `verified.spec.allow_cta`.
- Do not read secondary `used_content_refs`.
- Do not infer from `marketing_scenarios`.
- Do not add Composer/Verifier prompts.

## Acceptance matrix (implementation)

| # | Scenario | Expected |
|---|---|---|
| 1 | «Я боюсь боли» free text | answer + `primary_content_ref=implantation__faq__pain.md` + CTA `consult` |
| 2 | Same from starter menu / widget_config | identical CTA to #1 |
| 3 | Generic FAQ with valid primary + valid `cta_key`/`cta_action` | CTA shown |
| 4 | Generic FAQ with valid primary, no CTA frontmatter | no CTA |
| 5 | Valid answer, missing/invalid primary | answer kept; no CTA; warning |
| 6 | Valid answer, invented secondary ref with CTA in another doc | no CTA (primary-only) |
| 7 | Explicit service/price path already set `selected_cta_key` | primary MD CTA does not replace |
| 8 | Terminal / error / medical handoff / verifier block | no CTA |
| 9 | CTA click | existing leadflow with correct variant key |
| 10 | `/ask` vs `/ask/stream` | identical `cta` + `meta.cta_key` |

## Forbidden in governance commit

- Product code changes
- LIVE / LLM / E2E eval runs
- Verifier policy / prompt changes
- Frozen artifact edits (S-series, A9R, W1b, widget e2e turns)
- TSC-C / TSC-D
- Global `allow_cta=True` for generic FullContext

## Forbidden in implementation (until owner GO)

- Regex / new routes / new selectors / service hardcodes
- CTA from `used_content_refs` without primary
- Verifier semantic policy change
- Weakening Numeric / contact / medical gates

## Test commands (governance)

```powershell
python -m pytest tests/test_final_verified_primary_content_cta_projection_governance.py -q
git diff --check
```

## STOP

After PRE-CODE ✅ — **STOP**. Implementation only after separate owner GO.
