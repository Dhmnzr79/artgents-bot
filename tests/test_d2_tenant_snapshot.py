from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.d2_tenant_snapshot import D2TenantSnapshotError, build_d2_bundle, build_d2_model_view, load_d2_tenant_snapshot
from tests.d2_ci_http import FakeProvider, http_env, raw, send


def _copy_demo(tmp_path: Path, name: str = "demo") -> Path:
    root = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", root / name)
    return root


def test_material_without_korotko_is_published(tmp_path: Path) -> None:
    root = _copy_demo(tmp_path)
    docs = root / "demo" / "md"
    (docs / "ordinary.md").write_text(
        """---\ndoc_id: ordinary\n---\n<!-- private note -->\n## Первый раздел\nПервый текст.\n### Вложенный {#inside}\nВложенный текст.\n```md\n## Не заголовок\n```\n## Дубликат {#inside}\nЭтот якорь не публикуется.\n""",
        encoding="utf-8",
    )
    (docs / "empty.md").write_text("<!-- no public text -->\n", encoding="utf-8")

    snapshot = load_d2_tenant_snapshot("demo", clients_root=root)
    ordinary = next(item for item in snapshot.content if item.content_ref == "ordinary.md")

    assert "Коротко" not in ordinary.display_text
    assert [item.section_ref for item in ordinary.sections] == ["h:1", "a:inside"]
    assert "Вложенный текст" in ordinary.sections[0].display_text
    assert "md/empty.md:content_empty" in snapshot.diagnostics
    assert any(item == "md/ordinary.md:duplicate_section_ref:a:inside" for item in snapshot.diagnostics)


def test_snapshot_capture_identity_and_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_demo(tmp_path)
    first = load_d2_tenant_snapshot("demo", clients_root=root)
    (root / "demo" / "target_response" / "pricebook" / "family_prices.json").write_text("{}", encoding="utf-8")
    second = load_d2_tenant_snapshot("demo", clients_root=root)
    assert first.fingerprint != second.fingerprint

    first.bundle.services.clear()
    assert build_d2_bundle(first).services
    assert build_d2_model_view(first).active_service_catalog.canonical_json

    def forbidden_read(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("post-capture filesystem read")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    assert build_d2_bundle(first).offers
    assert build_d2_model_view(first).published_terms

    import core.d2_tenant_snapshot as snapshot_module

    monkeypatch.undo()
    original = snapshot_module._read_set
    calls = 0

    def changing(client_root: Path):
        nonlocal calls
        calls += 1
        result = original(client_root)
        if calls == 2:
            return result + (("md/late.md", b"# late"),)
        return result

    monkeypatch.setattr(snapshot_module, "_read_set", changing)
    with pytest.raises(D2TenantSnapshotError, match="tenant_pack_changed_during_capture"):
        load_d2_tenant_snapshot("demo", clients_root=root)


def test_snapshot_rejects_path_escape_and_missing_required_pack(tmp_path: Path) -> None:
    root = _copy_demo(tmp_path)
    with pytest.raises(D2TenantSnapshotError, match="client_id_invalid"):
        load_d2_tenant_snapshot("../demo", clients_root=root)
    (root / "demo" / "target_response" / "service_catalog.json").unlink()
    with pytest.raises(D2TenantSnapshotError, match="required_path_missing"):
        load_d2_tenant_snapshot("demo", clients_root=root)


@pytest.mark.parametrize("mode", ["missing", "invalid"])
def test_d2_catalog_ignores_legacy_policies_without_fingerprint_or_prompt_change(tmp_path, monkeypatch, mode):
    from dataclasses import replace
    from contracts.response_schema import ResponseDataCatalog, ResponseSchemaBundle
    from contracts.response_plan import SessionKey
    from core.d2_snapshot_sources import build_d2_snapshot_sources
    from core.d2_live_provider import build_d2_d1r_messages
    from tests.test_d2_live_provider_offline import _request

    root = _copy_demo(tmp_path)
    first = load_d2_tenant_snapshot("demo", clients_root=root)
    first_view = build_d2_model_view(first)
    first_messages = build_d2_d1r_messages(replace(_request(), model_view=first_view))
    for name in ("marketing.yaml", "clinic_strategy.yaml"):
        path = root / "demo" / "target_response" / name
        if mode == "missing":
            path.unlink()
        else:
            path.write_bytes(b"\xffnot even UTF-8 or YAML")

    def forbidden(*args, **kwargs):
        raise AssertionError("D2 constructed a legacy policy bundle")

    monkeypatch.setattr(ResponseSchemaBundle, "model_validate", forbidden)
    second = load_d2_tenant_snapshot("demo", clients_root=root)
    assert type(second.bundle) is ResponseDataCatalog
    assert not hasattr(second.bundle, "marketing")
    assert not hasattr(second.bundle, "strategy")
    assert second.fingerprint == first.fingerprint
    assert second.files == first.files
    second_view = build_d2_model_view(second)
    assert second_view == first_view
    assert build_d2_d1r_messages(replace(_request(), model_view=second_view)) == first_messages
    assert build_d2_snapshot_sources(second, model_view=second_view, operations=(),
                                    session_key=SessionKey(client_id="demo", sid="kb2")) == (
        build_d2_snapshot_sources(first, model_view=first_view, operations=(),
                                  session_key=SessionKey(client_id="demo", sid="kb2")))


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_legacy_policy_edits_preserve_price_replay_and_next_turn(http_env, transport):
    client, db, use, root = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
                                "target": {"type": "service", "id": "classic"}})))
    first = send(client, transport, sid="kb2", request_id="price", q="Сколько стоит имплантация одного зуба?")
    assert "76" in first["answer"] and "200" in first["answer"]
    assert "до 15%" in first["answer"]
    view = fake.inputs[0].model_view
    for name in ("marketing.yaml", "clinic_strategy.yaml"):
        (root / "clients" / "demo" / "target_response" / name).write_bytes(b"\xffinvalid legacy")
    assert send(client, transport, sid="kb2", request_id="price",
                q="Сколько стоит имплантация одного зуба?") == first
    assert len(fake.inputs) == 1
    second = send(client, transport, sid="kb2", request_id="next", q="А цена та же?")
    assert "76" in second["answer"] and "200" in second["answer"]
    assert second["revision"] > first["revision"]
    assert [row["label"] for row in second["ui"]["buttons"]] == [row["label"] for row in first["ui"]["buttons"]]
    assert len(fake.inputs) == 2
    assert fake.inputs[1].model_view == view
    assert fake.inputs[1].context.ordinary.discussion_scope.service_id == "classic"
    assert fake.inputs[1].context.ordinary.d2_shown_price_offer_refs
