# TASK — S36 Target Composer Request Materialization

**Branch / baseline:** `codex/stage-a` / `7b40486 feat: enforce scoped response evidence S35`

**Goal:** materialize one exact S35 closed evidence view into a deterministic, immutable
request for the future LLM Composer. This is the final offline adapter before a model call;
it does not call a model, generate an answer, or enter the product path.

## Owner laws

- S36 calls public S35 exactly once over the supplied exact S34 bound package. It never
  selects, ranks, searches, broadens, repairs, or falls back to other evidence.
- Every Composer evidence block corresponds one-to-one, in order, to an S35 scope record.
- S36 exact-dereferences only already selected identities from the supplied canonical
  bundle/doctor catalog/consultation records/MD root. Same ID with different source data is
  a mismatch, not permission to use it.
- Primary content uses only the selected MD body after frontmatter. Exact `kb:` and doctor
  profile refs use only their selected anchored section, never the whole neighboring MD.
- Offer material contains exact price, billing unit, package/includes and payment stages;
  candidate `fact_refs` and candidate follow-ups are excluded.
- Doctor material contains only doctor ID, name, position, experience years and exact
  selected profile section. No education/photo/schedule/active-state fields are invented.
- Commercial facts and consultation values are copied exactly. Strict facts, prices and
  numeric doctor fields are marked `must_preserve_exact=True`.
- FullContext remains the cached background architecture. S36 supplies per-turn primary
  evidence; it does not rebuild, replace, search, or mutate the full cached corpus.
- Follow-ups and CTA are output sidecars copied from S35. They are not evidence blocks and
  Composer must not invent them in prose.
- `medical_handoff` is preserved exactly but S36 does not claim prose-level safety. The
  future Composer and Verifier must enforce no diagnosis/differential/personal eligibility/
  treatment choice before product wiring.

## Contract

Add `core/target_composer_request.py`:

```python
TargetComposerEvidenceKind = Literal[
    "content",
    "offer",
    "doctor",
    "commercial_fact",
    "external_kb",
    "external_doctor",
    "consultation",
]

@dataclass(frozen=True, slots=True)
class TargetComposerEvidenceBlock:
    kind: TargetComposerEvidenceKind
    ref: str
    topics: tuple[str, ...]
    fact_ids: tuple[str, ...]
    text: str
    must_preserve_exact: bool

@dataclass(frozen=True, slots=True)
class TargetComposerRequest:
    user_message: str
    spec: TargetResponseSpec
    evidence_blocks: tuple[TargetComposerEvidenceBlock, ...]
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None

def materialize_target_composer_request(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    user_message: str,
    md_root: Path,
) -> TargetComposerRequest: ...
```

`user_message` must be exact `str`, nonempty, already trimmed; it is preserved unchanged.
S36 calls `build_target_scoped_response_evidence(bound_package, md_root=md_root)` once and
uses only that returned view for output identities/order.

### Exact materialization

- `content:{ref}` → kind `content`, selected document body after strict frontmatter;
- `offer:{id}` → kind `offer`, deterministic compact UTF-8 JSON text with only
  `offer_id`, `service_id`, `option_id`, `brand_id`, `price`, `package`,
  `payment_stages`; `must_preserve_exact=True`;
- `doctor:{id}` → kind `doctor`, deterministic compact UTF-8 JSON text with only
  `doctor_id`, `name`, `position`, `experience_years`, `profile_text` from exact
  `profile_ref`; `must_preserve_exact=True`;
- `fact:{id}` → kind `commercial_fact`, exact `text_fact`; preserve-exact iff
  `render_mode == "strict"`;
- external `kb:` → kind `external_kb`, only exact anchored section;
- external `doctor:{id}` → kind `external_doctor`, same allowed doctor payload and exact
  profile section as doctor material;
- `consultation:{ref}` → kind `consultation`, exact consultation `value`.

Exact `must_preserve_exact` matrix:

| kind | value |
|---|---:|
| `content` | `False` |
| `offer` | `True` |
| `doctor` | `True` |
| `commercial_fact` | `render_mode == "strict"` |
| `external_kb` | `False` |
| `external_doctor` | `True` |
| `consultation` | `False` |

For JSON doctor/offer blocks, `True` requires the later Composer to preserve structured
scalar facts and numbers exactly; it does not require emitting raw JSON verbatim. For a
strict commercial fact it requires the selected `text_fact` itself unchanged. `False`
allows natural wording but never authorizes a new fact or changed number. Consultation is
`False` deliberately: it is an editable semantic sales nudge, not a memorized phrase.

