"""CP6c: real HTTP D2 widget action ownership and replay."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts.d2_session_context import D2SessionActivity
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_no_legacy_path import no_legacy_calls
from tests.test_d2_ui_b12_scenarios import _content_pain_raw, _price_raw


def _ui(events):
    return next(payload for kind, payload in events if kind == "ui")


def test_current_scope_click_and_stale_foreign_forged_actions(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    first = _ui(sse_events(post_sse(client, sid="scope", request_id="overview",
                                    q="Сколько стоит имплантация?")))
    choices = first["ui"]["quick_replies"]
    selected = next(item for item in choices if item["reply_id"].endswith("one_tooth"))
    assert selected["source_client_id"] == "demo"
    assert first["revision"] == 1

    def bad(ref, *, sid="scope", client_id="demo", revision=1, request_id="bad"):
        return post(client, sid=sid, client_id=client_id, request_id=request_id,
                    q="", ref=ref, ui_revision=revision)

    assert bad("volume:implantation:forged").status_code == 400
    assert bad(selected["reply_id"], client_id="nikadent").status_code == 400
    assert bad(selected["reply_id"], revision=0).status_code == 400
    assert post(client, sid="scope", request_id="missing-revision", q="",
                ref=selected["reply_id"]).status_code == 400
    assert len(fake.inputs) == 1

    fake.raw = _price_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    with no_legacy_calls(ordinary=True):
        action = bad(selected["reply_id"], request_id="scope-click")
    assert action.status_code == 200
    clicked = action.get_json()
    assert clicked["revision"] == 2
    assert fake.inputs[-1].user_message == selected["label"]
    assert bad(selected["reply_id"], request_id="stale").status_code == 400
    assert bad(selected["reply_id"], revision=2, request_id="not-shown").status_code == 400
    assert len(fake.inputs) == 2
    replay = bad(selected["reply_id"], request_id="scope-click")
    assert replay.get_json() == clicked and len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="scope")).state.revision == 2

    fake.raw = _price_raw("implantation")
    expired = post(client, sid="expired-ui", request_id="overview", q="Имплантация цена").get_json()
    expired_ref = expired["ui"]["quick_replies"][0]["reply_id"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="expired-ui")
        record = store.read(key)
        old = record.model_copy(update={"activity": D2SessionActivity(
            session_key=key, last_user_turn_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )})
        with store._connection:
            store._connection.execute(
                "UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
                (old.model_dump_json(), "demo", "expired-ui"),
            )
    assert post(client, sid="expired-ui", request_id="stale-ttl", q="",
                ref=expired_ref, ui_revision=expired["revision"]).status_code == 400


def test_current_cta_enters_lead_owner_and_replays_once(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    overview = post(client, sid="cta", request_id="overview", q="Имплантация цена").get_json()
    ctas = [item for item in overview["ui"]["buttons"] if item["action_kind"] == "cta"]
    assert len(ctas) == 1
    ref = f"button:{ctas[0]['button_id']}"
    with no_legacy_calls(ordinary=False):
        events = sse_events(post_sse(client, sid="cta", request_id="click", q="",
                                     ref=ref, ui_revision=overview["revision"]))
    clicked = _ui(events)
    assert clicked["revision"] == 2
    assert len(fake.inputs) == 1  # Typed CTA entered the existing lead owner.
    assert post(client, sid="cta", request_id="click", q="", ref=ref,
                ui_revision=overview["revision"]).get_json() == clicked
    assert len(fake.inputs) == 1
    assert post(client, sid="cta", request_id="forged", q="",
                ref="button:never-shown", ui_revision=2).status_code == 400
    assert _ui(sse_events(post_sse(client, sid="cta", request_id="name", q="Анна")))["revision"] == 3
    phone = _ui(sse_events(post_sse(client, sid="cta", request_id="phone",
                                   q="+7 999 123 45 67")))
    assert phone["lead_effect"]["status"] == "demo_stub"

    def duplicate_effect(*_args, **_kwargs):
        raise AssertionError("duplicate lead effect")

    monkeypatch.setattr(D2DialogueStore, "update_lead_effect", duplicate_effect)
    assert post(client, sid="cta", request_id="phone", q="+7 999 123 45 67").get_json() == phone
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="cta")).state.revision == 4


def test_real_d2_payloads_render_and_retry_in_browser(http_env, tmp_path):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    sid = "cp6c-browser"
    first = post(client, sid=sid, request_id="b1", q="первый").get_json()
    choice = next(item for item in first["ui"]["quick_replies"]
                  if item["reply_id"].endswith("one_tooth"))
    fake.raw = _price_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    scope = post(client, sid=sid, request_id="b2", q="", ref=choice["reply_id"],
                 ui_revision=first["revision"]).get_json()
    fake.raw = _price_raw("implantation")
    second = post(client, sid=sid, request_id="b3", q="первый").get_json()
    button = next(item for item in second["ui"]["buttons"] if item["action_kind"] == "cta")
    lead = post(client, sid=sid, request_id="b4", q="",
                ref=f"button:{button['button_id']}", ui_revision=second["revision"]).get_json()
    after_ui = post(client, sid=sid, request_id="b5", q="после UI").get_json()
    manual = post(client, sid=sid, request_id="b6", q="ручной повтор").get_json()
    fake.raw = json.dumps(production_envelope_template(
        route="ADMIN", patient_text=None, commercial_intent="none",
        promotion_scope="none", scenario="none", primary_price_request_id=None,
        request_understanding={"subjects": [], "requests": []},
    ), ensure_ascii=False)
    terminal = post(client, sid="cp6c-terminal", request_id="terminal", q="terminal").get_json()
    assert terminal["ui"]["buttons"] == []
    fake.raw = _content_pain_raw()
    video = post(client, sid="cp6c-video", request_id="video", q="video").get_json()
    assert video["ui"]["video"] is not None
    assert [item["revision"] for item in (first, scope, second, lead, after_ui, manual)] == list(range(1, 7))

    payload_file = tmp_path / "real_d2_widget_payloads.json"
    payload_file.write_text(json.dumps({
        "first": first, "scope": scope, "second": second, "lead": lead,
        "afterUi": after_ui, "manual": manual, "terminal": terminal, "video": video,
    }, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "D2_WIDGET_PAYLOADS_FILE": str(payload_file)}
    harness = Path(__file__).parent / "js" / "d2_widget_harness.mjs"
    result = subprocess.run(["node", str(harness)], cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, text=True, timeout=75, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
