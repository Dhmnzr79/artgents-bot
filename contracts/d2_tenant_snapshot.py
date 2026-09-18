"""Immutable tenant data objects used only by the isolated D2 path."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_plan_materialization import D2AuthoredContentAuthority, D2PublishedOfferTerms
from contracts.response_schema import ResponseSchemaBundle
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot


@dataclass(frozen=True, slots=True)
class D2TenantSnapshot:
    client_id: str
    fingerprint: str
    bundle: ResponseSchemaBundle
    files: tuple[tuple[str, bytes], ...]
    content: tuple[D2AuthoredContentAuthority, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class D2ModelView:
    client_id: str
    fingerprint: str
    active_service_catalog: ActiveServiceCatalogSnapshot
    service_reference_catalog: ServiceReferenceCatalogSnapshot
    commercial_fact_catalog: CommercialFactCatalogSnapshot
    content: tuple[D2AuthoredContentAuthority, ...]
    published_terms: tuple[D2PublishedOfferTerms, ...]
