"""One private form submission through the existing D2 reservation and lead sender."""
import json
from datetime import datetime,timezone
from uuid import uuid4

from contracts.booking_form import BookingFormInput, BookingFormReceipt
from contracts.lead_consent import LeadConsentReceipt
from contracts.response_plan import SessionKey
from core.client_config_loader import tone_to_txt_dict
from core.d2_dialogue_store import D2DialogueStore
from core.d2_storage import dialogue_store_path
from core.d2_tenant_snapshot import d2_clients_root,load_d2_tenant_snapshot
from core.d2_usage_limits import ClientUsageAdmission,load_usage_limits,visitor_bucket
from core.lead_consent import lead_consent_definition
from core.widget_catalog import catalog_navigation
from lead_service import handle_lead,resolve_lead_submit_message
from session import normalize_phone

FORM_CHECKBOX_TEXT = 'Даю согласие на обработку имени и телефона для связи по моей заявке.'
UNCONFIRMED = 'Подтверждение отправки заявки пока не получено. Пожалуйста, свяжитесь с клиникой напрямую.'


def booking_form_definition(client_id):
    definition = lead_consent_definition(client_id)
    return dict(client_id=client_id,checkbox_text=definition.checkbox_text if definition else FORM_CHECKBOX_TEXT,
        definition_fingerprint=definition.fingerprint if definition else None,
        consent_url=definition.consent_url if definition else None,policy_url=definition.policy_url if definition else None)


def submit_booking_form(raw, *, client_id, peer_ip=None):
    form = BookingFormInput.model_validate(raw)
    if form.client_id != client_id:
        raise ValueError('form_owner_mismatch')
    visitor_bucket(form.visitor_id,peer_ip)
    phone = normalize_phone(form.phone)
    if not phone:
        raise ValueError('bad_phone')
    key = SessionKey(client_id=client_id,sid=form.sid)
    path = dialogue_store_path(client_id)
    path.parent.mkdir(parents=True,exist_ok=True)
    with D2DialogueStore(path) as store:
        fingerprint = store.private_fingerprint(json.dumps(form.model_dump(mode='json'),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
        reservation = store.reserve_request(key,request_id=form.request_id,request_fingerprint=fingerprint)
        if reservation.completed is not None:
            if not isinstance(reservation.completed,BookingFormReceipt):
                raise ValueError('form_request_kind_mismatch')
            return reservation.completed.public_result()
        try:
            limits = load_usage_limits(client_id,clients_root=d2_clients_root())
            usage = ClientUsageAdmission(store._connection,limits=limits,client_id=client_id,sid=form.sid,
                request_id=form.request_id,visitor_id=form.visitor_id,peer_ip=peer_ip) if limits else None
            if usage:usage.message()
            definition = lead_consent_definition(client_id)
            if not form.consent.accepted:
                raise ValueError('lead_consent_required')
            if definition is not None and form.consent.definition_fingerprint != definition.fingerprint:
                raise ValueError('lead_consent_changed')
            snapshot = load_d2_tenant_snapshot(client_id,clients_root=d2_clients_root())
            selection = None
            if form.selection is not None:
                if form.selection.catalog_version != snapshot.fingerprint:
                    raise ValueError('catalog_changed')
                nav = catalog_navigation(snapshot)
                service = snapshot.bundle.services.get(form.selection.service_id)
                if service is None or not service.active or not any(service_id==form.selection.service_id for section in nav.sections for service_id in section.service_ids):
                    raise ValueError('form_service_unavailable')
                offer = next((o for o in snapshot.bundle.offers if o.offer_id==form.selection.offer_id),None)
                if form.selection.offer_id is not None and (offer is None or not offer.active or offer.service_id!=form.selection.service_id
                        or (offer.option_id is not None and not any(o.option_id==offer.option_id and o.active for o in service.options))):
                    raise ValueError('form_offer_unavailable')
                from core.d2_price_offer import d2_offer_variant_label
                selection = dict(service_id=form.selection.service_id,service_name=service.name,
                    offer_id=form.selection.offer_id,variant_name=d2_offer_variant_label(snapshot.bundle,offer) if offer else '')
            now = datetime.now(timezone.utc)
            consent = LeadConsentReceipt(client_id=client_id,sid=form.sid,request_id=form.request_id,
                accepted_at=now,definition=definition) if definition is not None else None
            if usage:usage.lead()
            receipt = BookingFormReceipt(client_id=client_id,sid=form.sid,request_id=form.request_id,
                request_fingerprint=fingerprint,effect_id=uuid4().hex,status='pending',consent_receipt=consent,
                selection=form.selection,accepted_at=now,message=UNCONFIRMED)
            store.save_form_pending(receipt)
        except Exception:
            store.abandon_request(key,request_id=form.request_id,request_fingerprint=fingerprint)
            raise
        # Only this in-memory closure sees private contact fields. No automatic resend.
        payload = dict(name=form.name,phone=phone,situation_note=form.wish,sid=form.sid,
                       request_id=form.request_id,selection=selection)
        try:
            result,status = handle_lead(payload,client_id=client_id,consent_receipt=consent)
            delivery = result.get('delivery_status') or result.get('delivery')
            outcome = 'sent' if status==200 and delivery in {'email','email_pg_enqueue_failed','queued'} else 'demo_stub' if status==200 and delivery=='demo_stub' else 'failed' if delivery in {'email_smtp_not_configured','email_no_recipients','email_smtp_invalid_config'} else 'unknown'
        except Exception:
            outcome = 'unknown'
        text = resolve_lead_submit_message(client_id,tone_to_txt_dict(client_id)) if outcome in {'sent','demo_stub'} else UNCONFIRMED if outcome=='unknown' else 'Не удалось отправить заявку. Пожалуйста, свяжитесь с клиникой напрямую.'
        receipt = receipt.model_copy(update={'status':outcome,'message':text})
        store.finish_form(receipt)
        return receipt.public_result()
