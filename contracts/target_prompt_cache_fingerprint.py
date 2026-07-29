"""Provider prompt-cache identity contract (PERF-3).

Cache identity only -- ``(client_id, role, model, static_prefix_hash, corpus_sha256,
prompt_template_version, message_serialization_version)`` describes WHAT a prewarm attempt
would warm. It is never used as a lookup or lifecycle key: that role belongs exclusively to
the separate, explicit ``attempt_id`` in ``contracts/target_prompt_cache_attempt.py``. See
docs/evidence/performance/FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md sec 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TargetPromptCacheRole = Literal["composer", "verifier"]


@dataclass(frozen=True, slots=True)
class TargetPromptCacheFingerprint:
    """Descriptive/audit identity for one role's static prompt prefix. Never a lookup key.

    ``static_prefix_hash`` is the primary, directly-verifiable proof of prefix identity: it is
    the SHA-256 of the actual static prefix assembled by reusing the production message
    builders verbatim (sec 5). ``corpus_sha256`` mirrors ``TargetCachedFullContext.sha256`` for
    readable invalidation granularity. The two version ints catch the one class of change a
    text hash cannot (restructuring the assembly code without changing the resulting text).
    """

    client_id: str
    role: TargetPromptCacheRole
    model: str
    static_prefix_hash: str
    corpus_sha256: str
    prompt_template_version: int
    message_serialization_version: int
    fingerprint: str
