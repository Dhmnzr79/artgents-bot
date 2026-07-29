"""Owner-authorized prewarm attempt lifecycle contract (PERF-3).

``attempt_id`` is the ONLY lifecycle key -- never ``client_id``/``role``/``fingerprint``. A
fresh ``attempt_id`` with an unchanged fingerprint always gets a fresh marker without friction
(a new owner GO permitting); only reusing the same ``attempt_id`` is forbidden. Fingerprints
appear here as descriptive/audit data (cache identity, see
``contracts/target_prompt_cache_fingerprint.py``), never as part of the marker's own path or
key. See docs/evidence/performance/FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md sec 7.

An attempt marker proves only the fact and final state of that one specific, owner-authorized
run. It never means the provider's prompt cache is still warm -- warmth is only ever confirmed
by a live ``cached_tokens`` measurement (sec 8).

Model provenance is kept simple and explicit (owner directive): the attempt records the
operator-supplied ``requested_model`` and the ``configured_model`` resolved from env/config at
attempt time -- the two must be checked equal before any marker/provider call (the A9R2c stale
model-pin defense). The third provenance value, the ``observed`` model returned by the provider
itself, is recorded and checked per role call in the shared ledger's call records, not here --
no redundant parallel per-role model state is stored on the attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_prompt_cache_fingerprint import TargetPromptCacheRole

TargetPromptCacheAttemptStatus = Literal["started", "completed", "aborted", "failed"]


@dataclass(frozen=True, slots=True)
class TargetPromptCacheAttempt:
    """One owner-authorized live attempt. Immutable snapshot -- update via ``dataclasses.replace``.

    ``budget`` and ``retry`` are hard invariants encoded in the type itself: ``budget`` is fixed
    at 2 (at most 1 Composer + 1 Verifier warm call) and ``retry`` is fixed at 0 (single attempt
    per call, matching the existing ``call_count > 1`` retry-forbidden discipline). They are not
    free integers -- nothing may construct an attempt with any other value.
    """

    attempt_id: str
    client_id: str
    requested_model: str
    configured_model: str
    composer_fingerprint: str
    verifier_fingerprint: str
    planned_roles: tuple[TargetPromptCacheRole, ...]
    status: TargetPromptCacheAttemptStatus
    started_at: str
    completed_at: str | None
    calls_started: int
    calls_completed: int
    budget: Literal[2] = 2
    retry: Literal[0] = 0
