"""Fictional, mocked cloud contracts. This suite never calls external inference."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import httpx
    from fastapi.testclient import TestClient
    from teacherlens.student.api import Settings, create_app
    from teacherlens.student.dialogue import context_for, converse, demo_reply
    from teacherlens.student.huggingface import (Budget, CloudFailure, ENDPOINT, HuggingFaceProvider,
                                               MODEL, ROUTE, compact_context, strict_schema)
    from teacherlens.student.store import Store
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('Install mvp optional dependencies for cloud contract tests') from exc

STATS = {t: {'correct': 0, 'total': 2, 'step_errors': 0} for t in ('linear', 'distribution', 'negative')}
EXAMPLE = 'Equation was x+5=12, then x=17 because I moved the term.'
TOKEN = 'hf_' + 'synthetic_fixture_only'


def context(locale='en', text=EXAMPLE, state=None):
    return context_for(state or {'conversation': [], 'assessments': [], 'practice': [], 'plan': None},
                       text, 'operations', locale, STATS)


def answer(locale='en'):
    draft = demo_reply(context(), 'operations').model_dump()
    translations = {
        'en': ('Writing the inverse operation on both sides may help you review the change.', 'Which operation would you try?'),
        'ru': ('Запись обратной операции с обеих сторон поможет проверить преобразование.', 'Какую операцию вы попробуете?'),
        'kk': ('Екі жаққа кері амалды жазу өзгерісті тексеруге көмектесуі мүмкін.', 'Қай амалды қолданып көресіз?')}
    reply, question = translations[locale]
    draft.update(locale=locale, reply=reply, question=question)
    draft['proposal']['locale'] = locale
    if locale != 'en':
        for key in ('goal', 'uncertainty', 'rationale', 'success_criteria', 'checkpoint'):
            draft['proposal'][key] = reply
        draft['proposal']['steps'] = [reply]
    return draft


def envelope(payload, finish='stop'):
    return {'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(payload, ensure_ascii=False)}}]}


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.budget = Budget(Path(self.temp.name)/'quota.sqlite')
        self.provider = HuggingFaceProvider(TOKEN, MODEL, True, self.budget)

    def call(self, ctx=None, payload=None, status=200, raw=None):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(status, content=raw) if raw is not None else httpx.Response(status, json=payload or envelope(answer()))
        client = httpx.Client(transport=httpx.MockTransport(respond))
        with patch('teacherlens.student.huggingface.httpx.Client', return_value=client) as factory:
            response = converse(ctx or context(), 'operations', self.provider, 'huggingface')
        return response, requests, factory

    def test_english_equation_is_addressed_without_scores_or_complete_solution(self):
        response, requests, factory = self.call()
        self.assertEqual(response['mode'], 'huggingface')
        self.assertIn('inverse operation', response['message'])
        self.assertEqual(response['checked_math']['status'], 'not_equivalent')
        self.assertIn('subtract 5 on both sides', response['checked_math']['hint'])
        self.assertNotIn('0/2', response['message']); self.assertNotIn('x=7', json.dumps(response))
        self.assertFalse(response['proposal']['approved']); self.assertTrue(response['proposal']['evidence'])
        request = requests[0]; body = json.loads(request.content)
        self.assertEqual(str(request.url), ENDPOINT); self.assertEqual(body['model'], ROUTE)
        self.assertEqual(body['max_tokens'], 700); self.assertFalse(body['stream'])
        self.assertTrue(body['response_format']['json_schema']['strict'])
        self.assertEqual(request.headers['Authorization'], 'Bearer '+TOKEN)
        self.assertNotIn(TOKEN, request.content.decode()); self.assertNotIn(TOKEN, json.dumps(response))
        self.assertFalse(factory.call_args.kwargs['trust_env']); self.assertFalse(factory.call_args.kwargs['follow_redirects'])
        self.assertEqual(self.budget.health()['daily_remaining'], 4)

    def test_russian_and_kazakh_schema_and_response_contracts(self):
        messages = {'ru': 'Я решил x+5=12, затем x=17. Почему это неверно?',
                    'kk': 'Мен x+5=12 теңдеуін шешіп, x=17 алдым. Неге қате?'}
        for locale in ('ru', 'kk'):
            with self.subTest(locale=locale):
                result, requests, _ = self.call(context(locale, messages[locale]), envelope(answer(locale)))
                self.assertEqual(result['mode'], 'huggingface'); self.assertEqual(result['locale'], locale)
                self.assertEqual(result['checked_math']['status'], 'not_equivalent')
                self.assertEqual(result['proposal']['locale'], locale)
                self.assertEqual(json.loads(json.loads(requests[0].content)['messages'][1]['content'])['locale'], locale)
                self.assertEqual(result['question_source'], 'authored_math')

    def test_memory_correction_and_disagreement_are_in_request(self):
        state = {'conversation': [], 'assessments': [], 'practice': [], 'plan': None}
        first, _, _ = self.call()
        state['conversation'].append({'student_text': EXAMPLE, 'assistant': first})
        state['plan'] = {'strategy_id': 'balance', 'goal': 'Show both sides.', 'steps': ['Write the operation.'], 'minutes': 5, 'days': 2}
        corrected, requests, _ = self.call(context(text='x+5-5=12-5', state=state))
        self.assertEqual(corrected['checked_math']['status'], 'equivalent')
        sent = json.loads(json.loads(requests[0].content)['messages'][1]['content'])
        self.assertEqual(sent['recent_history'][0]['student'], EXAMPLE)
        self.assertEqual(sent['current_plan']['strategy_id'], 'balance')
        alternative = answer(); alternative['reply'] = 'We can try a shorter substitution check instead; your preference matters.'
        result, requests, _ = self.call(context(text='I disagree, I prefer checking instead.', state=state), envelope(alternative))
        self.assertIn('instead', result['message']); self.assertFalse(result['checked_math']['display'])
        self.assertIn('I disagree', requests[0].content.decode())

    def test_context_minimization_and_contact_masking(self):
        ctx = context(text='Please check learner@example.org')
        ctx['recent_history'] = [{'student': f'Old turn {i} learner@example.org', 'partner': 'p'*1000, 'question': None} for i in range(5)]
        ctx['identity'] = 'PRIVATE_SYNTHETIC_IDENTITY'
        ctx['current_plan'] = {'strategy_id': 'check', 'goal': 'Email learner@example.org', 'steps': ['Contact learner@example.org']*5, 'minutes': 5, 'days': 2, 'private': 'PRIVATE_PLAN'}
        raw = compact_context(ctx); sent = json.loads(raw)
        self.assertEqual(len(sent['recent_history']), 2)
        self.assertNotIn('Old turn 2', raw); self.assertNotIn('learner@example.org', raw)
        self.assertNotIn('PRIVATE', raw); self.assertEqual(len(sent['current_plan']['steps']), 3)
        ctx['checked_math']['message'] = 'x'*13000
        with self.assertRaises(CloudFailure): compact_context(ctx)

    def test_missing_token_unconfirmed_account_and_unverified_route_never_call(self):
        for token, model, confirmed in (('', MODEL, True), (TOKEN, MODEL, False), (TOKEN, MODEL+':auto', True)):
            with self.subTest(model=model, confirmed=confirmed):
                provider = HuggingFaceProvider(token, model, confirmed, self.budget)
                with patch('teacherlens.student.huggingface.httpx.Client') as client:
                    result = converse(context(), 'operations', provider, 'huggingface')
                client.assert_not_called(); self.assertFalse(provider.health()['ready'])
                self.assertEqual(result['mode'], 'demo'); self.assertTrue(result['fallback'])
        self.assertEqual(self.budget.health()['daily_remaining'], 5)

    def test_health_lists_all_configuration_blockers_without_secret_values(self):
        provider = HuggingFaceProvider('', MODEL, False, self.budget)
        health = provider.health()
        self.assertEqual(health['status'], 'missing_token')
        self.assertEqual(health['blocking_reasons'], ['missing_token', 'missing_free_tier_confirmation'])
        self.assertFalse(health['token_present']); self.assertFalse(health['free_tier_confirmed'])
        configured = self.provider.health()
        self.assertEqual(configured['status'], 'huggingface_ready')
        self.assertTrue(configured['token_present']); self.assertTrue(configured['free_tier_confirmed'])
        self.assertNotIn(TOKEN, json.dumps(configured))

    def test_health_distinguishes_application_quota_and_provider_failures(self):
        self.provider.budget = Budget(Path(self.temp.name)/'disabled.sqlite', daily=0)
        self.assertEqual(self.provider.health()['status'], 'application_quota_exhausted')
        self.provider.budget = self.budget
        self.budget.record('unavailable')
        self.assertEqual(self.provider.health()['status'], 'provider_unavailable')
        self.budget.record('rate_limited')
        self.assertEqual(self.provider.health()['status'], 'rate_limited')
        self.budget.record('credits_exhausted')
        self.assertEqual(self.provider.health()['status'], 'credits_exhausted')

    def test_daily_budget_persists_across_provider_instances(self):
        self.budget = Budget(Path(self.temp.name)/'one.sqlite', daily=1)
        self.provider = HuggingFaceProvider(TOKEN, MODEL, True, self.budget)
        self.call()
        restarted = HuggingFaceProvider(TOKEN, MODEL, True, Budget(self.budget.path, daily=1))
        with patch('teacherlens.student.huggingface.httpx.Client') as client:
            result = converse(context(), 'operations', restarted, 'huggingface')
        client.assert_not_called(); self.assertEqual(result['mode'], 'demo')
        self.assertIn('limit is exhausted', result['fallback'])

    def test_monthly_budget_and_atomic_global_reservation(self):
        budget = Budget(Path(self.temp.name)/'atomic.sqlite', daily=10, monthly=1)
        def attempt(_):
            try: Budget(budget.path, daily=10, monthly=1).reserve(); return True
            except CloudFailure: return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)
        self.assertEqual(budget.health()['monthly_remaining'], 0)

    def test_period_rollover_changes_counts_without_clearing_current_month_limit(self):
        with patch.object(self.budget, 'periods', return_value=('day:fictional-a', 'month:fictional-a')):
            self.budget.reserve()
        with patch.object(self.budget, 'periods', return_value=('day:fictional-b', 'month:fictional-a')):
            health = self.budget.health()
            self.assertEqual(health['daily_remaining'], 5); self.assertEqual(health['monthly_remaining'], 49)
        with patch.object(self.budget, 'periods', return_value=('day:fictional-b', 'month:fictional-b')):
            self.assertEqual(self.budget.health()['monthly_remaining'], 50)

    def test_rate_limit_and_exhausted_credits_pause_without_retries(self):
        for status, expected in ((429, 'rate_limited'), (402, 'credits_exhausted')):
            with self.subTest(status=status):
                self.budget = Budget(Path(self.temp.name)/f'{status}.sqlite')
                self.provider = HuggingFaceProvider(TOKEN, MODEL, True, self.budget)
                result, requests, _ = self.call(status=status, raw=b'PRIVATE_PROVIDER_BODY')
                self.assertEqual(len(requests), 1); self.assertEqual(result['mode'], 'demo')
                self.assertNotIn('PRIVATE_PROVIDER_BODY', json.dumps(result)); self.assertTrue(self.budget.health()['paused'])
                self.assertEqual(self.budget.health()['last_result'], expected)
                # A successful concurrent request cannot erase a credit/cooldown block.
                self.budget.record('accepted_response'); self.assertTrue(self.budget.health()['paused'])
                with patch('teacherlens.student.huggingface.httpx.Client') as client:
                    converse(context(), 'operations', self.provider, 'huggingface')
                client.assert_not_called()

    def test_authentication_server_errors_redirects_and_timeout_are_sanitized(self):
        for status in (401, 403, 400, 503, 302):
            self.budget = Budget(Path(self.temp.name)/f'error-{status}.sqlite')
            self.provider = HuggingFaceProvider(TOKEN, MODEL, True, self.budget)
            result, requests, _ = self.call(status=status, raw=TOKEN.encode())
            self.assertEqual(result['mode'], 'demo'); self.assertEqual(len(requests), 1)
            self.assertNotIn(TOKEN, json.dumps(result))
        self.provider = HuggingFaceProvider(TOKEN, MODEL, True, Budget(Path(self.temp.name)/'timeout.sqlite'))
        client = httpx.Client(transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(httpx.ReadTimeout(TOKEN))))
        with patch('teacherlens.student.huggingface.httpx.Client', return_value=client):
            result = converse(context(), 'operations', self.provider, 'huggingface')
        self.assertEqual(result['mode'], 'demo'); self.assertNotIn(TOKEN, json.dumps(result))

    def test_malformed_truncated_oversized_and_invalid_prose_fall_back(self):
        invalid = answer(); invalid['reply'] = 'The answer is x=7.'
        wrong_locale = answer('ru')
        unknown_field = {**answer(), 'diagnosis': 'invented'}
        cases = [b'not json', json.dumps(envelope(answer(), 'length')).encode(),
                 json.dumps(envelope(invalid)).encode(), json.dumps(envelope(wrong_locale)).encode(),
                 json.dumps(envelope(unknown_field)).encode(), b'x'*32769, b'{"choices": []}']
        for raw in cases:
            with self.subTest(raw_length=len(raw)):
                self.provider = HuggingFaceProvider(TOKEN, MODEL, True, Budget(Path(self.temp.name)/f'malformed-{len(raw)}.sqlite'))
                result, requests, _ = self.call(raw=raw)
                self.assertEqual(result['mode'], 'demo'); self.assertEqual(len(requests), 1)
                self.assertFalse(result['proposal']['approved'])

    def test_strict_schema_requires_nullable_question_and_all_plan_properties(self):
        schema = strict_schema()
        self.assertIn('question', schema['required'])
        plan = schema['$defs']['StrategyDraft']
        self.assertEqual(set(plan['required']), set(plan['properties']))
        self.assertNotIn('"default"', json.dumps(schema))


class CloudApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.settings = Settings('synthetic-gateway-'+'x'*40, str(Path(temp.name)/'session.sqlite'),
                                 provider_mode='huggingface', hf_token=TOKEN, hf_free_tier_confirmed=True)
        self.client = TestClient(create_app(self.settings)); self.addCleanup(self.client.close)
        gateway = {'X-TeacherLens-Gateway': self.settings.gateway_key}
        key = self.client.post('/session', headers=gateway).json()['token']
        self.headers = {**gateway, 'Authorization': 'Bearer '+key}
        a = self.client.post('/assessment/start', headers=self.headers, json={'kind': 'diagnostic'}).json()['assessments'][0]
        for pid in a['problem_ids']:
            self.client.post(f"/assessment/{a['id']}/answer", headers=self.headers, json={'problem_id': pid, 'answer': '0'})

    def test_cloud_requires_explicit_fictional_data_confirmation(self):
        with patch('teacherlens.student.huggingface.httpx.Client') as external:
            result = self.client.post('/conversation', headers=self.headers, json={'text': EXAMPLE}).json()
        external.assert_not_called()
        self.assertIn('fictional data only', result['conversation'][-1]['assistant']['fallback'])
        self.assertEqual(result['provider_status']['daily_remaining'], 5)
        self.assertEqual(self.client.post('/conversation', headers=self.headers, json={'text': EXAMPLE, 'external_ai_consent': 1}).status_code, 422)

    def test_non_synthetic_session_is_blocked_even_with_confirmation(self):
        token = self.headers['Authorization'].removeprefix('Bearer ')
        with Store(self.settings.db_path).session(token, True) as state:
            state['data_kind'] = 'real_records_not_authorized'
        with patch('teacherlens.student.huggingface.httpx.Client') as external:
            result = self.client.post('/conversation', headers=self.headers,
                                      json={'text': EXAMPLE, 'external_ai_consent': True}).json()
        external.assert_not_called()
        self.assertEqual(result['conversation'][-1]['assistant']['mode'], 'demo')
        self.assertEqual(result['provider_status']['daily_remaining'], 5)

    def test_health_is_local_access_protected_and_secret_free(self):
        with patch('teacherlens.student.huggingface.httpx.Client') as external:
            result = self.client.get('/provider/health', headers=self.headers)
        external.assert_not_called(); self.assertEqual(result.status_code, 200)
        self.assertNotIn(TOKEN, result.text); self.assertNotIn(TOKEN, repr(self.settings))
        self.assertEqual(result.json()['provider_status']['check_kind'], 'configuration_only')
        self.assertEqual(self.client.get('/provider/health').status_code, 403)

    def test_missing_token_preserves_working_demo_and_reports_manual_setup(self):
        with TestClient(create_app(replace(self.settings, hf_token=''))) as client:
            result = client.get('/state', headers=self.headers).json()
            self.assertEqual(result['provider_mode'], 'demo')
            self.assertIn('Set HF_TOKEN locally', result['provider_notice'])
            self.assertFalse(result['provider_status']['ready'])

    def test_approved_cloud_response_remains_editable_and_evidence_is_server_owned(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope(answer()))))
        with patch('teacherlens.student.huggingface.httpx.Client', return_value=client):
            result = self.client.post('/conversation', headers=self.headers,
                                      json={'text': EXAMPLE, 'external_ai_consent': True}).json()
        proposal = result['conversation'][-1]['assistant']['proposal']
        self.assertEqual(result['provider_status']['last_result'], 'accepted_response')
        payload = {k: v for k, v in proposal.items() if k != 'evidence'}
        self.assertEqual(self.client.put('/plan', headers=self.headers, json=payload).status_code, 422)
        payload.update(approved=True, goal='My edited goal: check each transformation.')
        saved = self.client.put('/plan', headers=self.headers, json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['plan']['goal'], payload['goal'])
        self.assertEqual(saved.json()['plan']['supporting_evidence'][-1]['status'], 'not_equivalent')


class ConfigurationTests(unittest.TestCase):
    def test_launcher_configuration_reports_process_precedence_without_secrets(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('dev_mvp', root/'scripts/dev_mvp.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'.env'
            path.write_text('AI_PROVIDER=huggingface\nHF_FREE_TIER_CONFIRMED=false\nHF_TOKEN=\n', encoding='utf-8')
            process_env = {'AI_PROVIDER': 'demo', 'HF_TOKEN': TOKEN}
            merged = module.load_local_environment(process_env.copy(), path)
            result = module.configuration_summary(merged, process_env)
            self.assertEqual(result['selected'], 'demo'); self.assertTrue(result['token_present'])
            self.assertFalse(result['free_tier_confirmed'])
            self.assertEqual(result['process_override_keys'], ['AI_PROVIDER', 'HF_TOKEN'])
            self.assertNotIn(TOKEN, json.dumps(result))
            self.assertEqual(module.configuration_summary(module.load_local_environment({}, path), {})['blocking_reasons'],
                             ['missing_token', 'missing_free_tier_confirmation'])

    def test_env_example_is_safe_and_launcher_keeps_token_out_of_next_process(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('dev_mvp', root/'scripts/dev_mvp.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        env = module.load_local_environment({}, root/'.env.example')
        self.assertEqual(env['HF_TOKEN'], ''); self.assertEqual(env['AI_PROVIDER'], 'demo')
        self.assertEqual(env['HF_FREE_TIER_CONFIRMED'], 'false')
        existing = module.load_local_environment({'AI_PROVIDER': 'demo', 'HF_TOKEN': TOKEN}, root/'.env.example')
        self.assertEqual(existing['HF_TOKEN'], TOKEN)
        self.assertNotIn('HF_TOKEN', module.frontend_environment(existing))
        self.assertNotIn('hf_token', module.frontend_environment({'hf_token': TOKEN}))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'.env'; path.write_text('UNKNOWN_SETTING=literal', encoding='utf-8')
            with self.assertRaises(ValueError): module.load_local_environment({}, path)

    def test_new_provider_configuration_overrides_legacy_and_budget_values_are_bounded(self):
        with patch.dict('os.environ', {'AI_PROVIDER': 'huggingface', 'TEACHERLENS_PROVIDER': 'ollama'}, clear=True):
            self.assertEqual(Settings.environment().provider_mode, 'huggingface')
        with tempfile.TemporaryDirectory() as temp:
            for daily, monthly in ((11, 50), (5, 101), (-1, 50)):
                with self.assertRaises(ValueError): Budget(Path(temp)/'quota.sqlite', daily, monthly)


if __name__ == '__main__': unittest.main()
