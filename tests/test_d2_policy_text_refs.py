"""One captured MD source for ordinary context and code-owned action refusals."""
import json
import shutil
from pathlib import Path

import pytest
import yaml

from core.clinic_policies_loader import resolve_policy_text, validate_policy_text_refs
from core.d2_snapshot_sources import d2_authored_policy_answers
from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation


@pytest.mark.parametrize("ref,md,error", [
    ("../other.md#rule", "", "ref_invalid"),
    ("other/policy.md#rule", "", "ref_invalid"),
    ("policy.md", "", "ref_invalid"),
    (0, "", "ref_invalid"),
    ("policy.md#rule", "### Other {#other}\nText", "missing_or_duplicate"),
    ("policy.md#rule", "### Rule {#rule}\n\n### Next {#next}\nText", "section_empty"),
    ("policy.md#rule", "### Rule {#rule}\nOne\n### Again {#rule}\nTwo", "missing_or_duplicate"),
    ("policy.md#rule", "### Rule {#rule}\nOne\n## Again {#rule}\nTwo", "missing_or_duplicate"),
])
def test_bad_reference_is_data_error(ref, md, error):
    with pytest.raises(ValueError, match=error):
        resolve_policy_text({"text_ref": ref}, lambda _: md)


def test_missing_document_and_old_inline_copy_never_fall_back():
    with pytest.raises(ValueError, match="document_missing"):
        resolve_policy_text({"text_ref": "policy.md#rule"}, {}.__getitem__)
    for field in ("answer", "approved_text", "note"):
        with pytest.raises(ValueError, match="inline_text_forbidden"):
            resolve_policy_text({"text_ref": "policy.md#rule", field: "old copy"},
                                lambda _: "### Rule {#rule}\nNew text")


@pytest.mark.parametrize("raw_data", [None, [], {"policies": []}, {"policies": {"x": None}}])
def test_bad_registry_rejected(raw_data):
    with pytest.raises(ValueError, match="malformed"):
        validate_policy_text_refs(raw_data, lambda _: "")


def test_captured_text_survives_disk_edit_and_new_snapshot_sees_edit(tmp_path):
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    first = load_d2_tenant_snapshot("demo", clients_root=root)
    before = d2_authored_policy_answers(first)["no_oms"]
    path = root / "demo/md/clinic__info__policies.md"
    changed = "По ОМС не принимаем. Это обновлённый текст из MD."
    path.write_text(path.read_text(encoding="utf-8").replace(before, changed), encoding="utf-8")
    assert d2_authored_policy_answers(first)["no_oms"] == before
    second = load_d2_tenant_snapshot("demo", clients_root=root)
    assert d2_authored_policy_answers(second)["no_oms"] == changed
    assert second.fingerprint != first.fingerprint
    view = build_d2_model_view(second)
    assert changed in next(doc.display_text for doc in second.content
                           if doc.content_ref == "clinic__info__policies.md")
    catalog = json.loads(view.clinic_policy_catalog_json)
    assert {"policy_id": "no_oms", "text_ref": "clinic__info__policies.md#no_oms"} in catalog["policies"]
    assert changed not in view.clinic_policy_catalog_json


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("kind", ["price", "booking"])
@pytest.mark.parametrize("policy,fields", [
    ("no_pediatric_dentistry", {"age_group": "child"}),
    ("no_oms", {"payment_scheme": "oms", "payment_scheme_intent": "requested_payment"}),
    ("no_dms", {"payment_scheme": "dms", "payment_scheme_intent": "requested_payment"}),
])
def test_md_owns_refusal_and_history_without_price_or_booking(http_env, transport, kind, policy, fields):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/md/clinic__info__policies.md"
    rules = yaml.safe_load((tmp / "clients/demo/clinic_policies.yaml").read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    before = resolve_policy_text(rules["policies"][policy], lambda _: text)
    expected = before + " Подробности уточните в клинике."
    path.write_text(text.replace(before, expected), encoding="utf-8")
    block = {"kind": kind, "request_id": "r1", **fields}
    if kind == "price":
        block["target"] = {"type": "service", "id": "caries"}
    fake = use(FakeProvider(raw(block)))
    result = send(client, transport, request_id="first", q="Лечение и условия приёма")
    assert result["answer"] == expected
    assert not result["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert not any(b["action_kind"] == "cta" for b in result["ui"]["buttons"])
    assert send(client, transport, request_id="first", q="Лечение и условия приёма") == result
    assert len(fake.inputs) == 1
    fake.raw = raw(explanation("Могу рассказать об услугах."))
    send(client, transport, request_id="next", q="Расскажите")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == expected


@pytest.mark.parametrize("tenant", ["demo", "nikadent"])
def test_all_authored_rows_resolve_without_inline_copies(tenant):
    root = Path("clients") / tenant
    data = yaml.safe_load((root / "clinic_policies.yaml").read_text(encoding="utf-8"))
    validate_policy_text_refs(data, lambda name: (root / "md" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("group,service,brand", [
    ("service_alternatives", "braces", None),
    ("brand_alternatives", "classic", "osstem"),
])
def test_unavailable_price_uses_md_without_creating_offer(http_env, transport, group, service, brand):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/md/clinic__info__policies.md"
    data = yaml.safe_load((tmp / "clients/demo/clinic_policies.yaml").read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    old = resolve_policy_text(data[group][0], lambda _: text)
    expected = "Этот вариант в клинике недоступен. Уточните альтернативы у администратора."
    path.write_text(text.replace(old, expected), encoding="utf-8")
    block = {"kind": "price", "request_id": "r1", "target": {"type": "service", "id": service}}
    if brand:
        block["brand_id"] = brand
    fake = use(FakeProvider(raw(block)))
    result = send(client, transport, q="Сколько стоит этот вариант?")
    suffix = "\n\n- Элайнеры для выравнивания зубов" if service == "braces" else ""
    assert result["answer"] == expected + suffix
    assert result["ui"]["projected_commercial_ids"]["price_offer_ids"] == []
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("ref", ["missing.md#rule", "clinic__info__policies.md#missing", "../nikadent/md/policy.md#rule"])
def test_broken_policy_ref_fails_before_provider_without_booking(http_env, transport, ref):
    from tests.d2_ci_http import post, post_sse, sse_events
    from session import mem_get, session_client_scope
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/clinic_policies.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["policies"]["no_pediatric_dentistry"]["text_ref"] = ref
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    fake = use(FakeProvider(raw({"kind": "booking", "request_id": "r1", "age_group": "adult"})))
    response = (post if transport == "json" else post_sse)(client, sid="bad-ref", q="Хочу записаться")
    body = response.get_json() if transport == "json" else dict(sse_events(response))
    assert "d2_invalid_turn" in json.dumps(body)
    assert fake.inputs == []
    with session_client_scope("demo"):
        assert mem_get("bad-ref").get("lead_intent") != "collecting_name"
