from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.planner_compute_executor import PlannerSpeculationHandle


@dataclass(frozen=True)
class AskTurnContext:
    """Состояние turn после pre-Resolver guards — готов к Resolver + post-Resolver routing."""

    q: str
    sid: str
    client_id: str
    ref: str
    data: dict
    st: dict
    # PERF-4: handle for a speculatively-started Planner compute (Variant C), or None if
    # none was started (deterministic Ingress hit / admission overload). Exactly one of
    # join_planner_speculation / discard_planner_speculation is ever called on it, by
    # whichever downstream code path is actually taken -- never both.
    planner_speculation: "PlannerSpeculationHandle | None" = None
