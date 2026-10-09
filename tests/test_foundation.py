import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from teacherlens.cli import main
from teacherlens.config import ExperimentConfig, load_config
from teacherlens.data import load_dataset
from teacherlens.evaluation import evaluate, question_groups, split_dataset
from teacherlens.experiment import run_experiment
from teacherlens.inference import load_model, predict_rows
from teacherlens.model import create_model
from teacherlens.text import build_text, normalize_text

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic.csv"


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = load_dataset(FIXTURE)
        self.config = ExperimentConfig(str(FIXTURE), str(self.root / "run"), data_kind="synthetic")

    def write_csv(self, rows, fields=None):
        path = self.root / "data.csv"
        fields = fields or [key for key in self.rows[0] if key != "label"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_literal_na_and_composite_labels(self):
        self.assertEqual(self.rows[0]["label"], "True_Correct:NA")
        self.assertEqual(self.rows[1]["label"], "False_Misconception:Whole number comparison")

    def test_missing_file(self):
        with self.assertRaisesRegex(ValueError, "Dataset not found"):
            load_dataset(self.root / "missing.csv")

    def test_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            load_dataset(self.write_csv([], ["row_id"]))

    def test_invalid_rows(self):
        changes = [{"StudentExplanation": " "}, {"Category": "unknown"},
                   {"Category": "True_Misconception", "Misconception": "NA"},
                   {"Misconception": "unexpected"}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                load_dataset(self.write_csv([{**self.rows[0], **change}]))

    def test_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate row_id"):
            load_dataset(self.write_csv([self.rows[0], self.rows[0]]))

    def test_correct_answer_can_have_misconception(self):
        row = {**self.rows[0], "Category": "True_Misconception", "Misconception": "Synthetic reason"}
        self.assertEqual(load_dataset(self.write_csv([row]))[0]["label"], "True_Misconception:Synthetic reason")

    def test_bom_and_invalid_encoding(self):
        path = self.write_csv(self.rows)
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        self.assertEqual(len(load_dataset(path)), 16)
        path.write_bytes(b"\xff\xfe\x00")
        with self.assertRaisesRegex(ValueError, "Cannot read CSV"):
            load_dataset(path)

    def test_inconsistent_question(self):
        with self.assertRaisesRegex(ValueError, "inconsistent QuestionText"):
            load_dataset(self.write_csv([self.rows[0], {**self.rows[1], "QuestionText": "other"}]))

    def test_empty_and_malformed_csv(self):
        with self.assertRaisesRegex(ValueError, "no rows"):
            load_dataset(self.write_csv([]))
        path = self.write_csv([self.rows[0]])
        path.write_text(path.read_text() + "broken,row\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "malformed"):
            load_dataset(path)
        path.write_text("row_id,row_id\n1,1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate column"):
            load_dataset(path)

    def test_unlabeled_inference_input(self):
        fields = ["row_id", "QuestionId", "QuestionText", "MC_Answer", "StudentExplanation"]
        rows = load_dataset(self.write_csv(self.rows, fields), labeled=False)
        self.assertNotIn("label", rows[0])

    def test_config_validation_and_paths(self):
        for values in ({"test_size": 0}, {"test_size": 1}, {"seed": True},
                       {"C": float("nan")}, {"max_iter": -1}, {"data_kind": "guess"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(self.config, **values)
        path = self.root / "config.json"
        path.write_text(json.dumps({"dataset_path": "data.csv", "output_dir": "outputs"}))
        self.assertEqual(load_config(path).dataset_path, str(self.root / "data.csv"))
        path.write_text('{"unknown": 1}')
        with self.assertRaisesRegex(ValueError, "Invalid experiment config"):
            load_config(path)

    def test_math_and_unicode_preserved(self):
        self.assertEqual(normalize_text("  É  X − 1/2 ≤ 0.8\n"), "é x − 1/2 ≤ 0.8")
        model = create_model(self.config)
        model.fit(["x − 1/2 ≤ 0.8", "x + 4 = 8"], ["a", "b"])
        vocabulary = model["tfidf"].vocabulary_
        for token in ("−", "/", "≤", "1", "2"):
            self.assertIn(token, vocabulary)

    def test_labels_and_ids_not_features(self):
        text = build_text({**self.rows[0], "label": "secret_target", "QuestionId": "secret_id"})
        self.assertNotIn("secret", text)

    def test_disjoint_deterministic_groups(self):
        train, test, groups = split_dataset(self.rows, self.config)
        self.assertFalse(set(groups[train]) & set(groups[test]))
        train2, test2, _ = split_dataset(self.rows, self.config)
        np.testing.assert_array_equal(train, train2)
        np.testing.assert_array_equal(test, test2)
        self.assertEqual(set(train) | set(test), set(range(len(self.rows))))

    def test_question_aliases_merge_transitively(self):
        rows = [{"QuestionId": "1", "QuestionText": "A"},
                {"QuestionId": "2", "QuestionText": " a "},
                {"QuestionId": "2", "QuestionText": "B"},
                {"QuestionId": "3", "QuestionText": "b"}]
        self.assertEqual(len(set(question_groups(rows))), 1)

    def test_impossible_splits_fail(self):
        with self.assertRaisesRegex(ValueError, "two distinct"):
            split_dataset(self.rows[:2], self.config)
        with self.assertRaisesRegex(ValueError, "fewer than two labels"):
            split_dataset(self.rows[::2], self.config)

    def test_unseen_labels_and_metrics(self):
        result = evaluate(["a", "b", "unseen"], ["a", "a", "b"],
                          np.array([[.9, .1], [.8, .2], [.1, .9]]), np.array(["a", "b"]))
        self.assertAlmostEqual(result["accuracy"], 1 / 3)
        self.assertAlmostEqual(result["macro_f1"], 2 / 9)
        self.assertAlmostEqual(result["map_at_3"], .5)
        self.assertEqual(result["unseen_test_labels"], ["unseen"])
        self.assertEqual(result["unseen_test_rows"], 1)
        self.assertEqual(result["confusion_matrix"], [[1, 0, 0], [1, 0, 0], [0, 1, 0]])

    def test_map_at_3_ranks_and_cutoff(self):
        classes = np.array(["a", "b", "c", "d"])
        probabilities = np.tile([.4, .3, .2, .1], (5, 1))
        result = evaluate(["a", "b", "c", "d", "unseen"], ["a"] * 5,
                          probabilities, classes)
        # Rank 1, 2, 3, 4 and unseen contribute 1, 1/2, 1/3, 0, 0.
        self.assertAlmostEqual(result["map_at_3"], (1 + 1 / 2 + 1 / 3) / 5)

    def test_map_at_3_probability_ties(self):
        result = evaluate(["c", "d"], ["a", "a"],
                          np.full((2, 4), .25), np.array(["a", "b", "c", "d"]))
        self.assertAlmostEqual(result["map_at_3"], 1 / 6)

    def test_all_documented_category_combinations(self):
        rows = []
        for correct in ("True", "False"):
            for reason in ("Correct", "Misconception", "Neither"):
                category = f"{correct}_{reason}"
                rows.append({**self.rows[0], "row_id": category, "Category": category,
                             "Misconception": "Synthetic annotation" if reason == "Misconception" else "NA"})
        loaded = load_dataset(self.write_csv(rows))
        self.assertEqual(len(loaded), 6)
        for row in loaded:
            self.assertEqual(row["label"], f"{row['Category']}:{row['Misconception']}")

    def test_end_to_end_unseen_labels_remain_in_holdout(self):
        _, test, _ = split_dataset(self.rows, self.config)
        rows = [dict(row) for row in self.rows]
        for index in test:
            rows[index].update(Category="False_Misconception", Misconception="Held-out synthetic label")
        config = replace(self.config, dataset_path=str(self.write_csv(rows)))
        report = run_experiment(config)
        label = "False_Misconception:Held-out synthetic label"
        self.assertEqual(report["unseen_test_labels"], [label])
        self.assertEqual(report["unseen_test_rows"], len(test))
        self.assertEqual(report["per_class"][label]["support"], len(test))
        self.assertEqual(report["per_class"][label]["recall"], 0)
        self.assertEqual(report["map_at_3"], 0)

    def test_vectorizer_fits_only_training(self):
        model = create_model(self.config)
        model.fit(["alpha maths", "beta maths"], ["a", "b"])
        model.predict(["heldoutunique"])
        self.assertNotIn("heldoutunique", model["tfidf"].vocabulary_)

    def test_end_to_end_repeatability_artifacts_and_inference(self):
        report = run_experiment(self.config)
        again = run_experiment(replace(self.config, output_dir=str(self.root / "repeat")))
        self.assertEqual(report, again)
        self.assertEqual(report["data_kind"], "synthetic")
        self.assertIn("Synthetic fixture", report["interpretation"])
        metadata = json.loads((self.root / "run" / "experiment.json").read_text())
        self.assertEqual(metadata["dataset_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        model = load_model(self.root / "run" / "model.joblib")
        self.assertEqual(len(predict_rows(model, self.rows)), len(self.rows))
        self.assertEqual(predict_rows(model, self.rows)[0]["data_kind"], "synthetic")
        with self.assertRaisesRegex(ValueError, "already exists"):
            run_experiment(self.config)

    def test_cli_missing_data_and_prediction(self):
        path = self.root / "missing.json"
        path.write_text(json.dumps({"dataset_path": "missing.csv", "output_dir": "out"}))
        self.assertEqual(main(["train", "--config", str(path)]), 2)
        run_experiment(self.config)
        output = self.root / "predictions.csv"
        arguments = ["predict", "--model", str(self.root / "run" / "model.joblib"),
                     "--data", str(FIXTURE), "--output", str(output)]
        self.assertEqual(main(arguments), 0)
        self.assertEqual(main(arguments), 2)
        with output.open(newline="", encoding="utf-8") as handle:
            predictions = list(csv.DictReader(handle))
        self.assertEqual(len(predictions), 16)
        self.assertEqual(predictions[0]["data_kind"], "synthetic")


if __name__ == "__main__":
    unittest.main()
