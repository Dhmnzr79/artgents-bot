"""Widget presentation (v1) and integration policy contracts."""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

WIDGET_PRESENTATION_SCHEMA_VERSION = 1
WIDGET_INTEGRATION_SCHEMA_VERSION = 1

FORBIDDEN_PRESENTATION_KEYS = frozenset(
    {
        "packId",
        "pack_id",
        "clientId",
        "apiBase",
        "allowedOrigins",
        "allowed_origins",
    }
)

LEGACY_SNAKE_WIDGET_KEYS = frozenset(
    {
        "bot_name",
        "online_label",
        "welcome_text",
        "starter_prompts",
        "video_aspect",
        "demo_launcher",
        "launcher_cta_label",
        "launcher_subtitle",
        "launcher_teaser",
        "launcher_tagline",
        "launcher_teaser_text",
        "launcher_mobile_cta_label",
    }
)

_CAMEL_CASE_RE = re.compile(r"^[a-z][a-zA-Z0-9]*$")


class WidgetConfigValidationError(ValueError):
    """Raised when widget_config.json fails v1 validation."""

    def __init__(self, client_id: str, field: str, message: str) -> None:
        self.client_id = client_id
        self.field = field
        self.message = message
        super().__init__(f"{client_id}:widget_config.json:{field}:{message}")


class WidgetIntegrationValidationError(ValueError):
    """Raised when widget_integration.json fails validation."""

    def __init__(self, client_id: str, field: str, message: str) -> None:
        self.client_id = client_id
        self.field = field
        self.message = message
        super().__init__(f"{client_id}:widget_integration.json:{field}:{message}")


class _WidgetStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WidgetStarterPromptV1(_WidgetStrictModel):
    label: str
    q: str | None = None
    videoKey: str | None = None
    soon: StrictBool | None = None

    @field_validator("label", mode="after")
    @classmethod
    def _label_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty")
        return value


class WidgetPresentationV1(_WidgetStrictModel):
    schemaVersion: Literal[1]
    botName: str
    onlineLabel: str
    welcomeText: str | None
    starterPrompts: list[WidgetStarterPromptV1]
    videoAspect: Literal["horizontal", "vertical"]
    demoLauncher: StrictBool
    launcherCtaLabel: str
    launcherSubtitle: str | None
    launcherTeaser: StrictBool
    launcherTagline: str | None = None
    launcherTeaserText: str | None = None
    launcherMobileCtaLabel: str | None = None

    @field_validator("botName", "onlineLabel", "launcherCtaLabel", mode="after")
    @classmethod
    def _required_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty")
        return value

    @model_validator(mode="after")
    def _launcher_teaser_text_required_when_enabled(self) -> WidgetPresentationV1:
        if self.launcherTeaser and not (self.launcherTeaserText or "").strip():
            raise ValueError("launcher_teaser_text_required")
        return self


class WidgetIntegrationV1(_WidgetStrictModel):
    schemaVersion: Literal[1]
    allowedOrigins: list[str]

    @field_validator("allowedOrigins", mode="after")
    @classmethod
    def _origins_non_empty_exact(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("empty")
        out: list[str] = []
        seen: set[str] = set()
        for raw in value:
            normalized = parse_exact_allowed_origin(raw)
            if normalized in seen:
                raise ValueError("duplicate_origin")
            seen.add(normalized)
            out.append(normalized)
        return out


def parse_exact_allowed_origin(value: str) -> str:
    """Validate and normalize one allowed origin (strict; no scheme inference)."""
    v = (value or "").strip()
    if not v or "*" in v:
        raise ValueError("invalid_origin")
    lowered = v.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError("scheme_required")
    if v.endswith("/") and not v.endswith("://"):
        v = v.rstrip("/")
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("invalid_scheme")
    if parsed.username or parsed.password:
        raise ValueError("credentials_forbidden")
    if parsed.query or parsed.fragment:
        raise ValueError("query_or_fragment_forbidden")
    if parsed.path and parsed.path != "/":
        raise ValueError("path_forbidden")
    if not parsed.hostname:
        raise ValueError("hostname_required")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def normalize_allowed_origin(value: str) -> str:
    """Best-effort normalize for runtime Origin/Referer headers (already full URLs)."""
    try:
        return parse_exact_allowed_origin(value)
    except ValueError:
        return ""


def _reject_legacy_and_forbidden_keys(
    raw: dict[str, Any],
    *,
    client_id: str,
    path: str,
) -> None:
    for key in raw:
        if key in FORBIDDEN_PRESENTATION_KEYS:
            raise WidgetConfigValidationError(client_id, key, f"forbidden_key:{path}")
        if key in LEGACY_SNAKE_WIDGET_KEYS:
            raise WidgetConfigValidationError(client_id, key, "legacy_snake_case_forbidden")
        if "_" in key and key not in ("schemaVersion",):
            raise WidgetConfigValidationError(client_id, key, "snake_case_forbidden")
        if not _CAMEL_CASE_RE.match(key) and key != "schemaVersion":
            raise WidgetConfigValidationError(client_id, key, "invalid_key_format")


def validate_widget_presentation_document(
    raw: Any,
    *,
    client_id: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise WidgetConfigValidationError(client_id, "root", "must_be_object")
    _reject_legacy_and_forbidden_keys(raw, client_id=client_id, path="presentation")
    try:
        model = WidgetPresentationV1.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = first.get("loc") or ()
        field = ".".join(str(part) for part in loc) if loc else "root"
        code = first.get("type") or "invalid"
        raise WidgetConfigValidationError(client_id, field, str(code)) from exc
    return model.model_dump(mode="json")


def validate_widget_integration_document(
    raw: Any,
    *,
    client_id: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise WidgetIntegrationValidationError(client_id, "root", "must_be_object")
    for key in raw:
        if "_" in key and key != "schemaVersion":
            raise WidgetIntegrationValidationError(client_id, key, "snake_case_forbidden")
    try:
        model = WidgetIntegrationV1.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = first.get("loc") or ()
        field = ".".join(str(part) for part in loc) if loc else "root"
        code = first.get("type") or "invalid"
        raise WidgetIntegrationValidationError(client_id, field, str(code)) from exc
    return model.model_dump(mode="json")


def parse_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
