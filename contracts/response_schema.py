"""Target response-data authoring contracts (S1, offline and unwired).

These models describe future client-owned schema data and validate local references in
memory. They do not load client packs, select content, read session state, or influence
the product response path.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("string_must_not_be_blank")
    return value


def _require_iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date_must_be_iso_yyyy_mm_dd") from exc
    if parsed.isoformat() != value:
        raise ValueError("date_must_be_iso_yyyy_mm_dd")
    return value


def _require_source_ref(value: str) -> str:
    if ":" not in value:
        raise ValueError("source_ref_prefix_invalid")
    prefix, target = value.split(":", 1)
    if prefix not in {"fact", "kb", "doctor"}:
        raise ValueError("source_ref_prefix_invalid")
    if not target.strip():
        raise ValueError("source_ref_target_empty")
    if prefix == "kb":
        if target.count("#") != 1:
            raise ValueError("kb_ref_requires_doc_and_chunk")
        document, chunk = target.split("#", 1)
        if not document.strip() or not chunk.strip():
            raise ValueError("kb_ref_requires_doc_and_chunk")
    return value


def _require_fact_ref(value: str) -> str:
    if not value.startswith("fact:"):
        raise ValueError("initial_fact_ref_requires_fact_prefix")
    return value


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
IsoDate = Annotated[str, AfterValidator(_require_iso_date)]
SourceRef = Annotated[str, AfterValidator(_require_source_ref)]
FactSourceRef = Annotated[SourceRef, AfterValidator(_require_fact_ref)]
MoneyAmount = Annotated[StrictInt, Field(ge=0)]
Priority = StrictInt

ServiceFamily = Literal[
    "diagnostics",
    "therapy",
    "endodontics",
    "surgery",
    "periodontology",
    "implantology",
    "prosthodontics",
    "orthodontics",
    "aesthetics",
]
ServiceRole = Literal["protocol", "advanced_protocol", "supporting"]
SelectionMode = Literal["scope", "context", "direct"]
PatientExtent = Literal["one_tooth", "few_teeth", "full_arch"]
PatientStage = Literal[
    "natural_tooth_present",
    "extraction_context",
    "implant_placed",
]
PatientJaw = Literal["upper", "lower"]
ReportedContext = Literal["reported_bone_deficit"]
BillingUnit = Literal[
    "tooth",
    "implant",
    "tooth_package",
    "jaw",
    "both_jaws",
    "procedure",
    "unit",
    "course",
]
MarketingScenario = Literal[
    "pain_fear",
    "cost",
    "time",
    "doctor_trust",
    "result_reliability",
]


class TargetSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


class TargetServiceSelection(TargetSchemaModel):
    mode: SelectionMode
    extent: list[PatientExtent] | None = None
    stage: list[PatientStage] | None = None
    jaw: list[PatientJaw] | None = None
    reported_context: list[ReportedContext] | None = None

    @field_validator("extent", "stage", "jaw", "reported_context", mode="after")
    @classmethod
    def _non_empty_unique_selection(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("selection_values_empty")
        if _duplicates(value):
            raise ValueError("selection_values_duplicate")
        return value


class TargetOptionSelection(TargetSchemaModel):
    extent: list[PatientExtent] | None = None
    stage: list[PatientStage] | None = None
    jaw: list[PatientJaw] | None = None
    reported_context: list[ReportedContext] | None = None

    @field_validator("extent", "stage", "jaw", "reported_context", mode="after")
    @classmethod
    def _non_empty_unique_selection(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("selection_values_empty")
        if _duplicates(value):
            raise ValueError("selection_values_duplicate")
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> "TargetOptionSelection":
        if all(getattr(self, name) is None for name in ("extent", "stage", "jaw", "reported_context")):
            raise ValueError("option_selection_empty")
        return self


class TargetServiceOption(TargetSchemaModel):
    option_id: NonBlankStr
    name: NonBlankStr
    aliases: list[NonBlankStr] = Field(default_factory=list)
    active: bool | None = None
    content_ref: NonBlankStr | None = None
    selection: TargetOptionSelection | None = None

    @field_validator("aliases", mode="after")
    @classmethod
    def _aliases_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("option_alias_duplicate")
        return value


class TargetService(TargetSchemaModel):
    name: NonBlankStr
    aliases: list[NonBlankStr] = Field(default_factory=list)
    family: ServiceFamily
    roles: list[ServiceRole] = Field(default_factory=list)
    active: bool = True
    content_ref: NonBlankStr | None = None
    selection: TargetServiceSelection
    options: list[TargetServiceOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_lists(self) -> "TargetService":
        if _duplicates(self.aliases):
            raise ValueError("service_alias_duplicate")
        if _duplicates(self.roles):
            raise ValueError("service_role_duplicate")
        option_ids = [option.option_id for option in self.options]
        if _duplicates(option_ids):
            raise ValueError("service_option_id_duplicate")
        return self


class TargetBrand(TargetSchemaModel):
    canonical_name: NonBlankStr
    country: NonBlankStr
    aliases: list[NonBlankStr] = Field(default_factory=list)

    @field_validator("aliases", mode="after")
    @classmethod
    def _aliases_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("brand_alias_duplicate")
        return value


class TargetBrandCatalog(TargetSchemaModel):
    version: Annotated[StrictInt, Field(ge=1)] = 1
    brands: dict[NonBlankStr, TargetBrand] = Field(default_factory=dict)


class TargetFixedPrice(TargetSchemaModel):
    mode: Literal["fixed"]
    amount: MoneyAmount
    currency: NonBlankStr
    billing_unit: BillingUnit


class TargetFromPrice(TargetSchemaModel):
    mode: Literal["from"]
    min_amount: MoneyAmount
    currency: NonBlankStr
    billing_unit: BillingUnit


class TargetRangePrice(TargetSchemaModel):
    mode: Literal["range"]
    min_amount: MoneyAmount
    max_amount: MoneyAmount
    currency: NonBlankStr
    billing_unit: BillingUnit

    @model_validator(mode="after")
    def _ordered_range(self) -> "TargetRangePrice":
        if self.min_amount > self.max_amount:
            raise ValueError("price_range_min_exceeds_max")
        return self


class TargetNoPublicPrice(TargetSchemaModel):
    mode: Literal["no_public_price"]
    approved_text: NonBlankStr


TargetPrice: TypeAlias = Annotated[
    TargetFixedPrice | TargetFromPrice | TargetRangePrice | TargetNoPublicPrice,
    Field(discriminator="mode"),
]

FamilyLevelPrice: TypeAlias = Annotated[
    TargetFixedPrice | TargetFromPrice | TargetRangePrice,
    Field(discriminator="mode"),
]


class TargetPricePackage(TargetSchemaModel):
    label: NonBlankStr
    includes: list[NonBlankStr] = Field(default_factory=list)

    @field_validator("includes", mode="after")
    @classmethod
    def _includes_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("package_include_duplicate")
        return value


class TargetPaymentStage(TargetSchemaModel):
    label: NonBlankStr
    amount: MoneyAmount
    currency: NonBlankStr


class TargetPriceFollowup(TargetSchemaModel):
    id: NonBlankStr
    label: NonBlankStr
    action: NonBlankStr


class TargetOffer(TargetSchemaModel):
    offer_id: NonBlankStr
    service_id: NonBlankStr
    option_id: NonBlankStr | None = None
    brand_id: NonBlankStr | None = None
    active: bool = True
    applies_to_extents: list[PatientExtent] | None = None
    price: TargetPrice
    package: TargetPricePackage
    payment_stages: list[TargetPaymentStage] | None = None
    fact_refs: list[NonBlankStr] = Field(default_factory=list)
    followups: list[TargetPriceFollowup] = Field(default_factory=list)

    @field_validator("applies_to_extents", mode="after")
    @classmethod
    def _applies_to_extents_unique(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("offer_applies_to_extents_empty")
        if _duplicates(value):
            raise ValueError("offer_applies_to_extents_duplicate")
        return value

    @field_validator("payment_stages", mode="after")
    @classmethod
    def _payment_stages_are_non_empty_and_unique(
        cls, value: list[TargetPaymentStage] | None
    ) -> list[TargetPaymentStage] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("offer_payment_stages_empty")
        if _duplicates([stage.label for stage in value]):
            raise ValueError("offer_payment_stage_label_duplicate")
        return value

    @model_validator(mode="after")
    def _unique_refs(self) -> "TargetOffer":
        if _duplicates(self.fact_refs):
            raise ValueError("offer_fact_ref_duplicate")
        followup_ids = [followup.id for followup in self.followups]
        if _duplicates(followup_ids):
            raise ValueError("offer_followup_id_duplicate")
        if "stages" in followup_ids and not self.payment_stages:
            raise ValueError("offer_stages_followup_requires_payment_stages")
        return self


class TargetCommercialFact(TargetSchemaModel):
    id: NonBlankStr
    kind: NonBlankStr
    text_fact: NonBlankStr
    render_mode: NonBlankStr
    active: bool = True
    active_from: IsoDate | None = None
    active_until: IsoDate | None = None
    allowed_service_ids: list[NonBlankStr] = Field(default_factory=list)
    allowed_topics: list[NonBlankStr] = Field(default_factory=list)
    detail_ref: NonBlankStr | None = None
    incompatible_with: list[NonBlankStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fact_invariants(self) -> "TargetCommercialFact":
        if _duplicates(self.allowed_service_ids):
            raise ValueError("fact_allowed_service_duplicate")
        if _duplicates(self.allowed_topics):
            raise ValueError("fact_allowed_topic_duplicate")
        if _duplicates(self.incompatible_with):
            raise ValueError("fact_incompatible_ref_duplicate")
        if self.id in self.incompatible_with:
            raise ValueError("fact_incompatible_self_reference")
        if self.active_from is not None and self.active_until is not None:
            if self.active_from > self.active_until:
                raise ValueError("fact_active_from_after_active_until")
        return self


class TargetStrategyMatch(TargetSchemaModel):
    family: ServiceFamily | None = None
    extent: PatientExtent | None = None
    stage: PatientStage | None = None
    jaw: PatientJaw | None = None
    reported_context: ReportedContext | None = None


class TargetStrategyRule(TargetSchemaModel):
    id: NonBlankStr
    match: TargetStrategyMatch = Field(default_factory=TargetStrategyMatch)
    max_options: Annotated[StrictInt, Field(ge=2, le=3)] | None = None
    service_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
    offer_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _match_is_not_empty(self) -> "TargetStrategyRule":
        if all(
            getattr(self.match, field) is None
            for field in ("family", "extent", "stage", "jaw", "reported_context")
        ):
            raise ValueError("strategy_rule_match_empty")
        return self


class TargetClinicStrategy(TargetSchemaModel):
    version: Annotated[StrictInt, Field(ge=1)] = 1
    default_max_options: Annotated[StrictInt, Field(ge=2, le=3)] = 3
    default_service_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
    default_offer_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
    rules: list[TargetStrategyRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rule_ids_unique(self) -> "TargetClinicStrategy":
        if _duplicates([rule.id for rule in self.rules]):
            raise ValueError("strategy_rule_id_duplicate")
        return self


class TargetMarketingLimits(TargetSchemaModel):
    max_marketing_facts_per_turn: Annotated[StrictInt, Field(ge=0, le=3)]
    max_amplifiers_per_turn: Annotated[StrictInt, Field(ge=0, le=2)]
    max_scenarios_per_turn: Annotated[StrictInt, Field(ge=0, le=2)]

    @model_validator(mode="after")
    def _amplifiers_fit_fact_limit(self) -> "TargetMarketingLimits":
        if self.max_amplifiers_per_turn > self.max_marketing_facts_per_turn:
            raise ValueError("marketing_amplifier_limit_exceeds_fact_limit")
        return self


class TargetInitialCommercialBlock(TargetSchemaModel):
    ordered_fact_refs: list[FactSourceRef] = Field(default_factory=list)

    @field_validator("ordered_fact_refs", mode="after")
    @classmethod
    def _refs_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("initial_fact_ref_duplicate")
        return value


class TargetScenarioRule(TargetSchemaModel):
    ordered_amplifier_refs: list[SourceRef] = Field(default_factory=list)
    allowed_semantic_contexts: list[NonBlankStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs_unique(self) -> "TargetScenarioRule":
        if _duplicates(self.ordered_amplifier_refs):
            raise ValueError("scenario_amplifier_ref_duplicate")
        if _duplicates(self.allowed_semantic_contexts):
            raise ValueError("scenario_semantic_context_duplicate")
        return self


class TargetFamilyPrice(TargetSchemaModel):
    family_price_id: NonBlankStr
    topic: NonBlankStr
    price: FamilyLevelPrice
    applies_to_service_ids: list[NonBlankStr]
    approved_context: NonBlankStr

    @field_validator("applies_to_service_ids", mode="after")
    @classmethod
    def _applies_unique_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("family_price_applies_empty")
        if _duplicates(value):
            raise ValueError("family_price_applies_duplicate")
        return value


class TargetFamilyPriceCatalog(TargetSchemaModel):
    version: Annotated[StrictInt, Field(ge=1)] = 1
    records: list[TargetFamilyPrice] = Field(default_factory=list)

    @model_validator(mode="after")
    def _record_ids_unique(self) -> "TargetFamilyPriceCatalog":
        if _duplicates([record.family_price_id for record in self.records]):
            raise ValueError("family_price_id_duplicate")
        return self


class TargetMarketingPolicy(TargetSchemaModel):
    version: Annotated[StrictInt, Field(ge=1)] = 1
    limits: TargetMarketingLimits
    initial_commercial_blocks: dict[NonBlankStr, TargetInitialCommercialBlock] = Field(
        default_factory=dict
    )
    scenario_rules: dict[MarketingScenario, TargetScenarioRule] = Field(default_factory=dict)
    cta_contexts: dict[NonBlankStr, NonBlankStr]

    @model_validator(mode="after")
    def _default_cta_required(self) -> "TargetMarketingPolicy":
        if "default" not in self.cta_contexts:
            raise ValueError("marketing_default_cta_missing")
        return self


class ResponseSchemaBundle(TargetSchemaModel):
    """In-memory aggregate used only for deterministic cross-reference validation."""

    services: dict[NonBlankStr, TargetService]
    brands: TargetBrandCatalog
    offers: list[TargetOffer]
    facts: dict[NonBlankStr, TargetCommercialFact]
    strategy: TargetClinicStrategy
    marketing: TargetMarketingPolicy
    family_prices: TargetFamilyPriceCatalog = Field(
        default_factory=TargetFamilyPriceCatalog
    )

    @model_validator(mode="after")
    def _local_references_exist(self) -> "ResponseSchemaBundle":
        offer_ids = [offer.offer_id for offer in self.offers]
        if _duplicates(offer_ids):
            raise ValueError("bundle_offer_id_duplicate")
        offer_id_set = set(offer_ids)

        fact_ids = [fact.id for fact in self.facts.values()]
        if _duplicates(fact_ids):
            raise ValueError("bundle_fact_id_duplicate")
        for fact_id, fact in self.facts.items():
            if fact_id != fact.id:
                raise ValueError("bundle_fact_key_id_mismatch")

        for offer in self.offers:
            service = self.services.get(offer.service_id)
            if service is None:
                raise ValueError("bundle_offer_service_missing")
            if offer.option_id is not None:
                option_ids = {option.option_id for option in service.options}
                if offer.option_id not in option_ids:
                    raise ValueError("bundle_offer_option_missing")
            if offer.brand_id is not None and offer.brand_id not in self.brands.brands:
                raise ValueError("bundle_offer_brand_missing")
            if any(fact_ref not in self.facts for fact_ref in offer.fact_refs):
                raise ValueError("bundle_offer_fact_missing")

        for fact in self.facts.values():
            if any(service_id not in self.services for service_id in fact.allowed_service_ids):
                raise ValueError("bundle_fact_service_missing")
            if any(fact_id not in self.facts for fact_id in fact.incompatible_with):
                raise ValueError("bundle_fact_incompatible_missing")

        if any(
            service_id not in self.services
            for service_id in self.strategy.default_service_priorities
        ):
            raise ValueError("bundle_strategy_service_missing")
        if any(
            offer_id not in offer_id_set
            for offer_id in self.strategy.default_offer_priorities
        ):
            raise ValueError("bundle_strategy_offer_missing")

        for rule in self.strategy.rules:
            if any(service_id not in self.services for service_id in rule.service_priorities):
                raise ValueError("bundle_strategy_service_missing")
            if any(offer_id not in offer_id_set for offer_id in rule.offer_priorities):
                raise ValueError("bundle_strategy_offer_missing")

        for ref in self._marketing_refs():
            if ref.startswith("fact:") and ref.removeprefix("fact:") not in self.facts:
                raise ValueError("bundle_marketing_fact_missing")

        for record in self.family_prices.records:
            if any(
                service_id not in self.services
                for service_id in record.applies_to_service_ids
            ):
                raise ValueError("bundle_family_price_service_missing")

        return self

    def _marketing_refs(self) -> list[str]:
        refs: list[str] = []
        for block in self.marketing.initial_commercial_blocks.values():
            refs.extend(block.ordered_fact_refs)
        for rule in self.marketing.scenario_rules.values():
            refs.extend(rule.ordered_amplifier_refs)
        return refs


S1_MODEL_TYPES = (
    TargetServiceSelection,
    TargetOptionSelection,
    TargetServiceOption,
    TargetService,
    TargetBrand,
    TargetBrandCatalog,
    TargetFixedPrice,
    TargetFromPrice,
    TargetRangePrice,
    TargetNoPublicPrice,
    TargetFamilyPrice,
    TargetFamilyPriceCatalog,
    TargetPricePackage,
    TargetPaymentStage,
    TargetPriceFollowup,
    TargetOffer,
    TargetCommercialFact,
    TargetStrategyMatch,
    TargetStrategyRule,
    TargetClinicStrategy,
    TargetMarketingLimits,
    TargetInitialCommercialBlock,
    TargetScenarioRule,
    TargetMarketingPolicy,
    ResponseSchemaBundle,
)
