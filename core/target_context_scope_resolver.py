"""Canonical multi-level Scoped FullContext resolver (PERF-6 Phase 2, shadow-only).

Single producer of ``TargetContextScopeDecision``. Pure, offline, deterministic, zero LLM calls,
zero network. Never mutates its inputs, never touches the real Composer/Verifier invocation --
callers only ever read the returned decision for local/log-only use.

Level order: ``service_exact -> topic -> context_group -> full`` (seam audit §5-6). Any resolver
exception is caught by the public entry point and converted into a safe ``full`` decision -- never
surfaced to the caller as an error (seam audit §5 "full" / TASK.md "Widening algorithm").

``service_exact`` reads its closure directly from the already-materialized
``TargetComposerRequest.evidence_blocks`` -- no new closure-computation logic, since S22-S36
already produce exactly this for the exact-service path. ``topic`` reads MD frontmatter ``topic:``
(the same deterministic source ``core/topic_taxonomy.py`` already uses) plus the services/offers/
facts/doctors whose own content falls in that topic. ``context_group`` is fully generic and
data-driven by an optional ``TargetContextGroupCatalog`` -- on the real demo pack this is always
``None`` (no ``context_groups.json`` exists yet), so ``context_group`` is structurally unreachable
today; it is implemented and tested only against synthetic fixtures (seam audit §12 gap).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_context_scope_decision import (
    ContextScopeLevel,
    TargetContextScopeDecision,
)
from core.target_composer_request import TargetComposerRequest
from core.topic_taxonomy import load_client_topic_taxonomy

CONTEXT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class TargetContextGroup:
    """One authored group record (synthetic/testing only -- no demo file exists yet)."""

    group_id: str
    topics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetContextGroupCatalog:
    """Container for authored context groups (synthetic/testing only in Phase 2)."""

    groups: tuple[TargetContextGroup, ...] = ()

    def group_for_topic(self, topic: str) -> TargetContextGroup | None:
        for group in self.groups:
            if topic in group.topics:
                return group
        return None

    def group_by_id(self, group_id: str) -> TargetContextGroup | None:
        for group in self.groups:
            if group.group_id == group_id:
                return group
        return None


@dataclass(frozen=True, slots=True)
class TargetContextScopeResolution:
    """Decision plus the ordered list of levels attempted (observability only).

    ``widening_steps`` is not part of ``TargetContextScopeDecision`` itself (that contract holds
    only the final outcome) -- it is exposed here because the shadow observability event needs the
    full attempted-levels trail, which only the resolver has visibility into.
    """

    decision: TargetContextScopeDecision
    widening_steps: tuple[ContextScopeLevel, ...]


@dataclass(frozen=True, slots=True)
class _Closure:
    content_refs: tuple[str, ...]
    offer_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    policy_sections: tuple[str, ...]


def _dedup(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return tuple(seen)


def _strip_doc_ref(raw: str) -> str:
    """``content:{file}`` or ``kb:{file}#{anchor}`` -> bare ``{file}``."""

    value = raw
    if value.startswith("content:"):
        value = value.removeprefix("content:")
    elif value.startswith("kb:"):
        value = value.removeprefix("kb:")
    if "#" in value:
        value = value.split("#", 1)[0]
    return value


def _evidence_closure(
    request: TargetComposerRequest,
    doctor_catalog: TargetDoctorCatalog,
) -> _Closure:
    content_refs: list[str] = []
    offer_ids: list[str] = []
    fact_ids: list[str] = []
    doctor_ids: list[str] = []
    policy_sections: list[str] = []
    for block in request.evidence_blocks:
        if block.kind in ("content", "external_kb"):
            content_refs.append(_strip_doc_ref(block.ref))
        elif block.kind == "offer":
            offer_ids.append(block.ref.removeprefix("offer:"))
        elif block.kind == "commercial_fact":
            fact_ids.append(block.ref.removeprefix("fact:"))
        elif block.kind in ("doctor", "external_doctor"):
            doctor_id = block.ref.removeprefix("doctor:")
            doctor_ids.append(doctor_id)
            doctor = doctor_catalog.doctors.get(doctor_id)
            if doctor is not None and doctor.profile_ref:
                content_refs.append(_strip_doc_ref(doctor.profile_ref))
        elif block.kind == "clinic_contact":
            field = block.ref.removeprefix("clinic_contact:")
            policy_sections.append(f"contact_{field}")
        elif block.kind == "consultation":
            content_refs.append(_strip_doc_ref(block.ref.removeprefix("consultation:")))
        # unknown kinds are structurally impossible (TargetComposerEvidenceBlock.kind is a
        # closed Literal, validated at materialization time) -- no else branch needed.
    return _Closure(
        content_refs=_dedup(tuple(content_refs)),
        offer_ids=_dedup(tuple(offer_ids)),
        fact_ids=_dedup(tuple(fact_ids)),
        doctor_ids=_dedup(tuple(doctor_ids)),
        policy_sections=_dedup(tuple(policy_sections)),
    )


