"""Authored navigation; services/offers and financial data stay in the D2 pack."""
from pydantic import Field, model_validator
from contracts.response_plan import ResponsePlanModel
from contracts.response_schema import NonBlankStr


class WidgetCatalogSection(ResponsePlanModel):
    section_id: NonBlankStr
    title: NonBlankStr
    subtitle: NonBlankStr
    service_ids: tuple[NonBlankStr, ...] = Field(min_length=1)


class WidgetCatalogNavigation(ResponsePlanModel):
    version: int = Field(ge=1, le=1)
    client_id: NonBlankStr
    label: NonBlankStr
    unpriced_text: NonBlankStr
    sections: tuple[WidgetCatalogSection, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_refs(self):
        sections = [s.section_id for s in self.sections]
        services = [ref for s in self.sections for ref in s.service_ids]
        if len(set(sections)) != len(sections) or len(set(services)) != len(services):
            raise ValueError('catalog_duplicate_reference')
        return self

    def bind(self,client_id,active_service_ids):
        if self.client_id!=client_id:
            raise ValueError('widget_catalog_owner_mismatch')
        if {ref for section in self.sections for ref in section.service_ids}!=set(active_service_ids):
            raise ValueError('widget_catalog_service_refs_invalid')
        return self
