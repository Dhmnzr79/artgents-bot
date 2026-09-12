from core.price_ref_routing import parse_price_widget_ref


def test_parse_price_widget_ref_service():
    assert parse_price_widget_ref("price:classic") == {
        "service_id": "classic",
        "group_id": None,
        "aspect": None,
    }


def test_parse_price_widget_ref_overview():
    assert parse_price_widget_ref("price:implantation/overview") == {
        "service_id": None,
        "group_id": "implantation",
        "aspect": "overview",
    }


def test_parse_price_widget_ref_aspect_stages():
    assert parse_price_widget_ref("price:all_on_4/stages") == {
        "service_id": "all_on_4",
        "group_id": None,
        "aspect": "stages",
    }

