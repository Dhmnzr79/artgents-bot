"""Non-contact consent definition, frozen UI and acceptance evidence."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

LEAD_CONSENT_ACCEPT_REF = "lead:consent_accept"


class LeadConsentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    checkbox_text: str = Field(min_length=1)
    consent_url: str
    policy_url: str

    @field_validator("version", "checkbox_text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("consent_blank")
        return value

    @field_validator("consent_url", "policy_url")
    @classmethod
    def safe_link(cls, value):
        url = urlsplit(value)
        if (value != value.strip() or url.scheme != "https" or not url.hostname
                or url.username or url.password):
            raise ValueError("consent_https_link_required")
        return value

    @property
    def fingerprint(self):
        return sha256(json.dumps(self.model_dump(), sort_keys=True,
                                 ensure_ascii=False).encode("utf-8")).hexdigest()


class LeadConsentPrompt(LeadConsentDefinition):
    source_client_id: str = Field(min_length=1)
    definition_fingerprint: str = Field(min_length=64, max_length=64)
    accept_ref: Literal["lead:consent_accept"] = LEAD_CONSENT_ACCEPT_REF


class LeadConsentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: str = Field(min_length=1)
    sid: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    accepted_at: datetime
    definition: LeadConsentDefinition

    @field_validator("accepted_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("consent_timestamp_timezone_required")
        return value
