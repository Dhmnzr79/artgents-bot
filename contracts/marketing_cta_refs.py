"""Pure CTA-reference integrity for the target marketing policy (S20)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from contracts.response_schema import NonBlankStr, TargetMarketingPolicy


class MarketingCtaIndex(BaseModel):
    """Exact CTA keys supplied by the client-owned tone boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cta_keys: tuple[NonBlankStr, ...] = ()

    @field_validator("cta_keys", mode="after")
    @classmethod
    def _cta_keys_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("marketing_cta_index_key_duplicate")
        return value


class MarketingCtaReferenceError(ValueError):
    """All policy CTA keys absent from one explicit CTA index."""

    code = "marketing_cta_refs_missing"

    def __init__(self, *, missing_cta_keys: tuple[str, ...]) -> None:
        self.missing_cta_keys = missing_cta_keys
        super().__init__(self.code)


def validate_marketing_cta_refs(
    policy: TargetMarketingPolicy,
    index: MarketingCtaIndex,
) -> None:
    """Fail once with every exact CTA key absent from the supplied index."""

    available_cta_keys = set(index.cta_keys)
    missing_cta_keys = tuple(
        sorted(set(policy.cta_contexts.values()) - available_cta_keys)
    )
    if missing_cta_keys:
        raise MarketingCtaReferenceError(missing_cta_keys=missing_cta_keys)
