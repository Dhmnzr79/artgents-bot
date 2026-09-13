from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.lead_email import normalize_recipients, send_lead_email, smtp_configured
from lead_service import handle_lead

_FULL_SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "bot@example.com",
    "SMTP_PASSWORD": "secret",
    "SMTP_FROM": "bot@example.com",
}


def _send_test_lead() -> tuple[bool, str]:
    return send_lead_email(
        client_id="demo",
        lead_cfg={"recipients": ["admin@demo.ru"], "subject_template": "Заявка"},
        name="Иван",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="s1",
        request_id="r1",
        captured_at="2026-01-01T00:00:00+00:00",
    )


def test_normalize_recipients_skips_placeholders() -> None:
    assert normalize_recipients(["admin@clinic.ru", "REPLACE_WITH_EMAIL"]) == ["admin@clinic.ru"]
    assert normalize_recipients([]) == []


def test_handle_lead_demo_stub() -> None:
    payload, status = handle_lead(
        {
            "name": "Мария",
            "phone": "+79001234567",
            "intent": "lead",
        },
        client_id="demo",
    )
    assert status == 200
    assert payload["delivery"] == "demo_stub"


@patch.dict(
    "os.environ",
    {
        "SMTP_HOST": "mail.artgents.ru",
        "SMTP_PORT": "465",
        "SMTP_USE_SSL": "1",
        "SMTP_FROM": "bot@artgents.ru",
        "SMTP_USER": "bot@artgents.ru",
        "SMTP_PASSWORD": "secret",
    },
    clear=False,
)
@patch("core.lead_email._connect_smtp")
def test_send_lead_email_ssl_success(mock_connect: MagicMock) -> None:
    mock_smtp = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_smtp

    ok, status = send_lead_email(
        client_id="demo",
        lead_cfg={
            "recipients": ["admin@demo.ru"],
            "subject_template": "Заявка с демо-бота",
        },
        name="Иван",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="s1",
        request_id="r1",
        captured_at="2026-01-01T00:00:00+00:00",
    )

    assert ok is True
    assert status == "email"
    mock_connect.assert_called_once_with("mail.artgents.ru", 465)
    mock_smtp.login.assert_called_once_with("bot@artgents.ru", "secret")
    mock_smtp.send_message.assert_called_once()


@patch.dict(
    "os.environ",
    {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_FROM": "bot@example.com",
        "SMTP_USER": "bot@example.com",
        "SMTP_PASSWORD": "secret",
    },
    clear=False,
)
@patch("core.lead_email._connect_smtp")
def test_send_lead_email_starttls_success(mock_connect: MagicMock) -> None:
    mock_smtp = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_smtp

    ok, status = send_lead_email(
        client_id="demo",
        lead_cfg={
            "recipients": ["admin@demo.ru"],
            "subject_template": "Заявка с демо-бота",
        },
        name="Иван",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="s1",
        request_id="r1",
        captured_at="2026-01-01T00:00:00+00:00",
    )

    assert ok is True
    assert status == "email"
    mock_connect.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()


@patch.dict("os.environ", _FULL_SMTP_ENV, clear=True)
def test_send_lead_email_no_recipients() -> None:
    ok, status = send_lead_email(
        client_id="demo",
        lead_cfg={"recipients": ["REPLACE_WITH_DEMO_ADMIN_EMAIL"]},
        name="",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="",
        request_id="",
        captured_at="2026-01-01T00:00:00+00:00",
    )
    assert ok is False
    assert status == "email_no_recipients"


@patch("pg_sink.enqueue_lead")
@patch("lead_service.send_lead_email", return_value=(True, "email"))
@patch(
    "lead_service.load_lead_config",
    return_value={"recipients": ["admin@demo.ru"], "subject_template": "Заявка"},
)
@patch("lead_service.leads_mode", return_value="email")
@patch("lead_service.leads_enabled", return_value=True)
def test_handle_lead_demo_email_no_pii_in_pg(
    _enabled, _mode, _cfg, mock_send, mock_pg_enqueue
) -> None:
    payload, status = handle_lead(
        {
            "name": "Анна",
            "phone": "+79007654321",
            "intent": "lead",
            "sid": "sid-1",
            "request_id": "req-1",
        },
        client_id="demo",
    )
    assert status == 200
    assert payload["delivery"] == "email"
    assert payload["delivery_status"] == "email"
    mock_send.assert_called_once()
    mock_pg_enqueue.assert_not_called()


@patch("pg_sink.enqueue_lead")
@patch("lead_service.send_lead_email", return_value=(True, "email"))
@patch("lead_service.load_lead_config", return_value={"store_in_postgres": True, "recipients": ["admin@demo.ru"]})
@patch("lead_service.leads_mode", return_value="email")
@patch("lead_service.leads_enabled", return_value=True)
def test_handle_lead_pg_row_has_no_pii_when_store_enabled(
    _enabled, _mode, mock_cfg, mock_send, mock_pg_enqueue
) -> None:
    payload, status = handle_lead(
        {
            "name": "Анна",
            "phone": "+79007654321",
            "intent": "lead",
            "sid": "sid-1",
            "request_id": "req-1",
        },
        client_id="demo",
    )
    assert status == 200
    mock_pg_enqueue.assert_called_once()
    row = mock_pg_enqueue.call_args[0][0]
    assert row["delivery_status"] == "email"
    assert row["name"] is None
    assert row["phone"] is None


@pytest.mark.parametrize("missing", tuple(_FULL_SMTP_ENV))
@patch("core.lead_email._connect_smtp")
def test_partial_smtp_config_fails_closed_without_connect(
    mock_connect: MagicMock, missing: str
) -> None:
    env = dict(_FULL_SMTP_ENV)
    env.pop(missing)
    with patch.dict("os.environ", env, clear=True):
        assert smtp_configured() is False
        ok, status = _send_test_lead()
    assert ok is False
    assert status == "email_smtp_not_configured"
    mock_connect.assert_not_called()


@patch("core.lead_email._connect_smtp")
def test_smtp_entirely_absent_fails_closed_without_connect(mock_connect: MagicMock) -> None:
    with patch.dict("os.environ", {}, clear=True):
        ok, status = _send_test_lead()
    assert ok is False
    assert status == "email_smtp_not_configured"
    mock_connect.assert_not_called()


@pytest.mark.parametrize("port", ("not-a-port", "0", "65536"))
@patch("core.lead_email._connect_smtp")
def test_invalid_smtp_port_fails_closed_without_connect(
    mock_connect: MagicMock, port: str
) -> None:
    env = {**_FULL_SMTP_ENV, "SMTP_PORT": port}
    with patch.dict("os.environ", env, clear=True):
        ok, status = _send_test_lead()
    assert ok is False
    assert status == "email_smtp_invalid_config"
    mock_connect.assert_not_called()


@patch.dict("os.environ", _FULL_SMTP_ENV, clear=True)
@patch("core.lead_email._connect_smtp", side_effect=OSError("SMTP unavailable"))
def test_smtp_connection_failure_returns_delivery_status(_mock_connect: MagicMock) -> None:
    ok, status = _send_test_lead()
    assert ok is False
    assert status == "email_failed"
