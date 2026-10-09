"""Train once on a fixed holdout and record auditable experiment artifacts."""

from collections import Counter
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import warnings

import joblib
from sklearn.exceptions import ConvergenceWarning

from .data import load_dataset
from .evaluation import evaluate, split_dataset
from .model import create_model
from .text import build_text


def run_experiment(config):
    output = Path(config.output_dir)
    if output.exists():
        raise ValueError(f"Output directory already exists: {output}. Choose a new directory to preserve previous runs.")
    rows = load_dataset(config.dataset_path)
    train, test, groups = split_dataset(rows, config)
    model = create_model(config)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            model.fit([build_text(rows[i]) for i in train], [rows[i]["label"] for i in train])
        except ConvergenceWarning as exc:
            raise ValueError("Logistic regression did not converge; increase max_iter and rerun") from exc
    test_texts = [build_text(rows[i]) for i in test]
    report = evaluate([rows[i]["label"] for i in test], model.predict(test_texts),
                      model.predict_proba(test_texts), model.classes_)
    report["data_kind"] = config.data_kind
    report["interpretation"] = ("Synthetic fixture smoke test only; not evidence of student-data performance."
                                if config.data_kind == "synthetic" else
                                "Labeled question-group holdout; not a Kaggle leaderboard score or classroom validation.")
    report["macro_f1_policy"] = "Union of training and test labels, including zero-support training labels; zero_division=0"
    split = {}
    for name, indices in (("train", train), ("test", test)):
        split[name] = {
            "indices": indices.tolist(),
            "rows": len(indices),
            "groups": len(set(groups[indices])),
            "label_counts": dict(sorted(Counter(rows[i]["label"] for i in indices).items())),
        }
    source = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                                         stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=source, text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    metadata = {
        "config": config.to_dict(),
        "dataset_sha256": hashlib.sha256(Path(config.dataset_path).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "versions": {name: version(name) for name in ("teacherlens", "scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl")},
        "git_commit": commit, "git_dirty": dirty,
        "split": split,
        "split_policy": "Connected QuestionId and NFC/lowercase/whitespace-normalized QuestionText groups; GroupShuffleSplit",
    }
    output.mkdir(parents=True, exist_ok=False)
    for filename, value in (("metrics.json", report), ("experiment.json", metadata)):
        (output / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    joblib.dump({"pipeline": model, "data_kind": config.data_kind, "package_version": version("teacherlens")},
                output / "model.joblib")
    return report
