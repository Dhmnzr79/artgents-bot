"""Materialize answer packet cards into composer-ready text blocks."""

from __future__ import annotations

from contracts.answer_packet import AnswerPacketSnapshot, MaterializedCard, PacketCard, PacketCardKind
from contracts.answer_plan import AspectKind
from core.price_offers import format_rub, get_price_offers, offers_from_service_entry
from core.pricebook_loader import load_pricebook_service, load_pricing_facts
from core.md_chunks import get_chunk_by_ref

_ASPECT_PRIORITY: tuple[AspectKind, ...] = (
    "price",
    "payment",
    "included",
    "warranty",
    "pain",
    "duration",
    "comparison",
    "stages",
    "overview",
)

_CONTENT_PACKET_KINDS: frozenset[PacketCardKind] = frozenset(
    {"content", "price", "promo", "payment", "warranty"}
)
_DETERMINISTIC_CARD_KINDS: frozenset[PacketCardKind] = frozenset({"price", "promo"})


def _aspect_sort_key(card: PacketCard, *, primary_aspect: AspectKind | None) -> tuple[int, int]:
    aspect = card.aspect or "overview"
    primary_rank = 0 if primary_aspect and aspect == primary_aspect else 1
    order = {a: i for i, a in enumerate(_ASPECT_PRIORITY)}
    return primary_rank, order.get(aspect, 99)  # type: ignore[arg-type]


def _ordered_content_cards(packet: AnswerPacketSnapshot) -> list[PacketCard]:
    cards = [c for c in packet.cards if c.kind in _CONTENT_PACKET_KINDS]
    return sorted(cards, key=lambda c: _aspect_sort_key(c, primary_aspect=packet.primary_aspect))


def _chunk_body(*, client_id: str | None, source_ref: str | None) -> str | None:
    ref = (source_ref or "").strip()
    if not ref:
        return None
    chunk = get_chunk_by_ref(ref, client_id=client_id)
    if not isinstance(chunk, dict):
        return None
    parts: list[str] = []
    h3 = str(chunk.get("h3") or "").strip()
    body = str(chunk.get("text") or "").strip()
    if h3:
        parts.append(h3)
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip() or None


def _unit_line(unit: str | None) -> str | None:
    u = (unit or "").strip().lower()
    if u == "jaw":
        return "За одну челюсть."
    if u == "one_tooth":
        return "За один зуб."
    if u == "full_mouth":
        return "За обе челюсти."
    return None


def _planner_brand_filter() -> tuple[str | None, str | None]:
    try:
        from core.turn_planner_llm import turn_plan_brand_filter_from_ctx

        return turn_plan_brand_filter_from_ctx()
    except Exception:
        return None, None


def render_price_fact_block(
    *,
    client_id: str | None,
    service_id: str | None,
    brand: str | None = None,
    brand_group: str | None = None,
) -> str | None:
    """Deterministic price fact block (brands + unit + includes/excludes), no intro/CTA."""
    sid = (service_id or "").strip()
    if not sid:
        return None
    entry = load_pricebook_service(client_id, sid)
    if not entry:
        return None
    planner_brand, planner_brand_group = _planner_brand_filter()
    brand_eff = brand or planner_brand
    group_eff = brand_group or planner_brand_group
    offers = (
        get_price_offers(
            client_id,
            sid,
            unit=entry.default_unit,
            brand=brand_eff,
            brand_group=group_eff,
        )
        if brand_eff or group_eff
        else offers_from_service_entry(entry)
    )
    if offers:
        lines: list[str] = []
        for offer in offers:
            lines.append(f"{offer.brand_label} — {format_rub(offer.total)}")
        unit_line = _unit_line(str(offers[0].unit or entry.default_unit or ""))
        if unit_line:
            lines.append(unit_line)
        sample = next((o for o in offers if o.recommended), offers[0])
        includes = [str(x).strip() for x in (sample.includes or []) if str(x).strip()]
        if includes:
            lines.append(f"В стоимость входят: {', '.join(includes)}.")
        excludes = [str(x).strip() for x in (sample.excludes or []) if str(x).strip()]
        for item in excludes:
            lines.append(item if item.endswith(".") else f"{item}.")
        text = "\n".join(lines).strip()
        return text or None
    if entry.price_model == "simple" and entry.price is not None:
        price = entry.price
        prefix = "от " if price.price_type == "from" else ""
        lines = [f"{prefix}{format_rub(price.value)}"]
        unit_line = _unit_line(str(entry.default_unit or ""))
        if unit_line:
            lines.append(unit_line)
        note = str(price.note or "").strip()
        if note:
            lines.append(note if note.endswith(".") else f"{note}.")
        return "\n".join(lines).strip() or None
    return None


def _promo_text(*, client_id: str | None, fact_id: str | None) -> str | None:
    fid = (fact_id or "").strip()
    if not fid:
        return None
    facts_file = load_pricing_facts(client_id)
    if not facts_file:
        return None
    fact = facts_file.facts.get(fid)
    if not fact or fact.kind != "promo":
        return None
    body = str(fact.text_fact or "").strip()
    return body or None


def _materialize_card(
    card: PacketCard,
    *,
    client_id: str | None,
    service_id: str | None,
) -> MaterializedCard | None:
    if card.kind == "price":
        sid = (card.fact_id or service_id or "").strip() or None
        text = render_price_fact_block(client_id=client_id, service_id=sid)
        if not text:
            return None
        return MaterializedCard(
            aspect=card.aspect,
            kind=card.kind,
            text=text,
            verbatim=True,
            source_ref=card.source_ref,
            fact_id=card.fact_id or sid,
        )
    if card.kind == "promo":
        text = _promo_text(client_id=client_id, fact_id=card.fact_id)
        if not text:
            return None
        return MaterializedCard(
            aspect=card.aspect,
            kind=card.kind,
            text=text,
            verbatim=False,
            fact_id=card.fact_id,
        )
    if card.kind in {"content", "payment", "warranty"}:
        text = _chunk_body(client_id=client_id, source_ref=card.source_ref)
        if not text:
            return None
        return MaterializedCard(
            aspect=card.aspect,
            kind=card.kind,
            text=text,
            verbatim=False,
            source_ref=card.source_ref,
            fact_id=card.fact_id,
        )
    return None


def materialize_cards(
    packet: AnswerPacketSnapshot,
    *,
    client_id: str | None,
) -> list[MaterializedCard]:
    """Resolve packet cards to text blocks in aspect-priority order (no cta/buttons)."""
    out: list[MaterializedCard] = []
    svc = (packet.service_id or "").strip() or None
    for card in _ordered_content_cards(packet):
        if card.suppressed_reason:
            continue
        materialized = _materialize_card(card, client_id=client_id, service_id=svc)
        if materialized is not None:
            out.append(materialized)
    return out


def materialize_deterministic_cards(
    packet: AnswerPacketSnapshot,
    *,
    client_id: str | None,
) -> list[MaterializedCard]:
    """Price/promo cards only — for full-context composer (medical text from knowledge base)."""
    return [c for c in materialize_cards(packet, client_id=client_id) if c.kind in _DETERMINISTIC_CARD_KINDS]
