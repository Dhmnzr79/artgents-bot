#!/usr/bin/env python3
"""Cross-document alias collision report (Metadata-First v1 §9)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.client_runtime import list_buildable_client_ids
from core.content_linter import alias_collision_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Report duplicate aliases across md files")
    parser.add_argument("--client", default="all", help="Pack id or 'all'")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--min-files",
        type=int,
        default=2,
        help="Minimum files sharing the same normalized alias (default: 2)",
    )
    args = parser.parse_args()

    if args.client == "all":
        client_ids = list_buildable_client_ids()
    else:
        client_ids = [args.client.strip()]

    payload: dict[str, dict[str, list[str]]] = {}
    total = 0
    for cid in client_ids:
        coll = alias_collision_report(cid)
        filtered = {k: v for k, v in coll.items() if len(v) >= max(2, int(args.min_files))}
        payload[cid] = filtered
        total += len(filtered)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"# Alias collisions ({total} keys)\n")
        for cid, coll in payload.items():
            print(f"## {cid} ({len(coll)} keys)\n")
            for nk, files in sorted(coll.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                print(f"- {nk!r}: {', '.join(files)}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
