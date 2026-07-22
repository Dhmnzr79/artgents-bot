# TASK — S28 Minimal Target Response Materialization Plan

**Ветка:** `codex/stage-a`

**Baseline:** `4da1b4d feat: assemble vertical offline response materials S27`

**Серия / checkpoint:** `S28` — минимальный downstream materialization plan над уже
проверенным S27 material boundary. Он фиксирует, какие factual components передаются
следующему слою, но не пишет ответ и не подключается к product path.

**Режим:** governance + один new pure unwired module + synthetic/real-data unit tests +
target architecture status. Никаких client-data changes, MD parsing, UI materialization,
Composer/runtime/routes/authority, A9 или live/LLM.

## Owner direction

После S27 владелец подтвердил следующий шаг и отдельно уточнил ожидаемое будущее
поведение: обычный информационный вопрос должен получать ответ по MD и тематические
follow-up при их наличии; маркетинговые, price и doctor additions не должны превращать
каждый ответ в перегруженную сборку.

S28 поэтому не создаёт ещё один selector. Он принимает уже готовые S27 materials и
явный upstream список требуемых компонентов. Результат — компактный downstream plan для
будущего materializer. Existing old `AnswerPacket` не переиспользуется и не
ремонтируется: это legacy product contract с IO/config/runtime ownership.

Канонический upstream `ResponseSpec` из `docs/ARCH_TARGET_DESIGN.md` остаётся отдельным
будущим ResponsePolicy boundary **до** evidence assembly. Только он будет владеть tone,
allowed/forbidden topics, required facts, handoff и allowed deterministic cards. S28 не
использует это имя и не инвертирует target chain.

## Exact public API

Создать `core/target_response_materialization_plan.py`:

```python
from typing import Literal, TypeAlias

TargetResponseComponent: TypeAlias = Literal["content", "price", "doctors"]


@dataclass(frozen=True, slots=True)
class TargetResponseMaterializationPlan:
    service_id: str
    selected_brand_id: str | None
    required_components: tuple[TargetResponseComponent, ...]
    unfulfilled_components: tuple[TargetResponseComponent, ...]
    primary_content_ref: str | None
    offer_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    commercial_fact_ids: tuple[str, ...]
    external_source_refs: tuple[str, ...]
    consultation_content_ref: str | None
    cta_key: str


def build_target_response_materialization_plan(
    materials: TargetOfflineResponseMaterials,
    *,
    required_components: Sequence[str],
) -> TargetResponseMaterializationPlan:
    ...
```

## Exact laws

### 1. Input validation

- `materials` обязан быть exact `TargetOfflineResponseMaterials`; иначе
  `TargetResponseMaterializationPlanError(
  "materialization_plan_materials_invalid", materials)`;
- `required_components` обязан быть `Sequence`, но не `str/bytes`;
- каждый item обязан быть exact одним из `content`, `price`, `doctors`;
- empty sequence запрещён;
- duplicates запрещены, порядок caller сохраняется;
- stable errors:
  - `materialization_plan_components_invalid` с offending container/item;
  - `materialization_plan_components_empty` с empty tuple;
  - `materialization_plan_component_duplicate` с copied tuple;
- error наследует `ValueError`, хранит `code`, `value`; exact message
  `f"{code}: {value!r}"`.

S28 не revalidates/repairs nested S27 models и не нормализует component strings.

### 2. Component projection

Для каждого required component в caller order:

- `content` fulfilled только если `materials.selected_content_ref is not None`;
  тогда `primary_content_ref` — exact ref, иначе `None` и `content` добавляется в
  `unfulfilled_components`;
- `price` fulfilled только если `materials.offers` non-empty;
  тогда `offer_ids` — exact projected S27 order, иначе empty и `price` unfulfilled;
- `doctors` fulfilled только если `materials.doctors` non-empty;
  тогда `doctor_ids` — exact authored S27 order, иначе empty и `doctors` unfulfilled;
- не запрошенный component всегда даёт empty/`None` output и не считается unfulfilled.

`unfulfilled_components` сохраняет порядок `required_components`. Это fail-closed signal
для будущего policy/materializer boundary. Сам materializer обязан surface/fail closed,
не брать похожую цену, другой документ или врача другой услуги и не решать, нужно ли
уточнение/defer. Такое решение принадлежит будущему upstream ResponsePolicy.

### 3. Automatic additions already selected by S21/S22

S28 не принимает отдельные marketing toggles и не повторяет policy:

- `commercial_fact_ids` — exact S27 fact order;
- `external_source_refs` — exact S27 ref order;
- `consultation_content_ref` — exact `consultation_close.content_ref` или `None`;
- `cta_key` — exact `materials.marketing_selection.cta_key`.

Эти fields — уже выбранные content identities, которые downstream не имеет права
reselect/replace. Будущими остаются только exact payload materialization и форма
отображения/UI. S28 не читает и не формулирует текст, не отмечает cadence state.

### 4. Identity-only contract

Plan содержит только identity/order/inclusion decisions. Он намеренно не копирует:

- деньги, package, payment stages и price followups из offers;
- doctor position/experience/profile text;
- commercial fact text, consultation value и MD body.

Следующий materializer получает plan вместе с S27 materials и может брать exact payload
только по перечисленным IDs/refs. Это не второй источник правды и не потеря данных.

## Follow-up boundary

S28 не строит UI follow-ups:

- price followups уже сохранены внутри S27 projected offers;
- ordinary content navigation в demo сейчас authored как MD `suggest_h3`;
- S28 сохраняет exact `primary_content_ref`, но не читает MD/frontmatter;
- следующий отдельный materialization checkpoint должен разрешить suggestions только из
  выбранного документа, сохранить authored order и не смешивать их с price followups;
