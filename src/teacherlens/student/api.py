"""Same-origin gateway API for the synthetic, local student workflow."""
from dataclasses import dataclass, field
import os
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .math_engine import BANK, TOPICS, assess, form, verify_bank
from .partner import DemoProvider, OllamaProvider, STRATEGIES
from .dialogue import Locale, StrategyDraft, context_for, converse
from .store import Store
from .huggingface import Budget, HuggingFaceProvider, MODEL


@dataclass(frozen=True)
class Settings:
    gateway_key: str
    db_path: str
    provider_mode: str = 'demo'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = ''
    ollama_locales: str = 'en'
    hf_token: str = field(default='', repr=False)
    hf_model: str = MODEL
    hf_free_tier_confirmed: bool = False
    hf_daily_limit: int = 5
    hf_monthly_limit: int = 50

    @classmethod
    def environment(cls):
        return cls(os.getenv('TEACHERLENS_GATEWAY_KEY', ''), os.getenv('TEACHERLENS_DB', 'data/student-mvp/demo.sqlite'),
                   os.getenv('AI_PROVIDER', os.getenv('TEACHERLENS_PROVIDER', 'demo')), os.getenv('TEACHERLENS_OLLAMA_URL', 'http://127.0.0.1:11434'),
                   os.getenv('TEACHERLENS_OLLAMA_MODEL', ''), os.getenv('TEACHERLENS_OLLAMA_LOCALES', 'en'),
                   os.getenv('HF_TOKEN', ''), os.getenv('HF_MODEL', MODEL), os.getenv('HF_FREE_TIER_CONFIRMED', '').lower() == 'true',
                   int(os.getenv('HF_DAILY_REQUEST_LIMIT', '5')), int(os.getenv('HF_MONTHLY_REQUEST_LIMIT', '50')))


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Start(Input):
    kind: Literal['diagnostic', 'retest']


class Answer(Input):
    problem_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=80)
    step: str = Field(default='', max_length=165)


class Conversation(Input):
    text: str = Field(min_length=1, max_length=600)
    obstacle: Literal['not_sure', 'operations', 'brackets', 'signs', 'checking', 'pace'] = 'not_sure'
    locale: Locale = 'en'
    problem_id: str | None = Field(default=None, max_length=40)
    step: str = Field(default='', max_length=165)
    external_ai_consent: bool = Field(default=False, strict=True)


class PlanInput(StrategyDraft):
    approved: bool = Field(strict=True)
    source_turn_id: str | None = Field(default=None, max_length=24)
    uncertainty: str = Field(default='The cause is uncertain; test whether this method helps.', min_length=5, max_length=300)
    rationale: str = Field(default='Make each equation change visible and independently check it.', min_length=5, max_length=300)
    success_criteria: str = Field(default='On two fresh problems, check a step and substitute the final value.', min_length=5, max_length=300)
    checkpoint: str = Field(default='Complete assigned practice, then the fresh follow-up and reflection.', min_length=5, max_length=300)


class Reflection(Input):
    text: str = Field(min_length=5, max_length=600)
    helpful: Literal['yes', 'partly', 'no', 'unsure']
    next_action: Literal['keep', 'revise']


def completed(state, kind):
    return next((a for a in reversed(state['assessments']) if a['kind'] == kind and len(a['results']) == len(a['problem_ids'])), None)


def evidence(assessment):
    return {topic: {'correct': sum(r['feedback']['correct'] for r in assessment['results'] if BANK[r['problem_id']].topic == topic),
                    'step_errors': sum(r['feedback']['step_status'] == 'not_equivalent' for r in assessment['results'] if BANK[r['problem_id']].topic == topic),
                    'total': sum(BANK[r['problem_id']].topic == topic for r in assessment['results'])} for topic in TOPICS}


def snapshot(state):
    # No session key, limiter timings or provider internals reach the browser.
    public = {k: v for k, v in state.items() if k not in ('request_times', 'provider_calls')}
    public['assessments'] = [{**a, 'problems': [BANK[key].public() for key in a['problem_ids']],
                              'complete': len(a['results']) == len(a['problem_ids'])} for a in state['assessments']]
    public['practice_problems'] = [BANK[key].public() for key in state['plan']['problem_ids']] if state['plan'] else []
    before, after = completed(state, 'diagnostic'), completed(state, 'retest')
    public['progress'] = {'before': evidence(before) if before else None, 'after': evidence(after) if after else None,
                          'interpretation': 'Two different problems per topic. A score change is descriptive, not proof of learning gains or strategy effectiveness.'}
    return public


