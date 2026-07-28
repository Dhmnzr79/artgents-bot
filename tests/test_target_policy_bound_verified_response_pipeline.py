from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path

import pytest

import core.target_policy_bound_verified_response_pipeline as pipeline_module
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_spec import TargetResponseSpec
from core.target_composer_executor import TargetComposerExecutorError
from core.target_composer_request import TargetComposerRequestError
from core.target_response_policy import TargetResponsePolicyBuildError
from core.target_response_verifier import TargetResponseVerificationError
from core.target_policy_bound_verified_response_pipeline import (
    run_target_offline_policy_bound_verified_response_pipeline,
)
from core.target_spec_offline_response_package import TargetSpecOfflineResponsePackageError


def _spec() -> TargetResponseSpec:
    return TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "service_id": "service_one",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "forbidden_topics": ("diagnosis",),
            "required_fact_ids": (),
            "required_components": ("content",),
            "followup_source": "content",
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )


def _arguments() -> dict[str, object]:
    return {
        "policy_request": object(),
        "bundle": object(),
        "doctor_catalog": object(),
        "external_index": object(),
        "consultation_values": object(),
        "brand_term": None,
        "strategy_context": object(),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "md_root": Path("md"),
        "cached_full_context": TargetCachedFullContext(
            corpus_text="---BEGIN DOC:a.md---\nx\n---END DOC:a.md---",
            document_count=1,
            document_paths=("a.md",),
            sha256="placeholder",
        ),
        "include_initial_block": False,
        "include_consultation_close": False,
        "include_cta": False,
        "user_message": "message",
        "tone": object(),
        "composer_backend": object(),
        "semantic_backend": object(),
    }


def test_public_signature_and_function_is_exact_straight_line() -> None:
    assert list(
        inspect.signature(run_target_offline_policy_bound_verified_response_pipeline).parameters
    ) == [
        "policy_request",
        "bundle",
        "doctor_catalog",
        "external_index",
        "consultation_values",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "md_root",
        "cached_full_context",
        "include_initial_block",
        "include_consultation_close",
        "include_cta",
        "user_message",
        "tone",
        "composer_backend",
        "semantic_backend",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
        "turn_topic",
        "effective_scope",
        "client_id",
        "contact_fields",
    ]
    assert inspect.signature(
        run_target_offline_policy_bound_verified_response_pipeline
    ).return_annotation == "TargetVerifiedComposedResponse"
    source = inspect.getsource(run_target_offline_policy_bound_verified_response_pipeline)
    tree = ast.parse(source)
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert not any(
        isinstance(node, (ast.If, ast.IfExp, ast.Try, ast.Raise, ast.Match, ast.While, ast.For))
        for node in ast.walk(function)
    )
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    called_names = [
        call.func.id for call in calls if isinstance(call.func, ast.Name)
    ]
    assert called_names == [
        "run_target_offline_policy_bound_verified_response_pipeline_with_selection",
    ]


