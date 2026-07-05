from __future__ import annotations

from core.answer_lens import describe_view, price_view
from core.service_node import ServiceNode, load_service_node


def _node_without_price_or_content() -> ServiceNode:
    return ServiceNode(
        service_id="catalog_only",
        title="Catalog Only",
        active=True,
        content_ref=None,
        price_model=None,
        default_unit=None,
        tags=(),
        offers=(),
        followups=(),
        cta_key=None,
        intro_text=None,
    )


def test_describe_view_veneers_uses_content_ref_and_title():
    node = load_service_node("demo", "veneers")
    assert node is not None

    view = describe_view(node)

    assert view.content_ref
    assert "Виниры" in view.title


def test_price_view_all_on_4_sorts_offers_and_marks_brand_choice():
    node = load_service_node("demo", "all_on_4")
    assert node is not None

    view = price_view(node)

    assert view.price_model == "complex"
    assert len(view.offers) == 3
    assert [offer.total for offer in view.offers] == [318000, 368000, 428000]
    assert view.min_total == 318000
    assert view.has_brand_choice is True


def test_price_view_veneers_single_offer_has_no_brand_choice():
    node = load_service_node("demo", "veneers")
    assert node is not None

    view = price_view(node)

    assert len(view.offers) == 1
    assert view.min_total == 35000
    assert view.has_brand_choice is False


def test_price_view_empty_offers_has_no_min_total_or_brand_choice():
    view = price_view(_node_without_price_or_content())

    assert view.offers == ()
    assert view.min_total is None
    assert view.has_brand_choice is False


def test_describe_view_without_content_ref_keeps_none():
    view = describe_view(_node_without_price_or_content())

    assert view.content_ref is None
