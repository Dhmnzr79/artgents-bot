"""Catalog-driven brand mention lookup in a patient message (entity lookup only)."""

from __future__ import annotations

import re

from contracts.response_schema import TargetBrandCatalog
from core.target_brand_resolver import TargetBrandResolutionError

_TERM_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_MATCH_BOUNDARY = r"(?<!\w)"
_MATCH_END = r"(?!\w)"


def _normalize_term(value: str) -> str:
    tokens = _TERM_SPLIT_RE.split(value.strip().casefold())
    return " ".join(token for token in tokens if token)


def _normalize_message_for_search(message: str) -> str:
    tokens = _TERM_SPLIT_RE.split(message.strip().casefold())
    return " ".join(token for token in tokens if token)


def _compile_term_pattern(normalized_term: str) -> re.Pattern[str]:
    words = normalized_term.split()
    if not words:
        raise TargetBrandResolutionError("brand_resolution_term_invalid", normalized_term)
    body = r"\s+".join(re.escape(word) for word in words)
    return re.compile(f"{_MATCH_BOUNDARY}{body}{_MATCH_END}", re.UNICODE)


def _build_term_patterns(
    brand_catalog: TargetBrandCatalog,
) -> tuple[tuple[re.Pattern[str], str], ...]:
    alias_owner: dict[str, str] = {}
    entries: list[tuple[str, str]] = []
    for brand_id, brand in brand_catalog.brands.items():
        lookup_values = (brand_id, brand.canonical_name, *brand.aliases)
        for raw in lookup_values:
            normalized = _normalize_term(str(raw))
            if not normalized:
                continue
            owner = alias_owner.get(normalized)
            if owner is not None and owner != brand_id:
                raise TargetBrandResolutionError(
                    "brand_resolution_ambiguous",
                    raw,
                    (owner, brand_id),
                )
            alias_owner[normalized] = brand_id
            entries.append((normalized, brand_id))

    unique_entries = list(dict.fromkeys(entries))
    unique_entries.sort(key=lambda item: (-len(item[0].split()), -len(item[0])))
    return tuple((_compile_term_pattern(term), brand_id) for term, brand_id in unique_entries)


def extract_brand_mentions_from_message(
    brand_catalog: TargetBrandCatalog,
    message: str,
) -> tuple[str, ...]:
    """Return distinct brand_ids in first-mention order from one patient message."""

    if not isinstance(message, str) or not message.strip():
        return ()

    patterns = _build_term_patterns(brand_catalog)
    normalized_message = _normalize_message_for_search(message)
    if not normalized_message:
        return ()

    raw_matches: list[tuple[int, int, str]] = []
    for pattern, brand_id in patterns:
        for match in pattern.finditer(normalized_message):
            start, end = match.span()
            raw_matches.append((start, end, brand_id))

    raw_matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    selected: list[tuple[int, str]] = []
    for start, end, brand_id in raw_matches:
        if any(not (end <= occ_start or start >= occ_end) for occ_start, occ_end in occupied):
            continue
        occupied.append((start, end))
        selected.append((start, brand_id))

    ordered_brand_ids: list[str] = []
    seen_brand_ids: set[str] = set()
    for _, brand_id in sorted(selected, key=lambda item: item[0]):
        if brand_id in seen_brand_ids:
            continue
        seen_brand_ids.add(brand_id)
        ordered_brand_ids.append(brand_id)
    return tuple(ordered_brand_ids)
