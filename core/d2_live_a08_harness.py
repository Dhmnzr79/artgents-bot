"""Two-turn CP3 A08 runner, deliberately internal and transport-free by default."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import CP3_MAX_PROVIDER_CALLS, D2Cp3LiveProvider


CP3_FIRST_MESSAGE = "Нет одного зуба, сколько стоит восстановить?"
CP3_SECOND_MESSAGE = "А протезирование?"


@dataclass(frozen=True, slots=True)
class D2Cp3LiveResult:
    client_id: str
    model: str
    provider_call_count: int
    first_topic_id: str | None
    first_offer_ids: tuple[str, ...]
    second_topic_id: str | None
    second_offer_ids: tuple[str, ...]
    second_applied_extent: str | None
    observations: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_cp3_a08_live(
    *,
    clients_root: Path,
    database_path: Path,
    provider: D2Cp3LiveProvider,
    now: datetime | None = None,
) -> D2Cp3LiveResult:
    """Spend the complete owner-authorized budget on exactly the two A08 turns."""
    if provider.call_count:
        raise ValueError("d2_cp3_provider_must_be_fresh")
    timestamp = now or datetime.now(timezone.utc)
    key = SessionKey(client_id="demo", sid="cp3-live-a08")
    with D2DialogueStore(database_path) as store:
        first = run_d2_dialogue_turn(
            session_key=key,
            user_message=CP3_FIRST_MESSAGE,
            provider=provider,
            clients_root=clients_root,
            store=store,
            now=timestamp,
        )
        second = run_d2_dialogue_turn(
            session_key=key,
            user_message=CP3_SECOND_MESSAGE,
            provider=provider,
            clients_root=clients_root,
            store=store,
            now=timestamp,
        )
    if provider.call_count != CP3_MAX_PROVIDER_CALLS:
        raise RuntimeError("d2_cp3_two_calls_not_consumed")
    first_price = first.response.resolved.d2_price_block
    second_price = second.response.resolved.d2_price_block
    second_decision = second.response.resolved.d2_price_scope_decision
    return D2Cp3LiveResult(
        client_id=key.client_id,
        model=provider.model,
        provider_call_count=provider.call_count,
        first_topic_id=first.focus.topic_id,
        first_offer_ids=tuple(row.offer_id for row in first_price.rows) if first_price else (),
        second_topic_id=second.focus.topic_id,
        second_offer_ids=tuple(row.offer_id for row in second_price.rows) if second_price else (),
        second_applied_extent=second_decision.applied_extent if second_decision else None,
        observations=tuple(asdict(item) for item in provider.observations),
    )