- до этого нельзя заявлять, что новый path уже воспроизводит follow-up UI.

Итоговое target-поведение остаётся: обычный content answer + тематические follow-up при
наличии; price/doctor/marketing добавляются только когда разрешены соответствующими
upstream policy и material plan fields.

## Deliberate S28 limits

S28 не:

- читает raw patient message, TurnFrame или session;
- выбирает service/brand/offer/doctor/marketing заново;
- исправляет опечатки и не применяет A9 patient scope;
- читает MD, `suggest_h3`, price followups или profile body;
- создаёт text blocks, prompt, natural-language answer, cards/buttons;
- задаёт upstream ResponseSpec, tone, allowed/forbidden topics, required-fact policy,
  handoff или deterministic-card policy;
- вызывает old `AnswerPacket`, materializer, Composer, Verifier, FullContext;
- подключается к planner/routes/API/app/UI/config;
- меняет contracts S1–S27, clients, runtime, authority или A9 artifacts;
- запускает live/LLM.

Канонический ResponsePolicy/ResponseSpec (medical handoff, contacts, booking, lead,
allowed/forbidden topics, tone, required facts/cards) остаётся будущим отдельным
**upstream** boundary checkpoint до evidence assembly. Не раздувать S28 фиктивными
режимами, которых текущая S27 vertical slice не может доказать.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_response_materialization_plan.py` — new pure offline projection;
- `tests/test_target_response_materialization_plan.py` — new synthetic contract;
- `tests/test_demo_target_response_materialization_plan.py` — new real demo acceptance;
- `docs/ARCH_TARGET_DESIGN.md` — честная S28 boundary/status note;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion checker `✅`.

Любой другой файл — стоп и отдельное owner/architect decision.

## Protected / вне scope

- весь `clients/**`, `contracts/**` и existing core S1–S27;
- old `contracts/answer_packet.py`, `core/answer_packet*.py`, Composer/runtime;
- MD/frontmatter loaders and content/price followup resolution;
- TurnFrame/A9, medical/contact/booking/lead boundaries;
- Response materializer, prompt, natural language, Verifier, UI/session;
- golden/live/eval fixtures;
- A9 design/raw/frozen/harness/evidence/re-audit;
- live/LLM, merge, `main`, other branches, product authority.

## Acceptance tests

### Synthetic contract

`tests/test_target_response_materialization_plan.py` proves:

1. exact API/field order, frozen/slots shell and identity-only payload;
2. invalid materials/container/item/empty/duplicate errors exact;
3. component order preserved without normalization;
4. content-only ordinary answer references only selected MD and no price/doctor IDs;
5. price-only references only projected offer IDs in S27 order;
6. doctors-only references exact linked doctor IDs in authored order;
7. composite order preserved and all requested identities present;
8. missing content/price/doctors marked unfulfilled without fallback;
9. known brand with no service offer gives unfulfilled price, never generic offer;
10. unrequested missing component is not reported unfulfilled;
11. marketing fact/source/consultation/CTA identities pass exact without reselection;
12. money/stages/followups/text/profile are absent from plan shape;
13. repeated calls stateless and no S27 input mutation;
14. imports only stdlib + S27 facade; no IO/client/contracts expansion/runtime;
15. source has only four governed error codes, no broad exception translation.

### Real demo acceptance

`tests/test_demo_target_response_materialization_plan.py` proves read-only:

1. real S27 All-on-4 materials load through existing frozen tools;
2. content-only plan points to exact All-on-4 MD and contains no price/doctor IDs;
3. price+doctors plan contains exact S27 projected offer order and linked doctor order;
4. Nobel price plan contains only `all_on_4.jaw.nobel`;
5. caries content plan points to exact MD; price contains only `caries.default`;
6. caries+Nobel price is unfulfilled with no generic fallback;
7. cost/doctor-trust/consultation identities and CTA pass exact from S27;
8. client files unchanged; no product imports/writes/skip/xfail/live/LLM.

### Minimal neighbors

- `tests/test_target_offline_response_assembly.py`;
- `tests/test_demo_target_offline_response_assembly.py`;
- `tests/test_target_response_evidence.py`;
- `tests/test_demo_target_response_evidence.py`;
- `tests/test_target_offer_projection.py`;
- `tests/test_target_brand_offer_projection.py`.

Не запускать old AnswerPacket/Composer/runtime suites, full suite, A9 или live/LLM.

## Checker and git gates

1. Governance TASK + roadmap pending; independent checker `✅` before code.
2. Commit `docs: govern target response materialization plan S28`; push only stage-a.
3. Implement only allowlist; target then minimal neighbors.
4. Independent completion checker `✅`; then roadmap `[x]`.
5. Commit `feat: project target response materialization plans S28`; push stage-a.
6. Final clean/synced.

## Definition of Done

- S28 declaratively projects requested components from S27 without re-selection;
- missing required material is explicit and fail-closed;
- ordinary content-only plan stays clean; marketing identity remains policy-selected;
- follow-up data remains in its owners and its materialization is not falsely claimed;
- both checker gates `✅`, target/neighbors green, no skip/xfail;
- no clients/contracts/runtime/authority/A9/live changes;
- two commits pushed only stage-a, clean/synced;
- next checkpoint evaluates minimal identity-safe materialization (including selected-doc
  content suggestions and selected-offer price followups), not another selector;
- canonical upstream ResponsePolicy/ResponseSpec remains before evidence assembly and is
  not duplicated or silently redefined by S28.
