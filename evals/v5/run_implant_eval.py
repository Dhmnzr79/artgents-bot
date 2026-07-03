from __future__ import annotations

import argparse
import os
import sys
import warnings

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        "run_implant_eval.py is deprecated; implant battery merged into demo/risk.json. "
        "Use: python evals/v5/run_demo_eval.py --suite risk",
        DeprecationWarning,
        stacklevel=1,
    )
    from run_demo_eval import main as demo_main

    argv = list(argv or [])
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--client", default=None)
    ap.add_argument("--case-id", action="append", default=None)
    ns, rest = ap.parse_known_args(argv)
    forwarded = ["--suite", "risk"]
    if ns.client:
        forwarded.extend(["--client", ns.client])
    if ns.case_id:
        for cid in ns.case_id:
            forwarded.extend(["--case-id", cid])
    forwarded.extend(rest)
    path = (os.getenv("IMPLANT_EVAL_PATH") or "").strip()
    if path and os.path.isfile(path):
        os.environ["DEMO_EVAL_RISK_PATH"] = path
    return demo_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
