"""Validate the explicitly configured chat endpoint; never choose a fallback."""
from urllib.parse import urlparse

import config
from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError, validate_alibaba_chat_transport_config,
    validate_alibaba_chat_api_key,
)


def validate_chat_transport_config():
    base = (config.CHAT_BASE_URL or "").strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.hostname == "api.deepseek.com":
        if base not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            raise AlibabaEndpointConfigurationError("chat_base_url_invalid")
        return base, validate_alibaba_chat_api_key(config.CHAT_API_KEY)
    return validate_alibaba_chat_transport_config()
