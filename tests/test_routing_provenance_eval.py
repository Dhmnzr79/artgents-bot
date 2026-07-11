"""Unit tests for eval-net routing provenance helpers (no LLM)."""
from __future__ import annotations

from evals.v5.smoke_case_runner import (
    extract_routing_provenance,
    validate_routing_provenance,
)


def test_extract_routing_provenance_from_metadata_first() -> None:
    resp = {
        "meta": {
            "answer_path": "composer",
            "metadata_first": {
                "turn_planner_used": True,
                "route_intent": "content",
                "source_route_decision": {"source": "catalog_md", "ref": "implantation__faq__pain.md"},
            },
        }
    }
    prov = extract_routing_provenance(resp)
    assert prov["turn_planner_used"] is True
    assert prov["route_intent"] == "content"
    assert prov["source"] == "catalog_md"
    assert prov["answer_path"] == "composer"


def test_validate_routing_provenance_baseline_ignores_turn_planner() -> None:
    row = {
        "current": {
            "route_intent": "content",
            "source": "none",
            "answer_path": "composer",
            "orch_route": "content",
        },
        "current_diagnostic": {"turn_planner_used": False},
    }
    prov_match = {
        "turn_planner_used": False,
        "route_intent": "content",
        "source": "none",
        "answer_path": "composer",
        "orch_route": "content",
    }
    prov_flipped_planner = dict(prov_match)
    prov_flipped_planner["turn_planner_used"] = True
    assert validate_routing_provenance(row=row, provenance=prov_match, baseline=True) is None
    assert validate_routing_provenance(row=row, provenance=prov_flipped_planner, baseline=True) is None

    prov_bad_route = dict(prov_match)
    prov_bad_route["route_intent"] = "price_concern"
    reason = validate_routing_provenance(row=row, provenance=prov_bad_route, baseline=True)
    assert reason and "provenance.current.route_intent" in reason


def test_validate_routing_provenance_target_skips_diagnostics() -> None:
    row = {
        "target": {
            "route_intent": "content",
            "turn_planner_used": True,
            "source_any": ["none", "catalog_md"],
            "answer_path": "composer",
        },
        "target_forbidden": {
            "route_intent": ["price_concern"],
            "source": ["trust"],
        },
    }
    ok = {
        "turn_planner_used": False,
        "route_intent": "content",
        "source": "none",
        "answer_path": "composer",
        "orch_route": "content",
    }
    assert validate_routing_provenance(row=row, provenance=ok, baseline=False) is None


def test_routing_provenance_ctx_keys_separate_from_widget_meta() -> None:
    from core.metadata_first_observability import (
        _METADATA_FIRST_TURN_KEYS,
        _ROUTING_PROVENANCE_CTX_KEYS,
    )

    for key in _ROUTING_PROVENANCE_CTX_KEYS:
        assert key not in _METADATA_FIRST_TURN_KEYS
    assert "route_intent" in _METADATA_FIRST_TURN_KEYS
