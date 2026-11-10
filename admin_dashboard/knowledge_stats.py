"""Read-only current tenant pack sizes; no model requests or dialogue reads."""
import json
import math
from types import SimpleNamespace

from contracts.d2_dialogue import D2ProviderInput
from core.d2_live_provider import build_d2_d1r_messages, price_tool
from core.d2_tenant_snapshot import d2_clients_root, load_d2_tenant_snapshot, build_d2_model_view
from admin_dashboard.repository import StorageUnavailable


def knowledge_stats(client_id):
    try:
        snapshot = load_d2_tenant_snapshot(client_id, clients_root=d2_clients_root())
        view = build_d2_model_view(snapshot)
        # Only system content is measured. The unused user block has no history.
        request = D2ProviderInput(user_message='', model_view=view,
            context=SimpleNamespace(model_dump_json=lambda: '{}'))
        system, _ = build_d2_d1r_messages(request)
        tool_chars = len(json.dumps([price_tool()], ensure_ascii=False, separators=(',', ':')))
        system_chars = len(system['content'])
        md = [(name, raw) for name, raw in snapshot.files if name.startswith('md/')]
        md_chars = sum(len(raw.decode('utf-8')) for _, raw in md)
        corpus_chars = len(view.approved_md_corpus)
        total_chars = system_chars + tool_chars
        return dict(documents=len(md), services=len(snapshot.bundle.services),
            active_services=sum(s.active for s in snapshot.bundle.services.values()),
            offers=len(snapshot.bundle.offers), active_offers=sum(o.active for o in snapshot.bundle.offers),
            md_bytes=sum(len(raw) for _, raw in md), md_chars=md_chars,
            pack_bytes=sum(len(raw) for _, raw in snapshot.files),
            corpus_chars=corpus_chars, system_chars=system_chars,
            other_system_chars=system_chars-corpus_chars, tool_chars=tool_chars,
            total_chars=total_chars,
            # Explicit heuristic interval, NOT a provider tokenizer or invoice.
            estimated_tokens_low=math.ceil(total_chars/4),
            estimated_tokens_high=math.ceil(total_chars/2))
    except (ValueError, OSError, UnicodeError) as exc:
        raise StorageUnavailable('knowledge_stats_unavailable') from exc
