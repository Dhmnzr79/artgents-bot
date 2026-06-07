"""Overview period bounds for admin dashboard."""
from __future__ import annotations

from admin_dashboard.app import _overview_period_bounds


def test_overview_period_today() -> None:
    d0, d1, key, label = _overview_period_bounds("today")
    assert key == "today"
    assert label == "сегодня"
    assert (d1 - d0).days == 1


def test_overview_period_week() -> None:
    d0, d1, key, label = _overview_period_bounds("week")
    assert key == "week"
    assert label == "7 дней"
    assert (d1 - d0).days == 7


def test_overview_period_unknown_defaults_today() -> None:
    _, _, key, _ = _overview_period_bounds("year")
    assert key == "today"
