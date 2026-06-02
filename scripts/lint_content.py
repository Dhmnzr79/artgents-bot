#!/usr/bin/env python3
"""Lint client md frontmatter and refs (Metadata-First v1)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.client_runtime import list_buildable_client_ids
from core.content_linter import (
    alias_collision_report,
    format_lint_report,
    lint_all_clients,
    lint_client_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint clients/{id}/md frontmatter")
    parser.add_argument(
        "--client",
        default="all",
        help="Pack id or 'all' (default: all buildable clients)",
    )
    parser.add_argument(
        "--collisions",
        action="store_true",
        help="Print cross-document alias collisions (warning only)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable issue list")
    args = parser.parse_args()

    if args.client == "all":
        client_ids = list_buildable_client_ids()
    else:
        client_ids = [args.client.strip()]

    results = lint_all_clients(client_ids)
    exit_code = 0
    if any(not r.ok for r in results):
        exit_code = 1

    if args.json:
        payload = [
            {
                "client_id": r.client_id,
                "ok": r.ok,
                "issues": [
                    {
                        "level": i.level,
                        "code": i.code,
                        "message": i.message,
                        "path": i.path,
                        "field": i.field,
                    }
                    for i in r.issues
                ],
            }
            for r in results
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_lint_report(results))

    if args.collisions:
        print("\n# Alias collisions (same norm key in multiple files)\n")
        for cid in client_ids:
            coll = alias_collision_report(cid)
            print(f"## {cid} ({len(coll)} keys)")
            for nk, files in sorted(coll.items(), key=lambda kv: -len(kv[1]))[:30]:
                print(f"  - {nk!r}: {', '.join(files)}")
            if len(coll) > 30:
                print(f"  ... and {len(coll) - 30} more")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
