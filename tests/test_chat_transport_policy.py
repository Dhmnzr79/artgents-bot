import pytest
import config
from core.chat_transport_policy import validate_chat_transport_config


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
