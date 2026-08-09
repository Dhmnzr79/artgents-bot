"""Immutable active service catalog snapshot for ONE_CALL stable prefix (§6.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from contracts.response_schema import ResponseSchemaBundle

_ACTIVE_SERVICE_CATALOG_HEADER = "=== ACTIVE_SERVICE_CATALOG ==="


@dataclass(frozen=True, slots=True)
class ActiveServiceCatalogSnapshot:
    """Deterministic active-service catalog derived from bundle — never reload by client_id."""

    canonical_json: str

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> ActiveServiceCatalogSnapshot:
        rows: list[dict[str, str]] = []
        for service_id in sorted(bundle.services):
            service = bundle.services[service_id]
            if not service.active:
                continue
            title = str(service.name or service_id).strip()
            rows.append({"service_id": str(service_id), "title": title})
        canonical_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        return cls(canonical_json=canonical_json)

    def block_text(self) -> str:
        return f"{_ACTIVE_SERVICE_CATALOG_HEADER}\n{self.canonical_json}"
