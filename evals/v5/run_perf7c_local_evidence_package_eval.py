"""Offline PERF-7C local Evidence Package eval runner.

Loads the frozen matrix (``evals/v5/perf7c_local_evidence_package_eval_matrix.json``), builds the
real lexical paragraph index and cached FullContext from the canonical client MD pack, constructs a
typed ``TargetComposerRequest`` per scenario, and calls the real, unmodified
``build_target_evidence_package`` -- no Planner/Boundary/Composer/Verifier, no LLM, no network, no
provider transport, no Flask/server. Deterministic: running this script twice against an unchanged
client pack produces byte-identical categorical/source-ID results (only ``timing_ms``/``generated_at``
differ, both excluded from the determinism comparison the accompanying test performs).

Never writes a query, a generated answer, a session id, PII, or a contact value anywhere -- not to
stdout, not to the optional ``--output`` result JSON. The result artifact holds only scenario ids,
expected/actual source IDs, categorical verdicts, counts, timings, fingerprints, and error codes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.target_response_spec import TargetResponseSpec  # noqa: E402
from core.target_cached_full_context import build_target_cached_full_context  # noqa: E402
from core.target_composer_request import TargetComposerEvidenceBlock, TargetComposerRequest  # noqa: E402
from core.target_evidence_package_builder import (  # noqa: E402
    TargetEvidencePackageBuilderError,
    build_target_evidence_package,
)
from core.target_lexical_paragraph_index import build_target_lexical_paragraph_index  # noqa: E402
from core.target_response_followup_policy import TargetResponseFollowupSelection  # noqa: E402

DEFAULT_MATRIX_PATH = _EVAL_DIR / "perf7c_local_evidence_package_eval_matrix.json"

_PLACEHOLDER_TEXT_BY_KIND = {
    "content": "synthetic content placeholder text for eval scenario only, never real MD prose",
    "external_kb": "synthetic external_kb placeholder text for eval scenario only",
    "offer": "synthetic offer placeholder text for eval scenario only",
    "commercial_fact": "synthetic commercial fact placeholder text for eval scenario only",
    "doctor": "synthetic doctor placeholder text for eval scenario only",
    "external_doctor": "synthetic external doctor placeholder text for eval scenario only",
    "consultation": "synthetic consultation placeholder text for eval scenario only",
    "clinic_contact": "synthetic clinic contact placeholder text for eval scenario only",
}
_MUST_PRESERVE_EXACT_BY_KIND = {
    "content": False,
    "external_kb": False,
    "offer": True,
    "commercial_fact": True,
    "doctor": True,
    "external_doctor": True,
    "consultation": False,
    "clinic_contact": True,
}


class EvalHarnessError(RuntimeError):
    pass


def _build_evidence_block(raw: dict[str, Any]) -> TargetComposerEvidenceBlock:
    kind = raw["kind"]
    ref = raw["ref"]
    topics = tuple(raw.get("topics") or ())
    fact_ids = tuple(raw.get("fact_ids") or ())
    return TargetComposerEvidenceBlock(
        kind=kind,
        ref=ref,
        topics=topics,
        fact_ids=fact_ids,
        text=_PLACEHOLDER_TEXT_BY_KIND[kind],
        must_preserve_exact=_MUST_PRESERVE_EXACT_BY_KIND[kind],
    )


def _build_request(scenario: dict[str, Any]) -> TargetComposerRequest:
    builder_input = scenario["builder_input"]
    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": builder_input["spec"]["response_mode"],
            "service_id": builder_input["spec"]["service_id"],
            "tone_key": "commercial_warm",
            "allowed_topics": tuple(builder_input["spec"]["allowed_topics"]),
            "forbidden_topics": tuple(builder_input["spec"]["forbidden_topics"]),
            "required_fact_ids": tuple(builder_input["spec"]["required_fact_ids"]),
            "required_components": tuple(builder_input["spec"]["required_components"]),
        }
    )
    blocks = tuple(_build_evidence_block(b) for b in builder_input["evidence_blocks"])
    return TargetComposerRequest(
        user_message=scenario["synthetic_query"],
        spec=spec,
        evidence_blocks=blocks,
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )


def _classify(scenario: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    """Compare actual outcome against the frozen expectation. Never mutates the expectation."""

    expected = scenario["expected"]
    findings: dict[str, Any] = {
        "scenario_id": scenario["scenario_id"],
        "scenario_class": scenario["scenario_class"],
        "verdict": None,
        "critical_false_narrow": False,
        "safe_over_fallback": False,
        "unexpected_scoped_target": False,
        "session_contamination": False,
        "missing_md_refs": [],
        "offer_id_mismatch": False,
        "fact_id_mismatch": False,
        "doctor_id_mismatch": False,
        "policy_section_mismatch": False,
        "session_ref_mismatch": False,
        "builder_exception": None,
    }

    if outcome.get("exception_code") is not None:
        if expected.get("expect_exception") == outcome["exception_code"]:
            findings["verdict"] = "match_expected_exception"
        elif expected.get("expect_exception") is not None:
            findings["verdict"] = "wrong_exception_code"
            findings["builder_exception"] = outcome["exception_code"]
        else:
            findings["verdict"] = "unexpected_builder_exception"
            findings["builder_exception"] = outcome["exception_code"]
        return findings

    if expected.get("expect_exception") is not None:
        findings["verdict"] = "expected_exception_but_none_raised"
        findings["critical_false_narrow"] = True
        return findings

    package = outcome["package"]
    acceptable = set(expected["acceptable_completeness_status"])
    actual_status = package["completeness_status"]

    offer_ok = sorted(package["structured_record_ids"]["offer_ids"]) == expected["expected_offer_ids"]
    fact_ok = sorted(package["structured_record_ids"]["fact_ids"]) == expected["expected_fact_ids"]
    doctor_ok = sorted(package["structured_record_ids"]["doctor_ids"]) == expected["expected_doctor_ids"]
    policy_ok = sorted(package["structured_record_ids"]["policy_sections"]) == expected["expected_policy_sections"]
    session_ok = sorted(package["session_derived_refs"]) == expected["expected_session_refs"]
    findings["offer_id_mismatch"] = not offer_ok
    findings["fact_id_mismatch"] = not fact_ok
    findings["doctor_id_mismatch"] = not doctor_ok
    findings["policy_section_mismatch"] = not policy_ok
    findings["session_ref_mismatch"] = not session_ok
    if expected["expected_session_refs"] == [] and package["session_derived_refs"]:
        findings["session_contamination"] = True

    missing_md = sorted(set(expected["required_md_refs"]) - set(package["selected_md_refs"]))
    findings["missing_md_refs"] = missing_md

    if actual_status not in acceptable:
        if actual_status != "fullcontext_fallback" and "fullcontext_fallback" in acceptable:
            findings["critical_false_narrow"] = True
            findings["verdict"] = "critical_false_narrow_expected_fallback"
        elif actual_status == "fullcontext_fallback" and "fullcontext_fallback" not in acceptable:
            findings["safe_over_fallback"] = True
            findings["verdict"] = "safe_over_fallback"
        else:
            findings["critical_false_narrow"] = True
            findings["verdict"] = "critical_false_narrow_wrong_status"
    else:
        structural_ok = offer_ok and fact_ok and doctor_ok and policy_ok and session_ok and not missing_md
        if actual_status == "fullcontext_fallback":
            findings["verdict"] = "match_expected_fallback" if structural_ok else "fallback_structural_mismatch"
            if not structural_ok:
                findings["critical_false_narrow"] = True
        elif actual_status == "insufficient_widened":
            # PERF-7C correction: relevance is decided independently from question meaning and
            # canonical authority (the matrix's own `lexical_target_options`, frozen before this
            # run) -- never from what the search function actually returned. A widened package
            # whose extra MD ref(s) fall outside that independently-decided allowed set is a
            # critical false-narrow, full stop -- regardless of a unique top score, regardless of
            # completeness_status="insufficient_widened", and regardless of whether the target
            # happened to match a *previous* (circular, now-corrected) expectation. An empty
            # `lexical_target_options` list means no document in the corpus was judged genuinely
            # relevant to this exact frozen query -- any widened result is therefore automatically
            # irrelevant.
            lexical_options = expected.get("lexical_target_options")
            target_ok = True
            if lexical_options is not None:
                actual_targets = set(package["selected_md_refs"]) - set(expected["required_md_refs"])
                target_ok = bool(actual_targets & set(lexical_options))
            if structural_ok and target_ok:
                findings["verdict"] = "match_expected_widened"
            elif not target_ok:
                findings["verdict"] = "critical_false_narrow_irrelevant_lexical_target"
                findings["critical_false_narrow"] = True
                findings["unexpected_scoped_target"] = True
            else:
                findings["verdict"] = "widened_structural_mismatch"
                findings["critical_false_narrow"] = True
        else:  # complete
            if structural_ok:
                findings["verdict"] = "match_expected_complete"
            else:
                findings["verdict"] = "critical_false_narrow_missing_required_source"
                findings["critical_false_narrow"] = True

    return findings


def run_eval(client_id: str, matrix_path: Path) -> dict[str, Any]:
    md_root = _REPO_ROOT / "clients" / client_id / "md"
    lexical_index = build_target_lexical_paragraph_index(md_root)
    cached_full_context = build_target_cached_full_context(md_root)
    full_context_tokens = len(cached_full_context.corpus_text) // 4

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    scenarios = matrix["scenarios"]

    per_scenario: list[dict[str, Any]] = []
    package_tokens: list[int] = []
    builder_ms: list[float] = []
    exceptions_count = 0

    for scenario in scenarios:
        request = _build_request(scenario)
        started = time.perf_counter()
        outcome: dict[str, Any]
        try:
            package = build_target_evidence_package(
                request,
                lexical_index,
                cached_full_context,
                md_root=md_root,
                explicit_followup=scenario["builder_input"]["explicit_followup"],
                session_derived_refs=tuple(scenario["builder_input"]["session_derived_refs"]),
                comparison_required=scenario["builder_input"]["comparison_required"],
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            builder_ms.append(elapsed_ms)
            package_tokens.append(package.estimated_tokens)
            outcome = {
                "exception_code": None,
                "package": {
                    "completeness_status": package.completeness_status,
                    "fallback_reason": package.fallback_reason,
                    "selected_md_refs": list(package.selected_md_refs),
                    "selected_paragraph_refs": list(package.selected_paragraph_refs),
                    "structured_record_ids": {
                        "offer_ids": list(package.structured_record_ids.offer_ids),
                        "fact_ids": list(package.structured_record_ids.fact_ids),
                        "doctor_ids": list(package.structured_record_ids.doctor_ids),
                        "policy_sections": list(package.structured_record_ids.policy_sections),
                    },
                    "session_derived_refs": list(package.session_derived_refs),
                    "retrieval_derived_refs": list(package.retrieval_derived_refs),
                    "serialized_context_chars": package.serialized_context_chars,
                    "estimated_tokens": package.estimated_tokens,
                    "package_fingerprint": package.package_fingerprint,
                },
            }
        except TargetEvidencePackageBuilderError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            builder_ms.append(elapsed_ms)
            outcome = {"exception_code": exc.code, "package": None}
        except Exception as exc:  # noqa: BLE001 -- unexpected exceptions are themselves a finding
            elapsed_ms = (time.perf_counter() - started) * 1000
            builder_ms.append(elapsed_ms)
            exceptions_count += 1
            outcome = {"exception_code": f"unexpected:{type(exc).__name__}", "package": None}

        findings = _classify(scenario, outcome)
        findings["timing_ms"] = round(elapsed_ms, 3)
        if outcome["package"] is not None:
            findings["actual_completeness_status"] = outcome["package"]["completeness_status"]
            findings["actual_fallback_reason"] = outcome["package"]["fallback_reason"]
            findings["actual_estimated_tokens"] = outcome["package"]["estimated_tokens"]
            findings["actual_package_fingerprint"] = outcome["package"]["package_fingerprint"]
        else:
            findings["actual_completeness_status"] = None
            findings["actual_fallback_reason"] = None
            findings["actual_estimated_tokens"] = None
            findings["actual_package_fingerprint"] = None
        per_scenario.append(findings)

    total = len(scenarios)
    complete_count = sum(1 for f in per_scenario if f["actual_completeness_status"] == "complete")
    widened_count = sum(1 for f in per_scenario if f["actual_completeness_status"] == "insufficient_widened")
    fallback_count = sum(1 for f in per_scenario if f["actual_completeness_status"] == "fullcontext_fallback")
    scoped_count = complete_count + widened_count

    lexical_widen_scenarios = [
        f for f in per_scenario if f["scenario_class"] not in {
            "exact_service", "price", "doctor", "contacts", "parking", "pain_fear",
            "marketing_concern", "no_matching_fact", "new_independent_service",
            "explicit_followup_price",
        }
    ]
    lexical_hit_count = sum(1 for f in lexical_widen_scenarios if f["actual_completeness_status"] == "insufficient_widened")
    lexical_ambiguous_count = sum(
        1 for f in lexical_widen_scenarios if f.get("actual_fallback_reason") == "lexical_ambiguous_top_match"
    )
    lexical_miss_count = sum(
        1
        for f in lexical_widen_scenarios
        if f["actual_completeness_status"] == "fullcontext_fallback"
        and f.get("actual_fallback_reason") in {"lexical_zero_hits", "lexical_only_weak_prefix_matches", "lexical_no_comparison_document_found"}
    )

    critical_false_narrow = [f for f in per_scenario if f["critical_false_narrow"]]
    safe_over_fallback = [f for f in per_scenario if f["safe_over_fallback"]]
    session_contamination = [f for f in per_scenario if f["session_contamination"]]
    id_mismatches = [
        f
        for f in per_scenario
        if f["offer_id_mismatch"] or f["fact_id_mismatch"] or f["doctor_id_mismatch"] or f["policy_section_mismatch"]
    ]

    sorted_tokens = sorted(package_tokens) if package_tokens else [0]
    sorted_ms = sorted(builder_ms) if builder_ms else [0.0]

    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        idx = min(len(values) - 1, int(round(pct * (len(values) - 1))))
        return values[idx]

    class_counts: dict[str, int] = {}
    for f in per_scenario:
        class_counts[f["scenario_class"]] = class_counts.get(f["scenario_class"], 0) + 1

    verdict_counts: dict[str, int] = {}
    for f in per_scenario:
        verdict_counts[f["verdict"]] = verdict_counts.get(f["verdict"], 0) + 1

    binding_pass = (
        len(critical_false_narrow) == 0
        and len(session_contamination) == 0
        and len(id_mismatches) == 0
        and exceptions_count == 0
    )

    lexical_relevance_defects = [
        f for f in critical_false_narrow if f["verdict"] == "critical_false_narrow_irrelevant_lexical_target"
    ]
    if binding_pass:
        top_verdict = "PERF7C_OFFLINE_PACKAGE_EVAL_PASS"
    elif critical_false_narrow and len(lexical_relevance_defects) == len(critical_false_narrow) and (
        len(session_contamination) == 0 and len(id_mismatches) == 0 and exceptions_count == 0
    ):
        # Every critical failure is specifically an irrelevant-lexical-target defect (not a
        # structural Builder defect, not session contamination, not a missing exact ID, not an
        # unhandled exception) -- a distinct, more specific verdict than the generic
        # "critical false-narrow found", per the PERF-7C correction owner GO.
        top_verdict = "PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND"
    else:
        top_verdict = "PERF7C_CRITICAL_FALSE_NARROW_FOUND"

    result = {
        "schema_version": 1,
        "suite_id": matrix["suite_id"],
        "client_id": client_id,
        "matrix_scenario_count": total,
        "class_counts": class_counts,
        "verdict_counts": verdict_counts,
        "metrics": {
            "total_scenarios": total,
            "scoped_complete_count": complete_count,
            "scoped_widened_count": widened_count,
            "scoped_count": scoped_count,
            "fullcontext_fallback_count": fallback_count,
            "scoped_rate": round(scoped_count / total, 4) if total else 0.0,
            "fallback_rate": round(fallback_count / total, 4) if total else 0.0,
            "critical_false_narrow_count": len(critical_false_narrow),
            "safe_over_fallback_count": len(safe_over_fallback),
            "session_contamination_count": len(session_contamination),
            "structured_id_mismatch_count": len(id_mismatches),
            "builder_exception_count": exceptions_count,
            "lexical_hit_count": lexical_hit_count,
            "lexical_ambiguous_count": lexical_ambiguous_count,
            "lexical_miss_count": lexical_miss_count,
            "package_tokens_p50": sorted_tokens[len(sorted_tokens) // 2],
            "package_tokens_p95": _percentile(sorted_tokens, 0.95),
            "builder_ms_p50": round(_percentile(sorted_ms, 0.5), 3),
            "builder_ms_p95": round(_percentile(sorted_ms, 0.95), 3),
            "full_context_estimated_tokens": full_context_tokens,
        },
        "critical_false_narrow_scenario_ids": [f["scenario_id"] for f in critical_false_narrow],
        "lexical_relevance_defect_scenario_ids": [f["scenario_id"] for f in lexical_relevance_defects],
        "safe_over_fallback_scenario_ids": [f["scenario_id"] for f in safe_over_fallback],
        "session_contamination_scenario_ids": [f["scenario_id"] for f in session_contamination],
        "structured_id_mismatch_scenario_ids": [f["scenario_id"] for f in id_mismatches],
        "unexpected_scoped_target_scenario_ids": [f["scenario_id"] for f in per_scenario if f["unexpected_scoped_target"]],
        "scenarios": [
            {
                "scenario_id": f["scenario_id"],
                "scenario_class": f["scenario_class"],
                "verdict": f["verdict"],
                "actual_completeness_status": f["actual_completeness_status"],
                "actual_fallback_reason": f["actual_fallback_reason"],
                "actual_estimated_tokens": f["actual_estimated_tokens"],
                "actual_package_fingerprint": f["actual_package_fingerprint"],
                "timing_ms": f["timing_ms"],
                "builder_exception": f["builder_exception"],
            }
            for f in per_scenario
        ],
        "binding_pass": binding_pass,
        "verdict": top_verdict,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PERF-7C offline local Evidence Package eval (no LLM, no network).")
    parser.add_argument("--client-id", dest="client_id", default="demo")
    parser.add_argument("--matrix", dest="matrix", default=str(DEFAULT_MATRIX_PATH))
    parser.add_argument("--output", dest="output", default=None)
    args = parser.parse_args(argv)

    matrix_path = Path(args.matrix)
    if not matrix_path.is_file():
        print(f"ERROR: matrix not found: {matrix_path}", file=sys.stderr)
        return 2

    result = run_eval(args.client_id, matrix_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = result["metrics"]
    print(f"verdict: {result['verdict']}")
    print(f"total_scenarios: {metrics['total_scenarios']}")
    print(f"scoped_rate: {metrics['scoped_rate']}  fallback_rate: {metrics['fallback_rate']}")
    print(f"critical_false_narrow: {metrics['critical_false_narrow_count']}")
    print(f"safe_over_fallback: {metrics['safe_over_fallback_count']}")
    print(f"session_contamination: {metrics['session_contamination_count']}")
    print(f"structured_id_mismatch: {metrics['structured_id_mismatch_count']}")
    print(f"builder_exceptions: {metrics['builder_exception_count']}")
    print(f"lexical_hit/ambiguous/miss: {metrics['lexical_hit_count']}/{metrics['lexical_ambiguous_count']}/{metrics['lexical_miss_count']}")
    print(f"package_tokens p50/p95: {metrics['package_tokens_p50']}/{metrics['package_tokens_p95']}")
    print(f"builder_ms p50/p95: {metrics['builder_ms_p50']}/{metrics['builder_ms_p95']}")
    print(f"full_context_estimated_tokens: {metrics['full_context_estimated_tokens']}")

    return 0 if result["binding_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
