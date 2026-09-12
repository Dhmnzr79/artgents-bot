"""Fail-closed Alibaba OpenAI-compatible endpoint policy (Stage 3B)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import config

_ALLOWED_EXACT_HOSTS: frozenset[str] = frozenset(
    {
        "dashscope-intl.aliyuncs.com",
        "dashscope.aliyuncs.com",
    }
)
_BLOCKED_HOST_SUFFIXES: tuple[str, ...] = (
    "openai.com",
)
# Singapore MaaS: exactly {workspace}.ap-southeast-1.maas.aliyuncs.com
# workspace = one DNS label, non-empty, [a-z0-9-], no leading/trailing hyphen.
_MAAS_SINGAPORE_HOST_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.ap-southeast-1\.maas\.aliyuncs\.com$"
)


class AlibabaEndpointConfigurationError(RuntimeError):
    """Typed configuration failure before budget reservation or network."""

    def __init__(self, code: str, value: object = None) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


@dataclass(frozen=True, slots=True)
class AlibabaTransportObservability:
    """Non-secret provider routing metadata for logs/artifacts."""

    provider_kind: str = "alibaba_openai_compatible"
    provider_region: str | None = None


def _normalized_host(hostname: str | None) -> str:
    return (hostname or "").strip().lower().rstrip(".")


def _is_allowed_alibaba_host(host: str) -> bool:
    if not host:
        return False
    for blocked in _BLOCKED_HOST_SUFFIXES:
        if host == blocked or host.endswith(f".{blocked}"):
            return False
    if host in _ALLOWED_EXACT_HOSTS:
        return True
    return _MAAS_SINGAPORE_HOST_PATTERN.fullmatch(host) is not None


def validate_alibaba_chat_base_url(base_url: str | None) -> str:
    """Validate CHAT_BASE_URL; return normalized base without trailing slash."""

    raw = (base_url or "").strip()
    if not raw:
        raise AlibabaEndpointConfigurationError("chat_base_url_missing", base_url)
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise AlibabaEndpointConfigurationError("chat_base_url_scheme_invalid", raw)
    if parsed.username or parsed.password:
        raise AlibabaEndpointConfigurationError("chat_base_url_credentials_forbidden", raw)
    if parsed.query or parsed.params or parsed.fragment:
        raise AlibabaEndpointConfigurationError("chat_base_url_query_forbidden", raw)
    host = _normalized_host(parsed.hostname)
    if not _is_allowed_alibaba_host(host):
        raise AlibabaEndpointConfigurationError("chat_base_url_host_blocked", host)
    path = parsed.path or ""
    if path.endswith("/"):
        path = path.rstrip("/")
    return f"https://{host}{path}"


def validate_capability_live_model(model: str) -> str:
    expected = config.SALES_ONE_PLUS_FLASH_MODEL
    observed = (model or "").strip()
    if observed != expected:
        raise AlibabaEndpointConfigurationError("capability_model_invalid", observed)
    return observed


def validate_alibaba_chat_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        raise AlibabaEndpointConfigurationError("chat_api_key_missing")
    return key


def validate_alibaba_chat_transport_config(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str]:
    """Endpoint + API key gate used by production and eval LIVE child."""

    resolved_base = validate_alibaba_chat_base_url(base_url or config.CHAT_BASE_URL)
    resolved_key = validate_alibaba_chat_api_key(api_key or config.CHAT_API_KEY)
    return resolved_base, resolved_key


def observability_from_base_url(base_url: str) -> AlibabaTransportObservability:
    host = _normalized_host(urlparse(base_url).hostname)
    region = None
    if host and "ap-southeast-1" in host:
        region = "ap-southeast-1"
    elif host and "dashscope-intl" in host:
        region = "intl"
    return AlibabaTransportObservability(provider_region=region)


def build_openai_compatible_client_kwargs(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    validate_endpoint: bool = True,
) -> dict[str, object]:
    """Central OpenAI SDK client kwargs: max_retries=0; optional strict Alibaba endpoint gate."""

    if validate_endpoint:
        resolved_base, resolved_key = validate_alibaba_chat_transport_config(
            base_url=base_url,
            api_key=api_key,
        )
    else:
        resolved_key = (api_key or config.CHAT_API_KEY or "").strip()
        resolved_base = (base_url or config.CHAT_BASE_URL or "").strip().rstrip("/")
    kwargs: dict[str, object] = {
        "api_key": resolved_key,
        "max_retries": 0,
    }
    if resolved_base:
        kwargs["base_url"] = resolved_base
    return kwargs
