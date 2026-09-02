"""Shown service options snapshot validation and model-visible projection."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_plan import SessionKey
from contracts.response_plan_composer import ServiceDescriptor
from contracts.response_plan_dialogue_context import (
    ModelVisibleShownOptions,
    ShownOptionsFreshnessPolicy,
    ShownOptionsSnapshotError,
    ShownServiceOptionsSnapshot,
    require_non_negative_int,
)
from contracts.response_plan_post_composer import PostComposerDiagnostic, PostComposerOwnershipError
from contracts.response_schema import ResponseSchemaBundle


@dataclass(frozen=True, slots=True)
class ValidatedShownOptionsSnapshot:
    snapshot: ShownServiceOptionsSnapshot
    age_turns: int
    eligible_service_ids: tuple[str, ...]


def build_eligible_shown_service_ids(
    snapshot: ShownServiceOptionsSnapshot,
    *,
    active_service_ids: frozenset[str],
    known_client_service_ids: frozenset[str],
    known_inactive_service_ids: frozenset[str],
) -> tuple[str, ...]:
    eligible: list[str] = []
    for service_id in snapshot.service_ids:
        if service_id not in known_client_service_ids:
            raise ShownOptionsSnapshotError("shown_service_id_not_in_client_catalog")
        if service_id in known_inactive_service_ids:
            continue
        if service_id not in active_service_ids:
            raise ShownOptionsSnapshotError("shown_service_id_not_in_authority_catalog")
        eligible.append(service_id)
    return tuple(eligible)


def validate_shown_options_snapshot(
    snapshot: ShownServiceOptionsSnapshot | None,
    *,
    session_key: SessionKey,
    source_client_id: str,
    current_turn_index: int,
    policy: ShownOptionsFreshnessPolicy,
    bundle: ResponseSchemaBundle,
) -> tuple[ValidatedShownOptionsSnapshot | None, tuple[PostComposerDiagnostic, ...]]:
    if snapshot is None:
        return None, ()
    require_non_negative_int("current_turn_index", current_turn_index)
    if snapshot.session_key != session_key:
        raise PostComposerOwnershipError("shown_options_session_key_mismatch")
    if snapshot.session_key.client_id != source_client_id:
        raise PostComposerOwnershipError("shown_options_client_mismatch")
    if snapshot.shown_at_turn > current_turn_index:
        raise ShownOptionsSnapshotError("shown_options_future_turn")
    age = current_turn_index - snapshot.shown_at_turn
    if age > policy.max_age_turns:
        return None, (
            PostComposerDiagnostic(code="shown_options_snapshot_stale", detail=age),
        )
    known_client_service_ids = frozenset(bundle.services.keys())
    known_inactive_service_ids = frozenset(
        service_id for service_id, service in bundle.services.items() if not service.active
    )
    active_service_ids = frozenset(
        service_id for service_id, service in bundle.services.items() if service.active
    )
    diagnostics: list[PostComposerDiagnostic] = []
    eligible: list[str] = []
    for service_id in snapshot.service_ids:
        if service_id not in known_client_service_ids:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="shown_options_snapshot_unavailable",
                    detail=service_id,
                )
            )
            continue
        if service_id in known_inactive_service_ids:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="shown_options_snapshot_unavailable",
                    detail=service_id,
                )
            )
            continue
        if service_id not in active_service_ids:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="shown_options_snapshot_unavailable",
                    detail=service_id,
                )
            )
            continue
        eligible.append(service_id)
    if not eligible:
        return None, tuple(diagnostics)
    return (
        ValidatedShownOptionsSnapshot(
            snapshot=snapshot,
            age_turns=age,
            eligible_service_ids=tuple(eligible),
        ),
        tuple(diagnostics),
    )


def model_visible_shown_options(
    snapshot: ShownServiceOptionsSnapshot,
    bundle: ResponseSchemaBundle,
) -> ModelVisibleShownOptions:
    services: list[tuple[str, str]] = []
    for service_id in snapshot.service_ids:
        service = bundle.services[service_id]
        services.append((service_id, service.name))
    return ModelVisibleShownOptions(topic_id=snapshot.topic_id, services=tuple(services))


def model_visible_shown_options_from_descriptors(
    snapshot: ShownServiceOptionsSnapshot,
    *,
    eligible_service_ids: tuple[str, ...],
    service_descriptors: tuple[ServiceDescriptor, ...],
) -> ModelVisibleShownOptions:
    labels = {descriptor.service_id: descriptor.label for descriptor in service_descriptors}
    services: list[tuple[str, str]] = []
    for service_id in snapshot.service_ids:
        if service_id not in eligible_service_ids:
            continue
        label = labels.get(service_id)
        if label is None:
            raise ShownOptionsSnapshotError("shown_service_id_not_in_authority_catalog")
        services.append((service_id, label))
    if not services:
        raise ShownOptionsSnapshotError("shown_service_ids_empty")
    return ModelVisibleShownOptions(topic_id=snapshot.topic_id, services=tuple(services))


def snapshot_topic_allowed_for_decision(
    validated: ValidatedShownOptionsSnapshot | None,
    *,
    decision_topic_id: str | None,
) -> tuple[str | None, tuple[PostComposerDiagnostic, ...], bool]:
    if validated is None:
        return decision_topic_id, (), False
    snapshot_topic = validated.snapshot.topic_id
    if decision_topic_id is None:
        return snapshot_topic, (), True
    if decision_topic_id != snapshot_topic:
        return (
            decision_topic_id,
            (
                PostComposerDiagnostic(
                    code="shown_options_topic_mismatch",
                    detail={"decision_topic": decision_topic_id, "snapshot_topic": snapshot_topic},
                ),
            ),
            False,
        )
    return decision_topic_id, (), True


def project_model_visible_shown_options_for_composer(
    snapshot: ShownServiceOptionsSnapshot,
    *,
    session_key: SessionKey,
    source_client_id: str,
    current_turn_index: int,
    policy: ShownOptionsFreshnessPolicy,
    service_descriptors: tuple[ServiceDescriptor, ...],
    known_client_service_ids: frozenset[str],
    known_inactive_service_ids: frozenset[str],
) -> ModelVisibleShownOptions | None:
    if snapshot.session_key != session_key:
        raise ShownOptionsSnapshotError("shown_options_session_key_mismatch")
    if snapshot.session_key.client_id != source_client_id:
        raise ShownOptionsSnapshotError("shown_options_client_mismatch")
    if snapshot.shown_at_turn > current_turn_index:
        raise ShownOptionsSnapshotError("shown_options_future_turn")
    age = current_turn_index - snapshot.shown_at_turn
    if age > policy.max_age_turns:
        return None
    active_service_ids = frozenset(descriptor.service_id for descriptor in service_descriptors)
    eligible = build_eligible_shown_service_ids(
        snapshot,
        active_service_ids=active_service_ids,
        known_client_service_ids=known_client_service_ids,
        known_inactive_service_ids=known_inactive_service_ids,
    )
    if not eligible:
        return None
    return model_visible_shown_options_from_descriptors(
        snapshot,
        eligible_service_ids=eligible,
        service_descriptors=service_descriptors,
    )
