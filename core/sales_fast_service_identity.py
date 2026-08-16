"""Pure current-turn service identity for the sales-fast path (Checkpoint A)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import ResponseSchemaBundle
from contracts.turn_frame import TurnFrame
from core.attribute_followup import query_has_explicit_service_object
from core.target_client_data import match_service_from_bundle
from core.target_generic_fullcontext_content import should_skip_session_service_hydration
from core.target_runtime_session import TargetRuntimeSessionState
from core.target_runtime_turn_frame_hydration import (
    hydrate_target_runtime_turn_frame_from_session,
)


@dataclass(frozen=True, slots=True)
class SalesFastServiceIdentity:
    """Authoritative service identities only — no response, price, or topic."""

    explicit_service_id: str | None
    explicit_service_term: str | None
    session_service_id: str | None
    catalog_ambiguous: bool

    @classmethod
    def from_catalog(
        cls,
        *,
        explicit_service_id: str | None,
        explicit_service_term: str | None,
        catalog_ambiguous: bool,
    ) -> SalesFastServiceIdentity:
        return cls(
            explicit_service_id=explicit_service_id,
            explicit_service_term=explicit_service_term,
            session_service_id=None,
            catalog_ambiguous=catalog_ambiguous,
        )

    def with_session_service(self, session_service_id: str | None) -> SalesFastServiceIdentity:
        return SalesFastServiceIdentity(
            explicit_service_id=self.explicit_service_id,
            explicit_service_term=self.explicit_service_term,
            session_service_id=session_service_id,
            catalog_ambiguous=self.catalog_ambiguous,
        )


def _catalog_authority_eligible(match: dict[str, object]) -> bool:
    service_id = str(match.get("matched_service_id") or "").strip()
    if not service_id:
        return False
    if not bool(match.get("is_confident")):
        return False
    if not bool(match.get("containment_eligible")):
        return False
    if bool(match.get("catalog_ambiguous")):
        return False
    return True


def resolve_catalog_service_identity(
    user_message: str,
    bundle: ResponseSchemaBundle,
) -> SalesFastServiceIdentity:
    """Compute confident explicit catalog match once per turn."""

    match = match_service_from_bundle(user_message, bundle)
    ambiguous = bool(match.get("catalog_ambiguous"))
    if not _catalog_authority_eligible(match):
        return SalesFastServiceIdentity.from_catalog(
            explicit_service_id=None,
            explicit_service_term=None,
            catalog_ambiguous=ambiguous,
        )
    service_id = str(match["matched_service_id"]).strip()
    service = bundle.services.get(service_id)
    if service is None or not service.active:
        return SalesFastServiceIdentity.from_catalog(
            explicit_service_id=None,
            explicit_service_term=None,
            catalog_ambiguous=ambiguous,
        )
    term = str(
        match.get("matched_phrase")
        or match.get("matched_service_term")
        or match.get("matched_label")
        or service.name
        or service_id
    ).strip()
    if not term:
        return SalesFastServiceIdentity.from_catalog(
            explicit_service_id=None,
            explicit_service_term=None,
            catalog_ambiguous=ambiguous,
        )
    return SalesFastServiceIdentity.from_catalog(
        explicit_service_id=service_id,
        explicit_service_term=term,
        catalog_ambiguous=ambiguous,
    )


def resolve_session_service_for_followup(
    *,
    turn_frame: TurnFrame,
    user_message: str,
    session_state: TargetRuntimeSessionState,
    allowed_service_ids: frozenset[str],
    explicit_service_id: str | None,
    commercial_intent: str | None = None,
) -> str | None:
    """Fresh session service for vague price/payment/included follow-up only."""

    if explicit_service_id:
        return None
    if commercial_intent not in {"price", "payment", "included"}:
        return None
    probe = turn_frame.model_copy(
        update={
            "service_id": None,
            "follow_up": False,
            "followup_of": None,
        }
    )
    aspect_map = {
        "price": "price",
        "payment": "payment",
        "included": "included",
    }
    aspect = aspect_map[str(commercial_intent)]
    if aspect not in probe.aspects:
        probe = probe.model_copy(
            update={
                "primary_aspect": aspect,
                "aspects": [aspect, *probe.aspects],
            }
        )
    if not should_skip_session_service_hydration(probe, user_message=user_message):
        hydrated = hydrate_target_runtime_turn_frame_from_session(
            probe,
            user_message=user_message,
            session_state=session_state,
            allowed_service_ids=allowed_service_ids,
        )
        if hydrated.service_id:
            return hydrated.service_id

    followup_kind = aspect if aspect in {"price", "payment", "included"} else None
    if query_has_explicit_service_object(user_message, kind=followup_kind):
        return None
    if not session_state.is_service_focus_fresh():
        return None
    last_service_id = str(session_state.last_service_id or "").strip()
    if not last_service_id or last_service_id not in allowed_service_ids:
        return None
    return last_service_id
