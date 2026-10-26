"""Synthetic records only; no research data or downloaded model required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from teacherlens.student.api import Settings, create_app
    from teacherlens.student.math_engine import BANK, X, assess, equation_solution, expression, form, verify_bank
    from teacherlens.student.partner import Choice, DemoProvider, OllamaProvider, recommendation
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('Install the mvp optional dependencies to run student tests') from exc


class MathEngineTests(unittest.TestCase):
    def test_all_24_answers_and_steps_are_exact_and_forms_disjoint(self):
        verify_bank()
        self.assertEqual(len(BANK), 24)
        self.assertFalse(set(form('diagnostic')) & set(form('retest')))
        self.assertFalse(set(form('diagnostic')) & {key for key in BANK if key.endswith(('-3','-4'))})
        for problem in BANK.values():
            self.assertTrue(assess(problem, problem.answer, problem.first_step)['correct'])

    def test_exact_fractions_decimals_implicit_multiplication_and_unicode(self):
        self.assertEqual(expression('0.5'), expression('1/2'))
        self.assertEqual(expression('−3 ÷ 2'), expression('-1.5'))
        self.assertEqual(equation_solution('2(x + 3) = 14'), 4)
        self.assertEqual(expression('2x'), 2*X)

    def test_hostile_unsupported_and_excessive_inputs_are_rejected(self):
        for text in ["__import__('os').system('whoami')", 'x**99999', '1/0', '1/x', 'x*x', 'sin(x)',
                     'nan', 'True', '1e300', '10001', '['*81, '(('*12+'1'+'))'*12]:
            with self.subTest(text=text), self.assertRaises(ValueError): expression(text)
        for text in ['x=x', 'x+1=x+2', 'x=1=2']:
            with self.assertRaises(ValueError): equation_solution(text)

    def test_final_answer_does_not_establish_reasoning(self):
        problem=BANK['distribution-1']
        wrong=assess(problem,'1')
        self.assertEqual(wrong['answer_status'],'verified_incorrect')
        self.assertIn('Insufficient evidence',wrong['reasoning_evidence'])
        self.assertIn('alone',wrong['possible_explanation'])
        lucky=assess(problem,'4','2*x + 3 = 14')
        self.assertTrue(lucky['correct'])
        self.assertEqual(lucky['step_status'],'not_equivalent')
        unreadable=assess(problem,'4','I guessed')
        self.assertEqual(unreadable['step_status'],'unreadable')
        self.assertIn('not evidence',unreadable['step_feedback'])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.settings=Settings('synthetic-test-gateway-'+'x'*40,str(Path(self.temp.name)/'demo.sqlite'))
        self.client=TestClient(create_app(self.settings));self.addCleanup(self.client.close)
        self.gateway={'X-TeacherLens-Gateway':self.settings.gateway_key}
        token=self.client.post('/session',headers=self.gateway).json()['token']
        self.headers={**self.gateway,'Authorization':'Bearer '+token}

    def send(self,path,body=None,method='POST',expected=200,headers=None):
        if path=='/plan' and body is not None:
            body={**body,'approved':True}
        response=self.client.request(method,path,json=body,headers=headers or self.headers)
        self.assertEqual(response.status_code,expected,response.text)
        return response.json()

    def diagnostic(self):
        state=self.send('/assessment/start',{'kind':'diagnostic'})
        current=state['assessments'][0]
        for pid in current['problem_ids']:
            state=self.send(f"/assessment/{current['id']}/answer",{'problem_id':pid,'answer':'0','step':''})
        return state

    def plan(self):
        self.send('/conversation',{'text':'Synthetic learner wants a slower check.','obstacle':'checking'})
        return self.send('/plan',{'strategy_id':'check','goal':'Check each answer by substitution.','minutes':10,'days':3,
                                 'steps':['Predict a sign.','Solve one line at a time.','Substitute.']},'PUT')

    def test_full_journey_persistence_progress_reflection_revision_and_deletion(self):
        state=self.diagnostic()
        self.assertEqual(sum(c['correct'] for c in state['progress']['before'].values()),0)
        state=self.plan()
        self.assertEqual(state['plan']['revision'],1)
        for pid in state['plan']['problem_ids']:
            state=self.send('/practice/answer',{'problem_id':pid,'answer':BANK[pid].answer})
        state=self.send('/assessment/start',{'kind':'retest'})
        retest=state['assessments'][-1]
        for pid in retest['problem_ids']:
            state=self.send(f"/assessment/{retest['id']}/answer",{'problem_id':pid,'answer':BANK[pid].answer})
        self.assertEqual(sum(c['correct'] for c in state['progress']['after'].values()),6)
        self.assertIn('not proof',state['progress']['interpretation'])
        state=self.send('/reflection',{'text':'Synthetic reflection: the checklist helped me notice signs.','helpful':'partly','next_action':'revise'})
        self.assertEqual(len(state['reflections']),1)
        revised=self.send('/plan',{'strategy_id':'signed','goal':'Slow down when writing negative signs.','minutes':5,'days':2,'steps':['Write each sign.']},'PUT')
        self.assertEqual(revised['plan']['revision'],2)
        self.assertEqual(revised['progress']['after'],state['progress']['after'])
        with TestClient(create_app(self.settings)) as restarted:
            self.assertEqual(restarted.get('/state',headers=self.headers).json()['plan']['revision'],2)
        self.send('/session',method='DELETE')
        self.send('/state',method='GET',expected=401)

    def test_missing_gateway_session_and_cross_session_access_fail(self):
        self.assertEqual(self.client.get('/state').status_code,403)
        self.assertEqual(self.client.get('/state',headers=self.gateway).status_code,401)
        state=self.send('/assessment/start',{'kind':'diagnostic'})
        other=self.client.post('/session',headers=self.gateway).json()['token']
        self.send(f"/assessment/{state['assessments'][0]['id']}/answer",{'problem_id':'linear-1','answer':'7'},
                  expected=404,headers={**self.gateway,'Authorization':'Bearer '+other})

    def test_prerequisites_no_overwrite_missing_problems_and_input_limits(self):
        self.send('/conversation',{'text':'No diagnostic yet'},expected=409)
        self.send('/assessment/start',{'kind':'retest'},expected=409)
        self.send('/reflection',{'text':'Nothing tested yet','helpful':'unsure','next_action':'keep'},expected=409)
        state=self.send('/assessment/start',{'kind':'diagnostic'}); aid=state['assessments'][0]['id']
        self.send('/assessment/start',{'kind':'diagnostic'},expected=409)
        self.send(f'/assessment/{aid}/answer',{'problem_id':'negative-8','answer':'4'},expected=404)
        self.send(f'/assessment/{aid}/answer',{'problem_id':'linear-1','answer':'1/0'},expected=422)
        self.send(f'/assessment/{aid}/answer',{'problem_id':'linear-1','answer':'7'})
        self.send(f'/assessment/{aid}/answer',{'problem_id':'linear-1','answer':'1'},expected=409)
        self.send('/conversation',{'text':'x'*601},expected=422)
        self.send('/conversation',{'text':'x'*5000},expected=413)

    def test_demo_does_not_call_live_provider_and_invalid_live_output_falls_back(self):
        self.diagnostic()
        provider=DemoProvider()
        with patch.object(provider,'choose',wraps=provider.choose) as call, TestClient(create_app(self.settings,provider)) as client:
            state=client.post('/conversation',headers=self.headers,json={'text':'Synthetic reflection','obstacle':'signs'}).json()
            call.assert_not_called()
            self.assertEqual(state['conversation'][-1]['assistant']['mode'],'demo')
        class InvalidProvider:
            def respond(self,*args):raise ValueError('invalid JSON, synthetic secret not for browser')
        live=Settings(self.settings.gateway_key,self.settings.db_path,provider_mode='ollama')
        with TestClient(create_app(live,InvalidProvider())) as client:
            response=client.post('/conversation',headers=self.headers,json={'text':'Try a strategy'}).json()['conversation'][-1]['assistant']
            self.assertEqual(response['mode'],'demo')
            self.assertIn('failed validation',response['fallback'])
            self.assertNotIn('synthetic secret',json.dumps(response))

    def test_verified_bad_step_is_targeted_even_with_correct_final_answer(self):
        state=self.send('/assessment/start',{'kind':'diagnostic'}); a=state['assessments'][0]
        for pid in a['problem_ids']:
            state=self.send(f"/assessment/{a['id']}/answer",{'problem_id':pid,'answer':BANK[pid].answer,
                       'step':'2*x + 3 = 14' if pid=='distribution-1' else ''})
        self.assertEqual(state['progress']['before']['distribution']['step_errors'],1)
        state=self.plan()
        self.assertIn('distribution',state['plan']['topics'])

    def test_provider_turn_budget_is_enforced(self):
        self.diagnostic()
        for _ in range(8):self.send('/conversation',{'text':'Synthetic reflection'})
        self.send('/conversation',{'text':'One more'},expected=429)

    def test_expired_session_cannot_read_saved_records(self):
        import sqlite3
        db=sqlite3.connect(self.settings.db_path)
        try:
            db.execute('UPDATE sessions SET expires=0');db.commit()
        finally:db.close()
        self.send('/state',method='GET',expected=401)

    def test_successful_mutation_rate_limit_preserves_saved_plan(self):
        self.diagnostic();self.plan()  # Nine successful mutations.
        update={'strategy_id':'check','goal':'Check the answer by substitution.','minutes':10,'days':3,'steps':['Substitute.']}
        for _ in range(31):self.send('/plan',update,'PUT')
        self.send('/plan',update,'PUT',expected=429)
        state=self.send('/state',method='GET')
        self.assertEqual(state['plan']['revision'],32)


class ProviderTests(unittest.TestCase):
    def test_demo_respects_student_preference_as_a_reflection_not_a_diagnosis(self):
        stats={topic:{'correct':0,'total':2} for topic in ('linear','distribution','negative')}
        response=recommendation(stats,'signs',DemoProvider(),'demo')
        self.assertEqual(response['strategies'][0]['id'],'signed')
        self.assertIn('not an established explanation',response['student_report_status'])
        self.assertIn('does not establish mastery',response['message'])

    def test_local_provider_contract_token_limit_and_data_minimization(self):
        import httpx
        captured=[]
        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json={'message':{'content':json.dumps({
                'question':'check','strategies':['balance','check'],'evidence_topics':['linear']})}})
        client=httpx.Client(transport=httpx.MockTransport(respond))
        provider=OllamaProvider('http://127.0.0.1:11434','synthetic-local-model')
        with patch('teacherlens.student.partner.httpx.Client',return_value=client):
            choice=provider.choose({'linear':{'correct':1,'total':2}},'checking')
        self.assertEqual(choice.question,'check')
        self.assertEqual(captured[0]['options']['num_predict'],400)
        self.assertFalse(captured[0]['stream'])
        self.assertNotIn('StudentExplanation',json.dumps(captured))
        self.assertNotIn('student_text',json.dumps(captured))

    def test_remote_and_cloud_models_are_rejected(self):
        for url,model in [('https://example.com','model'),('http://10.0.0.1','model'),('http://user@localhost','model'),('http://localhost:11434','model:cloud')]:
            with self.assertRaises(ValueError):OllamaProvider(url,model)

    def test_output_unknown_fields_and_duplicate_choices_are_rejected(self):
        with self.assertRaises(ValueError):Choice.model_validate({'question':'step','strategies':['balance','signed'],'evidence_topics':['linear'],'diagnosis':'a made-up label'})
        class Duplicates:
            def choose(self,*args):return Choice(question='step',strategies=['balance','balance'],evidence_topics=['linear'])
        response=recommendation({'linear':{'correct':0,'total':2}},'not_sure',Duplicates(),'ollama')
        self.assertEqual(response['mode'],'demo')
        self.assertIsNotNone(response['fallback'])


if __name__ == '__main__': unittest.main()
