from __future__ import annotations

"""Demo product eval — smoke + risk + core golden (v5 architecture)."""
import argparse
import os
import sys

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

from smoke_case_runner import here, run_smoke_suite

_SUITES: dict[str, str] = {
    "smoke": "demo/smoke.json",
    "risk": "demo/risk.json",
    "golden": "demo/golden.json",
    "emotion": "demo/emotion.json",
}

# Product CI runs smoke+risk only; golden grows incrementally (run --suite golden locally).
_CI_SUITES = ("smoke", "risk")
# Routing gate for strangler pilot (emotion P0/P1)
_ROUTING_SUITES = ("emotion",)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    ap = argparse.ArgumentParser(
        description="Demo product eval (smoke + risk + golden)",
        allow_abbrev=False,
    )
    ap.add_argument(
        "--suite",
        choices=[*_SUITES.keys(), "all", "product", "routing"],
        default="all",
        help=(
            "smoke | risk | golden | emotion | routing (=emotion) | "
            "product (smoke+risk) | all (default: all suites in file)"
        ),
    )
    ap.add_argument("--client", default=None, metavar="CLIENT_ID")
    ap.add_argument("--case-id", action="append", default=None, metavar="ID")
    ns, unknown = ap.parse_known_args(argv)
    if unknown:
        print(f"WARNING: ignored unknown args: {unknown!r}", file=sys.stderr, flush=True)

    bot_url = (os.getenv("BOT_URL") or "http://localhost:5000/ask").strip()
    timeout_sec = float(os.getenv("BOT_TIMEOUT_SEC") or "20")

    filter_ids: set[str] | None = None
    raw_ids: list[str] = []
    if ns.case_id:
        raw_ids.extend(str(x).strip() for x in ns.case_id if str(x).strip())
    env_csv = (os.getenv("DEMO_EVAL_CASE_ID") or "").strip()
    if env_csv:
        raw_ids.extend(x.strip() for x in env_csv.split(",") if x.strip())
    if raw_ids:
        filter_ids = set(raw_ids)

    client_filter: str | None = None
    if ns.client and str(ns.client).strip():
        client_filter = str(ns.client).strip().lower()
    elif (os.getenv("DEMO_EVAL_CLIENT") or os.getenv("E2E_SMOKE_CLIENT") or "").strip():
        client_filter = (
            os.getenv("DEMO_EVAL_CLIENT") or os.getenv("E2E_SMOKE_CLIENT") or ""
        ).strip().lower()

    if ns.suite == "product":
        suites = list(_CI_SUITES)
    elif ns.suite == "routing":
        suites = list(_ROUTING_SUITES)
    elif ns.suite == "all":
        suites = list(_SUITES.keys())
    else:
        suites = [ns.suite]
    exit_code = 0
    for name in suites:
        rel = _SUITES[name]
        path = (os.getenv(f"DEMO_EVAL_{name.upper()}_PATH") or "").strip() or here(rel)
        print(f"\n=== demo eval / {name} ({path}) ===\n", flush=True)
        code = run_smoke_suite(
            spec_path=path,
            bot_url=bot_url,
            timeout_sec=timeout_sec,
            client_filter=client_filter,
            filter_ids=filter_ids,
            expand_multiclient=False,
        )
        if code != 0:
            exit_code = code
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
