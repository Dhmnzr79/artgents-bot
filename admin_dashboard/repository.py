"""Bounded read-only views over the authoritative D2 receipts, never old PG events."""
from contextlib import contextmanager
import sqlite3
from time import monotonic

from contracts.booking_form import BookingFormReceipt
from contracts.d2_dialogue import D2CompletedTurn, D2DialogueRecord
from contracts.response_plan import SessionKey
from core.d2_admin_metrics import identity_hash, DETAIL_COLUMNS
from core.d2_publication import public_completed_turn_payload
from core.d2_storage import dialogue_store_path
from core.user_text_privacy import observability_safe_user_text
from core.widget_analytics import analytics_path


class StorageUnavailable(RuntimeError):
    pass


_REQUIRED_COLUMNS = {
    'd2_dialogue': {'client_id', 'sid', 'payload'},
    'd2_turn_request': {'client_id', 'sid', 'request_id', 'status', 'payload'},
    'd2_admin_observation': {'client_id', 'event_id', 'sid_hash', 'request_hash',
        'observed_at', 'kind', 'outcome', 'model', 'prompt_tokens',
        'completion_tokens', 'duration_ms', 'estimated_usd'},
}


@contextmanager
def reader(client_id):
    path = dialogue_store_path(client_id)
    if not path.exists():
        yield None
        return
    conn = None
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.create_function('identity_hash', 1, identity_hash, deterministic=True)
        deadline = monotonic() + 2
        conn.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'d2_dialogue', 'd2_turn_request'}.issubset(tables):
            raise StorageUnavailable('d2_schema_unavailable')
        for table, required in _REQUIRED_COLUMNS.items():
            if table in tables:
                columns = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
                if not required.issubset(columns):
                    raise StorageUnavailable('d2_schema_unavailable')
        yield conn
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise StorageUnavailable('d2_storage_unavailable') from exc
    finally:
        if conn is not None:
            conn.close()


def _metrics_present(conn):
    return conn is not None and conn.execute("SELECT 1 FROM sqlite_master WHERE name='d2_admin_observation' AND type='table'").fetchone() is not None


def _observation_source(conn):
    # The bot alone adds nullable telemetry columns; admin never bootstraps a DB.
    columns = {r['name'] for r in conn.execute('PRAGMA table_info(d2_admin_observation)')}
    missing = [name for name in DETAIL_COLUMNS if name not in columns]
    if not missing:
        return 'd2_admin_observation'
    return '(SELECT rowid AS rowid,*,' + ','.join(f'NULL AS {name}' for name in missing) + ' FROM d2_admin_observation)'


def _turn(row, client_id):
    try:
        value = D2CompletedTurn.model_validate_json(row['payload'])
        key = SessionKey(client_id=client_id, sid=row['sid'])
        if (value.context.session_key != key or value.response.resolved.session_delta.session_key != key
                or value.request_id != row['request_id']):
            raise ValueError('owner')
        return value
    except ValueError as exc:
        raise StorageUnavailable('d2_receipt_invalid') from exc


def _form(row, client_id):
    try:
        value = BookingFormReceipt.model_validate_json(row['payload'])
        if (value.client_id, value.sid, value.request_id) != (client_id, row['sid'], row['request_id']):
            raise ValueError('owner')
        return value
    except ValueError as exc:
        raise StorageUnavailable('d2_receipt_invalid') from exc


def _rows(conn, client_id, statuses, limit, cursor=None, sid=None):
    if conn is None:
        return []
    where = ['client_id=?', 'status IN (' + ','.join('?' for _ in statuses) + ')', 'payload IS NOT NULL']
    args = [client_id, *statuses]
    if cursor is not None:
        where.append('rowid<?')
        args.append(cursor)
    if sid is not None:
        where.append('sid=?')
        args.append(sid)
    return conn.execute('SELECT rowid AS cursor,sid,request_id,payload FROM d2_turn_request WHERE '
                        + ' AND '.join(where) + ' ORDER BY rowid DESC LIMIT ?', (*args, limit + 1)).fetchall()


def health(client_id):
    with reader(client_id) as conn:
        return {'state': 'ready' if conn is not None else 'empty', 'read_only': True,
                'metrics': _metrics_present(conn)}


