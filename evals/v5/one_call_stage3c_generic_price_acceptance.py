"""Owner-approved generic price acceptance (Stage 3C v3, separate from frozen v2 matrix)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenericPriceAcceptanceCase:
    case_id: str
    user_message: str
    critical_required_all: tuple[str, ...] = ()
    forbidden_price_tokens: tuple[str, ...] = ()
    required_offer_ids: tuple[str, ...] = ()
    featured_offer_id: str | None = None
    expected_mode: str | None = None
    explicit_brand: str | None = None


GENERIC_PRICE_ACCEPTANCE_V3: tuple[GenericPriceAcceptanceCase, ...] = (
    GenericPriceAcceptanceCase(
        case_id="gp03_generic_overview",
        user_message="Сколько стоит классический имплант за один зуб?",
        critical_required_all=("от", "76", "200", "Implantium", "Impro", "Nobel"),
        forbidden_price_tokens=("99999",),
        required_offer_ids=(
            "classic.one_tooth.implantium",
            "classic.one_tooth.impro",
            "classic.one_tooth.nobel",
        ),
        featured_offer_id="classic.one_tooth.impro",
        expected_mode="overview",
    ),
    GenericPriceAcceptanceCase(
        case_id="gp03_explicit_implantium",
        user_message="Сколько стоит классический имплант Implantium за один зуб?",
        critical_required_all=("76", "200"),
        forbidden_price_tokens=("85200", "101200"),
        required_offer_ids=("classic.one_tooth.implantium",),
        expected_mode="exact_offer",
        explicit_brand="implantium",
    ),
    GenericPriceAcceptanceCase(
        case_id="gp03_explicit_impro",
        user_message="Сколько стоит классический имплант Impro за один зуб?",
        critical_required_all=("85", "200"),
        forbidden_price_tokens=("76200", "101200"),
        required_offer_ids=("classic.one_tooth.impro",),
        expected_mode="exact_offer",
        explicit_brand="impro",
    ),
)

GENERIC_PRICE_ACCEPTANCE_V3_SHA256 = (
    "owner_approved_v3_generic_price_overview_entry_from_featured_single"
)
