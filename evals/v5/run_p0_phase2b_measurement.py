"""CLI for P0 Phase 2B Qwen 3.8 Flash streaming opportunity measurement."""

from __future__ import annotations

import argparse
import os
import sys

from evals.v5.p0_phase2b_contract import (
    CANDIDATE_MODEL_ID,
    CONTROL_MODEL_ID,
    assert_call_plan_within_budget,
    build_call_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P0 Phase 2B streaming measurement (eval-only)")
    parser.add_argument(
        "--mode",
        choices=("baseline", "plan", "canary", "full"),
        required=True,
    )
    parser.add_argument(
        "--dotenv",
        default=None,
        help="Optional path to .env (loads before LIVE modes; never logged)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dotenv:
        from dotenv import load_dotenv

        load_dotenv(args.dotenv, override=True)
    if args.mode == "baseline":
        from evals.v5.p0_phase2b_artifacts import baseline_report, persist_artifact

        report = baseline_report()
        persist_artifact("baseline_report.json", report)
        print(report)
        return 0
    if args.mode == "plan":
        from evals.v5.p0_phase2b_artifacts import persist_artifact

        plan = build_call_plan(include_canary=True, repeat_pass=True)
        assert_call_plan_within_budget(plan)
        payload = {
            "control_model": CONTROL_MODEL_ID,
            "candidate_model": CANDIDATE_MODEL_ID,
            "call_count": len(plan),
            "plan": [
                {"model_id": m, "case_id": c, "client_id": cl, "attempt": a}
                for m, c, cl, a in plan
            ],
        }
        persist_artifact("call_plan.json", payload)
        print(payload)
        return 0
    api_key = (os.getenv("CHAT_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not api_key:
        print("CHAT_API_KEY_missing", file=sys.stderr)
        return 2
    import app as app_module

    from evals.v5.p0_phase2b_measurement import persist_artifact, run_canary, run_full_matrix

    flask_app = app_module.app
    if args.mode == "canary":
        results = {
            "control": run_canary(CONTROL_MODEL_ID, flask_app=flask_app),
            "candidate": run_canary(CANDIDATE_MODEL_ID, flask_app=flask_app),
        }
        persist_artifact("canary_result.json", results)
        print(results)
        return 0
    if args.mode == "full":
        summary = run_full_matrix(flask_app, include_canary=False)
        persist_artifact("full_measurement_result.json", summary)
        print(
            {
                "live_call_count": summary["live_call_count"],
                "safe_faq_gain_median_ms": summary["safe_faq_gain_median_ms"],
                "latency_by_model": summary["latency_by_model"],
            }
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