JSON uses `json.dumps(..., ensure_ascii=False, separators=(",", ":"), sort_keys=False)`
over fields in the listed order. Pydantic source models are dumped in their contract field
order with `mode="json"`; absent optional values remain explicit `null`.

MD source paths must be relative `.md`, safely resolve inside `md_root`, be UTF-8 and have
strict mapping frontmatter. Anchored refs must contain exactly one nonempty anchor and that
explicit H2/H3 anchor must exist outside code fences. Section materialization includes its
heading and body until the next heading of equal or higher level. Empty document body or
anchored section fails closed.

## Consistency and errors

One public `TargetComposerRequestError(ValueError)` has `.code`, `.value`, exact message
`f"{code}: {value!r}"`. Precedence:

1. exact S34 bound-package type → `composer_request_package_invalid`;
2. exact `ResponseSchemaBundle` / exact `TargetDoctorCatalog` / valid exact sequence of
   `ServiceConsultationValue` → `composer_request_sources_invalid`;
3. exact trimmed nonempty user message → `composer_request_message_invalid`;
4. S35 typed errors propagate unchanged;
5. selected IDs/objects must exist exactly once and equal their S34 selected source
   objects; consultation refs/values must match → `composer_request_source_mismatch`;
6. unsafe/unreadable/invalid/empty MD or missing/duplicate anchor →
   `composer_request_material_invalid`;
7. block count/order/ref/topics/fact IDs must equal S35 scope records →
   `composer_request_output_inconsistent`.

S36 does not catch or rename S35 errors. It never returns partial blocks.

Step 5 means these exact comparisons, before any block is returned:

- `bundle.services[service_id] == bound_package.package.materials.service`; the selected
  service exists under the exact key, and its service/option content-ref set owns
  `materials.selected_content_ref`;
- every S35 selected offer ID occurs exactly once in `bundle.offers`, equals the same-ID
  selected S34 `materials.offers` object, and still belongs to the selected service;
- every S35 selected commercial fact key/ID resolves to exactly one `bundle.facts` object
  and equals the same-ID selected S34 `materials.commercial_facts` object;
- every plan doctor and external `doctor:` ID is present once in the catalog, contains the
  selected service ID in `service_ids`, and its exact
  `(doctor_id, name, position, experience_years, profile_ref)` projection equals the
  same-ID S34 `ServiceDoctorContext`;
- when consultation is selected, exactly one supplied record has its content ref and its
  full value equals the S34 selected `materials.consultation_close`; absent selection does
  not expose candidate consultation records.

## Explicit safety boundary

`TargetComposerRequest` is model-ready input, not a composed response. S36 has no provider,
prompt execution, model output, retry, session, cache mutation, UI rendering or verifier.
No claim about answer quality or medical prose is allowed without a separate Composer
executor checkpoint and owner-authorized live evaluation. Product wiring remains forbidden.

## Boundaries / allowlist

No A9/TurnFrame/patient-scope, live/LLM, clients data edits, old RAG/composer imports,
runtime/UI/session/cache mutation, Verifier, authority, or full suite. Do not edit S27–S35
contracts/tests.

- `TASK.md`
- `core/target_composer_request.py`
- `tests/test_target_composer_request.py`
- `tests/test_demo_target_composer_request.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- exact frozen shapes/signature/error codes and precedence;
- S35 called once; exact spec/follow-up/CTA identities preserved;
- one block per S35 record in exact order, with no raw package/candidates in output;
- primary content body excludes frontmatter; external KB/profile refs cannot widen beyond
  their exact anchored sections;
- exact offer JSON includes price/package/payment stages and excludes fact_refs/followups;
- exact doctor JSON includes only approved fields and excludes education/photo/schedule;
- selected commercial fact and consultation value are exact; candidate-only values cannot
  leak;
- same-ID but changed bundle/catalog/consultation source fails closed;
- protected mutations cover changed service content/object, offer/fact payload, doctor
  profile or service linkage, and consultation value;
- all seven evidence kinds have the exact `must_preserve_exact` matrix above;
- missing/bad/escaping MD or anchor fails without fallback/partial output;
- medical_handoff mode/spec is preserved without generated-prose safety claims;
- real demo All-on-4 request covers content, prices with payment stages, doctors, one
  selected commercial fact, consultation, follow-ups and CTA; no client writes;
- import firewall proves no provider/legacy composer/runtime/cache/search and no
  skip/xfail/live.

Run only S36 target/demo plus S35 and S34 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern target composer request S36` only to stage-a.
3. Implement only the allowlist and run minimal tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: materialize target composer request S36`; final clean/synced.

Next checkpoint after S36: minimal Composer executor over this exact request. Any live/LLM
evaluation still requires separate owner permission; Verifier and product wiring remain
later independent gates.
