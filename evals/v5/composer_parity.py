"""Composer-path parity checks for product eval (FULLCONTEXT roadmap stage 3.0).

When ``answer_path == composer`` legacy retrieval asserts (doc_id, source chunk) do not
apply.  Cases declare a ``composer_parity`` block with service_id, packet aspects,
amounts (T2), numeric gate, and forbidden-claim telemetry (C1–C2 from live-eval).
"""
from __future__ import annotations

import re
from typing import Any

_DIGITS_ONLY_RX = re.compile(r"[\s\u00a0\u202f.,]")


def norm(s: str) -> str:
    return (s or "").strip().lower()


def str_list_field(obj: dict[str, Any], key: str) -> list[str]:
    raw = obj.get(key)
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def normalize_digits(text: str) -> str:
    return _DIGITS_ONLY_RX.sub("", text or "")


def amount_in_text(amount: int, text: str) -> bool:
    return str(int(amount)) in normalize_digits(text)


def meta_gate_action(meta: dict[str, Any]) -> str:
    gate = meta.get("numeric_fact_gate")
    if isinstance(gate, dict):
        return str(gate.get("action") or "").strip()
    return ""


def meta_service_id(meta: dict[str, Any]) -> str:
    packet = meta.get("answer_packet")
    if isinstance(packet, dict):
        svc = str(packet.get("service_id") or "").strip()
        if svc:
            return svc
    return str(meta.get("matched_service_id") or meta.get("service_id") or "").strip()


def packet_aspects(meta: dict[str, Any]) -> set[str]:
    packet = meta.get("answer_packet")
    if not isinstance(packet, dict):
        return set()
    cards = packet.get("cards")
    if not isinstance(cards, list):
        return set()
    out: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        aspect = str(card.get("aspect") or "").strip()
        if aspect:
            out.add(norm(aspect))
    return out


def plan_aspects(meta: dict[str, Any]) -> set[str]:
    plan = meta.get("answer_plan")
    if not isinstance(plan, dict):
        return set()
    raw = plan.get("aspects")
    if not isinstance(raw, list):
        return set()
    return {norm(str(x)) for x in raw if str(x).strip()}


def aspects_union(meta: dict[str, Any]) -> set[str]:
    return packet_aspects(meta) | plan_aspects(meta)


def meta_str_list(meta: dict[str, Any], key: str) -> list[str]:
    raw = meta.get(key)
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def should_skip_legacy_retrieval_checks(*, meta: dict[str, Any], row: dict[str, Any]) -> bool:
    """Legacy doc_id / doc_type asserts are meaningless on the composer path."""
    if str(meta.get("answer_path") or "").strip() != "composer":
        return False
    return isinstance(row.get("composer_parity"), dict)


def validate_composer_parity(
    *,
    row: dict[str, Any],
    answer: str,
    meta: dict[str, Any],
) -> str | None:
    """Return failure reason, or None when parity checks pass / are not active."""
    parity = row.get("composer_parity")
    if not isinstance(parity, dict):
        return None

    answer_path = str(meta.get("answer_path") or "").strip()

    if parity.get("expect_not_composer") is True:
        if answer_path == "composer":
            return "composer_parity: composer fired on deterministic route"
        return None

    expected_path = str(parity.get("expected_answer_path") or "composer").strip()
    expected_path_any = str_list_field(parity, "expected_answer_path_any")

    if answer_path != "composer":
        return None

    if expected_path and answer_path != expected_path:
        return f"composer_parity: answer_path={answer_path!r} want={expected_path!r}"
    if expected_path_any and norm(answer_path) not in {norm(x) for x in expected_path_any}:
        return (
            f"composer_parity: answer_path={answer_path!r} "
            f"want_any={expected_path_any!r}"
        )

    want_svc = str(parity.get("expected_service_id") or row.get("expected_service_id") or "").strip()
    if want_svc:
        got_svc = meta_service_id(meta)
        if norm(got_svc) != norm(want_svc):
            return f"composer_parity: service_id got={got_svc!r} want={want_svc!r}"

    want_svc_any = str_list_field(parity, "expected_service_id_any") or str_list_field(
        row, "expected_service_id_any"
    )
    if want_svc_any:
        got_svc = meta_service_id(meta)
        if not got_svc or norm(got_svc) not in {norm(x) for x in want_svc_any}:
            return (
                f"composer_parity: service_id got={got_svc!r} "
                f"want_any={want_svc_any!r}"
            )

    forbidden_svc = str_list_field(parity, "forbidden_service_id") or str_list_field(
        row, "forbidden_service_id"
    )
    if forbidden_svc:
        got_svc = meta_service_id(meta)
        if got_svc and norm(got_svc) in {norm(x) for x in forbidden_svc}:
            return f"composer_parity: forbidden_service_id hit: {got_svc!r}"

    want_aspects = str_list_field(parity, "expected_packet_aspects")
    if want_aspects:
        got_aspects = aspects_union(meta)
        missing = [x for x in want_aspects if norm(x) not in got_aspects]
        if missing:
            return (
                f"composer_parity: expected_packet_aspects missing={missing!r} "
                f"got={sorted(got_aspects)!r}"
            )

    amounts_raw = parity.get("expected_packet_amounts")
    if isinstance(amounts_raw, list) and amounts_raw:
        amounts = [int(x) for x in amounts_raw]
        missing_amounts = [a for a in amounts if not amount_in_text(a, answer)]
        if missing_amounts:
            return f"composer_parity: missing_packet_amounts={missing_amounts}"

    if parity.get("require_numeric_gate_pass") is True:
        gate_action = meta_gate_action(meta)
        if gate_action and gate_action != "pass":
            return f"composer_parity: numeric_fact_gate.action={gate_action!r} (expected pass)"

    if parity.get("require_forbidden_claims_empty") is True:
        hits = meta_str_list(meta, "forbidden_claim_hits")
        if hits:
            return f"composer_parity: forbidden_claim_hits={hits!r}"

    want_ps = parity.get("expected_price_status") or row.get("expected_price_status")
    if want_ps is not None:
        got_ps = str(meta.get("price_status") or "").strip()
        if str(want_ps).strip() and norm(got_ps) != norm(str(want_ps)):
            return f"composer_parity: price_status got={got_ps!r} want={want_ps!r}"

    want_gid = parity.get("expected_pricebook_group_id") or row.get("expected_pricebook_group_id")
    if want_gid is not None:
        got_gid = str(meta.get("pricebook_group_id") or "").strip()
        if str(want_gid).strip() and norm(got_gid) != norm(str(want_gid)):
            return (
                f"composer_parity: pricebook_group_id got={got_gid!r} want={want_gid!r}"
            )

    return None
