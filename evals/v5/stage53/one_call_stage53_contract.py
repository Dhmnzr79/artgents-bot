"""Frozen contract for ONE_CALL Stage 5.3 multiclient offline harness (Checkpoint 1)."""

from __future__ import annotations

MEASUREMENT_ID = "one_call_stage53_multiclient"
MATRIX_SCHEMA = "one_call_stage53_multiclient_matrix_v1"
MATRIX_JSON_REL_PATH = "evals/v5/stage53/one_call_stage53_matrix_v1.json"

# Checkpoint 1: LIVE gate closed — sole authority for this stage.
LIVE_AUTHORIZED_ATTEMPT_ID: str | None = None

# Populated after matrix stabilization; governance tests pin raw-byte SHA.
FROZEN_MATRIX_SHA256: str = "f07925157c0201ef587bcc327d1e26685a8ea4221aa596ef9c34c9c447a5c139"

# Frozen matrix arithmetic (46 cases / 51 HTTP turns).
EXPECTED_CASE_COUNT = 46
EXPECTED_SINGLE_TURN_CASE_COUNT = 43
EXPECTED_MULTI_TURN_SESSION_COUNT = 3
EXPECTED_HTTP_TURN_COUNT = 51
EXPECTED_DEMO_CASE_COUNT = 19
EXPECTED_NIKADENT_CASE_COUNT = 27

# j01 harness default is demo; governance arithmetic counts it toward nikadent.
NIKADENT_ACCOUNTING_CASE_IDS: frozenset[str] = frozenset({"s53_j01_mt_cache_isolation"})
EXPECTED_ZERO_CALL_SINGLE_TURN_COUNT = 10
EXPECTED_ONE_CALL_SINGLE_TURN_COUNT = 33
EXPECTED_TOTAL_FAKE_PROVIDER_CALLS = 39

EXPECTED_CASE_IDS: tuple[str, ...] = (
    "s53_a01_demo_clinic",
    "s53_a02_nika_clinic",
    "s53_a03_demo_aprf",
    "s53_a04_nika_branches",
    "s53_a05_demo_allon4_price",
    "s53_a06_nika_allon4_price",
    "s53_b01_demo_kno_braces_1alt",
    "s53_b02_demo_kno_price_alt",
    "s53_b03_demo_unresolved",
    "s53_b04_demo_npp_price",
    "s53_b05_nika_kno_aligners",
    "s53_b06_nika_kno_sedation",
    "s53_b07_nika_kno_kt",
    "s53_b08_demo_pediatric_policy",
    "s53_b09_nika_pediatric_policy",
    "s53_c01_nika_crown_family",
    "s53_c02_nika_bridge_exact",
    "s53_c03_nika_inlay_exact",
    "s53_c04_nika_sinus_not_implant_family",
    "s53_c05_nika_tax_deduction",
    "s53_c06_nika_neutral_info",
    "s53_d01_demo_osse",
    "s53_d02_nika_osse",
    "s53_d03_demo_parking",
    "s53_d04_nika_no_aprf",
    "s53_d05_nika_no_demo_parking",
    "s53_e01_demo_doctors",
    "s53_e02_nika_doctors",
    "s53_e03_nika_no_demo_doctor",
    "s53_f01_demo_promo_overview",
    "s53_f02_nika_promo_overview",
    "s53_f03_nika_service_promo_none",
    "s53_f04_mt_promo_cadence",
    "s53_g01_demo_contacts",
    "s53_g02_nika_contacts",
    "s53_g03_nika_branch_ryabikova",
    "s53_g04_nika_branch_pogranichnaya",
    "s53_g05_nika_urgent_admin_branch",
    "s53_g06_demo_urgent_admin",
    "s53_g07_mt_booking",
    "s53_h01_demo_admin_symptom",
    "s53_h02_demo_fear_pain",
    "s53_h03_nika_admin_symptom",
    "s53_h04_nika_fear_osse",
    "s53_h05_demo_fear_osse",
    "s53_j01_mt_cache_isolation",
)

DIAGNOSTIC_CASE_IDS: frozenset[str] = frozenset(
    {
        "s53_d01_demo_osse",
        "s53_d02_nika_osse",
        "s53_h05_demo_fear_osse",
    }
)
