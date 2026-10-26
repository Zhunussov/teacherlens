"""Original authored material only; preserve parity with the public browser bank."""
import json
from pathlib import Path
import unittest

try:
    from teacherlens.student.math_engine import BANK, equation_solution, expression
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('Install mvp dependencies for math bank parity checks') from exc


class PublicBankTests(unittest.TestCase):
    def test_public_bank_matches_all_original_verified_problems(self):
        path = Path(__file__).resolve().parents[1]/'public-demo/lib/bank.json'
        public = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(public), 24)
        expected = [{'id': p.id, 'topic': p.topic, 'equation': p.equation, 'answer': p.answer, 'step': p.first_step} for p in BANK.values()]
        self.assertEqual(public, expected)
        for p in public:
            self.assertEqual(equation_solution(p['equation']), expression(p['answer']))
            self.assertEqual(equation_solution(p['step']), expression(p['answer']))


if __name__ == '__main__': unittest.main()