def overview(client_id, start, end):
    with reader(client_id) as conn:
        result = dict(sessions=0, saved_turns=0, forms=0, sent=0, demo_stub=0,
                      failed=0, unknown=0, pending=0, metrics_available=False,
                      observed_requests=0, observed_failures=0)
        if conn is None:
            return result
        result['sessions'] = conn.execute('SELECT count(*) FROM d2_dialogue WHERE client_id=?', (client_id,)).fetchone()[0]
        result['saved_turns'] = conn.execute("SELECT count(*) FROM d2_turn_request WHERE client_id=? AND status='complete' AND json_type(payload,'$.dialogue_ref')='object'", (client_id,)).fetchone()[0]
        for row in conn.execute("SELECT json_extract(payload,'$.status') AS outcome,count(*) AS n FROM d2_turn_request WHERE client_id=? AND status IN ('form_pending','form_complete') GROUP BY outcome", (client_id,)):
            if row['outcome'] in {'sent', 'demo_stub', 'failed', 'unknown', 'pending'}:
                result[row['outcome']] = row['n']
                result['forms'] += row['n']
        result['metrics_available'] = _metrics_present(conn)
        if result['metrics_available']:
            row = conn.execute("SELECT count(*) AS n,sum(outcome='failed') AS failures FROM d2_admin_observation WHERE client_id=? AND kind='request' AND observed_at>=? AND observed_at<?",
                               (client_id, start, end)).fetchone()
            result.update(observed_requests=row['n'], observed_failures=row['failures'] or 0)
        return result


def dialogs(client_id, limit, cursor=None):
    with reader(client_id) as conn:
        if conn is None:
            return {'items': [], 'next_cursor': None}
        where = 'client_id=?' + (' AND rowid<?' if cursor is not None else '')
        args = (client_id, cursor, limit + 1) if cursor is not None else (client_id, limit + 1)
        rows = conn.execute('SELECT rowid AS cursor,sid,payload FROM d2_dialogue WHERE ' + where + ' ORDER BY rowid DESC LIMIT ?', args).fetchall()
        items = []
        for row in rows[:limit]:
            try:
                record = D2DialogueRecord.model_validate_json(row['payload'])
                if record.state.session_key != SessionKey(client_id=client_id, sid=row['sid']):
                    raise ValueError('owner')
            except ValueError as exc:
                raise StorageUnavailable('d2_receipt_invalid') from exc
            items.append(dict(session_id=identity_hash(row['sid']), revision=record.state.revision,
                              last_activity=record.activity.last_user_turn_at.isoformat()))
        return {'items': items, 'next_cursor': rows[limit-1]['cursor'] if len(rows) > limit else None}


def thread(client_id, session_id, limit, cursor=None):
    with reader(client_id) as conn:
        if conn is None:
            return None
        found = conn.execute('SELECT sid FROM d2_dialogue WHERE client_id=? AND identity_hash(sid)=?', (client_id, session_id)).fetchone()
        if found is None:
            return None
        sid = found['sid']
        rows = _rows(conn, client_id, ('complete',), limit, cursor, sid)
        items = []
        for row in reversed(rows[:limit]):
            turn = _turn(row, client_id)
            # Private intake is deliberately absent from the public receipt view.
            if turn.dialogue_ref is None:
                continue
            publication = public_completed_turn_payload(turn, include_card_details=True)
            patient = turn.dialogue_ref.patient_text
            items.append(dict(revision=turn.committed_revision,
                request_key=identity_hash(turn.request_id),
                patient_text=observability_safe_user_text(patient, max_len=8000) if patient else None,
                selected_action=patient is None, answer=publication['answer'][:24000]))
        return {'items': items, 'session_id': session_id,
                'next_cursor': rows[limit-1]['cursor'] if len(rows) > limit else None}


def leads(client_id, limit, cursor=None):
    with reader(client_id) as conn:
        rows = _rows(conn, client_id, ('form_pending', 'form_complete'), limit, cursor)
        items = []
        for row in rows[:limit]:
            receipt = _form(row, client_id)
            items.append(dict(request_key=identity_hash(receipt.request_id),
                session_id=identity_hash(receipt.sid), status=receipt.status,
                accepted_at=receipt.accepted_at.isoformat(),
                service_id=receipt.selection.service_id if receipt.selection else None,
                offer_id=receipt.selection.offer_id if receipt.selection else None))
        return {'items': items, 'next_cursor': rows[limit-1]['cursor'] if len(rows) > limit else None}


def observations(client_id, start, end, limit, cursor=None, failures_only=False):
    with reader(client_id) as conn:
        if not _metrics_present(conn):
            return {'available': False, 'items': [], 'next_cursor': None}
        where = ['client_id=?', 'observed_at>=?', 'observed_at<?']
        args = [client_id, start, end]
        if cursor is not None:
            where.append('rowid<?')
            args.append(cursor)
        if failures_only:
            where.append("outcome='failed'")
        source = _observation_source(conn)
        rows = conn.execute('SELECT rowid AS cursor,observed_at,kind,outcome,model,prompt_tokens,completion_tokens,duration_ms,estimated_usd,sid_hash,request_hash,' + ','.join(DETAIL_COLUMNS) + ' FROM ' + source + ' WHERE '
                            + ' AND '.join(where) + ' ORDER BY rowid DESC LIMIT ?', (*args, limit + 1)).fetchall()
        items = [{k: row[k] for k in row.keys() if k != 'cursor'} for row in rows[:limit]]
        return {'available': True, 'items': items,
                'next_cursor': rows[limit-1]['cursor'] if len(rows) > limit else None}


