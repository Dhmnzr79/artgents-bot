"""Tenant lead consent configuration; evidence remains in the existing D2 store."""

from contracts.lead_consent import LeadConsentDefinition, LeadConsentReceipt
from core.client_config_loader import load_lead_config, leads_enabled, leads_mode


def lead_consent_definition(client_id: str) -> LeadConsentDefinition | None:
    if not leads_enabled(client_id) or leads_mode(client_id) == "demo_stub":
        return None
    raw = load_lead_config(client_id).get("consent")
    if not isinstance(raw, dict):
        raise ValueError("lead_consent_not_configured")
    try:
        return LeadConsentDefinition.model_validate(raw)
    except ValueError:
        raise ValueError("lead_consent_not_configured") from None


def consent_receipt_matches(receipt, *, client_id, sid, definition):
    return (isinstance(receipt, LeadConsentReceipt) and receipt.client_id == client_id
            and receipt.sid == sid and receipt.definition == definition)


def read_lead_consent_receipt(store, session_key):
    """Dereference the current private booking's proof, never a caller's JSON."""
    from session import mem_get

    definition = lead_consent_definition(session_key.client_id)
    if definition is None:
        return None
    request_id = mem_get(session_key.sid).get("lead_consent_request_id")
    completion = store.read_completion(session_key, request_id) if request_id else None
    receipt = completion.consent_receipt if completion else None
    return receipt if consent_receipt_matches(receipt, client_id=session_key.client_id,
                                              sid=session_key.sid, definition=definition) else None
