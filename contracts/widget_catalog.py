"""Authored navigation; services/offers and financial data stay in the D2 pack."""
from pydantic import Field, model_validator
from contracts.response_plan import ResponsePlanModel
from contracts.response_schema import NonBlankStr, ResponseDataCatalog


class WidgetCatalogSection(ResponsePlanModel):
    section_id: NonBlankStr
    title: NonBlankStr
    subtitle: NonBlankStr
    service_ids: tuple[NonBlankStr, ...] = Field(min_length=1)


class WidgetCatalogOfferGroup(ResponsePlanModel):
    title: NonBlankStr
    offer_ids: tuple[NonBlankStr, ...] = Field(min_length=1)


class WidgetCatalogNavigation(ResponsePlanModel):
    version: int = Field(ge=1, le=1)
    client_id: NonBlankStr
    label: NonBlankStr
    unpriced_text: NonBlankStr
    sections: tuple[WidgetCatalogSection, ...] = Field(min_length=1)
    service_subtitles: dict[NonBlankStr, NonBlankStr]
    show_sections: bool = True
    offer_groups: dict[NonBlankStr, tuple[WidgetCatalogOfferGroup, ...]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_refs(self):
        sections = [s.section_id for s in self.sections]
        services = [ref for s in self.sections for ref in s.service_ids]
        if len(set(sections)) != len(sections) or len(set(services)) != len(services):
            raise ValueError('catalog_duplicate_reference')
        if set(self.service_subtitles) != set(services):
            raise ValueError('catalog_service_subtitle_refs_invalid')
        return self

    def bind(self,client_id,bundle: ResponseDataCatalog):
        if self.client_id!=client_id:
            raise ValueError('widget_catalog_owner_mismatch')
        active_service_ids={key for key,service in bundle.services.items() if service.active}
        if {ref for section in self.sections for ref in section.service_ids}!=set(active_service_ids):
            raise ValueError('widget_catalog_service_refs_invalid')
        for service_id,groups in self.offer_groups.items():
            if service_id not in active_service_ids or not groups:
                raise ValueError('widget_catalog_group_service_invalid')
            service=bundle.services[service_id]
            expected={offer.offer_id for offer in bundle.offers if offer.active and offer.service_id==service_id
                      and (offer.option_id is None or any(option.option_id==offer.option_id and option.active is not False for option in service.options))}
            actual=[offer_id for group in groups for offer_id in group.offer_ids]
            if len(actual)!=len(set(actual)) or set(actual)!=expected:
                raise ValueError('widget_catalog_group_offer_refs_invalid')
        return self
