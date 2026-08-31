from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.response_plan import ComposerResult, RouteModePair, SessionKey
from contracts.response_plan_adapter import (
    ADAPTER_ERROR_CODES,
    ResponsePlanAdapterConditionAuthority,
    ResponsePlanAdapterError,
    ResponsePlanAdapterMaterialAuthority,
    ResponsePlanAdapterRouteAuthority,
    ResponsePlanAdapterSessionState,
    ResponsePlanAdapterTerminalAuthority,
    StrictTargetComposerEnvelope,
    assert_not_legacy_composer_output,
    envelope_to_composer_result,
)
from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_response_verifier import TargetVerifiedComposedResponse


def test_adapter_error_codes_closed_set() -> None:
    assert len(ADAPTER_ERROR_CODES) == 19
    with pytest.raises(ResponsePlanAdapterError) as exc:
        raise ResponsePlanAdapterError("adapter_client_mismatch")
    assert exc.value.code == "adapter_client_mismatch"


def test_adapter_error_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="adapter_error_code_invalid"):
        ResponsePlanAdapterError("not_a_real_code")  # type: ignore[arg-type]


def test_material_authority_is_frozen_and_extra_forbid() -> None:
    from tests.test_response_plan_production_adapter import _bound_package, _materials, _spec

    authority = ResponsePlanAdapterMaterialAuthority(
        source_client_id="demo",
        bound_package=_bound_package(spec=_spec(), materials=_materials()),
    )
    with pytest.raises(ValidationError):
        authority.source_client_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ResponsePlanAdapterMaterialAuthority(source_client_id="demo", bound_package=object(), extra=True)  # type: ignore[call-arg]


def test_session_state_model_is_frozen_and_extra_forbid() -> None:
    state = ResponsePlanAdapterSessionState(last_service_id="all_on_4")
    with pytest.raises(ValidationError):
        state.last_service_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ResponsePlanAdapterSessionState(last_service_id="all_on_4", unknown=True)  # type: ignore[call-arg]


def test_route_authority_rejects_invalid_pair() -> None:
    with pytest.raises(ValidationError):
        ResponsePlanAdapterRouteAuthority(route="ANSWER", mode="medical_terminal")


def test_terminal_authority_rejects_clarify() -> None:
    with pytest.raises(ValidationError):
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="CLARIFY",
            mode="standard",
            authority="governed_ui",
            display_text="text",
        )


def test_strict_composer_envelope_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        StrictTargetComposerEnvelope(route="ANSWER", mode="standard", patient_text="x", extra=1)  # type: ignore[call-arg]


def test_strict_composer_envelope_duplicate_requested_facts_rejected() -> None:
    with pytest.raises(ValidationError):
        StrictTargetComposerEnvelope(
            route="ANSWER",
            mode="standard",
            patient_text="x",
            requested_fact_ids=("fact_a", "fact_a"),
        )


def test_envelope_to_composer_result_admin_invariants() -> None:
    result = envelope_to_composer_result(
        StrictTargetComposerEnvelope(route="ADMIN", mode="standard", patient_text=None)
    )
    assert result.patient_text is None
    with pytest.raises(ResponsePlanAdapterError) as exc:
        envelope_to_composer_result(
            StrictTargetComposerEnvelope(route="ADMIN", mode="standard", patient_text="nope")
        )
    assert exc.value.code == "adapter_composer_envelope_invalid"


def test_envelope_rejects_contacts_mode() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        envelope_to_composer_result(
            StrictTargetComposerEnvelope(route="ANSWER", mode="contacts", patient_text=None)
        )
    assert exc.value.code == "adapter_composer_envelope_invalid"


def test_legacy_unverified_composer_output_rejected() -> None:
    legacy = TargetUnverifiedComposedResponse(
        text="legacy",
        spec=object(),  # type: ignore[arg-type]
        selected_followups=object(),  # type: ignore[arg-type]
        selected_cta_key=None,
    )
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output(legacy)
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_legacy_verified_composer_output_rejected() -> None:
    legacy = TargetVerifiedComposedResponse(
        text="legacy",
        spec=object(),  # type: ignore[arg-type]
        selected_followups=object(),  # type: ignore[arg-type]
        selected_cta_key=None,
    )
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output(legacy)
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_legacy_direct_fact_ids_envelope_rejected() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output({"direct_fact_ids": ["installment_12"], "text": "x"})
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_adapter_modules_have_no_forbidden_imports() -> None:
    repo = Path(__file__).resolve().parents[1]
    modules = (
        repo / "contracts" / "response_plan_adapter.py",
        repo / "core" / "response_plan_production_adapter.py",
    )
    forbidden = {"app", "session", "flask", "one_call_presentation_pass", "re"}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden), module


def test_adapter_not_imported_by_production_runtime() -> None:
    repo = Path(__file__).resolve().parents[1]
    forbidden_snippets = (
        "response_plan_production_adapter",
        "response_plan_adapter",
    )
    runtime_roots = (repo / "app.py", repo / "core" / "sales_one_plus_turn.py")
    for path in runtime_roots:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(snippet in text for snippet in forbidden_snippets), path