def costs(client_id, start, end):
    with reader(client_id) as conn:
        if not _metrics_present(conn):
            return {'available': False, 'items': [], 'estimated_usd': None, 'unpriced_calls': 0,
                    'legacy_calls': 0, 'legacy_estimated_usd': None, 'unsplit_calls': 0}
        rows = conn.execute("""SELECT model,count(*) AS calls,sum(prompt_tokens) AS prompt_tokens,
            sum(completion_tokens) AS completion_tokens,sum(cached_prompt_tokens) AS cached_prompt_tokens,
            sum(uncached_prompt_tokens) AS uncached_prompt_tokens,
            sum(CASE WHEN pricing_basis IS NOT NULL THEN estimated_usd END) AS estimated_usd,
            sum(CASE WHEN pricing_basis IS NULL THEN estimated_usd END) AS legacy_estimated_usd,
            sum(pricing_basis IS NULL) AS legacy_calls,
            sum(pricing_basis IS NOT NULL AND estimated_usd IS NULL) AS unpriced_calls,
            sum(cached_prompt_tokens IS NULL OR uncached_prompt_tokens IS NULL) AS unsplit_calls
            FROM """ + _observation_source(conn) + " WHERE client_id=? AND kind='provider' AND observed_at>=? AND observed_at<? GROUP BY model ORDER BY model", (client_id, start, end)).fetchall()
        items = [dict(row) for row in rows]
        sums = [row['estimated_usd'] for row in items if row['estimated_usd'] is not None]
        old_sums = [row['legacy_estimated_usd'] for row in items if row['legacy_estimated_usd'] is not None]
        return {'available': True, 'items': items, 'estimated_usd': sum(sums) if sums else None,
                'unpriced_calls': sum(row['unpriced_calls'] for row in items),
                'legacy_calls': sum(row['legacy_calls'] for row in items),
                'legacy_estimated_usd': sum(old_sums) if old_sums else None,
                'unsplit_calls': sum(row['unsplit_calls'] for row in items)}


def funnel(client_id, start, end):
    """Page-view action counts; delivery only from tenant-validated form receipts."""
    path = analytics_path(client_id)
    if not path.is_file():
        return dict(available=False, items=[], truncated=False)
    conn = None
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        deadline = monotonic() + 2
        conn.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
        events = conn.execute('''SELECT domain,path,view_hash,kind,sid_hash,request_hash
            FROM widget_event WHERE client_id=? AND observed_at>=? AND observed_at<?
            ORDER BY observed_at,view_hash,kind,request_hash LIMIT 50001''', (client_id, start, end)).fetchall()
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise StorageUnavailable('analytics_storage_unavailable') from exc
    finally:
        if conn is not None:
            conn.close()
    groups, submissions = {}, {}
    for event in events[:50000]:
        page = (event['domain'], event['path'])
        group = groups.setdefault(page, {key: set() for key in
            ('opened', 'question', 'form', 'submit', 'accepted', 'sent', 'demo_stub', 'unknown', 'failed', 'pending')})
        if event['kind'] not in {'opened', 'question', 'form', 'submit'}:
            raise StorageUnavailable('analytics_event_invalid')
        group[event['kind']].add(event['view_hash'])
        if event['kind'] == 'submit':
            submissions.setdefault((event['sid_hash'], event['request_hash']), set()).add((page, event['view_hash']))
    if submissions:
        with reader(client_id) as source:
            if source is not None:
                for row in source.execute("SELECT sid,request_id,payload FROM d2_turn_request WHERE client_id=? AND status IN ('form_pending','form_complete') AND payload IS NOT NULL", (client_id,)):
                    linked = submissions.get((identity_hash(row['sid']), identity_hash(row['request_id'])))
                    if not linked:
                        continue
                    receipt = _form(row, client_id)
                    for page, view in linked:
                        groups[page]['accepted'].add(view)
                        groups[page][receipt.status].add(view)
    items = [dict(domain=domain, path=page, **{key: len(views) for key, views in values.items()})
             for (domain, page), values in sorted(groups.items())]
    totals = {key: sum(item[key] for item in items) for key in
              ('opened', 'question', 'form', 'submit', 'accepted', 'sent', 'demo_stub', 'unknown', 'failed', 'pending')}
    return dict(available=True, items=items, totals=totals, truncated=len(events) > 50000)