def _closure_size(closure: _Closure, md_root: Path) -> int:
    total = 0
    for relpath in closure.content_refs:
        path = md_root / relpath
        try:
            total += len(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return total


def _has_required_components(closure: _Closure, required_components: tuple[str, ...]) -> bool:
    for component in required_components:
        if component == "content" and not closure.content_refs:
            return False
        if component == "price" and not closure.offer_ids:
            return False
        if component == "doctors" and not closure.doctor_ids:
            return False
    return True


def _completeness_ok(request: TargetComposerRequest, closure: _Closure) -> bool:
    spec = request.spec
    if not set(spec.required_fact_ids).issubset(set(closure.fact_ids)):
        return False
    return _has_required_components(closure, spec.required_components)


def _fingerprint(
    *,
    client_id: str,
    corpus_sha256: str,
    level: ContextScopeLevel,
    identity: str | None,
    closure: _Closure,
) -> str:
    included = sorted(
        (*closure.content_refs, *closure.offer_ids, *closure.fact_ids, *closure.doctor_ids, *closure.policy_sections)
    )
    payload = "|".join(
        [
            client_id,
            corpus_sha256,
            str(CONTEXT_SCHEMA_VERSION),
            level,
            identity or "",
            ",".join(included),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _full_decision(
    *,
    reason: str,
    widening_reason: str,
    client_id: str,
    cached_full_context: TargetCachedFullContext,
) -> TargetContextScopeDecision:
    content_refs = tuple(sorted(cached_full_context.document_paths))
    chars = len(cached_full_context.corpus_text)
    fingerprint = hashlib.sha256(
        "|".join(
            [
                client_id,
                cached_full_context.sha256,
                str(CONTEXT_SCHEMA_VERSION),
                "full",
                "",
                "",
            ]
        ).encode("utf-8")
    ).hexdigest()
    return TargetContextScopeDecision(
        level="full",
        reason=reason,
        service_id=None,
        topic=None,
        context_group_id=None,
        included_content_refs=content_refs,
        included_offer_ids=(),
        included_fact_ids=(),
        included_doctor_ids=(),
        included_policy_sections=(),
        estimated_chars=chars,
        estimated_tokens=chars // 4,
        package_fingerprint=fingerprint,
        completeness_status="full_required",
        widening_reason=widening_reason,
    )


def _md_topic(md_root: Path, relpath: str) -> str | None:
    path = md_root / relpath
    try:
        with open(path, encoding="utf-8-sig") as handle:
            post = frontmatter.load(handle)
    except (OSError, ValueError):
        return None
    raw = post.metadata.get("topic")
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    return normalized or None


def _try_service_exact(
    request: TargetComposerRequest,
    *,
    doctor_catalog: TargetDoctorCatalog,
) -> tuple[_Closure, bool] | None:
    spec = request.spec
    if spec.service_id is None:
        return None
    closure = _evidence_closure(request, doctor_catalog)
    complete = _completeness_ok(request, closure)
    return closure, complete


def _try_topic(
    request: TargetComposerRequest,
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    md_root: Path,
    client_id: str,
) -> tuple[str, _Closure, bool] | None:
    spec = request.spec
    if not spec.allowed_topics:
        return None
    taxonomy = load_client_topic_taxonomy(client_id)
    if not set(spec.allowed_topics).issubset(taxonomy):
        return None
    allowed = set(spec.allowed_topics)

    content_refs: list[str] = []
    for path in sorted(md_root.glob("*.md")):
        relpath = path.name
        topic = _md_topic(md_root, relpath)
        if topic in allowed:
            content_refs.append(relpath)
    if not content_refs:
        return None

    matched_service_ids: set[str] = set()
    for service_id, service in bundle.services.items():
        refs = [service.content_ref, *(option.content_ref for option in service.options)]
        for ref in refs:
            if ref and ref in content_refs:
                matched_service_ids.add(service_id)
                break

    offer_ids = tuple(
        offer.offer_id
        for offer in bundle.offers
        if offer.active and offer.service_id in matched_service_ids
    )
    fact_ids: list[str] = []
    for offer in bundle.offers:
        if offer.offer_id in offer_ids:
            fact_ids.extend(offer.fact_refs)
    doctor_ids = tuple(
        doctor_id
        for doctor_id, doctor in doctor_catalog.doctors.items()
        if matched_service_ids.intersection(doctor.service_ids)
        or _strip_doc_ref(doctor.profile_ref) in content_refs
    )
    # No contact-aspect signal is available at this call site (TurnFrame.aspects is not threaded
    # through the pipeline function this resolver is invoked from) -- honestly left empty rather
    # than guessed. See seam audit §12 gap list.
    closure = _Closure(
        content_refs=_dedup(tuple(content_refs)),
        offer_ids=_dedup(offer_ids),
        fact_ids=_dedup(tuple(fact_ids)),
        doctor_ids=_dedup(doctor_ids),
        policy_sections=(),
    )
    complete = _completeness_ok(request, closure)
    combined_topic = "+".join(sorted(allowed))
    return combined_topic, closure, complete


def _try_context_group(
    request: TargetComposerRequest,
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    md_root: Path,
    client_id: str,
    context_groups: TargetContextGroupCatalog | None,
) -> tuple[str, _Closure, bool] | None:
    if context_groups is None or not context_groups.groups:
        return None
    spec = request.spec
    candidate_topics: set[str] = set(spec.allowed_topics)
    matched_group: TargetContextGroup | None = None
    for topic in candidate_topics:
        group = context_groups.group_for_topic(topic)
        if group is not None:
            matched_group = group
            break
    if matched_group is None:
        return None

    content_refs: list[str] = []
    for path in sorted(md_root.glob("*.md")):
        relpath = path.name
        topic = _md_topic(md_root, relpath)
        if topic in matched_group.topics:
            content_refs.append(relpath)
    if not content_refs:
        return None

    matched_service_ids: set[str] = set()
    for service_id, service in bundle.services.items():
        refs = [service.content_ref, *(option.content_ref for option in service.options)]
        for ref in refs:
            if ref and ref in content_refs:
                matched_service_ids.add(service_id)
                break
    offer_ids = tuple(
        offer.offer_id
        for offer in bundle.offers
        if offer.active and offer.service_id in matched_service_ids
    )
    fact_ids: list[str] = []
    for offer in bundle.offers:
        if offer.offer_id in offer_ids:
            fact_ids.extend(offer.fact_refs)
    doctor_ids = tuple(
        doctor_id
        for doctor_id, doctor in doctor_catalog.doctors.items()
        if matched_service_ids.intersection(doctor.service_ids)
        or _strip_doc_ref(doctor.profile_ref) in content_refs
    )
    closure = _Closure(
        content_refs=_dedup(tuple(content_refs)),
        offer_ids=_dedup(offer_ids),
        fact_ids=_dedup(tuple(fact_ids)),
        doctor_ids=_dedup(doctor_ids),
        policy_sections=(),
    )
    complete = _completeness_ok(request, closure)
    return matched_group.group_id, closure, complete


def _resolve(
    request: TargetComposerRequest,
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    cached_full_context: TargetCachedFullContext,
    md_root: Path,
    client_id: str,
    context_groups: TargetContextGroupCatalog | None,
) -> TargetContextScopeResolution:
    spec = request.spec
    widening_steps: list[ContextScopeLevel] = []

    service_result = _try_service_exact(request, doctor_catalog=doctor_catalog)
    if service_result is not None:
        closure, complete = service_result
        widening_steps.append("service_exact")
        if complete:
            chars = _closure_size(closure, md_root)
            decision = TargetContextScopeDecision(
                level="service_exact",
                reason="service_exact_complete",
                service_id=spec.service_id,
                topic=None,
                context_group_id=None,
                included_content_refs=closure.content_refs,
                included_offer_ids=closure.offer_ids,
                included_fact_ids=closure.fact_ids,
                included_doctor_ids=closure.doctor_ids,
                included_policy_sections=closure.policy_sections,
                estimated_chars=chars,
                estimated_tokens=chars // 4,
                package_fingerprint=_fingerprint(
                    client_id=client_id,
                    corpus_sha256=cached_full_context.sha256,
                    level="service_exact",
                    identity=spec.service_id,
                    closure=closure,
                ),
                completeness_status="complete",
                widening_reason=None,
            )
            return TargetContextScopeResolution(decision=decision, widening_steps=tuple(widening_steps))

    topic_result = _try_topic(
        request,
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        md_root=md_root,
        client_id=client_id,
    )
    if topic_result is not None:
        topic_id, closure, complete = topic_result
        widening_steps.append("topic")
        if complete:
            chars = _closure_size(closure, md_root)
            widening_reason = (
                "service_exact_incomplete_widened_to_topic"
                if service_result is not None
                else None
            )
            decision = TargetContextScopeDecision(
                level="topic",
                reason="topic_complete",
                service_id=None,
                topic=topic_id,
                context_group_id=None,
                included_content_refs=closure.content_refs,
                included_offer_ids=closure.offer_ids,
                included_fact_ids=closure.fact_ids,
                included_doctor_ids=closure.doctor_ids,
                included_policy_sections=closure.policy_sections,
                estimated_chars=chars,
                estimated_tokens=chars // 4,
                package_fingerprint=_fingerprint(
                    client_id=client_id,
                    corpus_sha256=cached_full_context.sha256,
                    level="topic",
                    identity=topic_id,
                    closure=closure,
                ),
                completeness_status="complete" if widening_reason is None else "insufficient_widened",
                widening_reason=widening_reason,
            )
            return TargetContextScopeResolution(decision=decision, widening_steps=tuple(widening_steps))

    group_result = _try_context_group(
        request,
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        md_root=md_root,
        client_id=client_id,
        context_groups=context_groups,
    )
    if group_result is not None:
        group_id, closure, complete = group_result
        widening_steps.append("context_group")
        if complete:
            chars = _closure_size(closure, md_root)
            decision = TargetContextScopeDecision(
                level="context_group",
                reason="context_group_complete",
                service_id=None,
                topic=None,
                context_group_id=group_id,
                included_content_refs=closure.content_refs,
                included_offer_ids=closure.offer_ids,
                included_fact_ids=closure.fact_ids,
                included_doctor_ids=closure.doctor_ids,
                included_policy_sections=closure.policy_sections,
                estimated_chars=chars,
                estimated_tokens=chars // 4,
                package_fingerprint=_fingerprint(
                    client_id=client_id,
                    corpus_sha256=cached_full_context.sha256,
                    level="context_group",
                    identity=group_id,
                    closure=closure,
                ),
                completeness_status="insufficient_widened",
                widening_reason="topic_incomplete_widened_to_context_group",
            )
            return TargetContextScopeResolution(decision=decision, widening_steps=tuple(widening_steps))

    if widening_steps:
        widening_reason = f"{widening_steps[-1]}_incomplete_widened_to_full"
    else:
        widening_reason = "no_service_or_topic_signal"
    widening_steps.append("full")
    decision = _full_decision(
        reason="full_safe_fallback",
        widening_reason=widening_reason,
        client_id=client_id,
        cached_full_context=cached_full_context,
    )
    return TargetContextScopeResolution(decision=decision, widening_steps=tuple(widening_steps))


def resolve_target_context_scope(
    request: TargetComposerRequest,
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    cached_full_context: TargetCachedFullContext,
    md_root: Path,
    client_id: str = "demo",
    context_groups: TargetContextGroupCatalog | None = None,
) -> TargetContextScopeResolution:
    """Resolve one Scoped FullContext level decision for the already-materialized request.

    Pure and side-effect-free: reads ``request``/``bundle``/``doctor_catalog``/``md_root``, never
    writes anything, never calls a model. Any unexpected structural failure is caught here and
    converted into a safe ``full`` decision -- callers never see a resolver exception.
    """

    try:
        if type(request) is not TargetComposerRequest:
            raise TypeError("context_scope_request_invalid")
        return _resolve(
            request,
            bundle=bundle,
            doctor_catalog=doctor_catalog,
            cached_full_context=cached_full_context,
            md_root=md_root,
            client_id=client_id,
            context_groups=context_groups,
        )
    except Exception:  # noqa: BLE001 -- fail-closed to full by design, never a user-visible error
        decision = _full_decision(
            reason="full_safe_fallback",
            widening_reason="resolver_exception",
            client_id=client_id,
            cached_full_context=cached_full_context,
        )
        return TargetContextScopeResolution(decision=decision, widening_steps=("full",))
