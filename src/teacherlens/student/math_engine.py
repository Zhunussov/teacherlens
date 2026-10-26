"""Bounded AST grammar; never eval, sympify(user_input), or parse_expr(user_input)."""
import ast
import re
from dataclasses import dataclass

import sympy as sp

X = sp.Symbol('x')
TOPICS = {'linear': 'Linear equations', 'distribution': 'Distributive property', 'negative': 'Negative numbers'}


def expression(text):
    text = text.strip().replace('−', '-').replace('×', '*').replace('÷', '/')
    if not text or len(text) > 80 or not re.fullmatch(r'[0-9x.\s+*/()\-]+', text):
        raise ValueError('Use numbers, x, +, -, *, / and parentheses (at most 80 characters).')
    depth = 0
    for character in text:
        depth += (character == '(') - (character == ')')
        if depth > 10:
            raise ValueError('Too many nested parentheses.')
    text = re.sub(r'(\d|\))\s*(?=x|\()', r'\1*', text)
    try:
        tree = ast.parse(text, mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 50:
            raise ValueError('Expression is too complex for this curriculum.')

        def convert(node, depth=0):
            if depth > 10:
                raise ValueError('Too many nested operations.')
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                segment = ast.get_source_segment(text, node)
                value = sp.Rational(segment)
                if abs(value) > 10000:
                    raise ValueError('Numbers must be between -10000 and 10000.')
                return value
            if isinstance(node, ast.Name) and node.id == 'x':
                return X
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = convert(node.operand, depth+1)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = convert(node.left, depth+1), convert(node.right, depth+1)
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if right == 0 or right.has(X):
                    raise ValueError('Divide only by a nonzero number.')
                return left / right
            raise ValueError('This notation is not supported; use simple arithmetic.')

        value = sp.expand(convert(tree.body))
        if sp.Poly(value, X).degree() > 1:
            raise ValueError('Only linear expressions are supported.')
        return value
    except (SyntaxError, TypeError, sp.PolynomialError, ZeroDivisionError) as exc:
        raise ValueError('Could not read that expression. Try 2*x - 3 or 1/2.') from exc


def equation_solution(text):
    if len(text) > 165 or text.count('=') != 1:
        raise ValueError('Enter one equation with an equals sign.')
    left, right = map(expression, text.split('='))
    polynomial = sp.Poly(left-right, X)
    coefficient = polynomial.coeff_monomial(X)
    if coefficient == 0:
        raise ValueError('The equation must have exactly one solution for x.')
    return -polynomial.coeff_monomial(1) / coefficient


@dataclass(frozen=True)
class Problem:
    id: str
    topic: str
    equation: str
    answer: str
    first_step: str
    hint: str

    def public(self):
        return {'id': self.id, 'topic': self.topic, 'topic_name': TOPICS[self.topic],
                'equation': self.equation, 'hint': self.hint}


# Original authored material, not MAP content. Paired forms share a skill and
# operation count, not an empirically validated difficulty calibration.
_FORMS = {
    'linear': [
        ('x + 5 = 12', '7', 'x = 12 - 5'), ('3*x = 18', '6', 'x = 18/3'),
        ('x + 8 = 13', '5', 'x = 13 - 8'), ('4*x = 28', '7', 'x = 28/4'),
        ('x + 4 = 13', '9', 'x = 13 - 4'), ('5*x = 20', '4', 'x = 20/5'),
        ('2*x + 3 = 11', '4', '2*x = 8'), ('5*x - 4 = 16', '4', '5*x = 20')],
    'distribution': [
        ('2*(x + 3) = 14', '4', '2*x + 6 = 14'), ('3*(x - 2) = 12', '6', '3*x - 6 = 12'),
        ('4*(x + 2) = 28', '5', '4*x + 8 = 28'), ('2*(x - 4) = 6', '7', '2*x - 8 = 6'),
        ('2*(x + 4) = 20', '6', '2*x + 8 = 20'), ('3*(x - 1) = 12', '5', '3*x - 3 = 12'),
        ('3*(2*x + 1) = 21', '3', '6*x + 3 = 21'), ('-2*(x - 3) = 10', '-2', '-2*x + 6 = 10')],
    'negative': [
        ('x - (-3) = 8', '5', 'x + 3 = 8'), ('-2*x = 10', '-5', 'x = 10/(-2)'),
        ('x - (-4) = 9', '5', 'x + 4 = 9'), ('-3*x = 12', '-4', 'x = 12/(-3)'),
        ('x - (-2) = 9', '7', 'x + 2 = 9'), ('-4*x = 12', '-3', 'x = 12/(-4)'),
        ('-2*x - 5 = 7', '-6', '-2*x = 12'), ('x + (-6) = -10', '-4', 'x = -10 + 6')],
}
HINTS = {
    'linear': 'Keep the equation balanced: apply the same inverse operation to both sides.',
    'distribution': 'Multiply every term inside the parentheses, including its sign.',
    'negative': 'Write each sign explicitly. Check the result by substitution.',
}
BANK = {f'{topic}-{i+1}': Problem(f'{topic}-{i+1}', topic, equation, answer, step, HINTS[topic])
        for topic, forms in _FORMS.items() for i, (equation, answer, step) in enumerate(forms)}


def verify_bank():
    for problem in BANK.values():
        expected = equation_solution(problem.equation)
        if expression(problem.answer) != expected or equation_solution(problem.first_step) != expected:
            raise ValueError(f'Invalid authored problem: {problem.id}')


def assess(problem, answer, step=''):
    answer = answer.strip()
    if answer.startswith('x=') or answer.startswith('x ='):
        candidate = equation_solution(answer)
    else:
        candidate = expression(answer)
        if candidate.has(X):
            raise ValueError('Give a numerical value for x, such as -3 or 1/2.')
    correct = candidate == expression(problem.answer)
    step_status, step_note = 'not_provided', 'No intermediate step was supplied.'
    if step.strip():
        try:
            equivalent = equation_solution(step) == equation_solution(problem.equation)
            step_status = 'equivalent' if equivalent else 'not_equivalent'
            step_note = ('Your entered equation preserves the original solution.' if equivalent else
                         'Your entered equation does not preserve the original solution. That is a verified mathematical error in this step.')
        except ValueError:
            step_status, step_note = 'unreadable', 'That step could not be checked in the supported notation; it is not evidence of a mathematical error.'
    hypotheses = {
        'linear': 'An inverse operation may have been applied differently on the two sides. Compare both sides of your step.',
        'distribution': 'A multiplier may not have reached every term with its sign. Compare each product with the original brackets.',
        'negative': 'A sign decision may have changed the equation. Rewrite each negative sign before continuing.',
    }
    possible = (hypotheses[problem.topic]
                if step_status == 'not_equivalent' else
                'A final answer alone cannot establish why you reached it. Which operation felt uncertain?')
    return {'correct': bool(correct), 'answer_status': 'verified_correct' if correct else 'verified_incorrect',
            'verified_feedback': ('This value satisfies the equation.' if correct else 'This value does not satisfy the original equation.'),
            'step_status': step_status, 'step_feedback': step_note,
            'possible_explanation': possible if not correct or step_status == 'not_equivalent' else None,
            'reasoning_evidence': 'One supplied step only; reasoning not established.' if step else 'Insufficient evidence about reasoning.',
            'worked_step': problem.first_step, 'solution': problem.answer, 'hint': problem.hint}


def form(kind):
    positions = (1, 2) if kind == 'diagnostic' else (5, 6)
    return [f'{topic}-{i}' for topic in TOPICS for i in positions]
