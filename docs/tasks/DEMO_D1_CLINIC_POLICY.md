# DEMO D1 — clinic business policies

## Baseline

- Audited `origin/main`: `70696ca80d9a1c9f3a15a3472cccb800215a06bf`
- Worktree: `C:/Cursor Projects/artgents-bot-demo-d1-clinic-policy`
- Branch: `codex/demo-d1-clinic-policy`

## Scope

Wire authored `clients/*/clinic_policies.yaml` business policies into the active sales-fast / one-call path: prompt authority block, turn-local applicability heuristics (not legacy substring-only ingress), and post-model enforcement so forbidden pediatric / OMS / DMS promises cannot reach JSON or SSE UI.

## Design

- **Load**: `core/clinic_policies_loader.py` (unchanged YAML); `serialize_clinic_business_policies_block` in stable prefix and dynamic suffix.
- **Applicability**: `core/one_call_clinic_policy_authority.py` — intent heuristics per policy key; exclusions for adult self-ID, childhood history, negation; OMS/DMS via payment-scheme questions.
- **Enforcement**: `apply_clinic_business_policy_authority` in `build_one_call_presentation_result` replaces conflicting or applicable-turn prose with authored answers; mixed turns append deterministic contact lines; pediatric policy suppresses lead CTA.
- **No** second model call; **no** duplicate policy YAML; **no** full ingress restore.

## Limits (for D5)

Heuristic applicability is not full semantic understanding; edge phrasing may still need live rehearsal.

## Tests (record results in PR / Checker)

```text
python -m pytest -p no:cacheprovider --tb=short -q \
  tests/test_demo_clinic_policy_authority_offline.py \
  tests/test_clinic_policies_loader.py \
  tests/test_demo_implant_volume_scope_offline.py \
  tests/test_one_call_stage4_3_contacts_specific.py \
  tests/test_one_call_tenant_isolation_offline.py \
  tests/test_one_call_provider_call_budget_stage1.py
```

Evidence (checkpoint run, local env `CHAT_API_KEY=offline-pytest-dummy`):

```text
python -m pytest -p no:cacheprovider --tb=line -q \
  tests/test_demo_clinic_policy_authority_offline.py \
  tests/test_clinic_policies_loader.py \
  tests/test_demo_implant_volume_scope_offline.py \
  tests/test_one_call_stage4_3_contacts_specific.py \
  tests/test_one_call_tenant_isolation_offline.py \
  tests/test_one_call_provider_call_budget_stage1.py
```

Result: **49 passed, 8 failed** (all 8 in `test_one_call_provider_call_budget_stage1.py` — `AlibabaEndpointConfigurationError: chat_base_url_missing` or `chat_base_url_host_blocked` without full Alibaba transport config; same class of baseline/local env gap, not introduced by D1 policy changes). D1 suite `test_demo_clinic_policy_authority_offline.py`: **18 passed**.

Provider calls during tests: **0** (conftest transport block + fake backends).

## Foreign WIP

- `C:/Cursor Projects/artgents-bot-demo-volume-clarify` on `codex/demo-volume-clarify-tests` — not modified.
