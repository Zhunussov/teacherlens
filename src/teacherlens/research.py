"""Three-way question-group experiment; private artifacts never leave outputs/."""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import warnings

import joblib
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import GroupShuffleSplit
from threadpoolctl import threadpool_limits

from .config import ExperimentConfig
from .data import FEATURES, load_dataset
from .evaluation import evaluate, question_groups
from .model import create_model
from .text import build_text


@dataclass(frozen=True)
class ResearchConfig(ExperimentConfig):
    test_size: float = 0.2
    validation_size: float = 0.2
    C_candidates: tuple[float, ...] = (0.5, 1.0, 2.0)

    def __post_init__(self):
        super().__post_init__()
        if type(self.validation_size) not in (int, float) or not 0 < self.validation_size < 1 - self.test_size:
            raise ValueError("validation_size must be positive and leave a nonempty training fraction")
        if not isinstance(self.C_candidates, (tuple, list)) or not self.C_candidates:
            raise ValueError("C_candidates must be a nonempty list of finite positive numbers")
        for candidate in self.C_candidates:
            if type(candidate) not in (int, float) or not 0 < candidate < float("inf"):
                raise ValueError("C_candidates must contain finite positive numbers")
        if len(set(self.C_candidates)) != len(self.C_candidates):
            raise ValueError("C_candidates cannot contain duplicates")


def load_research_config(path):
    path = Path(path).resolve()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        config = ResearchConfig(**values)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid research config {path}: {exc}") from exc
    values = config.to_dict()
    for field in ("dataset_path", "output_dir"):
        values[field] = str((path.parent / values[field]).resolve())
    return ResearchConfig(**values)


def audit_and_deduplicate(rows):
    fields = ("QuestionId", *FEATURES, "Category", "Misconception")
    seen, retained = set(), []
    inputs = defaultdict(set)
    for row in rows:
        inputs[build_text(row)].add(row["label"])
        key = tuple(row[field] for field in fields)
        if key not in seen:
            seen.add(key)
            retained.append(row)
    counts = Counter(row["label"] for row in rows)
    statistics = {
        "raw_rows": len(rows), "retained_rows": len(retained),
        "exact_duplicates_removed": len(rows) - len(retained),
        "questions": len({row["QuestionId"] for row in rows}),
        "question_groups": len(set(question_groups(rows))),
        "composite_labels": len(counts),
        "missing_required_values": 0,
        "duplicate_row_ids": len(rows) - len({row["row_id"] for row in rows}),
        "column_types": {field: "string (integer-compatible identifiers)" if field in ("row_id", "QuestionId") and all(row[field].lstrip("-").isdigit() for row in rows) else "string"
                         for field in ("row_id", *fields)},
        "raw_category_counts": dict(sorted(Counter(row["Category"] for row in rows).items())),
        "raw_label_counts": dict(sorted(counts.items())),
        "retained_label_counts": dict(sorted(Counter(row["label"] for row in retained).items())),
        "normalized_inputs_with_conflicting_labels": sum(len(labels) > 1 for labels in inputs.values()),
        "rows_in_conflicting_normalized_input_groups": sum(len(inputs[build_text(row)]) > 1 for row in rows),
        "raw_labels_with_fewer_than_50_rows": sum(count < 50 for count in counts.values()),
        "raw_labels_with_fewer_than_10_rows": sum(count < 10 for count in counts.values()),
        "minimum_raw_class_count": min(counts.values()), "maximum_raw_class_count": max(counts.values()),
    }
    return retained, statistics


def three_way_split(rows, config):
    groups = question_groups(rows)
    if len(set(groups)) < 3:
        raise ValueError("Three-way holdout requires at least three question groups")
    try:
        development, test = next(GroupShuffleSplit(n_splits=1, test_size=config.test_size,
                                                    random_state=config.seed).split(rows, groups=groups))
        train_local, validation_local = next(GroupShuffleSplit(
            n_splits=1, test_size=config.validation_size / (1 - config.test_size),
            random_state=config.seed).split(development, groups=groups[development]))
    except ValueError as exc:
        raise ValueError(f"Insufficient question groups for the configured three-way split: {exc}") from exc
    train, validation = development[train_local], development[validation_local]
    if len({rows[i]["label"] for i in train}) < 2:
        raise ValueError("Research training partition has fewer than two classes")
    return {"train": train, "validation": validation, "test": test}, groups


def fit_baseline(config, rows, indices):
    model = create_model(config)
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            model.fit([build_text(rows[i]) for i in indices], [rows[i]["label"] for i in indices])
        except ConvergenceWarning as exc:
            raise ValueError("Research fit did not converge; increase max_iter before evaluating") from exc
    return model


def score_model(model, rows, indices):
    texts = [build_text(rows[i]) for i in indices]
    with threadpool_limits(limits=1):
        predictions = model.predict(texts)
        probabilities = model.predict_proba(texts)
    report = evaluate([rows[i]["label"] for i in indices], predictions, probabilities, model.classes_)
    return report, predictions


def select_candidate(candidates):
    # Validation alone; smaller C breaks exact score ties deterministically.
    return max(candidates, key=lambda item: (item["validation"]["map_at_3"],
                                            item["validation"]["macro_f1"], -item["C"]))


