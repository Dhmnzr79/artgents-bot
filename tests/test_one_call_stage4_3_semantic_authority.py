from __future__ import annotations

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallEnvelope
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import production_envelope_template
from core.sales_fast_turn_frame import build_provisional_turn_frame, build_turn_frame_from_semantic_frame
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.sales_one_plus_semantic_authority import (
    SalesOnePlusSemanticConflictError,
    bind_semantic_frame,
    governed_ui_authority_from_resolution,
)
from core.target_client_data import load_target_client_data


_DEMO_CATALOG = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
_DEMO_REF_CATALOG = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
_BUNDLE = load_target_client_data("demo").bundle


def _envelope(**overrides: object) -> OneCallEnvelope:
    return OneCallEnvelope.model_validate({**production_envelope_template(), **overrides})


def _governed_resolution(**kwargs: object) -> ExactSalesResolution:
    ui = ExactSalesFieldAuthority(authority="governed_ui", provenance="ui")
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    return ExactSalesResolution(
        service_id=kwargs.get("service_id", "classic"),
        aspect=kwargs.get("aspect", "price"),
        extent=kwargs.get("extent", "one_tooth"),
        jaw=kwargs.get("jaw", None),
        stage=kwargs.get("stage", None),
        service_id_authority=ui,
        aspect_authority=unknown,
        extent_authority=ui if kwargs.get("extent") else unknown,
        jaw_authority=unknown,
        stage_authority=unknown,
    )


def test_ui_fills_null_envelope_scope_fields() -> None:
    governed = governed_ui_authority_from_resolution(
        _governed_resolution(service_id="classic", extent="one_tooth")
    )
    frame = bind_semantic_frame(
        envelope=_envelope(service_id=None, extent=None),
        governed_ui=governed,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert frame.service_id == "classic"
    assert frame.service_id_provenance == "governed_ui"
    assert frame.extent == "one_tooth"
    assert frame.extent_provenance == "governed_ui"
    assert frame.rebind_kind == "full_rebuild"


def test_envelope_null_stays_null_without_governed_ui() -> None:
    governed = governed_ui_authority_from_resolution(_governed_resolution())
    governed = governed_ui_authority_from_resolution(
        ExactSalesResolution(
            None,
            None,
            None,
            None,
            None,
            ExactSalesFieldAuthority(authority="unknown", provenance="unknown"),
            ExactSalesFieldAuthority(authority="unknown", provenance="unknown"),
            ExactSalesFieldAuthority(authority="unknown", provenance="unknown"),
            ExactSalesFieldAuthority(authority="unknown", provenance="unknown"),
            ExactSalesFieldAuthority(authority="unknown", provenance="unknown"),
        )
    )
    frame = bind_semantic_frame(
        envelope=_envelope(service_id=None, extent=None, jaw=None, stage=None),
        governed_ui=governed,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert frame.service_id is None
    assert frame.service_id_provenance == "null"


def test_bind_semantic_frame_forces_clarify_commercial_intent_none() -> None:
    governed = governed_ui_authority_from_resolution(_governed_resolution())
    frame = bind_semantic_frame(
        envelope=_envelope(
            route="CLARIFY",
            patient_text="Уточните, один зуб или несколько?",
            clarify_axis="extent",
            commercial_intent="price",
            service_id="classic",
        ),
        governed_ui=governed,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert frame.route == "CLARIFY"
    assert frame.commercial_intent == "none"


def test_presentation_commercial_intent_for_clarify_is_none() -> None:
    from core.sales_one_plus_semantic_authority import presentation_commercial_intent

    frame = bind_semantic_frame(
        envelope=_envelope(
            route="CLARIFY",
            patient_text="Уточните объём.",
            clarify_axis="extent",
            commercial_intent="payment",
        ),
        governed_ui=governed_ui_authority_from_resolution(_governed_resolution()),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert presentation_commercial_intent(frame) == "none"


def test_ui_envelope_conflict_fail_closed() -> None:
    governed = governed_ui_authority_from_resolution(_governed_resolution(service_id="classic"))
    with pytest.raises(SalesOnePlusSemanticConflictError) as exc:
        bind_semantic_frame(
            envelope=_envelope(
                service_id=None,
                service_reference_status="resolved",
                requested_service_id="all_on_4",
            ),
            governed_ui=governed,
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        )
    assert exc.value.code == "semantic_ui_envelope_conflict_service_id"


def test_provisional_turn_frame_has_no_implantation_default() -> None:
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        "overview",
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    frame = build_provisional_turn_frame(
        resolution=resolution,
        user_message="Как обеспечивается стерильность?",
        client_id="demo",
        bundle=_BUNDLE,
    )
    assert frame.service_id is None
    assert frame.topic is None


def test_bind_semantic_frame_catalog_envelope_conflict_raises() -> None:
    from core.sales_one_plus_semantic_authority import (
        SalesOnePlusSemanticConflictError,
        bind_semantic_frame,
        governed_ui_authority_from_resolution,
    )
    from tests.test_one_call_stage4_3_semantic_authority import (
        _DEMO_CATALOG,
        _DEMO_REF_CATALOG,
        _envelope,
        _governed_resolution,
    )

    with pytest.raises(SalesOnePlusSemanticConflictError) as caught:
        bind_semantic_frame(
            envelope=_envelope(service_id="professional_whitening"),
            governed_ui=governed_ui_authority_from_resolution(_governed_resolution(service_id=None)),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            explicit_catalog_service_id="tomography",
        )
    assert caught.value.code == "semantic_catalog_envelope_conflict_service_id"


def test_authoritative_turn_frame_from_confirmed_implant_service() -> None:
    frame = build_turn_frame_from_semantic_frame(
        semantic=bind_semantic_frame(
            envelope=_envelope(service_id="classic"),
            governed_ui=governed_ui_authority_from_resolution(_governed_resolution()),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        ),
        user_message="Сколько стоит имплант?",
        bundle=_BUNDLE,
    )
    assert frame.service_id == "classic"
    assert frame.topic == "implantation"


def test_authoritative_turn_frame_non_implant_service_not_implantation() -> None:
    frame = build_turn_frame_from_semantic_frame(
        semantic=bind_semantic_frame(
            envelope=_envelope(service_id="professional_whitening"),
            governed_ui=governed_ui_authority_from_resolution(
                _governed_resolution(service_id="professional_whitening")
            ),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        ),
        user_message="Расскажите про отбеливание",
        bundle=_BUNDLE,
    )
    assert frame.service_id == "professional_whitening"
    assert frame.topic == "whitening"


def test_prosthodontics_family_maps_to_prosthetics_topic() -> None:
    frame = build_turn_frame_from_semantic_frame(
        semantic=bind_semantic_frame(
            envelope=_envelope(service_id="zirconia_crowns"),
            governed_ui=governed_ui_authority_from_resolution(
                _governed_resolution(service_id="zirconia_crowns")
            ),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        ),
        user_message="Сколько стоит циркониевая коронка?",
        bundle=_BUNDLE,
    )
    assert frame.service_id == "zirconia_crowns"
    assert frame.topic == "prosthetics"


def test_implantology_family_still_maps_to_implantation_topic() -> None:
    frame = build_turn_frame_from_semantic_frame(
        semantic=bind_semantic_frame(
            envelope=_envelope(service_id="classic"),
            governed_ui=governed_ui_authority_from_resolution(
                _governed_resolution(service_id="classic")
            ),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        ),
        user_message="Сколько стоит имплант?",
        bundle=_BUNDLE,
    )
    assert frame.service_id == "classic"
    assert frame.topic == "implantation"
