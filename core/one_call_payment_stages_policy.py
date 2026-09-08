"""When code may append payment-stage blocks on sales-fast price turns."""

from __future__ import annotations

from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from core.price_ref_routing import parse_price_widget_ref


def governed_payment_stages_ui_ref(nav_ref: str | None) -> bool:
    parsed = parse_price_widget_ref(nav_ref or "")
    return parsed is not None and str(parsed.get("aspect") or "").strip().lower() == "stages"


def payment_stages_materialization_allowed(
    *,
    semantic: SalesOnePlusSemanticFrame,
    user_message: str | None = None,
    nav_ref: str | None = None,
) -> bool:
    if governed_payment_stages_ui_ref(nav_ref):
        return True
    return semantic.commercial_intent == "payment_stages"