def split_summary(rows, split, groups):
    catalogue = {row["label"] for row in rows}
    result = {}
    for name, indices in split.items():
        counts = Counter(rows[i]["label"] for i in indices)
        result[name] = {"rows": len(indices), "question_groups": len(set(groups[indices])),
                        "classes": len(counts), "class_coverage_fraction": len(counts) / len(catalogue),
                        "label_counts": dict(sorted(counts.items()))}
    return result


def analyze_errors(rows, test, predictions, fit_indices, groups):
    truth = [rows[i]["label"] for i in test]
    fit_counts = Counter(rows[i]["label"] for i in fit_indices)
    confusion = Counter((actual, str(predicted)) for actual, predicted in zip(truth, predictions) if actual != predicted)
    bins = {"unseen_0": [], "rare_1_to_49": [], "frequent_50_plus": []}
    for i, (actual, predicted) in enumerate(zip(truth, predictions)):
        count = fit_counts[actual]
        bucket = "unseen_0" if count == 0 else ("rare_1_to_49" if count < 50 else "frequent_50_plus")
        bins[bucket].append(actual == predicted)
    bins = {name: {"rows": len(values), "accuracy": float(np.mean(values)) if values else None}
            for name, values in bins.items()}
    by_group = []
    for number, group in enumerate(sorted(set(groups[test])), 1):
        mask = groups[test] == group
        by_group.append({"anonymous_group": number, "rows": int(mask.sum()),
                         "accuracy": float(np.mean(np.array(truth)[mask] == predictions[mask]))})
    examples = [{"retained_index": int(index), "row_id": rows[index]["row_id"],
                 "true_label": actual, "predicted_label": str(predicted)}
                for index, actual, predicted in zip(test, truth, predictions) if actual != predicted][:20]
    return {"top_confusions": [{"true_label": actual, "predicted_label": predicted, "count": count}
                               for (actual, predicted), count in confusion.most_common(15)],
            "accuracy_by_fit_frequency": bins, "anonymous_question_accuracy": by_group}, examples


def run_research(config):
    output = Path(config.output_dir)
    if output.exists():
        raise ValueError(f"Output directory already exists: {output}; use a new directory")
    raw = load_dataset(config.dataset_path)
    rows, statistics = audit_and_deduplicate(raw)
    split, groups = three_way_split(rows, config)
    print(f"Prepared {len(rows)} deduplicated rows; question groups train/validation/test: "
          f"{len(set(groups[split['train']]))}/{len(set(groups[split['validation']]))}/{len(set(groups[split['test']]))}", flush=True)
    candidates = []
    for candidate in sorted(config.C_candidates):
        model = fit_baseline(replace(config, C=candidate), rows, split["train"])
        validation, _ = score_model(model, rows, split["validation"])
        candidates.append({"C": candidate, "validation": validation})
        print(f"Validation C={candidate}: MAP@3={validation['map_at_3']:.6f}", flush=True)
    selected = select_candidate(candidates)
    # Freeze selection, then refit training+validation before touching final test.
    fit_indices = np.sort(np.concatenate([split["train"], split["validation"]]))
    model = fit_baseline(replace(config, C=selected["C"]), rows, fit_indices)
    final, predictions = score_model(model, rows, split["test"])
    analysis, examples = analyze_errors(rows, split["test"], predictions, fit_indices, groups)
    report = {"data_kind": config.data_kind, "dataset": statistics,
              "split": split_summary(rows, split, groups),
              "selection_metric": "validation MAP@3, then macro F1, then smaller C",
              "candidates": candidates, "selected_C": selected["C"],
              "selected_validation": selected["validation"], "final_test": final,
              "final_fit_rows": len(fit_indices), "final_fit_classes": len(model.classes_),
              "error_analysis": analysis,
              "macro_f1_policy": "Union of fitted classes and evaluated true classes; zero-support classes score zero. Also report test-supported macro F1.",
              "interpretation": "Question-group holdout after exact deduplication; one seed; not classroom or leaderboard validation."}
    catalogue = final["per_class"]
    report["reliable_supported_misconceptions"] = sorted(
        [{"label": label, **catalogue[label]} for label in final["labels"]
         if "_Misconception:" in label and catalogue[label]["support"] >= 20],
        key=lambda entry: (-entry["f1-score"], -entry["support"], entry["label"]))[:10]
    metadata = {"config": config.to_dict(), "dataset_sha256": hashlib.sha256(Path(config.dataset_path).read_bytes()).hexdigest(),
                "python": platform.python_version(),
                "versions": {name: version(name) for name in ("teacherlens", "numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl")},
                "threads": 1, "retained_row_ids": [row["row_id"] for row in rows],
                "split_indices": {name: indices.tolist() for name, indices in split.items()}}
    try:
        metadata["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        metadata["git_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
    except (OSError, subprocess.CalledProcessError):
        metadata["git_commit"], metadata["git_dirty"] = None, None
    output.mkdir(parents=True, exist_ok=False)
    for filename, value in (("report.json", report), ("experiment.json", metadata), ("private_errors.json", examples)):
        (output / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    joblib.dump({"pipeline": model, "data_kind": config.data_kind, "package_version": version("teacherlens")}, output / "model.joblib")
    print(f"Final test accuracy={final['accuracy']:.6f}; MAP@3={final['map_at_3']:.6f}", flush=True)
    return report
