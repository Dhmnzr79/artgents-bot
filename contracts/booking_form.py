"""Structured private form input and PII-free durable submission evidence."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from contracts.lead_consent import LeadConsentReceipt


class FormModel(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)


class BookingSelection(FormModel):
    service_id: str = Field(min_length=1,max_length=150)
    offer_id: str | None = Field(default=None,max_length=200)
    catalog_version: str = Field(min_length=64,max_length=64)


class FormConsent(FormModel):
    accepted: StrictBool
    definition_fingerprint: str | None = None


class BookingFormInput(FormModel):
    client_id: str
    sid: str = Field(min_length=1,max_length=120)
    request_id: str = Field(min_length=1,max_length=120)
    visitor_id: str | None = None
    name: str = Field(min_length=1,max_length=120)
    phone: str = Field(min_length=1,max_length=40)
    wish: str = Field(default='',max_length=1500)
    selection: BookingSelection | None = None
    consent: FormConsent


class BookingFormReceipt(FormModel):
    client_id: str
    sid: str
    request_id: str
    request_fingerprint: str = Field(min_length=64,max_length=64)
    effect_id: str
    status: Literal['pending','sent','failed','unknown','demo_stub']
    accepted: Literal[True] = True
    consent_receipt: LeadConsentReceipt | None = None
    selection: BookingSelection | None = None
    accepted_at: datetime
    message: str

    @model_validator(mode='after')
    def receipt_identity(self):
        if self.accepted_at.tzinfo is None or self.accepted_at.utcoffset() is None:
            raise ValueError('form_timestamp_timezone_required')
        if self.consent_receipt is not None and (
            self.consent_receipt.client_id,self.consent_receipt.sid,self.consent_receipt.request_id
        )!=(self.client_id,self.sid,self.request_id):
            raise ValueError('form_consent_owner_mismatch')
        return self

    def public_result(self):
        success = self.status in {'sent','demo_stub'}
        return dict(ok=success,request_id=self.request_id,status=self.status,message=self.message,
                    error_code=None if success else 'submission_'+self.status)
