"""The tenant's existing document CTA vocabulary reaches D2 UI authorities."""
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_snapshot_sources import build_d2_snapshot_sources
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot


@pytest.mark.parametrize("content_ref,key,label", [
    ("implantation__info__steps.md", "plan", "Составить план лечения"),
    ("doctors__doctor__lavrenov.md", "doctor", "Записаться к врачу"),
    ("implantation__faq__cost.md", "price", "Уточнить стоимость"),
    ("clinic__info__contacts.md", "callback", "Перезвоните мне"),
])
def test_nikadent_document_cta_is_available_to_materialization(content_ref, key, label):
    snapshot = load_d2_tenant_snapshot("nikadent", clients_root=Path("clients"))
    sources = build_d2_snapshot_sources(snapshot, model_view=build_d2_model_view(snapshot),
        operations=(), session_key=SessionKey(client_id="nikadent", sid="cta-cleanup"))
    row = next(row for row in sources.d2_source_ui if row.content_ref == content_ref)
    assert row.cta is not None
    assert (row.cta.button_id, row.cta.label, row.cta.action_kind) == (key, label, "cta")
    assert row.cta.source_client_id == "nikadent"
