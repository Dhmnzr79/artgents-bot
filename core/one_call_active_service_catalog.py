"""Immutable active service catalog snapshot for ONE_CALL stable prefix (§6.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from contracts.response_schema import ResponseSchemaBundle

_ACTIVE_SERVICE_CATALOG_HEADER = "=== ACTIVE_SERVICE_CATALOG ==="


def _option_is_active(option) -> bool:
    return option.active is not False


def _collect_allowed_patient_stages(bundle: ResponseSchemaBundle) -> tuple[str, ...]:
    stages: set[str] = set()
    for service_id in sorted(bundle.services):
        service = bundle.services[service_id]
        if not service.active:
            continue
        if service.selection.stage:
            stages.update(service.selection.stage)
        for option in service.options:
            if not _option_is_active(option):
                continue
            if option.selection is not None and option.selection.stage:
                stages.update(option.selection.stage)
    return tuple(sorted(stages))


@dataclass(frozen=True, slots=True)
class ActiveServiceCatalogSnapshot:
    """Deterministic active-service catalog derived from bundle — never reload by client_id."""

    canonical_json: str
    active_service_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_patient_stages: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> ActiveServiceCatalogSnapshot:
        rows: list[dict[str, str]] = []
        active_ids: list[str] = []
        for service_id in sorted(bundle.services):
            service = bundle.services[service_id]
            if not service.active:
                continue
            token = str(service_id)
            active_ids.append(token)
            title = str(service.name or service_id).strip()
            rows.append({"service_id": token, "title": title})
        allowed_stages = _collect_allowed_patient_stages(bundle)
        canonical = {
            "services": rows,
            "allowed_patient_stages": list(allowed_stages),
        }
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        return cls(
            canonical_json=canonical_json,
            active_service_ids=frozenset(active_ids),
            allowed_patient_stages=frozenset(allowed_stages),
        )

    def block_text(self) -> str:
        return f"{_ACTIVE_SERVICE_CATALOG_HEADER}\n{self.canonical_json}"
