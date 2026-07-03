"""Deterministic numeric fact safety gate (PRODUCT_WORK_PLAN stage 5a).

Checks final assembled answer for ₽ / % / installment months against a turn whitelist.
Fail-open on parse doubt; block only when the answer collapses after removing bad facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from core.client_config_loader import numeric_fact_gate_enabled
from core.price_offers import load_price_offers

NumericFactGateAction = Literal["skipped", "pass", "remove_fact", "blocked"]

_RUB_RX = re.compile(
    r"(?<!\d)(?:от\s+)?(\d[\d\s\u00a0\u202f.,]*\d|\d)\s*(?:₽|руб\.?\b|р\.)",
    re.I | re.UNICODE,
)
_PCT_RX = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:%|процент\w*)",
    re.I | re.UNICODE,
)
_INSTALLMENT_CTX_RX = re.compile(
    r"рассроч\w*|без\s+процент\w*|в\s+рассрочку",
    re.I | re.UNICODE,
)
_INSTALLMENT_MONTHS_RX = re.compile(
    r"(\d+)\s*(?:мес(?:\.|яцев|яца)?|месяц(?:а|ев)?)\b",
    re.I | re.UNICODE,
)
_SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?])\s+|\n\n+")

_BLOCKED_FALLBACK = (
    "Точную стоимость и условия лучше уточнить на консультации — "
    "после осмотра назовут сумму по вашей ситуации."
)


@dataclass
class NumericFactGateResult:
    answer: str
    action: NumericFactGateAction
    reasons: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def meta_dict(self) -> dict[str, Any]:
        if self.action == "skipped":
            return {}
        return {
            "numeric_fact_gate": {
                "action": self.action,
                "reasons": list(self.reasons),
                "removed": list(self.removed),
            }
        }


def _parse_int_amount(raw: str) -> int | None:
    cleaned = re.sub(r"[\s\u00a0\u202f.,]", "", (raw or "").strip())
    if not cleaned.isdigit():
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_percent(raw: str) -> float | None:
    s = (raw or "").strip().replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def extract_rub_amounts(text: str) -> list[int]:
    out: list[int] = []
    for m in _RUB_RX.finditer(text or ""):
        val = _parse_int_amount(m.group(1))
        if val is not None:
            out.append(val)
    return out


def extract_percents(text: str) -> list[float]:
    out: list[float] = []
    for m in _PCT_RX.finditer(text or ""):
        val = _parse_percent(m.group(1))
        if val is not None:
            out.append(val)
    return out


def extract_installment_months(text: str) -> list[int]:
    """Months only when the same sentence mentions installment context."""
    out: list[int] = []
    for chunk in re.split(r"[.!?\n]+", text or ""):
        if not _INSTALLMENT_CTX_RX.search(chunk):
            continue
        for m in _INSTALLMENT_MONTHS_RX.finditer(chunk):
            try:
                out.append(int(m.group(1)))
            except ValueError:
                continue
    return out


def _text_has_numeric_facts(text: str) -> bool:
    t = text or ""
    return bool(extract_rub_amounts(t) or extract_percents(t) or extract_installment_months(t))


def gate_in_scope(*, route: str | None, meta: dict, allowed_source_text: str | None) -> bool:
    r = (route or "").strip().lower()
    if r == "price_lookup":
        return True
    m = meta if isinstance(meta, dict) else {}
    if m.get("price_offers_applied") or m.get("pricebook_applied"):
        return True
    return _text_has_numeric_facts(allowed_source_text or "")


def _offer_amounts(client_id: str | None, offer_ids: list[str]) -> set[int]:
    if not offer_ids:
        return set()
    wanted = {str(x).strip() for x in offer_ids if str(x).strip()}
    if not wanted:
        return set()
    rubs: set[int] = set()
    for offer in load_price_offers(client_id):
        if offer.offer_id not in wanted:
            continue
        rubs.add(int(offer.total))
        for stage in offer.payment_stages:
            rubs.add(int(stage.amount))
    return rubs


def build_allowed_numeric_sets(
    *,
    meta: dict,
    client_id: str | None,
    allowed_source_text: str | None,
) -> tuple[set[int], set[float], set[int]]:
    m = meta if isinstance(meta, dict) else {}
    source = allowed_source_text or ""

    rubs = set(extract_rub_amounts(source))
    percents = set(extract_percents(source))
    months = set(extract_installment_months(source))

    simple = m.get("pricebook_simple_value")
    if isinstance(simple, (int, float)) and int(simple) >= 0:
        rubs.add(int(simple))

    offer_ids = m.get("price_offer_ids") or []
    if isinstance(offer_ids, list):
        rubs |= _offer_amounts(client_id, [str(x) for x in offer_ids])

    return rubs, percents, months


def _sentence_has_unallowed(
    sentence: str,
    *,
    allowed_rubs: set[int],
    allowed_pcts: set[float],
    allowed_months: set[int],
) -> tuple[bool, str | None]:
    bad_rubs = [a for a in extract_rub_amounts(sentence) if a not in allowed_rubs]
    if bad_rubs:
        return True, f"rub:{bad_rubs[0]}"
    bad_pcts = [p for p in extract_percents(sentence) if p not in allowed_pcts]
    if bad_pcts:
        return True, f"pct:{bad_pcts[0]}"
    bad_months = [mo for mo in extract_installment_months(sentence) if mo not in allowed_months]
    if bad_months:
        return True, f"months:{bad_months[0]}"
    return False, None


def _remove_bad_sentences(
    answer: str,
    *,
    allowed_rubs: set[int],
    allowed_pcts: set[float],
    allowed_months: set[int],
) -> tuple[str, list[str], list[str]]:
    text = (answer or "").strip()
    if not text:
        return text, [], []

    parts = _SENTENCE_SPLIT_RX.split(text)
    if len(parts) <= 1:
        parts = [p for p in text.split("\n\n") if p.strip()] or [text]

    kept: list[str] = []
    removed: list[str] = []
    reasons: list[str] = []
    for part in parts:
        segment = part.strip()
        if not segment:
            continue
        bad, reason = _sentence_has_unallowed(
            segment,
            allowed_rubs=allowed_rubs,
            allowed_pcts=allowed_pcts,
            allowed_months=allowed_months,
        )
        if bad:
            removed.append(segment[:200])
            if reason:
                reasons.append(reason)
        else:
            kept.append(segment)

    if not kept and removed:
        return "", removed, reasons
    return "\n\n".join(kept).strip(), removed, reasons


def apply_numeric_fact_gate(
    *,
    answer: str,
    route: str | None,
    meta: dict | None,
    client_id: str | None,
    allowed_source_text: str | None,
) -> NumericFactGateResult:
    """Apply stage-5a numeric gate. Fail-open when disabled or out of scope."""
    base = (answer or "").strip()
    m = meta if isinstance(meta, dict) else {}

    if not numeric_fact_gate_enabled(client_id):
        return NumericFactGateResult(answer=base, action="skipped")

    if not gate_in_scope(route=route, meta=m, allowed_source_text=allowed_source_text):
        return NumericFactGateResult(answer=base, action="skipped")

    if not _text_has_numeric_facts(base):
        return NumericFactGateResult(answer=base, action="pass")

    allowed_rubs, allowed_pcts, allowed_months = build_allowed_numeric_sets(
        meta=m,
        client_id=client_id,
        allowed_source_text=allowed_source_text,
    )

    # Fail-open: answer has numeric facts but no whitelist to compare against.
    if not (allowed_rubs or allowed_pcts or allowed_months):
        return NumericFactGateResult(answer=base, action="pass", reasons=["no_whitelist"])

    bad_any = False
    reasons: list[str] = []
    for rub in extract_rub_amounts(base):
        if rub not in allowed_rubs:
            bad_any = True
            reasons.append(f"rub:{rub}")
    for pct in extract_percents(base):
        if pct not in allowed_pcts:
            bad_any = True
            reasons.append(f"pct:{pct}")
    for mo in extract_installment_months(base):
        if mo not in allowed_months:
            bad_any = True
            reasons.append(f"months:{mo}")

    if not bad_any:
        return NumericFactGateResult(answer=base, action="pass")

    cleaned, removed, remove_reasons = _remove_bad_sentences(
        base,
        allowed_rubs=allowed_rubs,
        allowed_pcts=allowed_pcts,
        allowed_months=allowed_months,
    )
    if cleaned:
        still_bad = False
        for rub in extract_rub_amounts(cleaned):
            if rub not in allowed_rubs:
                still_bad = True
                break
        if not still_bad:
            for pct in extract_percents(cleaned):
                if pct not in allowed_pcts:
                    still_bad = True
                    break
        if not still_bad:
            for mo in extract_installment_months(cleaned):
                if mo not in allowed_months:
                    still_bad = True
                    break
        if not still_bad:
            return NumericFactGateResult(
                answer=cleaned,
                action="remove_fact",
                reasons=sorted(set(reasons + remove_reasons)),
                removed=removed,
            )

    return NumericFactGateResult(
        answer=_BLOCKED_FALLBACK,
        action="blocked",
        reasons=sorted(set(reasons + remove_reasons)),
        removed=removed,
    )
