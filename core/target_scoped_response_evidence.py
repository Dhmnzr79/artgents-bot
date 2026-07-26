"""Closed topic/fact-scoped target evidence view (S35, offline/unwired)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn

import yaml
from pydantic import TypeAdapter, ValidationError
from yaml.nodes import MappingNode

from contracts.target_response_spec import CanonicalToken, TargetResponseSpec
from core.target_scope_aware_price_package import is_scope_aware_price_spec
from core.target_fullcontext_content_package import is_fullcontext_content_only_spec
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_offline_response_package import TargetOfflineResponsePackage
from core.target_response_followup_policy import (
    TargetResponseFollowupPolicyError,
    TargetResponseFollowupSelection,
    select_target_response_followups,
)
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    TargetResponseMaterializationPlanError,
    build_target_response_materialization_plan,
)
from core.target_spec_offline_response_package import (
    TargetSpecBoundOfflineResponsePackage,
)


_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)
_TOPIC_ADAPTER = TypeAdapter(CanonicalToken)


@dataclass(frozen=True, slots=True)
class TargetEvidenceScopeRecord:
    ref: str
    topics: tuple[str, ...]
    fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetScopedResponseEvidence:
    spec: TargetResponseSpec
    service_id: str | None
    primary_content_ref: str | None
    offer_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    commercial_fact_ids: tuple[str, ...]
    external_source_refs: tuple[str, ...]
    consultation_content_ref: str | None
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None
    scope_records: tuple[TargetEvidenceScopeRecord, ...]
    covered_fact_ids: tuple[str, ...]


class TargetScopedResponseEvidenceError(ValueError):
    """Typed fail-closed S35 validation/scope failure."""

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
    error = TargetScopedResponseEvidenceError(code, value)
    if cause is None:
        raise error
    raise error from cause


def _resolved_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _error("scoped_evidence_md_root_invalid", md_root)
    try:
        root = md_root.resolve(strict=True)
        is_dir = root.is_dir()
    except (OSError, RuntimeError) as exc:
        _error("scoped_evidence_md_root_invalid", md_root, exc)
    if not is_dir:
        _error("scoped_evidence_md_root_invalid", md_root)
    return root


def _document_ref(raw_ref: object, *, kb_ref: bool) -> str:
    if type(raw_ref) is not str:
        _error("scoped_evidence_source_invalid", raw_ref)
    value = raw_ref
    if kb_ref:
        if not value.startswith("kb:") or value.count("#") != 1:
            _error("scoped_evidence_source_invalid", raw_ref)
        value, anchor = value.removeprefix("kb:").split("#", 1)
        if not anchor:
            _error("scoped_evidence_source_invalid", raw_ref)
    elif "#" in value:
        _error("scoped_evidence_source_invalid", raw_ref)
    parts = value.split("/")
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or not value.endswith(".md")
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or bool(PureWindowsPath(value).drive)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _error("scoped_evidence_source_invalid", raw_ref)
    return value


def _topic(root: Path, raw_ref: object, *, kb_ref: bool) -> str:
    document_ref = _document_ref(raw_ref, kb_ref=kb_ref)
    candidate = root.joinpath(*document_ref.split("/"))
    try:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            _error("scoped_evidence_source_invalid", raw_ref)
        text = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError, RuntimeError) as exc:
        _error("scoped_evidence_source_invalid", raw_ref, exc)
    match = _FRONTMATTER.match(text)
    if match is None:
        _error("scoped_evidence_source_invalid", raw_ref)
    try:
        frontmatter = yaml.load(match.group("yaml"), Loader=_StrictFrontmatterLoader)
        if not isinstance(frontmatter, dict):
            _error("scoped_evidence_source_invalid", raw_ref)
        return _TOPIC_ADAPTER.validate_python(frontmatter.get("topic"))
    except (yaml.YAMLError, ValidationError) as exc:
        _error("scoped_evidence_source_invalid", raw_ref, exc)


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def build_target_scoped_response_evidence(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    *,
    md_root: Path,
) -> TargetScopedResponseEvidence:
    """Validate S34-selected identities and expose no candidate-material container."""

    if type(bound_package) is not TargetSpecBoundOfflineResponsePackage:
        _error("scoped_evidence_package_invalid", bound_package)
    root = _resolved_root(md_root)

    spec = bound_package.spec
    if spec.response_stage == "data_gap":
        package = bound_package.package
        return TargetScopedResponseEvidence(
            spec=spec,
            service_id=None,
            primary_content_ref=None,
            offer_ids=(),
            doctor_ids=(),
            commercial_fact_ids=(),
            external_source_refs=(),
            consultation_content_ref=None,
            selected_followups=package.selected_followups,
            selected_cta_key=bound_package.selected_cta_key,
            scope_records=(),
            covered_fact_ids=(),
        )
    if is_fullcontext_content_only_spec(spec):
        if bound_package.selected_cta_key is not None:
            _error("scoped_evidence_package_inconsistent", "selected_cta_key")
        package = bound_package.package
        plan = package.plan
        materials = package.materials
        facts_by_id = {fact.id: fact for fact in materials.commercial_facts}
        if any(fact_id not in facts_by_id for fact_id in plan.commercial_fact_ids):
            _error("scoped_evidence_package_inconsistent", "commercial_fact_ids")
        if plan.commercial_fact_ids and not spec.allow_consultation_close:
            _error("scoped_evidence_package_inconsistent", "consultation_content_ref")
        if len(plan.commercial_fact_ids) > 1:
            _error("scoped_evidence_package_inconsistent", "commercial_fact_ids")
        records: list[TargetEvidenceScopeRecord] = []
        for fact_id in plan.commercial_fact_ids:
            fact = facts_by_id[fact_id]
            matched_topics = tuple(
                topic for topic in spec.allowed_topics if topic in fact.allowed_topics
            )
            if not matched_topics:
                _error("scoped_evidence_package_inconsistent", "commercial_fact_topics")
            records.append(
                TargetEvidenceScopeRecord(
                    ref=f"fact:{fact_id}",
                    topics=matched_topics,
                    fact_ids=(fact_id,),
                )
            )
        return TargetScopedResponseEvidence(
            spec=spec,
            service_id=None,
            primary_content_ref=None,
            offer_ids=(),
            doctor_ids=(),
            commercial_fact_ids=plan.commercial_fact_ids,
            external_source_refs=(),
            consultation_content_ref=None,
            selected_followups=package.selected_followups,
            selected_cta_key=None,
            scope_records=tuple(records),
            covered_fact_ids=plan.commercial_fact_ids,
        )

    if is_scope_aware_price_spec(spec):
        package = bound_package.package
        plan = package.plan
        materials = package.materials
        if spec.response_stage == "stage_clarify":
            if (
                type(package) is not TargetOfflineResponsePackage
                or type(plan) is not TargetResponseMaterializationPlan
                or type(materials) is not TargetOfflineResponseMaterials
                or plan.required_components != ("price",)
                or spec.scope_price_topic is None
            ):
                _error("scoped_evidence_package_inconsistent", "scope_aware_price")
            if plan.offer_ids or materials.offers:
                _error("scoped_evidence_package_inconsistent", "stage_clarify_offers")
            return TargetScopedResponseEvidence(
                spec=spec,
                service_id=None,
                primary_content_ref=None,
                offer_ids=(),
                doctor_ids=(),
                commercial_fact_ids=(),
                external_source_refs=(),
                consultation_content_ref=None,
                selected_followups=package.selected_followups,
                selected_cta_key=bound_package.selected_cta_key,
                scope_records=(),
                covered_fact_ids=(),
            )
        if spec.response_stage == "data_gap":
            if (
                type(package) is not TargetOfflineResponsePackage
                or type(plan) is not TargetResponseMaterializationPlan
                or type(materials) is not TargetOfflineResponseMaterials
                or plan.required_components != ("price",)
                or spec.scope_price_topic is None
            ):
                _error("scoped_evidence_package_inconsistent", "scope_aware_price")
            if plan.offer_ids or materials.offers:
                _error("scoped_evidence_package_inconsistent", "data_gap_offers")
            return TargetScopedResponseEvidence(
                spec=spec,
                service_id=None,
                primary_content_ref=None,
                offer_ids=(),
                doctor_ids=(),
                commercial_fact_ids=(),
                external_source_refs=(),
                consultation_content_ref=None,
                selected_followups=package.selected_followups,
                selected_cta_key=None,
                scope_records=(),
                covered_fact_ids=(),
            )
        if (
            type(package) is not TargetOfflineResponsePackage
            or type(plan) is not TargetResponseMaterializationPlan
            or type(materials) is not TargetOfflineResponseMaterials
            or plan.required_components != ("price",)
            or plan.unfulfilled_components
            or spec.scope_price_topic is None
        ):
            _error("scoped_evidence_package_inconsistent", "scope_aware_price")
        if bound_package.selected_cta_key is not None and spec.response_stage != "broad_family_price":
            _error("scoped_evidence_package_inconsistent", "selected_cta_key")
        if plan.service_id is not None and spec.service_id not in (None, plan.service_id):
            _error("scoped_evidence_package_inconsistent", "service_id")
        offers_by_id = {offer.offer_id: offer for offer in materials.offers}
        if any(offer_id not in offers_by_id for offer_id in plan.offer_ids):
            _error("scoped_evidence_package_inconsistent", "offer_ids")
        overview_topic = spec.scope_price_topic
        records = [
            TargetEvidenceScopeRecord(
                ref=f"offer:{offer_id}",
                topics=(overview_topic,),
                fact_ids=(),
            )
            for offer_id in plan.offer_ids
        ]
        return TargetScopedResponseEvidence(
            spec=spec,
            service_id=plan.service_id,
            primary_content_ref=None,
            offer_ids=plan.offer_ids,
            doctor_ids=(),
            commercial_fact_ids=(),
            external_source_refs=(),
            consultation_content_ref=None,
            selected_followups=package.selected_followups,
            selected_cta_key=bound_package.selected_cta_key,
            scope_records=tuple(records),
            covered_fact_ids=(),
        )

    package = bound_package.package
    if (
        type(spec) is not TargetResponseSpec
        or type(package) is not TargetOfflineResponsePackage
        or type(package.plan) is not TargetResponseMaterializationPlan
        or type(package.materials) is not TargetOfflineResponseMaterials
        or type(package.selected_followups) is not TargetResponseFollowupSelection
    ):
        _error("scoped_evidence_package_inconsistent", "nested_types")
    plan = package.plan
    materials = package.materials
    if (
        spec.service_id is None
        or plan.service_id != spec.service_id
        or materials.service_id != spec.service_id
        or plan.required_components != spec.required_components
    ):
        _error("scoped_evidence_package_inconsistent", "service_or_components")

    try:
        canonical_plan = build_target_response_materialization_plan(
            materials,
            required_components=spec.required_components,
        )
    except TargetResponseMaterializationPlanError as exc:
        _error("scoped_evidence_package_inconsistent", "plan", exc)
    if plan != canonical_plan:
        _error("scoped_evidence_package_inconsistent", "plan")
    try:
        canonical_followups = select_target_response_followups(
            package.followup_candidates,
            source=spec.followup_source,
        )
    except TargetResponseFollowupPolicyError as exc:
        _error("scoped_evidence_package_inconsistent", "selected_followups", exc)
    if package.selected_followups != canonical_followups:
        _error("scoped_evidence_package_inconsistent", "selected_followups")

    offers_by_id = {offer.offer_id: offer for offer in materials.offers}
    doctors_by_id = {doctor.doctor_id: doctor for doctor in materials.doctors}
    facts_by_id = {fact.id: fact for fact in materials.commercial_facts}
    if any(offer_id not in offers_by_id for offer_id in plan.offer_ids):
        _error("scoped_evidence_package_inconsistent", "offer_ids")
    if any(doctor_id not in doctors_by_id for doctor_id in plan.doctor_ids):
        _error("scoped_evidence_package_inconsistent", "doctor_ids")
    if any(fact_id not in facts_by_id for fact_id in plan.commercial_fact_ids):
        _error("scoped_evidence_package_inconsistent", "commercial_fact_ids")
    if plan.external_source_refs != materials.external_source_refs:
        _error("scoped_evidence_package_inconsistent", "external_source_refs")
    if plan.consultation_content_ref is not None and (
        materials.consultation_close is None
        or materials.consultation_close.content_ref != plan.consultation_content_ref
    ):
        _error("scoped_evidence_package_inconsistent", "consultation_content_ref")
    if (
        bound_package.selected_cta_key is not None
        and (
            type(bound_package.selected_cta_key) is not str
            or bound_package.selected_cta_key != plan.cta_key
            or not spec.allow_cta
        )
    ):
        _error("scoped_evidence_package_inconsistent", "selected_cta_key")
    if (plan.commercial_fact_ids or plan.external_source_refs) and (
        not spec.allow_marketing_facts
    ):
        _error("scoped_evidence_package_inconsistent", "marketing_facts")
    if plan.consultation_content_ref is not None and not spec.allow_consultation_close:
        _error("scoped_evidence_package_inconsistent", "consultation_content_ref")
    if plan.unfulfilled_components:
        _error("scoped_evidence_component_unfulfilled", plan.unfulfilled_components)

    service_content_ref = materials.selected_content_ref
    if service_content_ref is None:
        _error("scoped_evidence_source_invalid", service_content_ref)
    service_topic = _topic(root, service_content_ref, kb_ref=False)

    records: list[TargetEvidenceScopeRecord] = []
    if plan.primary_content_ref is not None:
        content_topic = _topic(root, plan.primary_content_ref, kb_ref=False)
        records.append(
            TargetEvidenceScopeRecord(
                ref=f"content:{plan.primary_content_ref}",
                topics=(content_topic,),
                fact_ids=(),
            )
        )
    records.extend(
        TargetEvidenceScopeRecord(
            ref=f"offer:{offer_id}", topics=(service_topic,), fact_ids=()
        )
        for offer_id in plan.offer_ids
    )
    for doctor_id in plan.doctor_ids:
        doctor_topic = _topic(
            root,
            doctors_by_id[doctor_id].profile_ref,
            kb_ref=True,
        )
        records.append(
            TargetEvidenceScopeRecord(
                ref=f"doctor:{doctor_id}",
                topics=_ordered_unique((service_topic, doctor_topic)),
                fact_ids=(),
            )
        )
    records.extend(
        TargetEvidenceScopeRecord(
            ref=f"fact:{fact_id}",
            topics=(service_topic,),
            fact_ids=(fact_id,),
        )
        for fact_id in plan.commercial_fact_ids
    )
    for source_ref in plan.external_source_refs:
        if source_ref.startswith("kb:"):
            source_topics = (_topic(root, source_ref, kb_ref=True),)
        elif source_ref.startswith("doctor:"):
            doctor_id = source_ref.removeprefix("doctor:")
            doctor = doctors_by_id.get(doctor_id)
            if doctor is None:
                _error("scoped_evidence_package_inconsistent", source_ref)
            doctor_topic = _topic(root, doctor.profile_ref, kb_ref=True)
            source_topics = _ordered_unique((service_topic, doctor_topic))
        else:
            _error("scoped_evidence_source_invalid", source_ref)
        records.append(
            TargetEvidenceScopeRecord(
                ref=source_ref,
                topics=source_topics,
                fact_ids=(),
            )
        )
    if plan.consultation_content_ref is not None:
        consultation_topic = _topic(
            root,
            plan.consultation_content_ref,
            kb_ref=False,
        )
        records.append(
            TargetEvidenceScopeRecord(
                ref=f"consultation:{plan.consultation_content_ref}",
                topics=(consultation_topic,),
                fact_ids=(),
            )
        )

    refs = tuple(record.ref for record in records)
    if len(refs) != len(set(refs)):
        duplicate = next(ref for index, ref in enumerate(refs) if ref in refs[:index])
        _error("scoped_evidence_package_inconsistent", duplicate)

    forbidden = set(spec.forbidden_topics)
    allowed = set(spec.allowed_topics)
    for record in records:
        forbidden_hits = tuple(topic for topic in record.topics if topic in forbidden)
        if forbidden_hits:
            _error("scoped_evidence_topic_forbidden", (record.ref, forbidden_hits))
        if not allowed.intersection(record.topics):
            _error(
                "scoped_evidence_topic_not_allowed",
                (record.ref, record.topics),
            )

    covered_fact_ids = _ordered_unique(
        tuple(fact_id for record in records for fact_id in record.fact_ids)
    )
    missing_fact_ids = tuple(
        fact_id
        for fact_id in spec.required_fact_ids
        if fact_id not in covered_fact_ids
    )
    if missing_fact_ids:
        _error("scoped_evidence_required_fact_missing", missing_fact_ids)

    return TargetScopedResponseEvidence(
        spec=spec,
        service_id=plan.service_id,
        primary_content_ref=plan.primary_content_ref,
        offer_ids=plan.offer_ids,
        doctor_ids=plan.doctor_ids,
        commercial_fact_ids=plan.commercial_fact_ids,
        external_source_refs=plan.external_source_refs,
        consultation_content_ref=plan.consultation_content_ref,
        selected_followups=package.selected_followups,
        selected_cta_key=bound_package.selected_cta_key,
        scope_records=tuple(records),
        covered_fact_ids=covered_fact_ids,
    )
