"""Contextual dialogue contracts with synthetic data, never a downloaded model."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    import httpx

    from teacherlens.student.api import Settings, create_app
    from teacherlens.student.dialogue import (DialogueChoice, context_for, converse, demo_reply,
                                             math_evidence, validate_generated)
    from teacherlens.student.partner import DemoProvider, OllamaProvider
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('Install the mvp optional dependencies to run dialogue tests') from exc

STATS = {t: {'correct': 0, 'total': 2, 'step_errors': 0} for t in ('linear', 'distribution', 'negative')}
EXAMPLE = 'Equation was x+5=12, so I moved +5 to the right and got x=17, but it was wrong.'


def empty_state():
    return {'conversation': [], 'assessments': [], 'practice': [], 'plan': None}


class DialogueTests(unittest.TestCase):
    def test_wrong_transformation_verified_without_revealing_solution(self):
        context = context_for(empty_state(), EXAMPLE, 'operations', 'en', STATS)
        reply = converse(context, 'operations', DemoProvider(), 'demo')
        self.assertEqual(reply['checked_math']['status'], 'not_equivalent')
        self.assertIn('subtract 5 on both sides', reply['checked_math']['hint'])
        self.assertNotIn('0/2', reply['message'])
        self.assertNotIn('x = 7', json.dumps(reply))
        self.assertNotIn('x=7', json.dumps(reply))
        self.assertIn('Neither explanation is established', reply['message'])
        self.assertEqual(reply['question'].count('?'), 1)

    def test_equivalent_step_and_signed_distribution(self):
        for text, expected in [('x+5=12, then x+5-5=12-5', 'equivalent'),
                               ('-2(x-3)=10, then -2x-6=10', 'not_equivalent')]:
            self.assertEqual(math_evidence(text, [])['status'], expected)

    def test_explicit_new_problem_replaces_old_reference(self):
        first = {'assistant': {'checked_math': math_evidence(EXAMPLE, [])}}
        result = math_evidence('Another equation is 3x=18', [first])
        self.assertEqual(result['original'], '3x=18')
        self.assertEqual(result['source'], 'student_message')
        self.assertEqual(result['status'], 'insufficient_evidence')

    def test_unreadable_step_is_not_a_verified_error(self):
        checked = math_evidence('I cannot write this yet', [], 'linear-1', 'I moved it')
        self.assertEqual(checked['status'], 'unreadable')
        self.assertIn('not evidence', checked['message'])

    def test_multiturn_retains_equation_and_adapts_to_correction_and_disagreement(self):
        state = empty_state()
        first = converse(context_for(state, EXAMPLE, 'operations', 'en', STATS), 'operations', DemoProvider(), 'demo')
        state['conversation'].append({'student_text': EXAMPLE, 'assistant': first})
        second = converse(context_for(state, 'x+5-5=12-5', 'operations', 'en', STATS), 'operations', DemoProvider(), 'demo')
        self.assertEqual(second['checked_math']['original'], 'x+5=12')
        self.assertEqual(second['checked_math']['status'], 'equivalent')
        self.assertEqual([s['id'] for s in second['strategies']], ['balance', 'check'])
        self.assertNotEqual(first['message'], second['message'])
        alternative = converse(context_for(state, 'I disagree, I prefer checking instead.', 'checking', 'en', STATS), 'checking', DemoProvider(), 'demo')
        self.assertIn('different approach', alternative['message'])
        self.assertEqual(alternative['strategies'][0]['id'], 'check')
        self.assertIn('prefer', alternative['question'])

    def test_negative_number_parentheses_are_not_misidentified_as_distribution(self):
        response = math_evidence('x-(-3)=8, then x=11', [])
        self.assertEqual(response['status'], 'not_equivalent')
        self.assertIn('subtract 3 on both sides', response['hint'])
        self.assertNotIn('multiplier', response['hint'])
        context = context_for(empty_state(), '2(x+3)=14, then 2x+3=14', 'brackets', 'en', STATS)
        response = converse(context, 'brackets', DemoProvider(), 'demo')
        self.assertIn('expansion changes', response['message'])
        self.assertEqual(response['strategies'][0]['id'], 'expand')

    def test_provider_context_is_bounded_and_excludes_session_identity_and_hidden_answers(self):
        state = empty_state()
        for i in range(9):
            state['conversation'].append({'student_text': f'Synthetic turn {i}', 'assistant': {'message': 'Try one step.', 'question': None, 'student_report': 'signs'}})
        state['student_name'] = 'PRIVATE_SYNTHETIC_NAME'
        state['request_times'] = [1, 2]
        state['plan'] = {'strategy_id': 'balance', 'goal': 'Ask learner@example.org before practice.',
                         'steps': ['Write one operation.'], 'minutes': 10, 'days': 2, 'private_extra': 'PRIVATE_EXTRA'}
        context = context_for(state, EXAMPLE+' learner@example.org', 'operations', 'en', STATS)
        encoded = json.dumps(context)
        self.assertEqual(len(context['recent_history']), 4)
        self.assertNotIn('Synthetic turn 0', encoded)
        self.assertNotIn('PRIVATE_SYNTHETIC_NAME', encoded)
        self.assertNotIn('PRIVATE_EXTRA', encoded)
        self.assertNotIn('learner@example.org', encoded)
        self.assertIn('operations', context['student_confirmed_difficulties'])
        self.assertIn('signs', context['student_confirmed_difficulties'])
        self.assertNotIn('solution', context['checked_math'])

    def test_locale_fallback_is_explicit_and_structured_proposal_not_approved(self):
        response = converse(context_for(empty_state(), EXAMPLE, 'operations', 'kk', STATS), 'operations', DemoProvider(), 'demo')
        self.assertEqual(response['requested_locale'], 'kk')
        self.assertEqual(response['locale'], 'en')
        self.assertIn('English only', response['fallback'])
        self.assertFalse(response['proposal']['approved'])
        self.assertTrue(response['proposal']['evidence'])
        self.assertTrue(response['proposal']['checkpoint'])

    def test_demo_discusses_existing_plan_when_student_requests_revision(self):
        state = empty_state()
        state['plan'] = {'strategy_id': 'signed', 'goal': 'Make signs explicit.', 'steps': ['Circle signs.'], 'minutes': 10, 'days': 2}
        response = converse(context_for(state, 'My strategy checklist feels too long.', 'pace', 'en', STATS), 'pace', DemoProvider(), 'demo')
        self.assertIn('Make signs visible', response['message'])
        self.assertIn('change first', response['question'])
        self.assertEqual(response['proposal']['strategy_id'], 'signed')

    def test_generated_output_rejects_math_answers_extra_questions_and_bad_schema(self):
        context = context_for(empty_state(), EXAMPLE, 'operations', 'en', STATS)
        valid = demo_reply(context, 'operations').model_dump()
        # The model's prose may not generate numerical mathematics; server-owned questions can.
        valid['question'] = 'Which operation would keep the equation balanced?'
        validate_generated(DialogueChoice.model_validate(valid), 'en')
        for key, value in [('reply', 'The answer is x=7.'), ('reply', 'Why? Try again?'),
                           ('question', 'Why? What next?'), ('locale', 'ru')]:
            invalid = {**valid, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_generated(DialogueChoice.model_validate(invalid), 'en')
        with self.assertRaises(ValueError):
            DialogueChoice.model_validate({**valid, 'diagnosis': 'unsupported'})

    def test_live_local_adapter_sends_message_history_and_plan_and_bounds_generation(self):
        state = empty_state()
        state['conversation'] = [{'student_text': 'I want to slow down.', 'assistant': {'message': 'Try a visible step.', 'question': 'Which step?', 'student_report': 'pace'}}]
        state['plan'] = {'strategy_id': 'check', 'goal': 'Check by substitution.', 'steps': ['Compare both sides.'], 'minutes': 5, 'days': 2}
        context = context_for(state, EXAMPLE, 'operations', 'en', STATS)
        answer = demo_reply(context, 'operations').model_dump()
        answer['reply'] = 'You described moving a term. Writing the operation explicitly may make that change easier to review. You can suggest a different method.'
        answer['question'] = 'Which inverse operation could you write on both sides?'
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={'message': {'content': json.dumps(answer)}})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        with patch('teacherlens.student.partner.httpx.Client', return_value=client):
            response = converse(context, 'operations', OllamaProvider('http://localhost:11434', 'synthetic-model'), 'ollama')
        self.assertEqual(response['mode'], 'ollama')
        self.assertEqual(response['message'], answer['reply'])
        self.assertEqual(response['question_source'], 'authored_math')
        self.assertIn(EXAMPLE, calls[0]['messages'][1]['content'])
        sent = json.loads(calls[0]['messages'][1]['content'])
        self.assertEqual(sent['current_plan']['strategy_id'], 'check')
        self.assertEqual(sent['recent_history'][0]['student'], 'I want to slow down.')
        self.assertEqual(calls[0]['options']['num_predict'], 900)
        self.assertEqual(calls[0]['options']['num_ctx'], 8192)
        self.assertFalse(calls[0]['stream'])

    def test_timeout_invalid_output_and_unsupported_locale_fall_back_without_secret(self):
        class Broken:
            def respond(self, context):
                raise httpx.ReadTimeout('synthetic-private-provider-detail')
        context = context_for(empty_state(), EXAMPLE, 'operations', 'en', STATS)
        response = converse(context, 'operations', Broken(), 'ollama')
        self.assertEqual(response['mode'], 'demo')
        self.assertIn('unavailable', response['fallback'])
        self.assertNotIn('synthetic-private', json.dumps(response))
        context['locale'] = 'ru'
        provider = OllamaProvider('http://localhost:11434', 'synthetic-model')
        with patch('teacherlens.student.partner.httpx.Client') as client:
            response = converse(context, 'operations', provider, 'ollama')
            client.assert_not_called()
        self.assertEqual(response['locale'], 'en')

    def test_provider_locale_contract_supports_configured_codes(self):
        context = context_for(empty_state(), 'Synthetic request', 'operations', 'ru', STATS)
        answer = demo_reply(context, 'operations').model_dump()
        answer['locale'] = answer['proposal']['locale'] = 'ru'
        answer['reply'] = 'Давайте проверим шаг и обсудим другой подход, если он вам удобнее.'
        answer['question'] = 'Какой шаг вы хотите проверить?'
        client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'message': {'content': json.dumps(answer)}})))
        with patch('teacherlens.student.partner.httpx.Client', return_value=client):
            response = converse(context, 'operations', OllamaProvider('http://localhost:11434', 'synthetic-model', ('en', 'ru', 'kk')), 'ollama')
        self.assertEqual(response['locale'], 'ru')
        self.assertEqual(response['mode'], 'ollama')


class ConversationApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.settings = Settings('synthetic-gateway-'+ 'x'*40, str(Path(temp.name)/'demo.sqlite'))
        self.client = TestClient(create_app(self.settings)); self.addCleanup(self.client.close)
        gateway = {'X-TeacherLens-Gateway': self.settings.gateway_key}
        token = self.client.post('/session', headers=gateway).json()['token']
        self.headers = {**gateway, 'Authorization': 'Bearer '+token}
        a = self.client.post('/assessment/start', headers=self.headers, json={'kind': 'diagnostic'}).json()['assessments'][0]
        for pid in a['problem_ids']:
            self.client.post(f"/assessment/{a['id']}/answer", headers=self.headers, json={'problem_id': pid, 'answer': '0'})

    def chat(self, **body):
        response = self.client.post('/conversation', headers=self.headers, json={'text': EXAMPLE, **body})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_draft_edit_approval_and_persisted_multiturn(self):
        state = self.chat(obstacle='operations')
        self.assertIsNone(state['plan'])
        proposal = state['conversation'][-1]['assistant']['proposal']
        payload = {k: v for k, v in proposal.items() if k != 'evidence'}
        self.assertEqual(self.client.put('/plan', headers=self.headers, json=payload).status_code, 422)
        payload.update(approved=True, goal='My edited goal: show operations on both sides.', minutes=5)
        response = self.client.put('/plan', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['plan']['goal'], payload['goal'])
        self.assertEqual(response.json()['plan']['minutes'], 5)
        self.assertTrue(response.json()['plan']['supporting_evidence'])
        with TestClient(create_app(self.settings)) as restarted:
            response = restarted.post('/conversation', headers=self.headers, json={'text': 'x+5-5=12-5'})
        self.assertEqual(response.json()['conversation'][-1]['assistant']['checked_math']['status'], 'equivalent')
        self.assertEqual(len(response.json()['conversation']), 2)

    def test_selected_evidence_and_locale_validation(self):
        state = self.chat(text='I am unsure about my recorded answer.', problem_id='linear-1')
        self.assertEqual(state['conversation'][-1]['assistant']['checked_math']['original'], 'x + 5 = 12')
        self.assertEqual(self.client.post('/conversation', headers=self.headers, json={'text': 'Hi', 'problem_id': 'linear-8'}).status_code, 422)
        self.assertEqual(self.client.post('/conversation', headers=self.headers, json={'text': 'Hi', 'locale': 'fr'}).status_code, 422)

    def test_missing_local_configuration_is_transparently_demo(self):
        settings = Settings(self.settings.gateway_key, self.settings.db_path, provider_mode='ollama', ollama_model='')
        with TestClient(create_app(settings)) as client:
            state = client.get('/state', headers=self.headers).json()
            self.assertEqual(state['provider_mode'], 'demo')
            self.assertIn('No local model', state['provider_notice'])

    def test_approval_is_boolean_and_older_proposal_retains_its_evidence(self):
        first = self.chat()['conversation'][-1]['assistant']['proposal']
        self.chat(text='Another equation is 3x=18, then x=9')
        payload = {k: v for k, v in first.items() if k != 'evidence'}
        payload['approved'] = 1
        self.assertEqual(self.client.put('/plan', headers=self.headers, json=payload).status_code, 422)
        payload['approved'] = True
        response = self.client.put('/plan', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        math = [e for e in response.json()['plan']['supporting_evidence'] if e['kind'] == 'conversation_math']
        self.assertEqual(math[0]['original'], 'x+5=12')
        payload['source_turn_id'] = 'not-part-of-this-session'
        self.assertEqual(self.client.put('/plan', headers=self.headers, json=payload).status_code, 422)

    def test_attempt_context_is_specific_not_entire_diagnostic(self):
        state = self.client.get('/state', headers=self.headers).json()
        context = context_for(state, 'Check this step', 'operations', 'en', STATS, 'linear-1', 'x=17')
        self.assertEqual(context['relevant_checked_attempt']['problem_id'], 'linear-1')
        self.assertEqual(context['relevant_checked_attempt']['answer_status'], 'verified_incorrect')
        self.assertNotIn('assessments', context)


if __name__ == '__main__':
    unittest.main()
