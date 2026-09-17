from __future__ import annotations

from datetime import date

from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_d2_price_scope_selection import _envelope, _sources_with_scope_metadata


def test_frozen_scope_choices_and_text_survive_source_mutation() -> None:
    sources = _sources_with_scope_metadata()
    outcome = resolve_d2_envelope_response(_envelope(None), sources, as_of=date(2026, 9, 18))
    rendered, ui = outcome.rendered_text, outcome.ui_projection
    sources.material_authority.bundle.offers.clear()
    assert render_response_text(outcome.resolved) == rendered
    assert project_response_ui(outcome.resolved) == ui
    assert [item.extent for item in outcome.resolved.d2_price_scope_decision.volume_choices] == [
        "one_tooth", "few_teeth", "full_arch", "unknown"
    ]
