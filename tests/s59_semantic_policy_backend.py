"""Offline simulator for S59 simplified semantic Verifier policy (tests only)."""

from __future__ import annotations

from core.target_response_verifier import (
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
)

_PERSONAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("у вас волчан", "у вас волчан"),
    ("у вас диагноз", "диагноз"),
    ("вам нельзя", "вам нельзя"),
    ("вам можно", "вам можно"),
    ("вам точно под", "вам точно"),
    ("вам нужно выбрать", "вам нужно выбрать"),
    ("лучше выбрать имплант", "лучше выбрать имплант"),
    ("имплант, а не мост", "имплант, а не мост"),
)

_ABSURD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("100% безопас", "100% безопас"),
    ("гарантированно без осложнений", "гарантированно без осложнений"),
    ("полностью без риска", "полностью без риска"),
)


def _issue(kind: str, span: str) -> TargetSemanticIssue:
    return TargetSemanticIssue(kind=kind, offending_span=span)  # type: ignore[arg-type]


def _span_for_pattern(text: str, pattern: str) -> str:
    idx = text.lower().index(pattern)
    return text[idx : idx + len(pattern)]


class S59SemanticPolicyBackend:
    """Rule-based stand-in for live semantic Verifier under S59 policy."""

    def __init__(self) -> None:
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> TargetSemanticAssessment:
        self.invocations.append(invocation)
        text = invocation.candidate_text
        lower = text.lower()
        corpus = invocation.cached_full_context.lower()
        issues: list[TargetSemanticIssue] = []

        for pattern, _span in _PERSONAL_PATTERNS:
            if pattern in lower:
                issues.append(
                    _issue("personal_medical_conclusion", _span_for_pattern(text, pattern))
                )
                break

        for pattern, _span in _ABSURD_PATTERNS:
            if pattern in lower:
                issues.append(
                    _issue(
                        "material_external_medical_claim",
                        _span_for_pattern(text, pattern),
                    )
                )
                break

        if (
            "беремен" in lower
            and "не противопоказ" in lower
            and "беремен" in corpus
            and "противопоказ" in corpus
        ):
            issues.append(
                _issue(
                    "material_external_medical_claim",
                    _span_for_pattern(text, "не противопоказ"),
                )
            )

        if "999 999" in text or "999999" in text.replace(" ", ""):
            issues.append(_issue("unsupported_clinic_claim", "999 999"))

        if not any(issue.kind == "material_external_medical_claim" for issue in issues):
            for token, _span in (
                ("иммунн", "иммун"),
                ("аутоиммун", "аутоиммун"),
                ("лактац", "лактац"),
                ("гормон", "гормон"),
                ("заживл", "заживл"),
                ("родов", "родов"),
                ("грудн", "грудн"),
            ):
                if token in lower:
                    issues.append(
                        _issue("minor_external_detail", _span_for_pattern(text, token))
                    )

            if "компенсирован" in lower and "компенсирован" not in corpus:
                issues.append(
                    _issue(
                        "minor_external_detail",
                        _span_for_pattern(text, "компенсирован"),
                    )
                )

        return TargetSemanticAssessment(issues=tuple(issues))
