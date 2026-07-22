# TASK — S30 Minimal Follow-up Source Policy

**Branch / baseline:** `codex/stage-a` / `6d81fac feat: materialize selected-source followups S29`

**Goal:** offline/unwired policy that exposes exactly one already-materialized S29
follow-up family (`content`, `price`) or none. It does not decide the answer focus.

## Owner laws

- The future ResponseSpec/caller explicitly supplies `content`, `price` or `None`.
- `content` returns all S29 content candidates in exact authored order.
- `price` returns all S29 price candidates in exact authored order.
- Empty requested family returns no source and no candidates.
- Never merge, rank, truncate, deduplicate or fall back to the other family.

## Contract

Add `core/target_response_followup_policy.py`:

```python
TargetFollowupSource = Literal["content", "price"]

@dataclass(frozen=True, slots=True)
class TargetResponseFollowupSelection:
    source: TargetFollowupSource | None
    content: tuple[TargetContentFollowup, ...]
    price: tuple[TargetPriceFollowup, ...]

class TargetResponseFollowupPolicyError(ValueError):
    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")

def select_target_response_followups(
    followups: TargetResponseFollowups,
    *,
    source: TargetFollowupSource | None,
) -> TargetResponseFollowupSelection: ...
```

Validation order:

Both failures raise `TargetResponseFollowupPolicyError` with the governed `.code`,
`.value` and exact message `f"{code}: {value!r}"`:

1. `followups` must be exact `TargetResponseFollowups`; its fields must be exact tuples
   containing only exact S29 item types. Otherwise
   `followup_policy_candidates_invalid`, value = original `followups`.
2. `source` must be exact string `content`/`price` or `None`. Otherwise
   `followup_policy_source_invalid`, value = original `source`.

Selection is a shallow immutable projection: preserve exact item identities and order.
If the requested tuple is empty, return `(source=None, content=(), price=())`.

## Boundaries

No TurnFrame/A9/raw text inference, ResponseSpec implementation, MD/JSON/client reads,
widget rendering, button limits, session shown/clicked state, Composer, Verifier, runtime,
product authority or live/LLM. Do not edit S29 or `clients/**`.

Allowlist:

- `TASK.md`
- `core/target_response_followup_policy.py`
- `tests/test_target_response_followup_policy.py`
- `tests/test_demo_target_response_followup_policy.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal tests

- exact signatures, frozen/slots schema, public error class/inheritance, `.code`, `.value`,
  exact message and source containing exactly the two governed codes;
- invalid outer/inner candidate state and validation precedence;
- content, price and `None` select only the requested family;
- empty requested family has no fallback;
- exact order and item identity are preserved; inputs are unchanged;
- real demo All-on-4 content and price candidates follow the same rules;
- import firewall and no client writes/product imports/live.

Run only S30 target/demo plus S29 target/demo neighbors. No full suite, A9 or live/LLM.

## Gates

1. Independent governance checker `✅` before code.
2. Commit/push `docs: govern followup source policy S30` only to `codex/stage-a`.
3. Implement allowlist and run target + two S29 neighbors.
4. Independent completion checker `✅`, roadmap `[x]`.
5. Commit/push `feat: select followup source S30`; final clean/synced.

Next checkpoint: end-to-end offline response assembly over proven components; do not add
another policy layer unless that vertical integration exposes a concrete missing contract.
