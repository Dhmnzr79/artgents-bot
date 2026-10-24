import pytest
import config
from core.chat_transport_policy import validate_chat_transport_config
from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError, build_openai_compatible_client_kwargs,
)


@pytest.mark.parametrize("url", ["https://api.deepseek.com", "https://api.deepseek.com/v1"])
def test_explicit_deepseek(monkeypatch, url):
    monkeypatch.setattr(config, "CHAT_BASE_URL", url)
    monkeypatch.setattr(config, "CHAT_API_KEY", "fake-key")
    assert validate_chat_transport_config() == (url, "fake-key")


@pytest.mark.parametrize("url", ["http://api.deepseek.com", "https://api.deepseek.com/beta",
    "https://api.deepseek.com/?key=x", "https://wrong.example.com"])
def test_bad_endpoint_has_no_fallback(monkeypatch, url):
    monkeypatch.setattr(config, "CHAT_BASE_URL", url)
    with pytest.raises(RuntimeError):
        validate_chat_transport_config()


@pytest.mark.parametrize("url", ["https://api.tf.selcloud.ru/v1", "https://api.tf.selcloud.ru/v1/"])
def test_selectel_runtime_sdk_and_readiness_share_endpoint_gate(monkeypatch, url):
    from core.prod_readiness import _evaluate_chat_transport

    monkeypatch.setattr(config, "CHAT_BASE_URL", url)
    monkeypatch.setattr(config, "CHAT_API_KEY", "fake-selectel-key")
    assert validate_chat_transport_config() == (url.rstrip("/"), "fake-selectel-key")
    assert build_openai_compatible_client_kwargs() == {
        "base_url": url.rstrip("/"), "api_key": "fake-selectel-key", "max_retries": 0,
    }
    assert _evaluate_chat_transport() == []


@pytest.mark.parametrize("url", [
    "http://api.tf.selcloud.ru/v1", "https://api.tf.selcloud.ru",
    "https://api.tf.selcloud.ru/v1/chat/completions", "https://api.tf.selcloud.ru/beta",
    "https://api.tf.selcloud.ru:443/v1", "https://api.tf.selcloud.ru/v1?key=x",
    "https://api.tf.selcloud.ru/v1#fragment", "https://user:password@api.tf.selcloud.ru/v1",
    "https://api.tf.selcloud.ru.attacker.example/v1", "https://preview.tf.selcloud.ru/v1",
])
def test_selectel_rejects_unapproved_endpoints_before_sdk(monkeypatch, url):
    monkeypatch.setattr(config, "CHAT_BASE_URL", url)
    monkeypatch.setattr(config, "CHAT_API_KEY", "fake-selectel-key")
    with pytest.raises(AlibabaEndpointConfigurationError):
        validate_chat_transport_config()
    with pytest.raises(AlibabaEndpointConfigurationError):
        build_openai_compatible_client_kwargs()


def test_selectel_placeholder_blocks_transport_and_readiness(monkeypatch):
    from core.prod_readiness import _evaluate_chat_transport

    monkeypatch.setattr(config, "CHAT_BASE_URL", "https://api.tf.selcloud.ru/v1")
    monkeypatch.setattr(config, "CHAT_API_KEY", "PASTE_SELECTEL_API_KEY_HERE")
    with pytest.raises(AlibabaEndpointConfigurationError, match="chat_api_key_missing"):
        validate_chat_transport_config()
    assert "chat_api_key_missing" in _evaluate_chat_transport()


@pytest.mark.parametrize("tool_choice", [None, "auto", "none"])
def test_selectel_d2_call_arguments_offline(monkeypatch, tool_choice):
    from types import SimpleNamespace
    import llm
    from core.d2_live_provider import D2HttpProvider, price_tool
    from core.d2_costing import cache_split

    monkeypatch.setattr(config, "CHAT_BASE_URL", "https://api.tf.selcloud.ru/v1")
    monkeypatch.setattr(config, "CHAT_API_KEY", "fake-selectel-key")
    monkeypatch.setattr(llm, "CHAT_BASE_URL", config.CHAT_BASE_URL)
    monkeypatch.setattr(llm, "QWEN_ENABLE_THINKING", False)
    seen = []

    def respond(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Работает"))],
            usage=SimpleNamespace(prompt_tokens=58, completion_tokens=49,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                completion_tokens_details=SimpleNamespace(reasoning_tokens=44)),
        )

    # Record the real D2 -> shared LLM wrapper -> SDK call, without networking
    # or adding dependencies to the repository's isolated offline environment.
    monkeypatch.setattr(llm.chat_client.chat.completions, "create", respond)
    options = {} if tool_choice is None else {"tools": [price_tool()], "tool_choice": tool_choice}
    reply = D2HttpProvider(model="qwen3.8-flash-next")._call(
        ({"role": "user", "content": "Привет"},), **options)

    assert len(seen) == 1
    assert seen[0]["model"] == "qwen3.8-flash-next"
    assert seen[0]["extra_body"] == {"enable_thinking": False}  # Not a provider guarantee.
    assert "response_format" not in seen[0]
    if tool_choice is not None:
        assert seen[0]["tool_choice"] == tool_choice
        assert seen[0]["tools"][0]["function"]["name"] == "show_price"
    assert reply.choices[0].message.content == "Работает"
    assert reply.usage.completion_tokens_details.reasoning_tokens == 44
    assert cache_split(reply.usage, reply.usage.prompt_tokens) == (0, 58)
