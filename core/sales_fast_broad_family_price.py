"""Broad family price overview policy for sales-fast (non-authoritative presentation)."""

from __future__ import annotations

import re

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from contracts.turn_frame import TurnFrame
from core.answer_planner import detect_aspects_regex
from core.sales_fast_turn_frame import _infer_non_authoritative_broad_implantation_price_hint
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

BROAD_FAMILY_PRICE_NEUTRAL_INTRO = "Стоимость зависит от объёма работы."
SCOPED_FAMILY_PRICE_NEUTRAL_INTRO = "Стоимость зависит от выбранного объёма работы."

_EXPLICIT_SERVICE_RE = re.compile(
    r"all[\s-]?on[\s-]?[46]|straumann|nobel|implantium|impro",
    re.I | re.U,
)


def message_has_price_aspect(user_message: str) -> bool:
    aspects = tuple(detect_aspects_regex(user_message))
    return any(aspect in aspects for aspect in ("price", "payment", "included"))


def price_overview_intent(
    semantic: SalesOnePlusSemanticFrame,
    user_message: str,
) -> bool:
    if semantic.commercial_intent == "price":
        return True
    return message_has_price_aspect(user_message)


def explicit_service_blocks_broad_overview(
    *,
    semantic: SalesOnePlusSemanticFrame,
    turn_frame: TurnFrame,
    effective_scope: EffectiveScope | None,
    user_message: str,
) -> bool:
    if semantic.service_id or turn_frame.service_id:
        return True
    if semantic.service_reference_status == "resolved" and semantic.requested_service_id:
        return True
    if effective_scope is not None and effective_scope.extent not in {None, "unknown"}:
        return True
    if _infer_non_authoritative_broad_implantation_price_hint(user_message) is None:
        return True
    if _EXPLICIT_SERVICE_RE.search(user_message or ""):
        return True
    return False


def is_broad_family_price_overview_turn(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    semantic: SalesOnePlusSemanticFrame,
    turn_frame: TurnFrame,
    effective_scope: EffectiveScope | None,
    user_message: str,
) -> bool:
    spec = bound_package.spec
    if spec.response_stage != "broad_family_price" or not spec.scope_price_topic:
        return False
    if not price_overview_intent(semantic, user_message):
        return False
    if explicit_service_blocks_broad_overview(
        semantic=semantic,
        turn_frame=turn_frame,
        effective_scope=effective_scope,
        user_message=user_message,
    ):
        return False
    return True


def is_scoped_family_price_overview_turn(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    semantic: SalesOnePlusSemanticFrame,
    turn_frame: TurnFrame,
    user_message: str,
) -> bool:
    spec = bound_package.spec
    if not spec.scope_price_topic:
        return False
    if spec.response_stage not in {"scoped_family_price", "concrete_service_price"}:
        return False
    if semantic.service_id or turn_frame.service_id:
        return False
    if semantic.service_reference_status == "resolved" and semantic.requested_service_id:
        return False
    if not price_overview_intent(semantic, user_message):
        return False
    return True


def infer_broad_implantation_topic_for_turn(
    *,
    semantic: SalesOnePlusSemanticFrame,
    user_message: str,
    bundle: ResponseSchemaBundle,
    service_id: str | None,
) -> str | None:
    from core.sales_fast_turn_frame import _topic_for_confirmed_service

    topic = _topic_for_confirmed_service(
        service_id=service_id,
        bundle=bundle,
        user_message=user_message,
    )
    if topic is not None:
        return topic
    if price_overview_intent(semantic, user_message):
        return _infer_non_authoritative_broad_implantation_price_hint(user_message)
    return None