def create_app(settings=None, provider=None):
    settings = settings or Settings.environment()
    if len(settings.gateway_key) < 32:
        raise ValueError('Set TEACHERLENS_GATEWAY_KEY to a random server-only value of at least 32 characters, or use scripts/dev_mvp.py.')
    if settings.provider_mode not in ('demo', 'ollama', 'huggingface'):
        raise ValueError('Supported providers: demo, huggingface or local ollama.')
    verify_bank()
    store = Store(settings.db_path)
    provider_mode, provider_notice = settings.provider_mode, None
    if provider is None and provider_mode == 'ollama' and not settings.ollama_model:
        provider_mode = 'demo'
        provider_notice = 'No local model is configured. Authored demo mode is active; no live AI request is made.'
    cloud = None
    if settings.provider_mode == 'huggingface':
        cloud = provider or HuggingFaceProvider(settings.hf_token, settings.hf_model, settings.hf_free_tier_confirmed,
                                               Budget(settings.db_path+'.cloud-budget.sqlite', settings.hf_daily_limit, settings.hf_monthly_limit))
        if not cloud.ready:
            provider_mode = 'demo'
            provider_notice = cloud.reason + ' Authored demo mode is active; no cloud call is made.'
        provider = cloud
    else:
        provider = provider or (DemoProvider() if provider_mode == 'demo' else OllamaProvider(
            settings.ollama_url, settings.ollama_model, tuple(settings.ollama_locales.split(','))))
    app = FastAPI(title='TeacherLens local synthetic MVP', docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def bounded_request(request: Request, call_next):
        if request.method in ('POST', 'PUT'):
            body = b''
            async for chunk in request.stream():
                body += chunk
                if len(body) > 4096:
                    from fastapi.responses import JSONResponse
                    return JSONResponse({'detail': 'Request exceeds the 4 KB limit.'}, status_code=413)
            request._body = body
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def gateway(x_teacherlens_gateway: str = Header(default='')):
        if not secrets.compare_digest(x_teacherlens_gateway, settings.gateway_key):
            raise HTTPException(403, 'Use the TeacherLens same-origin gateway.')

    def token(authorization: str = Header(default=''), _=Depends(gateway)):
        return authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''

    @app.get('/health')
    def health(): return {'status': 'ok', 'data_kind': 'synthetic_demo'}

    @app.post('/session', dependencies=[Depends(gateway)])
    def session(): return {'token': store.create()}

    @app.delete('/session')
    def erase(key=Depends(token)):
        store.delete(key)
        return {'deleted': True}

    @app.get('/state')
    def state(key=Depends(token)):
        with store.session(key) as value:
            return {**snapshot(value), **provider_metadata()}

    def provider_metadata():
        return {'provider_mode': provider_mode, 'provider_notice': provider_notice,
                'provider_status': cloud.health() if cloud else {'selected': settings.provider_mode,
                    'ready': provider_mode != 'demo', 'check_kind': 'configuration_only',
                    'status': 'demo_selected' if provider_mode == 'demo' else 'local_configured',
                    'reason': 'Effective backend configuration selects demo. Changing .env requires restarting the launcher; process environment overrides the file.' if settings.provider_mode == 'demo' else provider_notice,
                    'token_present': bool(settings.hf_token), 'free_tier_confirmed': settings.hf_free_tier_confirmed}}

    @app.get('/provider/health')
    def provider_health(key=Depends(token)):
        with store.session(key):
            return provider_metadata()

    @app.post('/assessment/start')
    def start(data: Start, key=Depends(token)):
        with store.session(key, True) as value:
            if any(a['kind'] == data.kind for a in value['assessments']):
                raise HTTPException(409, 'This assessment already exists. Resume it; do not repeat the same form.')
            if data.kind == 'retest' and (not value['plan'] or not set(value['plan']['problem_ids']) <= {p['problem_id'] for p in value['practice']}):
                raise HTTPException(409, 'Complete every assigned practice problem before the follow-up.')
            value['assessments'].append({'id': secrets.token_hex(12), 'kind': data.kind, 'problem_ids': form(data.kind), 'results': []})
            return snapshot(value)

    @app.post('/assessment/{assessment_id}/answer')
    def answer(assessment_id: str, data: Answer, key=Depends(token)):
        with store.session(key, True) as value:
            current = next((a for a in value['assessments'] if a['id'] == assessment_id), None)
            if not current or data.problem_id not in current['problem_ids']:
                raise HTTPException(404, 'Assessment or assigned problem not found.')
            if any(r['problem_id'] == data.problem_id for r in current['results']):
                raise HTTPException(409, 'This assessment answer is already recorded and cannot be overwritten.')
            try: feedback = assess(BANK[data.problem_id], data.answer, data.step)
            except ValueError as exc: raise HTTPException(422, str(exc)) from exc
            current['results'].append({'problem_id': data.problem_id, 'answer': data.answer, 'step': data.step, 'feedback': feedback})
            return snapshot(value)

    @app.post('/conversation')
    def chat(data: Conversation, key=Depends(token)):
        with store.session(key, True) as value:
            diagnostic = completed(value, 'diagnostic')
            if not diagnostic:
                raise HTTPException(409, 'Finish the diagnostic before grounded strategy conversation.')
            if value['provider_calls'] >= 8:
                raise HTTPException(429, 'This demo has reached eight strategy turns. You can still edit your plan and practice.')
            value['provider_calls'] += 1
            allowed = {r['problem_id'] for a in value['assessments'] for r in a['results']}
            allowed.update(value['plan']['problem_ids'] if value['plan'] else [])
            if data.problem_id and data.problem_id not in allowed:
                raise HTTPException(422, 'Choose a problem from your recorded diagnostic or assigned practice.')
            context = context_for(value, data.text, data.obstacle, data.locale, evidence(diagnostic), data.problem_id, data.step)
            consent_notice = None
            if provider_mode == 'huggingface' and (not data.external_ai_consent or value['data_kind'] != 'synthetic_demo'):
                consent_notice = 'Cloud inference requires confirmation that this context contains fictional data only. This turn uses authored demo rules; nothing was sent externally.'
            response = converse(context, data.obstacle, provider, 'demo' if consent_notice else provider_mode)
            if consent_notice:
                response['fallback'] = consent_notice
            if provider_notice:
                response['fallback'] = provider_notice
            turn_id = secrets.token_hex(12)
            response['proposal']['source_turn_id'] = turn_id
            value['conversation'].append({'id': turn_id, 'student_text': data.text, 'problem_id': data.problem_id,
                                          'step': data.step, 'locale': data.locale, 'assistant': response})
            return {**snapshot(value), **provider_metadata()}

    @app.put('/plan')
    def plan(data: PlanInput, key=Depends(token)):
        if not data.approved:
            raise HTTPException(422, 'Review and approve the strategy before saving it.')
        if any(not step.strip() or len(step) > 200 for step in data.steps):
            raise HTTPException(422, 'Plan steps must contain 1–200 characters each.')
        with store.session(key, True) as value:
            diagnostic = completed(value, 'diagnostic')
            if not diagnostic or not value['conversation']:
                raise HTTPException(409, 'Discuss the completed diagnostic before choosing a plan.')
            stats = evidence(diagnostic)
            source_turn = next((t for t in value['conversation'] if t.get('id') == data.source_turn_id), None) if data.source_turn_id else None
            if data.source_turn_id and not source_turn:
                raise HTTPException(422, 'The proposal is not part of this session. Choose a stored proposal or edit your plan.')
            weak = [topic for topic, counts in stats.items() if counts['correct'] < counts['total'] or counts['step_errors']] or list(TOPICS)
            targets = list(dict.fromkeys([STRATEGIES[data.strategy_id]['topic'], *weak]))
            old = value['plan']
            value['plan'] = {**data.model_dump(), 'revision': old['revision']+1 if old else 1,
                             'topics': targets, 'problem_ids': [f'{topic}-{i}' for topic in targets for i in (3, 4)],
                             'evidence': stats, 'supporting_evidence': [
                                 {'kind': 'diagnostic', 'topic': STRATEGIES[data.strategy_id]['topic'],
                                  **stats[STRATEGIES[data.strategy_id]['topic']]}] + (
                                 [item for item in source_turn['assistant']['proposal']['evidence'] if item['kind'] != 'diagnostic'] if source_turn else []),
                             'evidence_assessment_id': diagnostic['id']}
            return snapshot(value)

    @app.post('/practice/answer')
    def practice(data: Answer, key=Depends(token)):
        with store.session(key, True) as value:
            if not value['plan'] or data.problem_id not in value['plan']['problem_ids']:
                raise HTTPException(404, 'Problem is not assigned by your plan.')
            if len(value['practice']) >= 100:
                raise HTTPException(429, 'Practice history limit reached for this local demo.')
            try: feedback = assess(BANK[data.problem_id], data.answer, data.step)
            except ValueError as exc: raise HTTPException(422, str(exc)) from exc
            value['practice'].append({'problem_id': data.problem_id, 'answer': data.answer, 'step': data.step,
                                      'plan_revision': value['plan']['revision'], 'feedback': feedback})
            return snapshot(value)

    @app.post('/reflection')
    def reflection(data: Reflection, key=Depends(token)):
        with store.session(key, True) as value:
            if not completed(value, 'retest'):
                raise HTTPException(409, 'Complete the follow-up before the final reflection.')
            if len(value['reflections']) >= 10:
                raise HTTPException(429, 'Reflection limit reached for this demo.')
            value['reflections'].append({**data.model_dump(), 'plan_revision': value['plan']['revision']})
            return snapshot(value)

    return app
