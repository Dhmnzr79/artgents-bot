"""Read-only widget catalog from one captured tenant snapshot; no dialogue/store."""
from datetime import date

from contracts.response_plan import D2FrozenPriceBlock
from contracts.widget_catalog import WidgetCatalogNavigation
from core.d2_commercial_plan import resolve_d2_commercial_plan, resolve_d2_commercial_compatibility
from core.d2_price_offer import build_d2_price_offer_row
from core.d2_snapshot_sources import _commercial_authority
from core.d2_tenant_snapshot import build_d2_model_view


def catalog_navigation(snapshot):
    raw = dict(snapshot.files).get('target_response/widget_catalog.json')
    if raw is None:
        raise ValueError('widget_catalog_missing')
    nav = WidgetCatalogNavigation.model_validate_json(raw)
    active = {key for key, service in snapshot.bundle.services.items() if service.active}
    return nav.bind(snapshot.client_id,active)


def build_widget_catalog(snapshot, *, as_of: date):
    nav = catalog_navigation(snapshot)
    bundle, client_id = snapshot.bundle, snapshot.client_id
    view = build_d2_model_view(snapshot)
    authority = _commercial_authority(client_id, view, bundle)
    terms = {item.offer_id:item for item in view.published_terms}
    documents = {doc.content_ref:doc for doc in snapshot.content}
    services = []
    for section in nav.sections:
        for service_id in section.service_ids:
            service = bundle.services[service_id]
            doc = documents.get(service.content_ref)
            if doc is None or doc.source_client_id != client_id or service_id not in doc.allowed_service_ids:
                raise ValueError('widget_catalog_content_unavailable')
            summary = next((s.display_text for s in doc.sections if s.section_ref == 'korotko'), doc.display_text)
            # Skip only the section heading; descriptions remain authored MD.
            description = '\n'.join(line for line in summary.splitlines() if not line.startswith('#')).strip()
            offers = [offer for offer in bundle.offers if offer.active and offer.service_id == service_id
                and (offer.option_id is None or any(o.option_id == offer.option_id and o.active for o in service.options))]
            offers.sort(key=lambda offer: (
                offer.price.mode == 'no_public_price',
                getattr(offer.price,'amount',getattr(offer.price,'min_amount',0)),offer.offer_id))
            rows = tuple(build_d2_price_offer_row(offer,bundle=bundle,client_id=client_id,
                                                terms=terms[offer.offer_id]) for offer in offers)
            def price_block(selected_rows, presentation):
                return D2FrozenPriceBlock(source_client_id=client_id, rows=selected_rows,
                    presentation=presentation).model_dump(mode='json')
            details = {}
            for row in rows:
                commercial = resolve_d2_commercial_plan(authority=authority,bundle=bundle,as_of=as_of,
                    service_id=service_id,offer_id=row.offer_id,include_packages=True,skip_shown=False,max_promo=None)
                parts = []
                for promo in commercial.promo_blocks:
                    parts.append(dict(kind='text',text=promo.display_text,price_owned=True,price_section='promotion'))
                for package in (commercial.price_booster_block,commercial.also_list_block):
                    if package is not None:
                        parts.append(dict(kind='text',text=package.body_text,price_owned=True,price_section='benefits'))
                published = frozenset((row.offer_id,*(p.fact_id for p in commercial.promo_blocks)))
                for block in resolve_d2_commercial_compatibility(authority=authority,published_ids=published):
                    parts.append(dict(kind='text',text=block.explanation_text,price_owned=True,price_section='conditions'))
                details[row.offer_id] = {'price':price_block((row,),'detail'),'parts':parts}
            services.append(dict(service_id=service_id,section_id=section.section_id,name=service.name,
                aliases=service.aliases,description=description,subtitle=nav.service_subtitles[service_id],
                price=price_block(rows,'detail' if len(rows)==1 else 'options') if rows else None,
                details=details))
    return dict(client_id=client_id,label=nav.label,catalog_version=snapshot.fingerprint,unpriced_text=nav.unpriced_text,
        sections=[s.model_dump(mode='json') for s in nav.sections],services=services)
