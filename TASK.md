# TASK — S31 Integrated Offline Response Package

**Branch / baseline:** `codex/stage-a` / `0d1ebc7 feat: select followup source S30`

**Goal:** one offline/unwired facade over the proven S27→S28→S29→S30 segment. This is
not the final bot path and does not implement canonical ResponseSpec, text or UI.

## Owner laws

- Call the four public stages once and in order: materials, plan, candidates, selection.
- Future ResponseSpec inputs remain explicit: `required_components` and `followup_source`.
- Return every stage result with exact object identity; do not rebuild or reinterpret it.
- Propagate every existing typed error unchanged; add no error class/code/fallback.
- Do not infer focus, merge links, select other services/offers or widen evidence.

## Contract

Add `core/target_offline_response_package.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetOfflineResponsePackage:
    materials: TargetOfflineResponseMaterials
    plan: TargetResponseMaterializationPlan
    followup_candidates: TargetResponseFollowups
    selected_followups: TargetResponseFollowupSelection

def assemble_target_offline_response_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_term: str,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    required_components: Sequence[str],
    followup_source: TargetFollowupSource | None,
    md_root: Path,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetOfflineResponsePackage: ...
```

Exact stage flow:

1. Call S27 with its inputs unchanged.
2. Call S28 with the exact S27 object and `required_components` unchanged.
3. Call S29 with exact S28/S27 objects and `md_root` unchanged.
4. Call S30 with exact S29 object and `source=followup_source` unchanged.
5. Return those exact four objects in the frozen package.

Stage order defines error precedence. Do not catch/wrap existing exceptions or prevalidate
later-stage inputs locally. Sequence defaults and supplied sequences are forwarded, not
mutated. S27 remains the owner of its own copying/validation.

## Boundaries

This integrates only the current offline segment. No TurnFrame/A9/raw inference, canonical
ResponsePolicy/ResponseSpec, answer text, MD body evidence rendering, widget/session,
Composer, Verifier, runtime/product authority or live/LLM. Do not edit S27–S30 or clients.

Allowlist:

- `TASK.md`
- `core/target_offline_response_package.py`
- `tests/test_target_offline_response_package.py`
- `tests/test_demo_target_offline_response_package.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal tests

- exact frozen/slots shape, signature/defaults and import firewall;
- four public stages called once/in exact order with identity-preserving handoff;
- all stage outputs preserved by identity; inputs not mutated;
- S27, S28, S29 and S30 typed errors propagate as the same exception object;
- real demo All-on-4 produces coherent service/material/plan/content-followup package;
- real price focus selects only price links; `None` selects none;
- real unfulfilled price remains empty without fallback; demo files unchanged;
- no test suppression, clients/product imports/writes/live.

Run S31 target/demo plus S27–S30 target/demo neighbors only. No full suite, A9 or live.

## Gates

1. Independent governance checker `✅` before code.
2. Commit/push `docs: govern integrated offline package S31` only to `codex/stage-a`.
3. Implement allowlist and run target + eight neighbor files.
4. Independent completion checker `✅`, roadmap `[x]`.
5. Commit/push `feat: assemble offline response package S31`; final clean/synced.

After S31, use the integrated boundary to specify the smallest real upstream ResponseSpec
contract; do not add another downstream policy brick without a demonstrated gap.
