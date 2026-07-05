from __future__ import annotations

from core.service_node import list_service_nodes, load_service_node


def test_service_node_simple_veneers():
    node = load_service_node("demo", "veneers")

    assert node is not None
    assert "Виниры" in node.title
    assert node.active is True
    assert node.content_ref
    assert node.price_model == "simple"
    assert node.default_unit == "one_tooth"
    assert len(node.offers) == 1
    offer = node.offers[0]
    assert offer.total == 35000
    assert offer.unit == "one_tooth"
    assert offer.recommended is False


def test_service_node_simple_without_unit_keeps_price():
    # unit-less simple services (отбеливание/КТ/лечение) must still expose the price
    node = load_service_node("demo", "professional_whitening")

    assert node is not None
    assert node.price_model == "simple"
    assert node.default_unit is None
    assert len(node.offers) == 1
    assert node.offers[0].total == 18000
    assert node.offers[0].unit == ""


def test_service_node_complex_all_on_4_offers_keep_pricebook_order():
    node = load_service_node("demo", "all_on_4")

    assert node is not None
    assert node.price_model == "complex"
    assert node.default_unit == "jaw"
    assert node.content_ref
    assert [(offer.brand, offer.total, offer.recommended) for offer in node.offers] == [
        ("Implantium", 318000, False),
        ("Impro", 368000, True),
        ("Nobel Biocare", 428000, False),
    ]
    assert [offer.brand_label for offer in node.offers] == [
        "Implantium (Южная Корея)",
        "Impro (Германия)",
        "Nobel Biocare (Швейцария)",
    ]


def test_service_node_missing_returns_none():
    assert load_service_node("demo", "definitely_missing_service") is None


def test_list_service_nodes_demo_returns_catalog_and_pricebook_services():
    nodes = list_service_nodes("demo")

    assert len(nodes) >= 20
    service_ids = {node.service_id for node in nodes}
    assert "veneers" in service_ids
    assert "all_on_4" in service_ids
