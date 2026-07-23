"""Service-derived target strategy context for runtime (S61 correction)."""

from __future__ import annotations

from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch


def resolve_target_runtime_strategy_context(
    bundle: ResponseSchemaBundle,
    *,
    service_id: str | None,
) -> TargetStrategyMatch:
    """Build strategy match from structured service catalog only (no A9 inference)."""

    if not service_id:
        return TargetStrategyMatch(family=None, extent=None)
    service = bundle.services.get(service_id)
    if service is None:
        return TargetStrategyMatch(family=None, extent=None)
    extent = None
    selection = service.selection
    if selection is not None and selection.extent is not None and len(selection.extent) == 1:
        extent = selection.extent[0]
    return TargetStrategyMatch(family=service.family, extent=extent)
