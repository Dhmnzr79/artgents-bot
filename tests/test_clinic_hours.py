from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.clinic_hours import is_clinic_open_now
from core.client_config_loader import tone_to_txt_dict
from lead_service import resolve_lead_submit_message


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    tz = ZoneInfo("Asia/Kamchatka")
    return datetime(year, month, day, hour, minute, tzinfo=tz).astimezone(timezone.utc)


def test_demo_has_no_hours_config() -> None:
    assert is_clinic_open_now("demo") is None


def test_resolve_lead_submit_message_demo_ignores_hours() -> None:
    txt = tone_to_txt_dict("demo")
    with patch("lead_service.is_clinic_open_now", return_value=False):
        msg = resolve_lead_submit_message("demo", txt)
    assert "демо-бот" in msg.lower()


def test_resolve_lead_submit_message_demo_uses_demo_stub_copy() -> None:
    txt = tone_to_txt_dict("demo")
    with patch("lead_service.is_clinic_open_now", return_value=True):
        msg = resolve_lead_submit_message("demo", txt)
    assert "демо-бот" in msg.lower()
