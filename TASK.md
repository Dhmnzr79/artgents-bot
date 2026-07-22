# TASK — S29 Selected-source Follow-up Materialization

**Branch / baseline:** `codex/stage-a` / `5612dba feat: project target response materialization plans S28`

**Goal:** materialize candidate follow-ups only from the S28-selected MD document and
S27-selected offers. Offline/unwired; no UI merge, session filtering, Composer or authority.

## Owner laws

- ordinary content answer may expose authored `suggest_h3` from its selected document;
- price answer may expose authored followups from its selected offers;
- content and price navigation stay separate and preserve source order;
- no fallback to another document/offer/service;
- this checkpoint creates structured candidates, not widget buttons or natural text.

## Exact API

Create `core/target_response_followup_materializer.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetContentFollowup:
    id: str
    label: str
    ref: str
    source_content_ref: str


@dataclass(frozen=True, slots=True)
class TargetPriceFollowup:
    id: str
    label: str
    ref: str
    action: str
    source_offer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetResponseFollowups:
    content: tuple[TargetContentFollowup, ...]
    price: tuple[TargetPriceFollowup, ...]


def materialize_target_response_followups(
    plan: TargetResponseMaterializationPlan,
    materials: TargetOfflineResponseMaterials,
    *,
    md_root: Path,
) -> TargetResponseFollowups:
    ...
```

## Fixed validation order and laws

Stable `TargetResponseFollowupMaterializationError(code, value)` stores `code`, `value`,
message `f"{code}: {value!r}"`. Validation order is fixed:

1. `plan` exact type, then `materials` exact type.
2. `md_root`: `isinstance(value, Path)`, `resolve(strict=True)`, existing directory.
3. Rebuild canonical expected S28 plan with `materials` + `plan.required_components`.
   If S28 rejects forged component state, raise `followup_plan_invalid(plan)`. Compare the
   **whole** dataclass, including required/unfulfilled and all identities. Difference is
   `followup_plan_materials_mismatch((plan, expected))`; no partial materialization.
4. Content branch, then price branch. An earlier error always wins.

Content branch runs only when `content` is required and fulfilled:

- ref must be a canonical relative POSIX `.md` path: no `#`, backslash, absolute path,
  empty/`.`/`..` part. Candidate uses `resolve(strict=True)` and must be a file whose
  resolved path is `is_relative_to(resolved_root)`; symlink escape is invalid;
- missing/unreadable/non-UTF-8 candidate is read-failed; only this selected file is read;
- require opening/closing `---` frontmatter delimiters and a mapping. Strict SafeLoader
  rejects duplicate and YAML merge keys;
- optional `suggest_h3`: missing/empty means no content candidates; otherwise exact list
  of unique nonblank strings, no normalization;
- scan body only, outside fenced code. Recognize exact line grammar
  `### <nonblank label> {#<id>}` with ID `[A-Za-z0-9_-]+`; headings without an explicit
  ID are not candidates. Duplicate explicit H3 ID fails before suggestion lookup;
- every suggested ID must exist in that same body. Preserve `suggest_h3` order; label is
  exact heading text, ref is `<primary_content_ref>#<id>`.

Price branch runs only when `price` is required and fulfilled. Full plan equality already
proves every ID in `plan.offer_ids` exists in selected S27 offers. Traverse plan offer order, then
authored followup order. Duplicate ID becomes one first-position record and accumulates
`source_offer_ids` in offer order; label/action must match or conflict. Ref is exact
`price:<service_id>/<id>`. No generic/other-brand lookup.

Unrequested/unfulfilled branch returns its empty tuple without source read/fallback.
Content and price remain separate; no ranking, mutation, shown-state or click handling.

| Code | Condition | Exact `value` |
|---|---|---|
| `followup_plan_invalid` | wrong type or S28 rejects forged component state | original `plan` |
| `followup_materials_invalid` | wrong type | original `materials` |
| `followup_md_root_invalid` | wrong type/unresolvable/not directory | original `md_root` |
| `followup_plan_materials_mismatch` | whole plan differs from rebuilt expected | `(plan, expected)` |
| `followup_content_ref_invalid` | ref grammar, containment or symlink escape | ref |
| `followup_content_read_failed` | missing/not-file/read/UTF-8 failure | ref |
| `followup_frontmatter_invalid` | delimiters/YAML/mapping/duplicate/merge invalid | ref |
| `followup_suggestions_invalid` | invalid container/item; duplicate uses copied tuple | offending value |
| `followup_anchor_duplicate` | duplicate explicit body H3 ID | ID |
| `followup_suggestion_not_found` | suggested ID absent from explicit body H3s | ID |
| `followup_price_conflict` | same ID has different payload | `(id, first_label, first_action, conflicting_label, conflicting_action)` |

## Explicit boundaries

S29 does not change `clients/**`, existing contracts/core, S27/S28 decisions, MD files or
prices. It does not create widget quick replies, choose one UI source, suppress an active
or already-clicked followup, mark session state, read raw text/TurnFrame/A9, or call
ResponsePolicy/ResponseSpec/Composer/Verifier/runtime. No live/LLM.

The future UI policy must choose/limit one source family per turn and apply shown/clicked
state. S29 only proves source-safe candidate materialization.

## Allowlist

- `TASK.md`;
- `core/target_response_followup_materializer.py` (new);
- `tests/test_target_response_followup_materializer.py` (new);
- `tests/test_demo_target_response_followup_materializer.py` (new);
- `docs/ARCH_TARGET_DESIGN.md`;
- `docs/STRANGLER_ROADMAP.md`.

Everything else is protected, including `clients/**`, `contracts/**`, old
`answer_packet*`, `md_chunks.py`, UI/runtime/session/A9/live artifacts.

## Acceptance

Synthetic target proves:

- exact frozen shapes/signature/errors/import firewall;
- input and canonical whole-plan rebuild/match, including forged component state;
- content: selected file only, exact order/labels/refs, empty/malformed/traversal/missing/
  duplicate/unknown-anchor fail-closed cases;
- price: selected offers only, exact order, stable duplicate aggregation/conflict,
  exact action/ref/provenance;
- component gates perform no unnecessary MD read and never fallback/merge;
- repeated calls stateless/read-only; no skip/xfail/hacks.

Real demo proves:

- All-on-4 content gives exact three authored `suggest_h3` refs/labels;
- caries content has no suggestions;
- All-on-4 price gives `stages`, then `includes`, each sourced by all three selected offers;
- Nobel price gives the same two IDs sourced only by Nobel;
- caries price has none; caries+Nobel unfulfilled price has none;
- content-only does not expose price and price-only does not read content suggestions;
- demo files unchanged; no product imports/writes/live.

Minimal neighbors: S28 target/demo and S27 target/demo only. No full suite, legacy UI,
A9 or live/LLM.

## Gates / commits

1. Governance checker `✅` before code.
2. Commit/push `docs: govern selected-source followups S29` only stage-a.
3. Implement allowlist; target + four neighbors.
4. Completion checker `✅`; roadmap `[x]`.
5. Commit/push `feat: materialize selected-source followups S29`; final clean/synced.

Next checkpoint: minimal UI-source policy over proven separate candidate tuples, not a
new selector and not product authority.
