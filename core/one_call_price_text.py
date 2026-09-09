"""Isolated price_text validation and canonical fallback (CP-EXACT-1B-SINGLE / MULTI-V1)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from contracts.one_call_envelope import OneCallCommercialIntent
from contracts.precomposer_selected_offer import (
    PrecomposerSelectedOfferResult,
    PriceTextDiagnostic,
    ResolvedPriceText,
)
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from core.one_call_multi_offer_price_block import build_canonical_multi_offer_price_block
from core.sales_fast_authoritative_commerce import (
    _CURRENCY_AMOUNT_RE,
    _FORBIDDEN_TOTAL_LINE_RE,
    _SENTENCE_SPLIT_RE,
    _amounts_in_text,
    _offer_widget_amount,
    _service_condition_text,
    build_canonical_exact_offer_price_line,
)

_PROSE_CURRENCY_AMOUNT_RE = re.compile(
    r"(?<!\d)(?:от\s+)?\d[\d\s\u00a0]*(?:\d{3})*(?:[.,]\d+)?\s*(?:₽|руб(?:\.|лей|ля)?|rub)(?!\w)",
    re.IGNORECASE,
)

_PRICE_ASSERTION_RE = re.compile(
    r"\b(?:стоимость|цена|сколько\s+стоит|составляет|стоит)\b",
    re.IGNORECASE,
)
_PACKAGE_CONTINUATION_RE = re.compile(
    r"\b(?:в\s+(?:эту|данную)\s+сумму|входит|включает|в\s+пакет)\b",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY_SPLIT_RE = re.compile(r"([,;])\s*")
_PRICE_GLUE_CLEANUP_RE = re.compile(
    r"(?:"
    r"\s*—\s*(?=[,.]|$)|"
    r"(?:составляет|стоит)\s*(?=[,.]|$)|"
    r"^\s*(?:стоимость|цена)\b[^.—–-]*(?:—|–|-)\s*"
    r")",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY_SPLIT_RE = re.compile(r"([,;])\s*")
_BROKEN_PRICE_FRAGMENT_RE = re.compile(
    r"^(?:стоимость|цена)\b(?:(?!\d)(?!.*(?:₽|руб)).)*$|"
    r"\b(?:составляет|стоит)\s*[,.]?\s*$",
    re.IGNORECASE,
)

_PACKAGE_ANCHOR_RE = re.compile(r"[\wа-яё\-]+", re.IGNORECASE | re.UNICODE)

_PROSE_CURRENCY_RANGE_RE = re.compile(
    r"(?<!\d)(?:от\s+)?\d[\d\s\u00a0]*(?:\d{3})*(?:[.,]\d+)?\s*[–—-]\s*"
    r"\d[\d\s\u00a0]*(?:\d{3})*(?:[.,]\d+)?\s*(?:₽|руб(?:\.|лей|ля)?|rub)(?!\w)",
    re.IGNORECASE,
)
_PROSE_THOUSANDS_RUB_RE = re.compile(
    r"(?<!\d)(?:от\s+)?\d[\d\s\u00a0]*(?:\d{3})*(?:[.,]\d+)?\s*тыс\.?\s*(?:₽|руб(?:\.|лей|ля)?|rub)(?!\w)",
    re.IGNORECASE,
)
_PROSE_PAYMENT_AMOUNT_RE = re.compile(
    r"плат[её]ж\w*\s+состав\w*[^.\n]{0,40}(?:₽|руб(?:\.|лей|ля)?|rub)",
    re.IGNORECASE | re.U,
)

NO_PUBLIC_PRICE_FALLBACK = "В материалах клиники стоимость этой услуги не указана"


def _normalize_package_anchor(label: str) -> str:
    tokens = _PACKAGE_ANCHOR_RE.findall(label.casefold())
    return " ".join(tokens)


def is_no_public_price_offer(offer: TargetOffer) -> bool:
    return offer.price.mode == "no_public_price"


def is_ambiguous_no_public_price_selection(
    selection: PrecomposerSelectedOfferResult,
) -> bool:
    return (
        selection.availability == "none"
        and selection.diagnostic == "ambiguous_no_public_price"
    )


def is_no_public_price_price_turn(
    *,
    commercial_intent: str,
    selection: PrecomposerSelectedOfferResult | None,
    resolved_price_text: ResolvedPriceText | None,
) -> bool:
    if commercial_intent != "price":
        return False
    if resolved_price_text is None or not resolved_price_text.line.strip():
        return False
    if selection is not None and selection.availability == "selected" and selection.offer is not None:
        return is_no_public_price_offer(selection.offer)
    return is_ambiguous_no_public_price_selection(selection) if selection is not None else False


def build_no_public_price_line(offer: TargetOffer) -> str:
    approved = str(offer.price.approved_text or "").strip()
    return approved or NO_PUBLIC_PRICE_FALLBACK


def displayed_offers_show_numeric_price(offers: Sequence[TargetOffer]) -> bool:
    """True when code-owned numeric offer amounts are shown on the turn."""

    return bool(code_owned_amounts_for_offers(offers))


def dedupe_price_line_from_patient_text(patient_text: str, price_line: str) -> str:
    """Drop patient prose that repeats the code-owned no-public-price line."""

    patient = patient_text.strip()
    line = price_line.strip()
    if not patient or not line:
        return patient
    if patient.casefold() == line.casefold():
        return ""
    if patient.casefold().startswith(line.casefold()):
        remainder = patient[len(line) :].lstrip(" .—–-\n")
        return remainder.strip()
    return patient


def _expected_amount(offer: TargetOffer) -> int | None:
    if offer.price.mode != "fixed" or offer.price.amount is None:
        return None
    return int(offer.price.amount)


def _currency_tokens(currency: str) -> tuple[str, ...]:
    token = currency.strip().upper()
    if token == "RUB":
        return ("₽", "руб", "rub")
    return (token.casefold(),)


def _billing_unit_tokens(billing_unit: str) -> tuple[str, ...]:
    unit = billing_unit.strip().casefold()
    mapping = {
        "procedure": ("процедур", "исследован", "услуг"),
        "tooth": ("зуб",),
        "jaw": ("челюст",),
        "unit": ("единиц",),
        "course": ("курс", "лечен"),
    }
    return mapping.get(unit, (unit,))


def _contains_currency(text: str, currency: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in _currency_tokens(currency))


def _contains_billing_unit(text: str, billing_unit: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in _billing_unit_tokens(billing_unit))


def _contains_package_anchor(text: str, package_label: str) -> bool:
    anchor = _normalize_package_anchor(package_label)
    if not anchor:
        return True
    return anchor in _normalize_package_anchor(text)


def validate_model_price_text(
    price_text: str | None,
    *,
    offer: TargetOffer,
    bundle: ResponseSchemaBundle,
) -> PriceTextDiagnostic | None:
    canonical_amount = _expected_amount(offer)
    if canonical_amount is None:
        return "wrong_amount"
    if price_text is None or not str(price_text).strip():
        return "missing"

    text = str(price_text).strip()
    amounts = _amounts_in_text(text)
    if canonical_amount not in amounts:
        return "wrong_amount"
    if len(amounts) > 1:
        return "extra_amount"
    if not _contains_currency(text, str(offer.price.currency or "RUB")):
        return "wrong_amount"
    if not _contains_billing_unit(text, str(offer.price.billing_unit or "")):
        return "wrong_unit"
    package_label = str(offer.package.label or "").strip()
    if package_label and not _contains_package_anchor(text, package_label):
        return "wrong_scope"
    if offer.service_id not in bundle.services:
        return "wrong_scope"
    return None


def resolve_price_text_for_turn(
    *,
    price_text: str | None,
    commercial_intent: OneCallCommercialIntent,
    selection: PrecomposerSelectedOfferResult,
    bundle: ResponseSchemaBundle,
) -> ResolvedPriceText:
    if commercial_intent != "price":
        if price_text is not None and str(price_text).strip():
            return ResolvedPriceText(
                line="",
                owner="none",
                diagnostic="unexpected_nonprice",
            )
        return ResolvedPriceText(line="", owner="none")

    if selection.availability == "multiple":
        diagnostic: PriceTextDiagnostic | None = None
        if price_text is not None and str(price_text).strip():
            diagnostic = "unexpected_multi_price_text"
        multi = build_canonical_multi_offer_price_block(
            bundle=bundle,
            selection=selection,
        )
        if multi.block:
            return ResolvedPriceText(
                line=multi.block,
                owner="canonical_multi",
                diagnostic=diagnostic,
                multi_offer_ids=multi.offer_ids,
            )
        return ResolvedPriceText(
            line="",
            owner="none",
            diagnostic=diagnostic or multi.diagnostic,  # type: ignore[arg-type]
            multi_offer_ids=multi.offer_ids,
        )

    if selection.availability != "selected" or selection.offer is None:
        if (
            selection.availability == "none"
            and selection.diagnostic == "ambiguous_no_public_price"
        ):
            line = NO_PUBLIC_PRICE_FALLBACK
            if price_text is not None and str(price_text).strip():
                diagnostic: PriceTextDiagnostic = "model_price_text_ignored"
            else:
                diagnostic = "canonical_code_owned"
            return ResolvedPriceText(
                line=line,
                owner="canonical_code",
                diagnostic=diagnostic,
            )
        if price_text is not None and str(price_text).strip():
            return ResolvedPriceText(
                line="",
                owner="none",
                diagnostic="unexpected_nonprice",
            )
        return ResolvedPriceText(line="", owner="none")

    offer = selection.offer
    if is_no_public_price_offer(offer):
        canonical = build_no_public_price_line(offer)
        if price_text is not None and str(price_text).strip():
            diagnostic: PriceTextDiagnostic = "model_price_text_ignored"
        else:
            diagnostic = "canonical_code_owned"
        return ResolvedPriceText(
            line=canonical,
            owner="canonical_code",
            diagnostic=diagnostic,
            selected_offer_id=offer.offer_id,
        )

    canonical = build_canonical_exact_offer_price_line(offer=offer, bundle=bundle)
    if price_text is not None and str(price_text).strip():
        failure = validate_model_price_text(price_text, offer=offer, bundle=bundle)
        diagnostic: PriceTextDiagnostic = failure or "model_price_text_ignored"
    else:
        diagnostic = "canonical_code_owned"
    return ResolvedPriceText(
        line=canonical,
        owner="canonical_code",
        diagnostic=diagnostic,
        selected_offer_id=offer.offer_id,
    )


def patient_text_contains_duplicate_amount(
    patient_text: str,
    *,
    offer: TargetOffer,
) -> bool:
    amount = _expected_amount(offer)
    if amount is None:
        return False
    return amount in _amounts_in_prose_text(patient_text)


def patient_text_contains_monetary_amount(patient_text: str) -> bool:
    return bool(_amounts_in_prose_text(patient_text))


def code_owned_amounts_for_offers(
    offers: Sequence[TargetOffer],
) -> frozenset[int]:
    """Canonical offer amounts rendered by code for the displayed offer set."""

    amounts: set[int] = set()
    for offer in offers:
        amount = _offer_widget_amount(offer)
        if amount is not None:
            amounts.add(int(amount))
    return frozenset(amounts)


def code_owned_payment_stage_amounts(
    offers: Sequence[TargetOffer],
) -> frozenset[int]:
    """Payment-stage amounts owned by code when stages are appended."""

    amounts: set[int] = set()
    for offer in offers:
        for stage in offer.payment_stages or ():
            if stage.amount is not None:
                amounts.add(int(stage.amount))
    return frozenset(amounts)


def allowed_amounts_for_price_prose_filter(
    displayed_offers: Sequence[TargetOffer],
    *,
    payment_stages_code_appended: bool,
) -> frozenset[int]:
    """Amounts that may remain in model prose on a code-owned price turn."""

    amounts = set(code_owned_amounts_for_offers(displayed_offers))
    if not payment_stages_code_appended:
        amounts.update(code_owned_payment_stage_amounts(displayed_offers))
    return frozenset(amounts)


def _amounts_in_prose_text(text: str) -> set[int]:
    amounts: set[int] = set()
    for match in _PROSE_CURRENCY_RANGE_RE.finditer(text):
        for part in re.split(r"[–—-]", match.group(0)):
            digits = re.sub(r"[^\d]", "", part)
            if digits:
                amounts.add(int(digits))
    for pattern in (_PROSE_CURRENCY_AMOUNT_RE, _CURRENCY_AMOUNT_RE):
        for match in pattern.finditer(text):
            digits = re.sub(r"[^\d]", "", match.group(0))
            if digits:
                amounts.add(int(digits))
    return amounts


def _remove_currency_range_literals(text: str) -> str:
    return _PROSE_CURRENCY_RANGE_RE.sub("", text)


def _remove_currency_literals_for_amounts(text: str, amounts: frozenset[int]) -> str:
    def _replace(match: re.Match[str]) -> str:
        digits = re.sub(r"[^\d]", "", match.group(0))
        if digits and int(digits) in amounts:
            return ""
        return match.group(0)

    cleaned = _PROSE_CURRENCY_AMOUNT_RE.sub(_replace, text)
    return _CURRENCY_AMOUNT_RE.sub(_replace, cleaned)


def _cleanup_price_glue(text: str) -> str:
    cleaned = _PRICE_GLUE_CLEANUP_RE.sub(" ", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ,.—–-")


def _sentence_has_forbidden_amounts(sentence: str, forbidden_amounts: frozenset[int]) -> bool:
    return bool(_amounts_in_prose_text(sentence) & forbidden_amounts)


def _is_pure_price_sentence(sentence: str, forbidden_amounts: frozenset[int]) -> bool:
    if _PROSE_CURRENCY_RANGE_RE.search(sentence):
        if _PACKAGE_CONTINUATION_RE.search(sentence):
            return False
        return bool(_PRICE_ASSERTION_RE.search(sentence)) or bool(
            re.search(r"(?:₽|руб)", sentence, re.IGNORECASE)
        )
    amounts = _amounts_in_prose_text(sentence)
    if not amounts or not amounts.issubset(forbidden_amounts):
        return False
    if _PACKAGE_CONTINUATION_RE.search(sentence):
        return False
    return bool(_PRICE_ASSERTION_RE.search(sentence)) or bool(
        re.search(r"(?:₽|руб)", sentence, re.IGNORECASE)
    )


def _split_sentence_into_clauses(sentence: str) -> list[tuple[str, str]]:
    """Split a sentence into (clause, separator-after-clause) pairs."""

    stripped = sentence.strip()
    if not stripped:
        return []
    parts = _CLAUSE_BOUNDARY_SPLIT_RE.split(stripped)
    if len(parts) == 1:
        return [(parts[0].strip(), "")]
    clauses: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        clause = parts[index].strip()
        separator = ""
        if index + 1 < len(parts) and parts[index + 1] in {",", ";"}:
            separator = parts[index + 1]
            index += 2
        else:
            index += 1
        if clause:
            clauses.append((clause, separator))
    return clauses


def _format_clause_separator(separator: str) -> str:
    if separator == ",":
        return ", "
    if separator == ";":
        return "; "
    return separator


def _join_kept_clause_fragments(fragments: list[tuple[str, str]]) -> str:
    """Join kept clause fragments while preserving original separators."""

    if not fragments:
        return ""
    text = fragments[0][0]
    for index in range(len(fragments) - 1):
        text += _format_clause_separator(fragments[index][1]) + fragments[index + 1][0]
    return text


def _extract_package_continuation(sentence: str) -> str | None:
    match = _PACKAGE_CONTINUATION_RE.search(sentence)
    if match is None:
        return None
    continuation = sentence[match.start() :].strip()
    return continuation or None


def _is_readable_prose_fragment(text: str) -> bool:
    fragment = text.strip()
    if len(fragment) < 8:
        return False
    if _BROKEN_PRICE_FRAGMENT_RE.search(fragment):
        return False
    if _PRICE_ASSERTION_RE.search(fragment) and not re.search(
        r"(?:₽|руб|\d)",
        fragment,
        re.IGNORECASE,
    ):
        return False
    return True


def _strip_forbidden_amounts_from_clause(
    clause: str,
    forbidden_amounts: frozenset[int],
) -> str | None:
    if not _sentence_has_forbidden_amounts(clause, forbidden_amounts):
        return clause.strip()
    if _is_pure_price_sentence(clause, forbidden_amounts):
        continuation = _extract_package_continuation(clause)
        return continuation if continuation and _is_readable_prose_fragment(continuation) else None
    stripped = _remove_currency_range_literals(clause)
    stripped = _remove_currency_literals_for_amounts(stripped, forbidden_amounts)
    stripped = _cleanup_price_glue(stripped)
    continuation = _extract_package_continuation(stripped)
    if continuation and _is_readable_prose_fragment(continuation):
        return continuation
    if stripped and not _sentence_has_forbidden_amounts(stripped, forbidden_amounts):
        return stripped if _is_readable_prose_fragment(stripped) else None
    return None


def _strip_forbidden_amounts_from_sentence(
    sentence: str,
    forbidden_amounts: frozenset[int],
) -> list[str]:
    if not _sentence_has_forbidden_amounts(sentence, forbidden_amounts):
        return [sentence]

    clause_pairs = _split_sentence_into_clauses(sentence)
    if len(clause_pairs) <= 1:
        only_clause = clause_pairs[0][0] if clause_pairs else sentence
        kept = _strip_forbidden_amounts_from_clause(only_clause, forbidden_amounts)
        return [kept] if kept else []

    kept_pairs: list[tuple[str, str]] = []
    for clause_text, separator_after in clause_pairs:
        fragment = _strip_forbidden_amounts_from_clause(clause_text, forbidden_amounts)
        if fragment:
            kept_pairs.append((fragment, separator_after))
    joined = _join_kept_clause_fragments(kept_pairs)
    return [joined] if joined else []


def strip_code_owned_price_claims_from_prose(
    patient_text: str,
    *,
    forbidden_amounts: frozenset[int],
) -> str:
    """Remove code-owned offer/stage amounts from model prose without dropping MD detail."""

    if not patient_text.strip() or not forbidden_amounts:
        return patient_text.strip()

    paragraphs = re.split(r"\n\s*\n", patient_text.strip())
    kept_paragraphs: list[str] = []
    for paragraph in paragraphs:
        parts = _SENTENCE_SPLIT_RE.split(paragraph)
        kept_parts: list[str] = []
        for part in parts:
            sentence = part.strip()
            if not sentence:
                continue
            kept_parts.extend(
                _strip_forbidden_amounts_from_sentence(
                    sentence,
                    forbidden_amounts,
                )
            )
        if kept_parts:
            kept_paragraphs.append(" ".join(kept_parts))
    return "\n\n".join(kept_paragraphs).strip()


def strip_unauthorized_price_claims_from_prose(
    patient_text: str,
    *,
    allowed_amounts: frozenset[int],
) -> str:
    """Remove only unauthorized monetary amounts; keep promo/installment prose."""

    if not patient_text.strip():
        return patient_text.strip()

    paragraphs = re.split(r"\n\s*\n", patient_text.strip())
    kept_paragraphs: list[str] = []
    for paragraph in paragraphs:
        parts = _SENTENCE_SPLIT_RE.split(paragraph)
        kept_parts: list[str] = []
        for part in parts:
            sentence = part.strip()
            if not sentence:
                continue
            if _FORBIDDEN_TOTAL_LINE_RE.search(sentence):
                continue
            amounts = _amounts_in_prose_text(sentence)
            if not amounts or amounts.issubset(allowed_amounts):
                kept_parts.append(sentence)
                continue
            forbidden = frozenset(amounts - allowed_amounts)
            kept_parts.extend(
                _strip_forbidden_amounts_from_sentence(sentence, forbidden)
            )
        if kept_parts:
            kept_paragraphs.append(" ".join(kept_parts))
    return "\n\n".join(kept_paragraphs).strip()


from config import COMPARISON_QUERY_RE, PRICE_LOOKUP_RE
from contracts.answer_plan import AspectKind
from core.answer_planner import detect_aspects_regex

_PAYMENT_TOPIC_RE = re.compile(
    r"(?:рассроч|оплат\w*\s+по\s+(?:част|этап)|оплат\w*\s+потом|кредит)",
    re.I | re.U,
)
_INCLUDED_TOPIC_RE = re.compile(
    r"(?:под\s+ключ|что\s+входит|входит\s+в\s+(?:акци|стоим|цен)|не\s+входит|"
    r"в\s+(?:эту|данную)\s+сумму\s+вход)",
    re.I | re.U,
)
_WARRANTY_TOPIC_RE = re.compile(r"гарант\w*", re.I | re.U)
_PAIN_TOPIC_RE = re.compile(
    r"(?:больно|боюсь|страш|страх|анестез|обезбол|безболезнен|седац|наркоз|во\s+сне)",
    re.I | re.U,
)
_DURATION_TOPIC_RE = re.compile(
    r"(?:сколько\s+(?:длит|времени|по\s+времени)|длительн|срок\w*|месяц\w*|недел\w*)",
    re.I | re.U,
)
_PROMOTION_TOPIC_RE = re.compile(r"скидк|акци", re.I | re.U)
_CONSULTATION_TOPIC_RE = re.compile(r"консультац", re.I | re.U)


def _promotion_topic_requested(user_message: str) -> bool:
    return bool(_PROMOTION_TOPIC_RE.search(user_message or ""))


def is_pure_price_only_request(user_message: str) -> bool:
    """True when free-text user message asks only about price, not mixed commercial axes."""

    text = (user_message or "").strip()
    if not text:
        return False
    if re.search(
        r"(?:сколько\s+стоит|стоимост\w*|цен\w*).+?(?:\s+и\s+|\s*,\s+)",
        text,
        re.I | re.U,
    ):
        return False
    aspects = tuple(detect_aspects_regex(text))
    supplemental = [aspect for aspect in aspects if aspect not in {"price", "overview"}]
    if supplemental:
        return False
    if _promotion_topic_requested(text):
        return False
    return "price" in aspects or bool(PRICE_LOOKUP_RE.search(text))


def resolve_pure_code_owned_monetary_request(
    user_message: str,
    *,
    nav_ref: str | None = None,
    current_ui_scope_action: object | None = None,
    current_ui_service_action: object | None = None,
    pending_price_clarify_active: bool = False,
) -> bool:
    """True when the turn is a pure code-owned monetary request (text or governed UI)."""

    if is_pure_price_only_request(user_message):
        return True

    from contracts.ui_scope_action import UiScopeAction, parse_ui_scope_ref
    from contracts.ui_service_action import UiServiceAction
    from core.one_call_payment_stages_policy import governed_payment_stages_ui_ref

    if governed_payment_stages_ui_ref(nav_ref):
        return True

    scope_action = current_ui_scope_action
    if scope_action is None and nav_ref:
        scope_action = parse_ui_scope_ref(nav_ref)
    if isinstance(scope_action, UiScopeAction):
        return True

    if isinstance(current_ui_service_action, UiServiceAction) and pending_price_clarify_active:
        return True

    return False


def should_fully_suppress_model_prose_for_code_owned_surface(
    *,
    pure_code_owned_monetary_request: bool,
    has_monetary_surface: bool,
    materialized_public_price: bool,
    nav_ref: str | None,
    no_public_price_line_turn: bool,
) -> bool:
    """Full model-prose suppression on pure code-owned monetary turns."""

    if not pure_code_owned_monetary_request or not has_monetary_surface:
        return False
    if no_public_price_line_turn:
        return False
    if materialized_public_price:
        return True
    from core.one_call_payment_stages_policy import governed_payment_stages_ui_ref

    return governed_payment_stages_ui_ref(nav_ref)


def _clause_matches_aspect(clause: str, aspect: AspectKind) -> bool:
    low = clause.casefold()
    if aspect == "payment":
        return bool(_PAYMENT_TOPIC_RE.search(low))
    if aspect == "included":
        return bool(_INCLUDED_TOPIC_RE.search(low))
    if aspect == "warranty":
        return bool(_WARRANTY_TOPIC_RE.search(low))
    if aspect == "pain":
        return bool(_PAIN_TOPIC_RE.search(low))
    if aspect == "duration":
        return bool(_DURATION_TOPIC_RE.search(low))
    if aspect == "comparison":
        return bool(COMPARISON_QUERY_RE.search(clause))
    if aspect == "stages":
        return "этап" in low
    return False


def _clause_matches_supplemental_request(clause: str, user_message: str) -> bool:
    aspects = tuple(detect_aspects_regex(user_message))
    requested = [aspect for aspect in aspects if aspect not in {"price", "overview"}]
    if any(_clause_matches_aspect(clause, aspect) for aspect in requested):
        return True
    if _promotion_topic_requested(user_message) and _PROMOTION_TOPIC_RE.search(clause):
        return True
    return False


def _filter_sentence_for_supplemental_request(sentence: str, user_message: str) -> str:
    stripped = sentence.strip()
    if not stripped:
        return ""
    if _clause_matches_supplemental_request(stripped, user_message):
        return stripped
    clauses = _split_sentence_into_clauses(stripped)
    if not clauses:
        return ""
    kept_fragments = [
        (clause, separator)
        for clause, separator in clauses
        if _clause_matches_supplemental_request(clause, user_message)
    ]
    if not kept_fragments:
        return ""
    rebuilt = _join_kept_clause_fragments(kept_fragments)
    return rebuilt if _is_readable_prose_fragment(rebuilt) else ""


def _is_payment_continuation_sentence(sentence: str, user_message: str) -> bool:
    aspects = tuple(detect_aspects_regex(user_message))
    if "payment" not in aspects:
        return False
    low = sentence.casefold()
    return bool(re.search(r"оформлен|консультац", low))


def _filter_paragraph_for_supplemental_request(paragraph: str, user_message: str) -> str:
    sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(paragraph) if part.strip()]
    kept_sentences: list[str] = []
    for sentence in sentences:
        filtered = _filter_sentence_for_supplemental_request(sentence, user_message)
        if filtered:
            kept_sentences.append(filtered)
            continue
        if kept_sentences and _is_payment_continuation_sentence(sentence, user_message):
            kept_sentences.append(sentence.strip())
    return " ".join(kept_sentences).strip()


def filter_price_turn_supplemental_prose(patient_text: str, user_message: str) -> str:
    """Keep model prose only for explicitly requested non-price commercial axes."""

    text = (patient_text or "").strip()
    if not text:
        return ""
    if is_pure_price_only_request(user_message):
        return ""

    kept_paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        filtered = _filter_paragraph_for_supplemental_request(paragraph, user_message)
        if filtered:
            kept_paragraphs.append(filtered)
    return "\n\n".join(kept_paragraphs).strip()


def assemble_price_turn_visible_text(
    *,
    price_line: str,
    patient_text: str,
    marketing_suffix: str,
) -> str:
    parts: list[str] = []
    if price_line.strip():
        parts.append(price_line.strip())
    if patient_text:
        parts.append(patient_text)
    if marketing_suffix.strip():
        parts.append(marketing_suffix.strip())
    return "\n\n".join(parts)


def enrich_price_line_with_mandatory_conditions(
    price_line: str,
    offers: Sequence[TargetOffer],
) -> str:
    """Append code-owned mandatory price disclaimers from structured offer fields."""

    from core.one_call_offer_commercial_blocks import build_price_conditions_block

    line = price_line.strip()
    if not line or not offers:
        return line
    conditions: list[str] = []
    exclude_condition = build_price_conditions_block(
        tuple(offers),
        skip_when_excludes_in_package_block=False,
    )
    if exclude_condition:
        conditions.append(exclude_condition)
    service_condition = _service_condition_text(tuple(offers))
    if service_condition:
        normalized_existing = {item.casefold() for item in conditions}
        if service_condition.casefold() not in normalized_existing:
            conditions.append(service_condition)
    if not conditions:
        return line
    line_cf = line.casefold()
    unique_conditions = [
        item for item in conditions if item.casefold() not in line_cf
    ]
    if not unique_conditions:
        return line
    return f"{line}\n\n" + "\n\n".join(unique_conditions)


def paragraph_contains_monetary_expression(paragraph: str) -> bool:
    text = (paragraph or "").strip()
    if not text:
        return False
    if _PROSE_CURRENCY_RANGE_RE.search(text):
        return True
    if _PROSE_CURRENCY_AMOUNT_RE.search(text):
        return True
    if _PROSE_THOUSANDS_RUB_RE.search(text):
        return True
    if _PROSE_PAYMENT_AMOUNT_RE.search(text):
        return True
    return False


def filter_monetary_paragraphs_from_model_prose(patient_text: str) -> tuple[str, int]:
    """Drop whole model paragraphs that contain currency-linked monetary expressions."""

    text = (patient_text or "").strip()
    if not text:
        return "", 0
    paragraphs = re.split(r"\n\s*\n", text)
    kept: list[str] = []
    removed = 0
    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if not stripped:
            continue
        if paragraph_contains_monetary_expression(stripped):
            removed += 1
            continue
        kept.append(stripped)
    return "\n\n".join(kept).strip(), removed


def record_monetary_prose_filter_meta(
    *,
    removed_paragraph_count: int = 0,
    fully_suppressed: bool = False,
    partial_answer: bool = False,
) -> None:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return
        if removed_paragraph_count > 0:
            request.ctx["monetary_prose_filter_triggered"] = True
            request.ctx["monetary_prose_paragraphs_removed"] = int(removed_paragraph_count)
        if fully_suppressed:
            request.ctx["monetary_prose_full_suppression"] = True
        if partial_answer:
            request.ctx["monetary_prose_partial_answer"] = True
    except Exception:
        return


def apply_model_prose_policy_for_code_owned_monetary_surface(
    patient_body: str,
    *,
    user_message: str,
    has_monetary_surface: bool,
    materialized_public_price: bool,
    pure_code_owned_monetary_request: bool = False,
    nav_ref: str | None = None,
    no_public_price_line_turn: bool = False,
) -> tuple[str, int, bool]:
    """Single paragraph-level policy for all code-owned monetary surfaces.

    Returns (filtered_text, removed_paragraph_count, partial_answer).
    """

    body = (patient_body or "").strip()
    if not has_monetary_surface:
        return body, 0, False
    if should_fully_suppress_model_prose_for_code_owned_surface(
        pure_code_owned_monetary_request=pure_code_owned_monetary_request,
        has_monetary_surface=has_monetary_surface,
        materialized_public_price=materialized_public_price,
        nav_ref=nav_ref,
        no_public_price_line_turn=no_public_price_line_turn,
    ):
        return "", 0, False
    filtered, removed = filter_monetary_paragraphs_from_model_prose(body)
    partial_answer = removed > 0 and not filtered.strip()
    return filtered, removed, partial_answer
