"""Deterministic target Composer request materialization (S36, offline/unwired)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, NoReturn, TypeAlias

import yaml
from yaml.nodes import MappingNode

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact, TargetOffer
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_response_spec import TargetResponseSpec
from contracts.price_only_source_sufficiency import (
    PriceOnlySourceContext,
    is_price_only_offer_source_sufficient,
    offer_identity_rows,
)
from contracts.target_composer_action_context import TargetComposerActionContext
from contracts.target_response_length_profile import TargetResponseLengthProfile
from core.service_data_context import ServiceDoctorContext
from core.target_composer_action_context import resolve_target_composer_action_context
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_policy import select_target_response_length_profile
from core.target_generic_fullcontext_content import is_generic_fullcontext_content_spec
from core.target_scope_aware_price_package import is_scope_aware_price_spec
from core.target_fullcontext_content_package import is_fullcontext_service_optional_spec
from core.target_contact_authority import materialize_clinic_contact_primary_evidence
from core.target_scoped_response_evidence import (
    TargetEvidenceScopeRecord,
    TargetScopedResponseEvidence,
    build_target_scoped_response_evidence,
)
from core.target_spec_offline_response_package import (
    TargetSpecBoundOfflineResponsePackage,
)


TargetComposerEvidenceKind: TypeAlias = Literal[
    "content",
    "offer",
    "doctor",
    "commercial_fact",
    "external_kb",
    "external_doctor",
    "consultation",
    "clinic_contact",
]

_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)
_EXPLICIT_HEADING = re.compile(
    r"^(?P<marks>#{2,3})[ \t]+(?P<label>.+?)[ \t]+"
    r"\{#(?P<anchor>[^}\r\n]+)\}[ \t]*$"
)
_HEADING = re.compile(r"^(?P<marks>#{1,6})[ \t]+.+$")
_FENCE = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")


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
    action_context: TargetComposerActionContext | None = None
    response_length_profile: TargetResponseLengthProfile | None = None


class TargetComposerRequestError(ValueError):
    """Typed fail-closed S36 source/materialization failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class _StrictFrontmatterLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        key: list(resolvers)
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, MappingNode):
            raise yaml.constructor.ConstructorError(
                None, None, f"expected a mapping node, but found {node.id}", node.start_mark
            )
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            if key_node.value == "<<" or key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.YAMLError("yaml_merge_key_forbidden")
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.YAMLError(f"duplicate_mapping_key:{key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _error(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetComposerRequestError(code, value)
    if cause is None:
        raise error
    raise error from cause


def _validated_consultations(
    values: Sequence[ServiceConsultationValue],
) -> tuple[ServiceConsultationValue, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        _error("composer_request_sources_invalid", values)
    copied = tuple(values)
    for value in copied:
        if type(value) is not ServiceConsultationValue:
            _error("composer_request_sources_invalid", value)
    refs = tuple(value.content_ref for value in copied)
    if len(refs) != len(set(refs)):
        _error("composer_request_sources_invalid", refs)
    return copied


def _root(md_root: Path) -> Path:
    try:
        return md_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _error("composer_request_material_invalid", md_root, exc)


def _document_and_anchor(raw_ref: object, *, anchored: bool) -> tuple[str, str | None]:
    if type(raw_ref) is not str:
        _error("composer_request_material_invalid", raw_ref)
    value = raw_ref
    anchor: str | None = None
    if anchored:
        if not value.startswith("kb:") or value.count("#") != 1:
            _error("composer_request_material_invalid", raw_ref)
        document, anchor = value.removeprefix("kb:").split("#", 1)
        if not anchor:
            _error("composer_request_material_invalid", raw_ref)
    else:
        document = value
        if "#" in document:
            _error("composer_request_material_invalid", raw_ref)
    parts = document.split("/")
    if (
        not document
        or "\\" in document
        or document.startswith("/")
        or not document.endswith(".md")
        or PurePosixPath(document).is_absolute()
        or PureWindowsPath(document).is_absolute()
        or bool(PureWindowsPath(document).drive)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _error("composer_request_material_invalid", raw_ref)
    return document, anchor


def _read_body(root: Path, raw_ref: object, *, anchored: bool) -> tuple[str, str | None]:
    document, anchor = _document_and_anchor(raw_ref, anchored=anchored)
    candidate = root.joinpath(*document.split("/"))
    try:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            _error("composer_request_material_invalid", raw_ref)
        text = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError, RuntimeError) as exc:
        _error("composer_request_material_invalid", raw_ref, exc)
    match = _FRONTMATTER.match(text)
    if match is None:
        _error("composer_request_material_invalid", raw_ref)
    try:
        frontmatter = yaml.load(match.group("yaml"), Loader=_StrictFrontmatterLoader)
    except yaml.YAMLError as exc:
        _error("composer_request_material_invalid", raw_ref, exc)
    if not isinstance(frontmatter, dict):
        _error("composer_request_material_invalid", raw_ref)
    body = text[match.end() :].strip()
    if not body:
        _error("composer_request_material_invalid", raw_ref)
    return body, anchor


def _section(body: str, anchor: str, raw_ref: str) -> str:
    lines = body.splitlines()
    matches: list[tuple[int, int]] = []
    fence_character: str | None = None
    fence_length = 0
    for index, line in enumerate(lines):
        if fence_character is not None:
            if re.fullmatch(
                rf"[ \t]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                line,
            ):
                fence_character = None
                fence_length = 0
            continue
        fence = _FENCE.match(line)
        if fence is not None:
            marker = fence.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        heading = _EXPLICIT_HEADING.fullmatch(line)
        if heading is not None and heading.group("anchor") == anchor:
            matches.append((index, len(heading.group("marks"))))
    if len(matches) != 1:
        _error("composer_request_material_invalid", raw_ref)
    start, level = matches[0]
    end = len(lines)
    fence_character = None
    fence_length = 0
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if fence_character is not None:
            if re.fullmatch(
                rf"[ \t]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                line,
            ):
                fence_character = None
                fence_length = 0
            continue
        fence = _FENCE.match(line)
        if fence is not None:
            marker = fence.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        heading = _HEADING.fullmatch(line)
        if heading is not None and len(heading.group("marks")) <= level:
            end = index
            break
    if not any(line.strip() for line in lines[start + 1 : end]):
        _error("composer_request_material_invalid", raw_ref)
    return "\n".join(lines[start:end]).strip()


def _document_body(root: Path, raw_ref: str) -> str:
    body, _anchor = _read_body(root, raw_ref, anchored=False)
    return body


def _anchored_section(root: Path, raw_ref: str) -> str:
    body, anchor = _read_body(root, raw_ref, anchored=True)
    return _section(body, anchor, raw_ref)  # type: ignore[arg-type]


def _compact_json(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    )


def _offer_text(offer: TargetOffer) -> str:
    return _compact_json(
        {
            "offer_id": offer.offer_id,
            "service_id": offer.service_id,
            "option_id": offer.option_id,
            "brand_id": offer.brand_id,
            "price": offer.price.model_dump(mode="json"),
            "package": offer.package.model_dump(mode="json"),
            "payment_stages": (
                None
                if offer.payment_stages is None
                else [stage.model_dump(mode="json") for stage in offer.payment_stages]
            ),
        }
    )


def _doctor_text(
    doctor_id: str,
    doctor: object,
    *,
    profile_text: str,
) -> str:
    return _compact_json(
        {
            "doctor_id": doctor_id,
            "name": doctor.name,  # type: ignore[attr-defined]
            "position": doctor.position,  # type: ignore[attr-defined]
            "experience_years": doctor.experience_years,  # type: ignore[attr-defined]
            "profile_text": profile_text,
        }
    )


def _source_mismatch(value: object) -> NoReturn:
    _error("composer_request_source_mismatch", value)


def _exact_sources(
    scoped: TargetScopedResponseEvidence,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultations: tuple[ServiceConsultationValue, ...],
) -> tuple[
    dict[str, TargetOffer],
    dict[str, object],
    dict[str, TargetCommercialFact],
    dict[str, ServiceConsultationValue],
]:
    materials = bound_package.package.materials
    service = bundle.services.get(scoped.service_id)
    if service is None or service != materials.service:
        _source_mismatch(("service", scoped.service_id))
    owned_content_refs = {
        ref
        for ref in (
            service.content_ref,
            *(option.content_ref for option in service.options),
        )
        if ref is not None
    }
    if materials.selected_content_ref not in owned_content_refs:
        plan = bound_package.package.plan
        offer_rows = offer_identity_rows(tuple(materials.offers), scoped.offer_ids)
        price_only_ctx = PriceOnlySourceContext(
            service_id=scoped.service_id,
            required_components=plan.required_components,
            requested_components=scoped.spec.required_components,
            offer_ids=plan.offer_ids,
            offer_service_ids=tuple(row[0] for row in offer_rows),
            offer_active_flags=tuple(row[1] for row in offer_rows),
            selected_content_ref=materials.selected_content_ref,
            primary_content_ref=plan.primary_content_ref,
            unfulfilled_components=plan.unfulfilled_components,
            response_stage=scoped.spec.response_stage,
            is_generic_fullcontext=is_generic_fullcontext_content_spec(scoped.spec),
            is_scope_aware_price=is_scope_aware_price_spec(scoped.spec),
            is_structured_service_availability=False,
        )
        if not is_price_only_offer_source_sufficient(price_only_ctx):
            _source_mismatch(("content", materials.selected_content_ref))

    source_offers: dict[str, TargetOffer] = {}
    material_offers = {offer.offer_id: offer for offer in materials.offers}
    for offer_id in scoped.offer_ids:
        matches = [offer for offer in bundle.offers if offer.offer_id == offer_id]
        if (
            len(matches) != 1
            or offer_id not in material_offers
            or matches[0] != material_offers[offer_id]
            or matches[0].service_id != scoped.service_id
        ):
            _source_mismatch(("offer", offer_id))
        source_offers[offer_id] = matches[0]

    doctor_ids = tuple(
        dict.fromkeys(
            (*scoped.doctor_ids, *(ref.removeprefix("doctor:") for ref in scoped.external_source_refs if ref.startswith("doctor:")))
        )
    )
    material_doctors = {doctor.doctor_id: doctor for doctor in materials.doctors}
    source_doctors: dict[str, object] = {}
    for doctor_id in doctor_ids:
        doctor = doctor_catalog.doctors.get(doctor_id)
        projection = (
            None
            if doctor is None
            else ServiceDoctorContext(
                doctor_id=doctor_id,
                name=doctor.name,
                position=doctor.position,
                experience_years=doctor.experience_years,
                profile_ref=doctor.profile_ref,
            )
        )
        if (
            doctor is None
            or scoped.service_id not in doctor.service_ids
            or material_doctors.get(doctor_id) != projection
        ):
            _source_mismatch(("doctor", doctor_id))
        source_doctors[doctor_id] = doctor

    source_facts: dict[str, TargetCommercialFact] = {}
    material_facts = {fact.id: fact for fact in materials.commercial_facts}
    for fact_id in scoped.commercial_fact_ids:
        fact = bundle.facts.get(fact_id)
        if (
            fact is None
            or fact.id != fact_id
            or material_facts.get(fact_id) != fact
        ):
            _source_mismatch(("fact", fact_id))
        source_facts[fact_id] = fact

    consultation_by_ref = {record.content_ref: record for record in consultations}
    if scoped.consultation_content_ref is not None:
        selected = consultation_by_ref.get(scoped.consultation_content_ref)
        if selected is None or selected != materials.consultation_close:
            _source_mismatch(("consultation", scoped.consultation_content_ref))
    return source_offers, source_doctors, source_facts, consultation_by_ref


def _scope_price_overview_sources(
    scoped: TargetScopedResponseEvidence,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
) -> dict[str, TargetOffer]:
    materials = bound_package.package.materials
    source_offers: dict[str, TargetOffer] = {}
    material_offers = {offer.offer_id: offer for offer in materials.offers}
    bundle_offers = {offer.offer_id: offer for offer in bundle.offers}
    for offer_id in scoped.offer_ids:
        material = material_offers.get(offer_id)
        bundle_offer = bundle_offers.get(offer_id)
        if (
            material is None
            or bundle_offer is None
            or bundle_offer.service_id not in materials.family_service_ids
        ):
            _source_mismatch(("offer", offer_id))
        source_offers[offer_id] = material
    return source_offers


def _family_overview_sources(
    scoped: TargetScopedResponseEvidence,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
) -> dict[str, TargetOffer]:
    materials = bound_package.package.materials
    source_offers: dict[str, TargetOffer] = {}
    material_offers = {offer.offer_id: offer for offer in materials.offers}
    for offer_id in scoped.offer_ids:
        matches = [offer for offer in bundle.offers if offer.offer_id == offer_id]
        if (
            len(matches) != 1
            or offer_id not in material_offers
            or matches[0] != material_offers[offer_id]
            or matches[0].service_id not in materials.family_service_ids
        ):
            _source_mismatch(("offer", offer_id))
        source_offers[offer_id] = matches[0]
    return source_offers


def _block(
    record: TargetEvidenceScopeRecord,
    *,
    root: Path,
    component_doctor_ids: frozenset[str],
    offers: dict[str, TargetOffer],
    doctors: dict[str, object],
    facts: dict[str, TargetCommercialFact],
    consultations: dict[str, ServiceConsultationValue],
) -> TargetComposerEvidenceBlock:
    if record.ref.startswith("content:"):
        kind: TargetComposerEvidenceKind = "content"
        text = _document_body(root, record.ref.removeprefix("content:"))
        preserve = False
    elif record.ref.startswith("offer:"):
        kind = "offer"
        offer_id = record.ref.removeprefix("offer:")
        offer = offers.get(offer_id)
        if offer is None:
            _source_mismatch(("offer", offer_id))
        text = _offer_text(offer)
        preserve = True
    elif record.ref.startswith("doctor:"):
        doctor_id = record.ref.removeprefix("doctor:")
        kind = "doctor" if doctor_id in component_doctor_ids else "external_doctor"
        doctor = doctors.get(doctor_id)
        if doctor is None:
            _source_mismatch(("doctor", doctor_id))
        text = _doctor_text(
            doctor_id,
            doctor,
            profile_text=_anchored_section(root, doctor.profile_ref),  # type: ignore[attr-defined]
        )
        preserve = True
    elif record.ref.startswith("fact:"):
        kind = "commercial_fact"
        fact_id = record.ref.removeprefix("fact:")
        fact = facts.get(fact_id)
        if fact is None:
            _source_mismatch(("fact", fact_id))
        text = fact.text_fact
        preserve = fact.render_mode == "strict"
    elif record.ref.startswith("kb:"):
        kind = "external_kb"
        text = _anchored_section(root, record.ref)
        preserve = False
    elif record.ref.startswith("consultation:"):
        kind = "consultation"
        content_ref = record.ref.removeprefix("consultation:")
        consultation = consultations.get(content_ref)
        if consultation is None:
            _source_mismatch(("consultation", content_ref))
        text = consultation.value
        preserve = False
    else:
        _error("composer_request_output_inconsistent", record.ref)
    if not text:
        _error("composer_request_material_invalid", record.ref)
    return TargetComposerEvidenceBlock(
        kind=kind,
        ref=record.ref,
        topics=record.topics,
        fact_ids=record.fact_ids,
        text=text,
        must_preserve_exact=preserve,
    )


def _attach_composer_action_context(request: TargetComposerRequest) -> TargetComposerRequest:
    if request.action_context is not None:
        return request
    action_context = resolve_target_composer_action_context(
        response_stage=request.spec.response_stage,
    )
    if action_context is None:
        return request
    return replace(request, action_context=action_context)


def _attach_response_length_profile(
    request: TargetComposerRequest,
    *,
    marketing_scenarios: tuple[str, ...],
) -> TargetComposerRequest:
    """PERF-5: single canonical producer call, explicit typed field -- no ContextVar/global.

    ``marketing_scenarios`` comes from ``bound_package.package.materials.marketing_selection.
    applied_scenarios`` (already resolved, already gated/capped upstream) -- a real, live signal
    available at this exact call site with no new parameter threaded through any caller.
    ``aspects``/``needs_clarification`` are not available here without threading a TurnFrame
    through several additional pipeline modules (out of PERF-5 Phase 2's scope); comparison_or_
    complex therefore does not yet fire on this live call site -- see the PERF-5 completion
    record for the exact data-flow limitation.
    """
    if request.response_length_profile is not None:
        return request
    profile = select_target_response_length_profile(
        request.spec,
        marketing_scenarios=marketing_scenarios,
    )
    return replace(request, response_length_profile=profile)


def _prepend_contact_evidence(
    blocks: tuple[TargetComposerEvidenceBlock, ...],
    *,
    client_id: str,
    contact_fields: tuple[str, ...] | None = None,
) -> tuple[TargetComposerEvidenceBlock, ...]:
    if contact_fields is None:
        return blocks
    contact_blocks = materialize_clinic_contact_primary_evidence(
        client_id,
        fields=contact_fields,  # type: ignore[arg-type]
    )
    if not contact_blocks:
        return blocks
    return contact_blocks + blocks


def materialize_target_composer_request(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    user_message: str,
    md_root: Path,
    contact_fields: tuple[str, ...] | None = None,
    client_id: str = "demo",
) -> TargetComposerRequest:
    """Create model-ready primary evidence without executing a Composer model."""

    if type(bound_package) is not TargetSpecBoundOfflineResponsePackage:
        _error("composer_request_package_invalid", bound_package)
    if type(bundle) is not ResponseSchemaBundle or type(doctor_catalog) is not TargetDoctorCatalog:
        _error("composer_request_sources_invalid", (bundle, doctor_catalog))
    consultations = _validated_consultations(consultation_values)
    if type(user_message) is not str or not user_message or user_message != user_message.strip():
        _error("composer_request_message_invalid", user_message)

    scoped = build_target_scoped_response_evidence(bound_package, md_root=md_root)
    marketing_scenarios = bound_package.package.materials.marketing_selection.applied_scenarios
    if is_fullcontext_service_optional_spec(scoped.spec):
        if not scoped.scope_records:
            blocks: tuple[TargetComposerEvidenceBlock, ...] = ()
            blocks = _prepend_contact_evidence(
                blocks,
                client_id=client_id,
                contact_fields=contact_fields,
            )
            return _attach_response_length_profile(
                _attach_composer_action_context(
                    TargetComposerRequest(
                    user_message=user_message,
                    spec=scoped.spec,
                    evidence_blocks=blocks,
                    selected_followups=scoped.selected_followups,
                    selected_cta_key=scoped.selected_cta_key,
                    )
                ),
                marketing_scenarios=marketing_scenarios,
            )
        facts_by_id = {
            fact.id: fact for fact in bound_package.package.materials.commercial_facts
        }
        root = _root(md_root)
        blocks = tuple(
            _block(
                record,
                root=root,
                component_doctor_ids=frozenset(),
                offers={},
                doctors={},
                facts=facts_by_id,
                consultations={},
            )
            for record in scoped.scope_records
        )
        projected = tuple((block.ref, block.topics, block.fact_ids) for block in blocks)
        expected = tuple(
            (record.ref, record.topics, record.fact_ids) for record in scoped.scope_records
        )
        if projected != expected:
            _error("composer_request_output_inconsistent", (projected, expected))
        blocks = _prepend_contact_evidence(
            blocks,
            client_id=client_id,
            contact_fields=contact_fields,
        )
        return _attach_response_length_profile(
            _attach_composer_action_context(
                TargetComposerRequest(
                user_message=user_message,
                spec=scoped.spec,
                evidence_blocks=blocks,
                selected_followups=scoped.selected_followups,
                selected_cta_key=scoped.selected_cta_key,
                )
            ),
            marketing_scenarios=marketing_scenarios,
        )
    if scoped.spec.response_stage in {"stage_clarify", "data_gap"}:
        return _attach_response_length_profile(
            _attach_composer_action_context(
                TargetComposerRequest(
                user_message=user_message,
                spec=scoped.spec,
                evidence_blocks=(),
                selected_followups=scoped.selected_followups,
                selected_cta_key=scoped.selected_cta_key,
                )
            ),
            marketing_scenarios=marketing_scenarios,
        )
    if is_scope_aware_price_spec(scoped.spec):
        offers = _scope_price_overview_sources(scoped, bound_package, bundle)
        root = _root(md_root)
        blocks = tuple(
            _block(
                record,
                root=root,
                component_doctor_ids=frozenset(),
                offers=offers,
                doctors={},
                facts={},
                consultations={},
            )
            for record in scoped.scope_records
        )
        projected = tuple((block.ref, block.topics, block.fact_ids) for block in blocks)
        expected = tuple(
            (record.ref, record.topics, record.fact_ids) for record in scoped.scope_records
        )
        if projected != expected:
            _error("composer_request_output_inconsistent", (projected, expected))
        return _attach_response_length_profile(
            _attach_composer_action_context(
                TargetComposerRequest(
                user_message=user_message,
                spec=scoped.spec,
                evidence_blocks=blocks,
                selected_followups=scoped.selected_followups,
                selected_cta_key=scoped.selected_cta_key,
                )
            ),
            marketing_scenarios=marketing_scenarios,
        )
    offers, doctors, facts, consultations_by_ref = _exact_sources(
        scoped,
        bound_package,
        bundle,
        doctor_catalog,
        consultations,
    )
    root = _root(md_root)
    blocks = tuple(
        _block(
            record,
            root=root,
            component_doctor_ids=frozenset(scoped.doctor_ids),
            offers=offers,
            doctors=doctors,
            facts=facts,
            consultations=consultations_by_ref,
        )
        for record in scoped.scope_records
    )
    projected = tuple((block.ref, block.topics, block.fact_ids) for block in blocks)
    expected = tuple(
        (record.ref, record.topics, record.fact_ids) for record in scoped.scope_records
    )
    if projected != expected:
        _error("composer_request_output_inconsistent", (projected, expected))
    blocks = _prepend_contact_evidence(
        blocks,
        client_id=client_id,
        contact_fields=contact_fields,
    )
    return _attach_response_length_profile(
        _attach_composer_action_context(
            TargetComposerRequest(
            user_message=user_message,
            spec=scoped.spec,
            evidence_blocks=blocks,
            selected_followups=scoped.selected_followups,
            selected_cta_key=scoped.selected_cta_key,
            )
        ),
        marketing_scenarios=marketing_scenarios,
    )
