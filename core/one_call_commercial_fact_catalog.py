"""Thin commercial fact identity projection for envelope validation (CP-EXACT-1A)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from contracts.response_schema import ResponseSchemaBundle

if TYPE_CHECKING:
    from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot

_COMMERCIAL_FACT_CATALOG_HEADER = "=== COMMERCIAL_FACT_CATALOG ==="


@dataclass(frozen=True, slots=True)
class CommercialFactCatalogSnapshot:
    """Deterministic fact-identity snapshot for envelope direct_fact_ids validation."""

    canonical_json: str
    fact_ids: frozenset[str] = field(default_factory=frozenset)
    active_fact_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_exact_catalog(
        cls, exact_catalog: ExactCommercialCatalogSnapshot
    ) -> CommercialFactCatalogSnapshot:
        payload = json.loads(exact_catalog.canonical_json)
        rows: list[dict[str, object]] = []
        for row in payload["facts"]:
            rows.append(
                {
                    "fact_id": str(row["fact_id"]),
                    "kind": str(row["kind"]),
                    "catalog_label": str(row["catalog_label"]),
                    "active": bool(row.get("active", True)),
                }
            )
        canonical = {"facts": rows}
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        return cls(
            canonical_json=canonical_json,
            fact_ids=exact_catalog.fact_ids,
            active_fact_ids=exact_catalog.active_fact_ids,
        )

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> CommercialFactCatalogSnapshot:
        from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot

        return cls.from_exact_catalog(ExactCommercialCatalogSnapshot.from_bundle(bundle))

    def block_text(self) -> str:
        return f"{_COMMERCIAL_FACT_CATALOG_HEADER}\n{self.canonical_json}"
