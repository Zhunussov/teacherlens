from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from teacherlens.data import load_dataset
from teacherlens.reproducibility import verify_research_runs
from teacherlens.evaluation import evaluate
from teacherlens.research import (ResearchConfig, audit_and_deduplicate, load_research_config,
                                 run_research, select_candidate, three_way_split)

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic.csv"


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = load_dataset(FIXTURE)
        self.config = ResearchConfig(str(FIXTURE), str(self.root / "run"), data_kind="synthetic",
                                     C_candidates=(.5, 1), max_features=1000)

    def test_three_way_split_disjoint_deterministic_and_complete(self):
        split, groups = three_way_split(self.rows, self.config)
        again, _ = three_way_split(self.rows, self.config)
        for name in split:
            np.testing.assert_array_equal(split[name], again[name])
        self.assertEqual(set(np.concatenate(list(split.values()))), set(range(len(self.rows))))
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
            self.assertFalse(set(groups[split[left]]) & set(groups[split[right]]))

    def test_dedup_retains_conflicting_annotations(self):
        original = self.rows[0]
        duplicate = {**original, "row_id": "new_id"}
        conflict = {**original, "row_id": "conflict", "Category": "True_Neither", "label": "True_Neither:NA"}
        retained, audit = audit_and_deduplicate([original, duplicate, conflict])
        self.assertEqual(len(retained), 2)
        self.assertEqual(audit["exact_duplicates_removed"], 1)
        self.assertEqual(audit["normalized_inputs_with_conflicting_labels"], 1)
        self.assertEqual(audit["rows_in_conflicting_normalized_input_groups"], 3)
        self.assertEqual(audit["column_types"]["row_id"], "string")

    def test_config_validation_and_resolution(self):
        for changes in ({"validation_size": .9}, {"validation_size": float("nan")},
                        {"C_candidates": []}, {"C_candidates": [1, 1]}, {"C_candidates": [float("inf")]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.config, **changes)
        path = self.root / "config.json"
        path.write_text(json.dumps({"dataset_path": "train.csv", "output_dir": "out"}))
        self.assertEqual(load_research_config(path).dataset_path, str(self.root / "train.csv"))

    def test_insufficient_groups_fail(self):
        with self.assertRaisesRegex(ValueError, "at least three"):
            three_way_split(self.rows[:4], self.config)

    def test_weighted_and_supported_macro_f1(self):
        report = evaluate(["a", "a", "b"], ["a", "a", "a"],
                          np.array([[.8, .1, .1]] * 3), np.array(["a", "b", "train_only"]))
        self.assertAlmostEqual(report["weighted_f1"], .8 * 2 / 3)
        self.assertAlmostEqual(report["macro_f1"], .8 / 3)
        self.assertAlmostEqual(report["macro_f1_test_supported"], .4)

    def test_selection_uses_validation_and_deterministic_ties(self):
        candidates = [{"C": 2, "validation": {"map_at_3": .7, "macro_f1": .3}},
                      {"C": .5, "validation": {"map_at_3": .7, "macro_f1": .3}},
                      {"C": 1, "validation": {"map_at_3": .6, "macro_f1": .9}}]
        self.assertEqual(select_candidate(candidates)["C"], .5)

    def test_research_reproducible_and_no_student_text_in_reports(self):
        first = run_research(self.config)
        second = run_research(replace(self.config, output_dir=str(self.root / "repeat")))
        self.assertEqual(first, second)
        self.assertTrue(verify_research_runs(self.root / "run", self.root / "repeat")["passed"])
        repeat_report = self.root / "repeat" / "report.json"
        altered = json.loads(repeat_report.read_text(encoding="utf-8"))
        altered["selected_C"] = 123
        repeat_report.write_text(json.dumps(altered), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Reproducibility mismatch"):
            verify_research_runs(self.root / "run", self.root / "repeat")
        self.assertEqual(first["data_kind"], "synthetic")
        for name in ("report.json", "experiment.json", "private_errors.json"):
            text = (self.root / "run" / name).read_text(encoding="utf-8")
            self.assertNotIn(self.rows[0]["StudentExplanation"], text)
            self.assertNotIn(self.rows[0]["QuestionText"], text)
        with self.assertRaisesRegex(ValueError, "already exists"):
            run_research(self.config)

    def test_selection_and_refit_do_not_touch_final_test(self):
        from teacherlens.research import fit_baseline, score_model
        split, _ = three_way_split(self.rows, self.config)
        calls = []

        def fit(config, rows, indices):
            calls.append(("fit", set(indices)))
            return fit_baseline(config, rows, indices)

        def score(model, rows, indices):
            calls.append(("score", set(indices)))
            return score_model(model, rows, indices)

        with patch("teacherlens.research.fit_baseline", side_effect=fit), patch("teacherlens.research.score_model", side_effect=score):
            run_research(self.config)
        self.assertEqual(calls, [("fit", set(split["train"])), ("score", set(split["validation"])),
                                 ("fit", set(split["train"])), ("score", set(split["validation"])),
                                 ("fit", set(split["train"]) | set(split["validation"])),
                                 ("score", set(split["test"]))])


if __name__ == "__main__":
    unittest.main()
