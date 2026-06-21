from __future__ import annotations

"""Lead turn golden eval (PRODUCT_WORK_PLAN stage 3.6)."""
import argparse
import os
import sys

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

from smoke_case_runner import here, run_smoke_suite


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    ap = argparse.ArgumentParser(description="Lead turn golden eval (demo client)", allow_abbrev=False)
    ap.add_argument("--client", default=None, metavar="CLIENT_ID")
    ap.add_argument("--case-id", action="append", default=None, metavar="ID")
    ns, unknown = ap.parse_known_args(argv)
    if unknown:
        print(f"WARNING: ignored unknown args: {unknown!r}", file=sys.stderr, flush=True)

    path = (os.getenv("LEAD_TURN_EVAL_PATH") or "").strip() or here("lead_turn_golden.json")
    bot_url = (os.getenv("BOT_URL") or "http://localhost:5000/ask").strip()
    timeout_sec = float(os.getenv("BOT_TIMEOUT_SEC") or "20")

    filter_ids: set[str] | None = None
    raw_ids: list[str] = []
    if ns.case_id:
        raw_ids.extend(str(x).strip() for x in ns.case_id if str(x).strip())
    env_csv = (os.getenv("LEAD_TURN_EVAL_CASE_ID") or "").strip()
    if env_csv:
        raw_ids.extend(x.strip() for x in env_csv.split(",") if x.strip())
    if raw_ids:
        filter_ids = set(raw_ids)

    client_filter: str | None = None
    if ns.client and str(ns.client).strip():
        client_filter = str(ns.client).strip().lower()
    elif (os.getenv("LEAD_TURN_EVAL_CLIENT") or os.getenv("E2E_SMOKE_CLIENT") or "").strip():
        client_filter = (
            os.getenv("LEAD_TURN_EVAL_CLIENT") or os.getenv("E2E_SMOKE_CLIENT") or ""
        ).strip().lower()

    print(f"\n=== lead turn golden eval ({path}) ===\n", flush=True)
    return run_smoke_suite(
        spec_path=path,
        bot_url=bot_url,
        timeout_sec=timeout_sec,
        client_filter=client_filter,
        filter_ids=filter_ids,
        expand_multiclient=False,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
