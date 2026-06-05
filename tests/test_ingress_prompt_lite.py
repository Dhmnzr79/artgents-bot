"""Level-1 ingress: lite prompt without catalog on typical questions."""

from __future__ import annotations

from ingress_gate import ingress_include_offered_catalog


def test_lite_price_question_no_catalog():
    assert ingress_include_offered_catalog("сколько стоит имплантация") is False


def test_lite_address_no_catalog():
    assert ingress_include_offered_catalog("где вы находитесь") is False


def test_lite_comparison_no_catalog():
    assert ingress_include_offered_catalog("имплант или мост что лучше") is False


def test_full_availability_with_catalog():
    assert ingress_include_offered_catalog("есть ли у вас имплантация") is True


def test_full_do_you_offer_with_catalog():
    assert ingress_include_offered_catalog("делаете ли виниры") is True


def test_full_braces_without_li_gets_catalog():
    assert ingress_include_offered_catalog("А брекеты делаете?") is True


def test_full_do_you_offer_kt_compound():
    assert ingress_include_offered_catalog("Вы делаете КТ зубов и сколько это стоит?") is True
