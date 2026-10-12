"""Isolated candidate comparison; no application imports this experiment."""
from __future__ import annotations
import argparse
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import d2_card_candidates as old
from scripts.experiment_d2_cards import isolated_http, ObservedProvider, cards, choose_tab, dump

ARMS = ('tool_grounded', 'tool_strict', 'split_grounded')
CHAINS = {
 'A': ['Nobel ставите?', 'А сколько стоит?', 'Один зуб', 'А гарантия?'],
 'B': ['Сколько стоит классическая имплантация одного зуба?', 'Это всё включено?',
       'Я боюсь боли. Как проходит обезболивание и сколько стоит All-on-6?'],
 'C': ['Сколько стоит имплантация?', 'Сколько стоит All-on-6?'],
 'D': ['Сколько стоит имплантация Osstem на один зуб?'],
 'E': ['Я боюсь боли. Как проходит обезболивание и сколько стоит All-on-6?'],
}

def corrected_schema():
    value = old.schema()
    node = value['properties']['clarification']
    node['anyOf'] = [part for part in node['anyOf'] if part.get('type') != 'null']
    node.pop('default', None)
    return value

def strict_schema(node):
    """Provider wire shape: optional absence encoded as null, not a semantic repair."""
    if isinstance(node, list):
        return [strict_schema(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = {('anyOf' if k == 'oneOf' else k): strict_schema(v)
           for k, v in node.items() if k not in {'default', 'title', 'minLength', 'maxLength', 'minItems', 'maxItems'}}
    if 'const' in out and isinstance(out['const'], str):
        out['enum'] = [out.pop('const')]
    if 'anyOf' in out:
        out['anyOf'] = [leaf for branch in out['anyOf']
                        for leaf in (branch['anyOf'] if set(branch) == {'anyOf'} else [branch])]
    if out.get('type') == 'object':
        required = set(node.get('required', []))
        for key, val in out.get('properties', {}).items():
            if key not in required and val.get('type') != 'null' and not any(
                n.get('type') == 'null' for n in val.get('anyOf', [])):
                out['properties'][key] = ({**val, 'anyOf': [*val['anyOf'], {'type': 'null'}]}
                    if 'anyOf' in val else {'anyOf': [val, {'type': 'null'}]})
        out['required'] = list(out.get('properties', {}))
        out['additionalProperties'] = False
    return out

def decode_strict(data):
    # Nullable wire encoding for optional fields whose domain accepts absence
    # but not null. Already meaningful null (brand/target/count etc.) is retained.
    data = copy.deepcopy(data)
    if isinstance(data, dict):
        for key in ('clarification', 'age_group', 'context', 'payment_scheme', 'payment_scheme_intent'):
            if key in data and data[key] is None:
                del data[key]
        if isinstance(data.get('volume'), dict):
            for key in ('extent', 'jaw'):
                if key in data['volume'] and data['volume'][key] is None:
                    del data['volume'][key]
        if isinstance(data.get('clarification'), dict) and data['clarification'].get('missing') == 'term':
            if data['clarification'].get('choices', object()) is None:
                del data['clarification']['choices']
    return data

def action_text(args):
    return '\n<D2_META>\n' + json.dumps({'actions': [{'name': 'show_price', 'arguments': args}]}, ensure_ascii=False) + '\n</D2_META>'

WRITER = '''You write the sole final Russian prose for this user turn. Use the full clinic knowledge and history. The server has already handled any price request; its actual result is provided below. Do not choose another service, brand, method, amount or action. Do not repeat prices, the card introduction, or promise to get a card. Answer only the independent informational part of the original question. For a price-only question return exactly <NO_TEXT>. If the server declined a price, do not invent an offer. Return natural Russian text only, with no JSON, metadata, tool calls or source markers. Preserve clinical caveats. The frozen card and clinic facts are authoritative; never contradict what is included.'''

class Runner(old.Runner):
    def __init__(self, output, prior_attempts=None):
        super().__init__(output, live=True)
        self.prior = [row for path in (prior_attempts or [])
                      for row in json.loads(Path(path).read_text(encoding='utf-8'))]
        from openai import OpenAI
        self.strict_client = OpenAI(api_key=self.client.api_key, base_url='https://api.deepseek.com/beta', max_retries=0, timeout=60)

    def call(self, arm, phase, request, messages, **kwargs):
        all_records = [*self.prior, *self.records]
        if len(all_records) >= 60 or sum(r['arm'] == arm for r in all_records) >= 20:
            raise ValueError('hard_budget_exhausted')
        row = dict(arm=arm, phase=phase, sid=request.context.session_key.sid,
                   question=request.user_message, status='reserved', messages=messages,
                   parameters=kwargs, endpoint='beta' if arm == 'tool_strict' else 'standard')
        self.records.append(row)
        self.save()
        start = time.monotonic()
        try:
            client = self.strict_client if arm == 'tool_strict' else self.client
            response = client.chat.completions.create(model=self.model, messages=messages,
                temperature=0, max_tokens=1536, extra_body={'thinking': {'type': 'disabled'}}, **kwargs)
            choice = response.choices[0]
            row.update(status='received', response=choice.message.model_dump(),
                       finish_reason=choice.finish_reason, usage=response.usage.model_dump())
            return choice.message
        except Exception as exc:
            row.update(status='error', error_type=type(exc).__name__, http_status=getattr(exc, 'status_code', None))
            # Provider error text only; no request headers or credentials.
            row['error_body'] = getattr(exc, 'body', None)
            raise
        finally:
            row['ms'] = round((time.monotonic() - start) * 1000)
            self.save()
            print(json.dumps({k: row.get(k) for k in ('arm', 'phase', 'question', 'status', 'ms')}, ensure_ascii=False), flush=True)

class Candidate:
    def __init__(self, arm, runner):
        self.arm, self.runner = arm, runner
        self.pending = None
        self.evidence = []

    def generate(self, request):
        if self.pending is not None:
            raise AssertionError('pending_not_cleared')
        if self.arm.startswith('tool'):
            instructions = old.tool_instructions() + '\nWhen calling show_price, any preceding prose is internal planning and will not be shown. After the server result, write the sole final answer. Omit clarification unless clarification is genuinely needed.'
            messages = old.base_messages(request, instructions)
            params = corrected_schema()
            function = dict(name='show_price', description='Show a catalog price card when a price is requested; known directions are valid without a chosen method.', parameters=params)
            if self.arm == 'tool_strict':
                function.update(strict=True, parameters=strict_schema(params))
            tools = [{'type': 'function', 'function': function}]
            msg = self.runner.call(self.arm, 'selection', request, messages, tools=tools, tool_choice='auto')
            if not msg.tool_calls:
                return msg.content or ''
            if len(msg.tool_calls) != 1 or msg.tool_calls[0].function.name != 'show_price':
                raise ValueError('unexpected_tools')
            call = msg.tool_calls[0]
            raw = old.strict_load(call.function.arguments)
            args = old.price_args(decode_strict(raw) if self.arm == 'tool_strict' else raw, request)
            self.pending = dict(request=request, messages=messages, first=msg, call=call, tools=tools)
        else:
            instructions = '''Extract the price request and the independent informational question. Return JSON with exactly price (null or price arguments) and text_question (null or informational question). Price-only means text_question=null. Information-only means price=null. For mixed requests preserve the informational part. Do not choose a method not stated by the user. Omit clarification unless genuinely needed; clarification:null is forbidden.\n''' + old.PRICE_RULES + '\nPrice arguments schema:\n' + json.dumps(corrected_schema())
            msg = self.runner.call(self.arm, 'extract', request, old.base_messages(request, instructions), response_format={'type': 'json_object'})
            obj = old.strict_load(msg.content or '')
            if set(obj) != {'price', 'text_question'}:
                raise ValueError('extract_shape')
            args = old.price_args(obj['price'], request) if obj['price'] is not None else None
            q = obj['text_question']
            if q is not None and (not isinstance(q, str) or not q.strip()):
                raise ValueError('text_question_shape')
            if args is None:
                if q is None:
                    raise ValueError('empty_extraction')
                messages = old.base_messages(request, old.writer_instructions())
                messages[1]['content'] += '\nTEXT_QUESTION:\n' + q
                written = self.runner.call(self.arm, 'write_information', request, messages)
                if written.tool_calls:
                    raise ValueError('information_writer_requested_tool')
                return old.combine(written.content or '', [], request)
            if q is not None:
                self.pending = dict(request=request, text_question=q)
        return action_text(args)

    def complete(self, response):
        pending, self.pending = self.pending, None
        if pending is None:
            return None
        request = pending['request']
        frozen = dict(rendered_text=response.rendered_text,
                      ui=response.ui_projection.model_dump(mode='json'),
                      price=response.resolved.d2_price_block.model_dump(mode='json') if response.resolved.d2_price_block else None)
        payload = json.dumps(frozen, ensure_ascii=False)
        if 'call' in pending:
            messages = copy.deepcopy(pending['messages'])
            messages.append(pending['first'].model_dump(exclude_none=True))
            messages.append(dict(role='tool', tool_call_id=pending['call'].id, content=payload))
            messages.append(dict(role='user', content=WRITER))
            result = self.runner.call(self.arm, 'completion', request, messages, tools=pending['tools'], tool_choice='none')
        else:
            messages = old.base_messages(request, WRITER)
            messages[1]['content'] += '\nTEXT_QUESTION:\n' + pending['text_question'] + '\nACTUAL_SERVER_RESULT:\n' + payload
            result = self.runner.call(self.arm, 'completion', request, messages)
        if result.tool_calls:
            raise ValueError('writer_requested_tool')
        raw = result.content or ''
        text = '' if raw.strip() == '<NO_TEXT>' else raw
        self.evidence.append(dict(question=request.user_message, frozen=frozen, raw_text=raw))
        return text

def protected(response):
    r = response.resolved
    ui = response.ui_projection.model_dump(mode='json')
    return dict(price=r.d2_price_block.model_dump(mode='json') if r.d2_price_block else None,
        body=[p for p in ui['body_parts'] if p.get('kind') == 'price_card' or p.get('price_owned')],
        parts=[p.model_dump(mode='json') for p in r.d2_request_parts if p.kind != 'content'],
        actions=[a.model_dump(mode='json') for a in r.ui_plan.price_select_actions])

def materializer(original, candidate):
    def resolve(operations, sources, **kwargs):
        first = original(operations, sources, **kwargs)
        text = candidate.complete(first)
        if text is None or text == '':
            return first
        from contracts.d2_dialogue_result import ExplanationOperation
        # Final writer has no action/source channel. Prose remains visible for evaluation.
        explanation = ExplanationOperation(request_id='r9', kind='content', content_text=text)
        second_kwargs = {**kwargs, 'd2_request_order': ('r9', *kwargs.get('d2_request_order', ())) }
        final = original((explanation, *operations), sources, **second_kwargs)
        if protected(first) != protected(final):
            raise AssertionError('completion_changed_price_owned_result')
        return final
    return resolve

def run(output, prior_attempts=None, arms=ARMS, skip_repeat=False):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / 'logs') or output.exists():
        raise ValueError('fresh_logs_directory_required')
    output.mkdir(parents=True)
    runner = Runner(output, prior_attempts)
    turns = []
    with isolated_http(output / 'isolated') as (client, patch, adapter):
        import core.d2_dialogue as dialogue
        original = dialogue.resolve_d2_operations
        for arm in arms:
            candidate = Candidate(arm, runner)
            observed = ObservedProvider(candidate)
            patch.setattr(adapter, 'D2HttpProvider', lambda **kw: observed)
            patch.setattr(dialogue, 'resolve_d2_operations', materializer(original, candidate))
            stop_arm = False
            for chain, questions in CHAINS.items():
                if skip_repeat and chain == 'E': continue
                if stop_arm: break
                sid = f'round2-{arm}-{chain}'
                latest = None
                for index, question in enumerate(questions):
                    if sum(r['arm'] == arm for r in runner.records) >= 19:
                        turns.append(dict(arm=arm, chain=chain, kind='budget_stop'))
                        stop_arm = True
                        break
                    payload = dict(client_id='demo', sid=sid, request_id=f'text-{index}', q=question)
                    before = len(runner.records)
                    response = client.post('/ask', json=payload)
                    body = response.get_json(silent=True) or {}
                    row = dict(arm=arm, chain=chain, kind='text', question=question,
                               status=response.status_code, response=body,
                               calls=len(runner.records)-before, history=observed.histories[-1:])
                    turns.append(row)
                    dump(output / 'turns.json', turns)
                    dump(output / f'{arm}-completion.json', candidate.evidence)
                    candidate.pending = None  # failed requests cannot leak pending into another turn
                    latest = body if response.status_code == 200 else latest
                    if any(r['status'] == 'error' for r in runner.records[before:]):
                        stop_arm = True
                        break  # no silent retry or alternate endpoint on rejection
                    if chain == 'B' and index == 0:
                        choice = choose_tab(body)
                        if choice:
                            observed.button = True
                            before_click = len(runner.records)
                            clicked = client.post('/ask', json=dict(client_id='demo', sid=sid,
                                request_id='tab', q='', ref=choice['reply_id'], ui_revision=body['revision']))
                            observed.button = False
                            selected = clicked.get_json(silent=True) or {}
                            assert len(runner.records) == before_click
                            turns.append(dict(arm=arm, chain=chain, kind='tab', status=clicked.status_code, response=selected))
                            latest = selected
                        else:
                            turns.append(dict(arm=arm, chain=chain, kind='tab_skipped'))
                        dump(output / 'turns.json', turns)
    dump(output / 'turns.json', turns)
    print(json.dumps(dict(calls=len(runner.records), turns=len(turns), output=str(output))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prior-attempts', type=Path, action='append')
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=ARMS)
    parser.add_argument('--skip-repeat', action='store_true')
    args = parser.parse_args()
    run(args.output, args.prior_attempts, args.arms, args.skip_repeat)
