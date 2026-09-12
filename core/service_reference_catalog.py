"""Immutable full service reference catalog snapshot for ONE_CALL stable prefix (Stage 5.1B)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from contracts.response_schema import ResponseSchemaBundle

_SERVICE_REFERENCE_CATALOG_HEADER = "=== SERVICE_REFERENCE_CATALOG ==="


@dataclass(frozen=True, slots=True)
class ServiceReferenceCatalogSnapshot:
    """Deterministic full-catalog identity snapshot — active and inactive services."""

    canonical_json: str
    service_ids: frozenset[str] = field(default_factory=frozenset)
    active_service_ids: frozenset[str] = field(default_factory=frozenset)
    inactive_service_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> ServiceReferenceCatalogSnapshot:
        rows: list[dict[str, object]] = []
        all_ids: list[str] = []
        active_ids: list[str] = []
        inactive_ids: list[str] = []
        for service_id in sorted(bundle.services):
            service = bundle.services[service_id]
            token = str(service_id)
            all_ids.append(token)
            is_active = bool(service.active)
            if is_active:
                active_ids.append(token)
            else:
                inactive_ids.append(token)
            title = str(service.name or service_id).strip()
            aliases = [str(a).strip() for a in service.aliases if str(a).strip()]
            rows.append(
                {
                    "service_id": token,
                    "title": title,
                    "aliases": aliases,
                    "active": is_active,
                }
            )
        canonical = {"services": rows}
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        return cls(
            canonical_json=canonical_json,
            service_ids=frozenset(all_ids),
            active_service_ids=frozenset(active_ids),
            inactive_service_ids=frozenset(inactive_ids),
        )

    def block_text(self) -> str:
        return f"{_SERVICE_REFERENCE_CATALOG_HEADER}\n{self.canonical_json}"

    def is_active(self, service_id: str | None) -> bool | None:
        if service_id is None:
            return None
        token = str(service_id).strip()
        if token not in self.service_ids:
            return None
        return token in self.active_service_ids
