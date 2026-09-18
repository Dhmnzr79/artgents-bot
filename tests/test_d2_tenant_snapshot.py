from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.d2_tenant_snapshot import D2TenantSnapshotError, build_d2_bundle, build_d2_model_view, load_d2_tenant_snapshot


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
    (root / "demo" / "target_response" / "marketing.yaml").unlink()
    with pytest.raises(D2TenantSnapshotError, match="required_path_missing"):
        load_d2_tenant_snapshot("demo", clients_root=root)
