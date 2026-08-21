"""Immutable commercial fact identity catalog snapshot (Checkpoint F, unwired until B1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from contracts.response_schema import ResponseSchemaBundle

_COMMERCIAL_FACT_CATALOG_HEADER = "=== COMMERCIAL_FACT_CATALOG ==="


@dataclass(frozen=True, slots=True)
class CommercialFactCatalogSnapshot:
    """Deterministic fact-identity snapshot derived from the current client bundle."""

    canonical_json: str
    fact_ids: frozenset[str] = field(default_factory=frozenset)
    active_fact_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> CommercialFactCatalogSnapshot:
        rows: list[dict[str, object]] = []
        all_ids: list[str] = []
        active_ids: list[str] = []
        for fact_id in sorted(bundle.facts):
            fact = bundle.facts[fact_id]
            token = str(fact_id)
            all_ids.append(token)
            is_active = bool(fact.active)
            if is_active:
                active_ids.append(token)
            rows.append(
                {
                    "fact_id": token,
                    "kind": str(fact.kind),
                    "catalog_label": str(fact.catalog_label),
                    "active": is_active,
                }
            )
        canonical = {"facts": rows}
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        return cls(
            canonical_json=canonical_json,
            fact_ids=frozenset(all_ids),
            active_fact_ids=frozenset(active_ids),
        )

    def block_text(self) -> str:
        return f"{_COMMERCIAL_FACT_CATALOG_HEADER}\n{self.canonical_json}"
