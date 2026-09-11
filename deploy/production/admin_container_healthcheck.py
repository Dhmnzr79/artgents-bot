"""Docker health probe for admin_dashboard (stdlib only; no secret logging)."""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

_TIMEOUT_SEC = 3
_URL = "http://127.0.0.1:9100/api/health"
_HEADER = "X-Admin-Dashboard-Token"


def main() -> int:
    token = (os.environ.get("ADMIN_DASHBOARD_TOKEN") or "").strip()
    if not token:
        return 1
    req = urllib.request.Request(_URL, headers={_HEADER: token})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            return 0 if resp.status == 200 else 1
    except urllib.error.HTTPError as exc:
        return 1 if exc.code != 200 else 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
