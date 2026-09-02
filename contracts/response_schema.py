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
    service_value_ref: FactSourceRef | None = None
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



class RequestedDisplayPolicy(BaseModel):
    """Owner-approved metadata for informational display without a concrete service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allow_clinic: bool = False
    allowed_topic_ids: tuple[NonBlankStr, ...] = ()
    canonical_text_is_scope_qualified: bool = False

    @model_validator(mode="after")
    def _qualified_when_extended(self) -> "RequestedDisplayPolicy":
        extended = self.allow_clinic or bool(self.allowed_topic_ids)
        if extended and not self.canonical_text_is_scope_qualified:
            raise ValueError("requested_display_requires_scope_qualification")
        return self


class TargetCommercialFact(TargetSchemaModel):
    id: NonBlankStr
    kind: NonBlankStr
    catalog_label: NonBlankStr
    text_fact: NonBlankStr
    render_mode: NonBlankStr
    active: bool = True
    active_from: IsoDate | None = None
    active_until: IsoDate | None = None
    allowed_service_ids: list[NonBlankStr] = Field(default_factory=list)
    allowed_topics: list[NonBlankStr] = Field(default_factory=list)
    detail_ref: NonBlankStr | None = None
    incompatible_with: list[NonBlankStr] = Field(default_factory=list)
    requested_display_policy: RequestedDisplayPolicy | None = None

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


GenericPriceMode = Literal["overview", "entry_from", "featured_single"]


class TargetGenericPricePolicy(TargetSchemaModel):
    """Clinic-owned policy for generic (non-brand-specific) price questions."""

    mode: GenericPriceMode
    featured_offer_id: NonBlankStr | None = None
    max_price_options: Annotated[StrictInt, Field(ge=2, le=3)] | None = None

    @model_validator(mode="after")
    def _featured_required_for_single(self) -> "TargetGenericPricePolicy":
        if self.mode == "featured_single" and self.featured_offer_id is None:
            raise ValueError("generic_price_featured_offer_required")
        return self


class TargetStrategyRule(TargetSchemaModel):
    id: NonBlankStr
    match: TargetStrategyMatch = Field(default_factory=TargetStrategyMatch)
    max_options: Annotated[StrictInt, Field(ge=2, le=3)] | None = None
    service_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
    offer_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
    generic_price_policy: TargetGenericPricePolicy | None = None

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
    default_generic_price_policy: TargetGenericPricePolicy | None = None
    rules: list[TargetStrategyRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rule_ids_unique(self) -> "TargetClinicStrategy":
        if _duplicates([rule.id for rule in self.rules]):
            raise ValueError("strategy_rule_id_duplicate")
        return self


class TargetAnswerProfileLimits(TargetSchemaModel):
    max_promos_per_turn: Annotated[StrictInt, Field(ge=0, le=2)] = 2
    max_amplifiers_per_turn: Annotated[StrictInt, Field(ge=0, le=4)] = 2


class TargetMarketingLimits(TargetSchemaModel):
    max_marketing_facts_per_turn: Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    max_amplifiers_per_turn: Annotated[StrictInt, Field(ge=0, le=4)] | None = None
    max_scenarios_per_turn: Annotated[StrictInt, Field(ge=0, le=2)] = 2
    service: TargetAnswerProfileLimits | None = None
    price: TargetAnswerProfileLimits | None = None

    @staticmethod
    def _cap_promos(value: int) -> int:
        return min(value, 2)

    @staticmethod
    def _cap_service_amplifiers(value: int) -> int:
        return min(value, 2)

    @staticmethod
    def _cap_price_amplifiers(value: int) -> int:
        return min(value, 4)

    @model_validator(mode="after")
    def _normalize_profiles(self) -> "TargetMarketingLimits":
        if self.service is not None:
            if self.service.max_promos_per_turn > 2:
                raise ValueError("marketing_service_promo_limit_exceeds_cap")
            if self.service.max_amplifiers_per_turn > 2:
                raise ValueError("marketing_service_amplifier_limit_exceeds_cap")
        if self.price is not None:
            if self.price.max_promos_per_turn > 2:
                raise ValueError("marketing_price_promo_limit_exceeds_cap")
            if self.price.max_amplifiers_per_turn > 4:
                raise ValueError("marketing_price_amplifier_limit_exceeds_cap")

        legacy_promos = self.max_marketing_facts_per_turn
        legacy_amplifiers = self.max_amplifiers_per_turn
        if self.service is None:
            promos = self._cap_promos(legacy_promos if legacy_promos is not None else 2)
            amplifiers = self._cap_service_amplifiers(
                legacy_amplifiers if legacy_amplifiers is not None else 2
            )
            self.service = TargetAnswerProfileLimits(
                max_promos_per_turn=promos,
                max_amplifiers_per_turn=amplifiers,
            )
        if self.price is None:
            promos = self._cap_promos(legacy_promos if legacy_promos is not None else 2)
            amplifiers = self._cap_price_amplifiers(
                legacy_amplifiers if legacy_amplifiers is not None else 4
            )
            if legacy_promos is not None:
                amplifiers = self._cap_price_amplifiers(
                    legacy_amplifiers if legacy_amplifiers is not None else 2
                )
            self.price = TargetAnswerProfileLimits(
                max_promos_per_turn=promos,
                max_amplifiers_per_turn=amplifiers,
            )
        if legacy_promos is None:
            self.max_marketing_facts_per_turn = self.service.max_promos_per_turn
        else:
            self.max_marketing_facts_per_turn = self._cap_promos(legacy_promos)
        if legacy_amplifiers is None:
            self.max_amplifiers_per_turn = self.service.max_amplifiers_per_turn
        else:
            self.max_amplifiers_per_turn = legacy_amplifiers
        return self

    def profile_limits(self, profile: str) -> tuple[int, int]:
        block = self.price if profile == "price" else self.service
        if block is None:
            return 2, 2
        return block.max_promos_per_turn, block.max_amplifiers_per_turn


class TargetAutomaticCommercialRefs(TargetSchemaModel):
    ordered_promo_refs: list[FactSourceRef] = Field(default_factory=list)
    ordered_amplifier_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs_unique(self) -> "TargetAutomaticCommercialRefs":
        if _duplicates(self.ordered_promo_refs):
            raise ValueError("automatic_promo_ref_duplicate")
        if _duplicates(self.ordered_amplifier_refs):
            raise ValueError("automatic_amplifier_ref_duplicate")
        return self


class TargetServiceAutomaticCommercial(TargetSchemaModel):
    service: TargetAutomaticCommercialRefs | None = None
    price: TargetAutomaticCommercialRefs | None = None


class TargetInitialCommercialBlock(TargetSchemaModel):
    ordered_fact_refs: list[FactSourceRef] = Field(default_factory=list)

    @field_validator("ordered_fact_refs", mode="after")
    @classmethod
    def _refs_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("initial_fact_ref_duplicate")
        return value


class TargetServicePromoMapping(TargetSchemaModel):
    ordered_fact_refs: list[FactSourceRef] = Field(default_factory=list)

    @field_validator("ordered_fact_refs", mode="after")
    @classmethod
    def _refs_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("priority_service_promo_ref_duplicate")
        return value


class TargetPromotionOverview(TargetSchemaModel):
    ordered_fact_refs: list[FactSourceRef] = Field(default_factory=list)

    @field_validator("ordered_fact_refs", mode="after")
    @classmethod
    def _refs_unique(cls, value: list[str]) -> list[str]:
        if _duplicates(value):
            raise ValueError("promotion_overview_ref_duplicate")
        return value


class TargetScenarioRule(TargetSchemaModel):
    ordered_amplifier_refs: list[SourceRef] = Field(default_factory=list)
    allowed_semantic_contexts: list[NonBlankStr] = Field(default_factory=list)
    allowed_topics: list[NonBlankStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs_unique(self) -> "TargetScenarioRule":
        if _duplicates(self.ordered_amplifier_refs):
            raise ValueError("scenario_amplifier_ref_duplicate")
        if _duplicates(self.allowed_semantic_contexts):
            raise ValueError("scenario_semantic_context_duplicate")
        if _duplicates(self.allowed_topics):
            raise ValueError("scenario_allowed_topic_duplicate")
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
    service_automatic_commercial: dict[NonBlankStr, TargetServiceAutomaticCommercial] = Field(
        default_factory=dict
    )
    ordered_amplifier_refs: list[SourceRef] = Field(default_factory=list)
    priority_service_promos: dict[NonBlankStr, TargetServicePromoMapping] = Field(
        default_factory=dict
    )
    promotion_overview: TargetPromotionOverview = Field(
        default_factory=TargetPromotionOverview
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
            self._validate_generic_price_policy_refs(
                rule.generic_price_policy,
                offer_id_set=offer_id_set,
            )

        self._validate_generic_price_policy_refs(
            self.strategy.default_generic_price_policy,
            offer_id_set=offer_id_set,
        )

        for ref in self._marketing_refs():
            if ref.startswith("fact:") and ref.removeprefix("fact:") not in self.facts:
                raise ValueError("bundle_marketing_fact_missing")

        self._validate_promo_authority_refs()

        for record in self.family_prices.records:
            if any(
                service_id not in self.services
                for service_id in record.applies_to_service_ids
            ):
                raise ValueError("bundle_family_price_service_missing")

        return self

    def _validate_generic_price_policy_refs(
        self,
        policy: TargetGenericPricePolicy | None,
        *,
        offer_id_set: set[str],
    ) -> None:
        if policy is None or policy.featured_offer_id is None:
            return
        if policy.featured_offer_id not in offer_id_set:
            raise ValueError("bundle_strategy_generic_price_offer_missing")

    def _marketing_refs(self) -> list[str]:
        refs: list[str] = []
        for block in self.marketing.initial_commercial_blocks.values():
            refs.extend(block.ordered_fact_refs)
        refs.extend(self.marketing.ordered_amplifier_refs)
        for mapping in self.marketing.priority_service_promos.values():
            refs.extend(mapping.ordered_fact_refs)
        for svc_policy in self.marketing.service_automatic_commercial.values():
            for profile_block in (svc_policy.service, svc_policy.price):
                if profile_block is None:
                    continue
                refs.extend(profile_block.ordered_promo_refs)
                refs.extend(profile_block.ordered_amplifier_refs)
        refs.extend(self.marketing.promotion_overview.ordered_fact_refs)
        for rule in self.marketing.scenario_rules.values():
            refs.extend(rule.ordered_amplifier_refs)
        service_value_refs = [
            service.service_value_ref
            for service in self.services.values()
            if service.service_value_ref
        ]
        refs.extend(service_value_refs)
        return refs

    def _validate_promo_authority_refs(self) -> None:
        promo_kinds = frozenset({"promo"})
        for service_id, mapping in self.marketing.service_automatic_commercial.items():
            if service_id not in self.services:
                raise ValueError("marketing_automatic_service_missing")
        for service_id, mapping in self.marketing.priority_service_promos.items():
            if service_id not in self.services:
                raise ValueError("marketing_priority_service_missing")
            for ref in mapping.ordered_fact_refs:
                if not ref.startswith("fact:"):
                    raise ValueError("marketing_priority_promo_ref_invalid")
                fact_id = ref.removeprefix("fact:")
                fact = self.facts.get(fact_id)
                if fact is None:
                    raise ValueError("bundle_marketing_fact_missing")
                if fact.kind not in promo_kinds:
                    raise ValueError("marketing_priority_promo_kind_invalid")
                if fact.allowed_service_ids and service_id not in fact.allowed_service_ids:
                    raise ValueError("marketing_priority_promo_service_applicability_invalid")
        for ref in self.marketing.promotion_overview.ordered_fact_refs:
            if not ref.startswith("fact:"):
                raise ValueError("marketing_overview_ref_invalid")
            fact_id = ref.removeprefix("fact:")
            fact = self.facts.get(fact_id)
            if fact is None:
                raise ValueError("bundle_marketing_fact_missing")
            if fact.kind not in promo_kinds:
                raise ValueError("marketing_overview_promo_kind_invalid")


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
    RequestedDisplayPolicy,
    TargetCommercialFact,
    TargetStrategyMatch,
    TargetStrategyRule,
    TargetClinicStrategy,
    TargetGenericPricePolicy,
    TargetMarketingLimits,
    TargetAnswerProfileLimits,
    TargetAutomaticCommercialRefs,
    TargetServiceAutomaticCommercial,
    TargetInitialCommercialBlock,
    TargetServicePromoMapping,
    TargetPromotionOverview,
    TargetScenarioRule,
    TargetMarketingPolicy,
    ResponseSchemaBundle,
)
