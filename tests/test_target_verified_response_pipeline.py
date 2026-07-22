from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import core.target_verified_response_pipeline as pipeline_module
from contracts.target_cached_full_context import TargetCachedFullContext
from core.target_composer_executor import TargetComposerExecutorError
from core.target_composer_request import TargetComposerRequestError
from core.target_response_verifier import TargetResponseVerificationError
from core.target_verified_response_pipeline import (
    run_target_offline_verified_response_pipeline,
)


def _arguments() -> dict[str, object]:
    return {
        "bound_package": object(),
        "bundle": object(),
        "doctor_catalog": object(),
        "consultation_values": object(),
        "user_message": "message",
        "md_root": Path("md"),
        "cached_full_context": TargetCachedFullContext(
            corpus_text="---BEGIN DOC:a.md---\nx\n---END DOC:a.md---",
            document_count=1,
            document_paths=("a.md",),
            sha256="placeholder",
        ),
        "tone": object(),
        "composer_backend": object(),
        "semantic_backend": object(),
    }


def test_public_signature_and_function_is_exact_straight_line() -> None:
    assert list(inspect.signature(run_target_offline_verified_response_pipeline).parameters) == [
        "bound_package",
        "bundle",
        "doctor_catalog",
        "consultation_values",
        "user_message",
        "md_root",
        "cached_full_context",
        "tone",
        "composer_backend",
        "semantic_backend",
    ]
    assert inspect.signature(
        run_target_offline_verified_response_pipeline
    ).return_annotation == "TargetVerifiedComposedResponse"
    source = inspect.getsource(run_target_offline_verified_response_pipeline)
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
        "materialize_target_composer_request",
        "execute_target_composer",
        "verify_target_composed_response",
    ]


def test_pipeline_passes_exact_objects_in_order_and_returns_verifier_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _arguments()
    request = object()
    unverified = object()
    verified = object()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def materialize(*args: object, **kwargs: object) -> object:
        calls.append(("s36", args, kwargs))
        return request

    def execute(*args: object, **kwargs: object) -> object:
        calls.append(("s37", args, kwargs))
        return unverified

    def verify(*args: object, **kwargs: object) -> object:
        calls.append(("s38", args, kwargs))
        return verified

    monkeypatch.setattr(pipeline_module, "materialize_target_composer_request", materialize)
    monkeypatch.setattr(pipeline_module, "execute_target_composer", execute)
    monkeypatch.setattr(pipeline_module, "verify_target_composed_response", verify)

    result = run_target_offline_verified_response_pipeline(**values)  # type: ignore[arg-type]

    assert result is verified
    assert [name for name, _args, _kwargs in calls] == ["s36", "s37", "s38"]
    assert calls[0][1] == (
        values["bound_package"],
        values["bundle"],
        values["doctor_catalog"],
        values["consultation_values"],
    )
    assert calls[0][2] == {
        "user_message": values["user_message"],
        "md_root": values["md_root"],
    }
    assert calls[1][1] == (request, values["composer_backend"])
    assert calls[1][2] == {
        "tone": values["tone"],
        "cached_full_context": values["cached_full_context"],
    }
    assert calls[2][1] == (request, unverified)
    assert calls[2][2] == {"semantic_backend": values["semantic_backend"]}


@pytest.mark.parametrize(
    ("failed_stage", "error"),
    [
        ("s36", TargetComposerRequestError("composer_request_package_invalid", "x")),
        ("s37", TargetComposerExecutorError("composer_executor_backend_failed", "X")),
        (
            "s38",
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
    request = object()
    unverified = object()
    calls: list[str] = []

    def materialize(*args: object, **kwargs: object) -> object:
        calls.append("s36")
        if failed_stage == "s36":
            raise error
        return request

    def execute(*args: object, **kwargs: object) -> object:
        calls.append("s37")
        if failed_stage == "s37":
            raise error
        return unverified

    def verify(*args: object, **kwargs: object) -> object:
        calls.append("s38")
        raise error

    monkeypatch.setattr(pipeline_module, "materialize_target_composer_request", materialize)
    monkeypatch.setattr(pipeline_module, "execute_target_composer", execute)
    monkeypatch.setattr(pipeline_module, "verify_target_composed_response", verify)

    with pytest.raises(type(error)) as caught:
        run_target_offline_verified_response_pipeline(**_arguments())  # type: ignore[arg-type]
    assert caught.value is error
    assert calls == {
        "s36": ["s36"],
        "s37": ["s36", "s37"],
        "s38": ["s36", "s37", "s38"],
    }[failed_stage]


def test_import_firewall_excludes_legacy_provider_runtime_and_live_hooks() -> None:
    source = Path("core/target_verified_response_pipeline.py").read_text(encoding="utf-8")
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
        "session",
        "search",
        "llm",
    )
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    assert all(token not in import_lines for token in forbidden)
    assert " import cache" not in import_lines
    assert " from cache" not in import_lines
    assert "pytest.skip" not in source
    assert "xfail" not in source
