"""Pure target brand-term resolution (S25, offline and unwired)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import TargetBrand, TargetBrandCatalog


@dataclass(frozen=True, slots=True)
class TargetBrandResolution:
    brand_id: str
    brand: TargetBrand


class TargetBrandResolutionError(ValueError):
    """Typed error for invalid or ambiguous S25 brand terms."""

    def __init__(
        self,
        code: str,
        value: object,
        candidate_brand_ids: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.value = value
        self.candidate_brand_ids = candidate_brand_ids
        super().__init__(f"{code}: {value!r}")


def _normalize(value: str) -> str:
    return value.strip().casefold()


def resolve_target_brand_term(
    brand_catalog: TargetBrandCatalog,
    brand_term: str,
) -> TargetBrandResolution | None:
    """Resolve one already-extracted term by authored ID, canonical name, or alias."""

    if not isinstance(brand_term, str) or not brand_term.strip():
        raise TargetBrandResolutionError("brand_resolution_term_invalid", brand_term)

    normalized_term = _normalize(brand_term)
    candidate_brand_ids: list[str] = []
    for brand_id, brand in brand_catalog.brands.items():
        lookup_values = (brand_id, brand.canonical_name, *brand.aliases)
        if any(_normalize(value) == normalized_term for value in lookup_values):
            candidate_brand_ids.append(brand_id)

    if not candidate_brand_ids:
        return None
    if len(candidate_brand_ids) > 1:
        raise TargetBrandResolutionError(
            "brand_resolution_ambiguous",
            brand_term,
            tuple(candidate_brand_ids),
        )

    brand_id = candidate_brand_ids[0]
    return TargetBrandResolution(
        brand_id=brand_id,
        brand=brand_catalog.brands[brand_id].model_copy(deep=True),
    )
