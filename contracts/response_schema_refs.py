"""Pure external source-reference integrity for the target response schema (S3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from contracts.response_schema import ResponseSchemaBundle, SourceRef


class ResponseSchemaExternalIndex(BaseModel):
    """Exact in-memory refs discovered by future KB/doctor index builders."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kb_refs: tuple[SourceRef, ...] = ()
    doctor_refs: tuple[SourceRef, ...] = ()

    @field_validator("kb_refs", mode="after")
    @classmethod
    def _kb_refs_are_exact_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not ref.startswith("kb:") for ref in value):
            raise ValueError("external_index_kb_prefix_invalid")
        if len(value) != len(set(value)):
            raise ValueError("external_index_kb_ref_duplicate")
        return value

    @field_validator("doctor_refs", mode="after")
    @classmethod
    def _doctor_refs_are_exact_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not ref.startswith("doctor:") for ref in value):
            raise ValueError("external_index_doctor_prefix_invalid")
        if len(value) != len(set(value)):
            raise ValueError("external_index_doctor_ref_duplicate")
        return value


class ResponseSchemaExternalRefError(ValueError):
    """All external refs missing from one explicit source index."""

    code = "external_refs_missing"

    def __init__(
        self,
        *,
        missing_kb_refs: tuple[str, ...],
        missing_doctor_refs: tuple[str, ...],
    ) -> None:
        self.missing_kb_refs = missing_kb_refs
        self.missing_doctor_refs = missing_doctor_refs
        super().__init__(self.code)


def validate_response_schema_external_refs(
    bundle: ResponseSchemaBundle,
    index: ResponseSchemaExternalIndex,
) -> None:
    """Fail once with every exact KB/doctor ref absent from the supplied index."""

    available_kb_refs = set(index.kb_refs)
    available_doctor_refs = set(index.doctor_refs)
    missing_kb_refs: set[str] = set()
    missing_doctor_refs: set[str] = set()

    for rule in bundle.marketing.scenario_rules.values():
        for ref in rule.ordered_amplifier_refs:
            if ref.startswith("kb:"):
                if ref not in available_kb_refs:
                    missing_kb_refs.add(ref)
            elif ref.startswith("doctor:") and ref not in available_doctor_refs:
                missing_doctor_refs.add(ref)

    if missing_kb_refs or missing_doctor_refs:
        raise ResponseSchemaExternalRefError(
            missing_kb_refs=tuple(sorted(missing_kb_refs)),
            missing_doctor_refs=tuple(sorted(missing_doctor_refs)),
        )
