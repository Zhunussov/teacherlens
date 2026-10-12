"""Pinned HF routing with persistent application quotas; no billing APIs or retries."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import time

import httpx

from .dialogue import DialogueChoice, SYSTEM_PROMPT, redact, validate_generated

MODEL = 'Qwen/Qwen3-4B-Instruct-2507'
ROUTE = MODEL + ':nscale'
ENDPOINT = 'https://router.huggingface.co/v1/chat/completions'


class CloudFailure(ValueError):
    """Only static, public messages are allowed here; never provider error bodies."""


class Budget:
    def __init__(self, path, daily=5, monthly=50):
        if not 0 <= daily <= 10 or not 0 <= monthly <= 100:
            raise ValueError('HF limits must be daily 0–10 and monthly 0–100.')
        self.path, self.daily, self.monthly = str(path), daily, monthly
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS counts (period TEXT PRIMARY KEY, used INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS status (id INTEGER PRIMARY KEY, result TEXT, pause REAL, blocked_month TEXT)')
            db.execute("INSERT OR IGNORE INTO status VALUES (1, 'not_tested', 0, '')")

    def periods(self):
        now = datetime.now(timezone.utc)
        return now.strftime('day:%Y-%m-%d'), now.strftime('month:%Y-%m')

    def health(self):
        day, month = self.periods()
        with closing(sqlite3.connect(self.path)) as db:
            counts = dict(db.execute('SELECT period, used FROM counts WHERE period IN (?, ?)', (day, month)))
            result, pause, blocked = db.execute('SELECT result, pause, blocked_month FROM status WHERE id=1').fetchone()
        return {'daily_limit': self.daily, 'daily_remaining': max(0, self.daily-counts.get(day, 0)),
                'monthly_limit': self.monthly, 'monthly_remaining': max(0, self.monthly-counts.get(month, 0)),
                'last_result': result, 'paused': pause > time.time() or blocked == month}

    def reserve(self):
        day, month = self.periods()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            _, pause, blocked = db.execute('SELECT result, pause, blocked_month FROM status WHERE id=1').fetchone()
            if pause > time.time() or blocked == month:
                raise CloudFailure('Cloud requests are paused after a provider limit or configuration error. Authored demo mode is active.')
            for period, limit in ((day, self.daily), (month, self.monthly)):
                used = db.execute('SELECT used FROM counts WHERE period=?', (period,)).fetchone()
                if (used[0] if used else 0) >= limit:
                    raise CloudFailure('The application daily or monthly cloud request limit is exhausted. Authored demo mode is active.')
            for period in (day, month):
                db.execute('INSERT INTO counts VALUES (?, 1) ON CONFLICT(period) DO UPDATE SET used=used+1', (period,))

    def record(self, code):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE status SET result=?, pause=MAX(pause, ?), blocked_month=CASE WHEN ? != '' THEN ? ELSE blocked_month END WHERE id=1",
                       (code, time.time()+300 if code in ('rate_limited', 'credentials') else 0,
                        self.periods()[1] if code == 'credits_exhausted' else '',
                        self.periods()[1] if code == 'credits_exhausted' else ''))


def compact_context(context):
    """Whitelist fields; omit identity, full records and all but two recent turns."""
    result = {key: context[key] for key in ('locale', 'checked_math', 'relevant_checked_attempt',
              'diagnostic_counts', 'student_confirmed_difficulties', 'strategy_catalogue')}
    result['current_message'] = redact(context['current_message'])
    result['recent_history'] = [{key: redact(turn.get(key) or '')[:limit]
                                for key, limit in (('student', 300), ('partner', 350), ('question', 120))}
                               for turn in context['recent_history'][-2:]]
    plan = context.get('current_plan')
    result['current_plan'] = ({'strategy_id': plan['strategy_id'], 'goal': redact(plan['goal'])[:150],
                             'steps': [redact(s)[:100] for s in plan['steps'][:3]],
                             'minutes': plan['minutes'], 'days': plan['days']} if plan else None)
    encoded = json.dumps(result, ensure_ascii=False)
    if len(encoded.encode('utf-8')) > 12000:
        raise CloudFailure('The minimized cloud context exceeds its size limit. Authored demo mode is active.')
    return encoded


def strict_schema():
    schema = DialogueChoice.model_json_schema()
    def visit(value):
        if isinstance(value, dict):
            value.pop('default', None)
            if 'properties' in value:
                value['required'] = list(value['properties'])
                value['additionalProperties'] = False
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(schema)
    return schema


class HuggingFaceProvider:
    def __init__(self, token, model, confirmed, budget):
        self._token, self.budget = token, budget
        self.reason = ('Set HF_TOKEN locally with Inference Providers permission.' if not re.fullmatch(r'hf_[A-Za-z0-9_]{8,}', token or '') else
                       'Only the verified Qwen/Nscale route is supported; check HF_MODEL.' if model not in (MODEL, ROUTE) else
                       'Confirm a free account without purchased credits, subscriptions or custom provider keys using HF_FREE_TIER_CONFIRMED=true.' if not confirmed else None)
        self.ready = self.reason is None

    def health(self):
        return {'selected': 'huggingface', 'ready': self.ready, 'reason': self.reason,
                'model': MODEL, 'route': ROUTE, 'check_kind': 'configuration_only', **self.budget.health()}

    def respond(self, context):
        if not self.ready:
            raise CloudFailure(self.reason + ' Authored demo mode is active.')
        content = compact_context(context)
        payload = {'model': ROUTE, 'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT+' Keep prose concise; propose at most three brief practice steps.'},
            {'role': 'user', 'content': content}], 'max_tokens': 700, 'temperature': 0.2,
            'stream': False, 'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'learning_strategy', 'strict': True, 'schema': strict_schema()}}}
        self.budget.reserve()  # Failed attempts also consume an application request.
        code = 'invalid_response'
        try:
            with httpx.Client(timeout=httpx.Timeout(12), trust_env=False, follow_redirects=False) as client:
                with client.stream('POST', ENDPOINT, headers={'Authorization': 'Bearer '+self._token}, json=payload) as response:
                    errors = {401: ('credentials', 'Hugging Face rejected the token or permission.'),
                              403: ('credentials', 'Hugging Face rejected access to this route.'),
                              402: ('credits_exhausted', 'Hugging Face reported exhausted credits; cloud calls are blocked for this UTC month.'),
                              429: ('rate_limited', 'Hugging Face rate limited this request; cloud calls are paused for five minutes.')}
                    if response.status_code in errors:
                        code, message = errors[response.status_code]
                        raise CloudFailure(message+' Authored demo mode is active.')
                    if response.status_code != 200:
                        code = 'unavailable'
                        raise CloudFailure('The configured cloud route is unavailable or rejected the request. Authored demo mode is active.')
                    raw = b''
                    for chunk in response.iter_bytes():
                        raw += chunk
                        if len(raw) > 32768: raise ValueError('Oversized output')
            choices = json.loads(raw)['choices']
            if len(choices) != 1 or choices[0].get('finish_reason') != 'stop' or choices[0]['message'].get('tool_calls'):
                raise ValueError('Incomplete or unexpected output')
            choice = DialogueChoice.model_validate_json(choices[0]['message']['content'])
            validate_generated(choice, context['locale'])
            code = 'accepted_response'
            return choice
        except CloudFailure:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            raise CloudFailure('Cloud inference timed out, failed, or returned an invalid strategy. Authored English demo mode is active.') from None
        finally:
            self.budget.record(code)