def test_pipeline_passes_exact_objects_in_order_and_returns_verifier_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _arguments()
    spec = _spec()
    bound = object()
    verified = object()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def build_spec(*args: object, **kwargs: object) -> object:
        calls.append(("s33", args, kwargs))
        return spec

    def assemble(*args: object, **kwargs: object) -> object:
        calls.append(("s34", args, kwargs))
        return bound

    def run_pipeline(*args: object, **kwargs: object) -> object:
        calls.append(("s39", args, kwargs))
        return verified

    monkeypatch.setattr(pipeline_module, "build_target_response_spec", build_spec)
    monkeypatch.setattr(
        pipeline_module,
        "assemble_target_spec_offline_response_package",
        assemble,
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_target_offline_verified_response_pipeline",
        run_pipeline,
    )
    monkeypatch.setattr(
        pipeline_module,
        "extract_target_session_selection",
        lambda _bound: pipeline_module.TargetMaterializedSessionSelection(
            shown_fact_ids=(),
            shown_amplifier_refs=(),
            shown_consultation_value_refs=(),
        ),
    )

    result = run_target_offline_policy_bound_verified_response_pipeline(**values)  # type: ignore[arg-type]

    assert result is verified
    assert [name for name, _args, _kwargs in calls] == ["s33", "s34", "s39"]
    assert calls[0][1] == (values["policy_request"],)
    assert calls[0][2] == {}
    assert calls[1][1] == (
        values["bundle"],
        values["doctor_catalog"],
        values["external_index"],
        values["consultation_values"],
    )
    assert calls[1][2] == {
        "spec": spec,
        "brand_term": values["brand_term"],
        "strategy_context": values["strategy_context"],
        "semantic_context": values["semantic_context"],
        "today": values["today"],
        "md_root": values["md_root"],
        "include_initial_block": values["include_initial_block"],
        "include_consultation_close": values["include_consultation_close"],
        "include_cta": values["include_cta"],
        "marketing_scenarios": (),
        "shown_fact_ids": (),
        "shown_amplifier_refs": (),
        "shown_consultation_value_refs": (),
        "turn_topic": None,
        "effective_scope": None,
        "client_id": "demo",
    }
    assert calls[2][1] == (
        bound,
        values["bundle"],
        values["doctor_catalog"],
        values["consultation_values"],
    )
    assert calls[2][2] == {
        "user_message": values["user_message"],
        "md_root": values["md_root"],
        "cached_full_context": values["cached_full_context"],
        "tone": values["tone"],
        "composer_backend": values["composer_backend"],
        "semantic_backend": values["semantic_backend"],
        "contact_fields": None,
        "client_id": "demo",
    }


@pytest.mark.parametrize(
    ("failed_stage", "error"),
    [
        ("s33", TargetResponsePolicyBuildError("response_policy_request_invalid", "x")),
        (
            "s34",
            TargetSpecOfflineResponsePackageError("spec_package_permission_forbidden", "cta"),
        ),
        ("s39", TargetComposerRequestError("composer_request_package_invalid", "x")),
        (
            "s39_late",
            TargetResponseVerificationError(
                "target_verifier_semantic_rejected",
                ("topic_scope_ok",),
            ),
        ),
    ],
)
def test_existing_typed_errors_propagate_unchanged_and_short_circuit(
    monkeypatch: pytest.MonkeyPatch,
    failed_stage: str,
    error: Exception,
) -> None:
    spec = _spec()
    bound = object()
    calls: list[str] = []

    def build_spec(*args: object, **kwargs: object) -> object:
        calls.append("s33")
        if failed_stage == "s33":
            raise error
        return spec

    def assemble(*args: object, **kwargs: object) -> object:
        calls.append("s34")
        if failed_stage == "s34":
            raise error
        return bound

    def run_pipeline(*args: object, **kwargs: object) -> object:
        calls.append("s39")
        raise error

    monkeypatch.setattr(pipeline_module, "build_target_response_spec", build_spec)
    monkeypatch.setattr(
        pipeline_module,
        "assemble_target_spec_offline_response_package",
        assemble,
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_target_offline_verified_response_pipeline",
        run_pipeline,
    )

    with pytest.raises(type(error)) as caught:
        run_target_offline_policy_bound_verified_response_pipeline(**_arguments())  # type: ignore[arg-type]
    assert caught.value is error
    assert calls == {
        "s33": ["s33"],
        "s34": ["s33", "s34"],
        "s39": ["s33", "s34", "s39"],
        "s39_late": ["s33", "s34", "s39"],
    }[failed_stage]


def test_import_firewall_excludes_legacy_provider_runtime_and_live_hooks() -> None:
    source = Path(
        "core/target_policy_bound_verified_response_pipeline.py"
    ).read_text(encoding="utf-8")
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    forbidden = (
        "numeric_fact_gate",
        "verifier_verdict",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "router",
        "search",
        "llm",
    )
    legacy_session_imports = (
        "from session import",
        "import session",
    )
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    assert all(token not in import_lines for token in forbidden)
    assert all(token not in import_lines for token in legacy_session_imports)
    assert " import cache" not in import_lines
    assert " from cache" not in import_lines
    assert "pytest.skip" not in source
    assert "xfail" not in source
