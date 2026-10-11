"""A bounded provider selects authored prompts, never diagnoses or grades."""
import json
from typing import Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field
from .math_engine import TOPICS

STRATEGIES = {
    'balance': {'title': 'One operation, both sides', 'topic': 'linear',
        'steps': ['Name the operation you want to undo.', 'Write it on both sides.', 'Substitute your answer into the original equation.'],
        'benefit': 'Makes each equation change visible.', 'tradeoff': 'More writing per problem; useful while checking habits.'},
    'expand': {'title': 'Expand, then simplify', 'topic': 'distribution',
        'steps': ['Draw an arrow to every term in parentheses.', 'Write every product with its sign.', 'Solve the expanded equation and substitute.'],
        'benefit': 'Separates expansion from solving.', 'tradeoff': 'An extra line, even when mental expansion feels faster.'},
    'signed': {'title': 'Make signs visible', 'topic': 'negative',
        'steps': ['Circle negative signs before calculating.', 'Rewrite subtraction of a negative as addition.', 'Check multiplication or division signs, then substitute.'],
        'benefit': 'Gives sign decisions their own checkpoint.', 'tradeoff': 'Slower at first; does not replace equation-balancing practice.'},
    'check': {'title': 'Predict, solve, check', 'topic': 'linear',
        'steps': ['Predict whether x should be positive or negative.', 'Solve one line at a time.', 'Substitute and compare both sides.'],
        'benefit': 'Catches some errors independently of the solving method.', 'tradeoff': 'Checking adds time and may not locate the first wrong step.'},
}
QUESTIONS = {
    'operation': 'Which operation felt least certain: undoing an operation, expanding brackets, or handling signs?',
    'step': 'Could you write the first step you tried? We can check the equation change without guessing your thinking.',
    'pace': 'Would one short worked example or a slower checklist help you try the next problem?',
    'check': 'How did you decide your answer was ready? Would substitution be a useful final check?',
}


class Choice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: Literal['operation', 'step', 'pace', 'check']
    strategies: list[Literal['balance', 'expand', 'signed', 'check']] = Field(min_length=2, max_length=3)
    evidence_topics: list[Literal['linear', 'distribution', 'negative']] = Field(min_length=1, max_length=3)


class Provider(Protocol):
    def choose(self, evidence: dict, obstacle: str) -> Choice: ...


class DemoProvider:
    def choose(self, evidence, obstacle):
        weak = [topic for topic, stats in evidence.items() if stats['correct'] < stats['total'] or stats.get('step_errors', 0)]
        mapping = {'linear': 'balance', 'distribution': 'expand', 'negative': 'signed'}
        preference = {'operations':'balance','brackets':'expand','signs':'signed','checking':'check','pace':'check'}
        preferred = [preference[obstacle]] if obstacle in preference else []
        strategies = list(dict.fromkeys(preferred + [mapping[t] for t in weak] + ['check', 'balance']))[:3]
        return Choice(question='step' if obstacle in ('not_sure','operations','brackets','signs') else 'pace' if obstacle == 'pace' else 'check', strategies=strategies,
                      evidence_topics=weak or list(evidence))


class OllamaProvider:
    """Local-only model endpoint. No raw answers, free text, IDs or records sent."""
    def __init__(self, url, model):
        parsed = urlparse(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.query:
            raise ValueError('Ollama must be an explicitly configured local HTTP endpoint.')
        if not model or len(model) > 80 or 'cloud' in model.lower():
            raise ValueError('Configure a local model name (max 80 characters).')
        self.url, self.model = url.rstrip('/'), model

    def choose(self, evidence, obstacle):
        prompt = {'topic_counts': evidence, 'student_selected_obstacle': obstacle,
                  'task': 'Select a clarification question and 2-3 distinct practice strategies. Reference only supplied topics. Do not infer psychology or mastery.',
                  'strategy_catalogue': STRATEGIES, 'question_catalogue': QUESTIONS}
        with httpx.Client(timeout=12, trust_env=False) as client:
            with client.stream('POST', self.url + '/api/chat', json={
                'model': self.model, 'stream': False, 'format': Choice.model_json_schema(),
                'messages': [{'role': 'system', 'content': 'Return only the required JSON schema. You select suggestions, never mathematical diagnoses.'},
                             {'role': 'user', 'content': json.dumps(prompt)}],
                'options': {'temperature': 0, 'num_predict': 400, 'num_ctx': 4096}}) as response:
                response.raise_for_status()
                content = b''
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > 32768:
                        raise ValueError('Provider response exceeds limit.')
        data = json.loads(content)
        return Choice.model_validate_json(data['message']['content'])


def recommendation(evidence, obstacle, provider, mode):
    fallback = None
    try:
        choice = Choice.model_validate(provider.choose(evidence, obstacle))
        if len(set(choice.strategies)) != len(choice.strategies) or not set(choice.evidence_topics) <= set(evidence):
            raise ValueError('Unsupported provider evidence or duplicate suggestions.')
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        choice = DemoProvider().choose(evidence, obstacle)
        mode = 'demo'
        fallback = 'Local AI was unavailable or returned invalid output. These suggestions use the guided demo rules.'
    counts = ', '.join(f"{TOPICS[topic]}: {stats['correct']}/{stats['total']} answers checked correct, {stats.get('step_errors', 0)} non-equivalent supplied steps" for topic, stats in evidence.items())
    return {'mode': mode, 'fallback': fallback, 'evidence': evidence,
            'message': f'Your stored diagnostic shows {counts}. This small sample does not establish mastery or explain the cause of an error. Let us choose a method to test together.',
            'question': QUESTIONS[choice.question], 'strategies': [{'id': key, **STRATEGIES[key]} for key in choice.strategies],
            'evidence_topics': choice.evidence_topics,
            'student_report': obstacle, 'student_report_status': 'Student-selected reflection, not an established explanation.'}
