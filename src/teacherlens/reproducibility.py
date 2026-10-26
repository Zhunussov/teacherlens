"""Compare trusted local research artifacts without publishing row identifiers."""

import json
from pathlib import Path

import joblib
import numpy as np


def verify_research_runs(first, second):
    first, second = Path(first), Path(second)
    reports = [json.loads((path / "report.json").read_text(encoding="utf-8")) for path in (first, second)]
    metadata = [json.loads((path / "experiment.json").read_text(encoding="utf-8")) for path in (first, second)]
    checks = {"aggregate_reports_equal": reports[0] == reports[1]}
    for key in ("dataset_sha256", "python", "versions", "threads", "retained_row_ids", "split_indices"):
        checks[f"{key}_equal"] = metadata[0][key] == metadata[1][key]
    configs = [{k: v for k, v in item["config"].items() if k != "output_dir"} for item in metadata]
    checks["config_equal_except_output_dir"] = configs[0] == configs[1]
    # Load only trusted, locally produced joblib artifacts.
    models = [joblib.load(path / "model.joblib")["pipeline"] for path in (first, second)]
    checks["vocabulary_equal"] = models[0]["tfidf"].vocabulary_ == models[1]["tfidf"].vocabulary_
    for step, attribute in (("tfidf", "idf_"), ("classifier", "classes_"),
                            ("classifier", "coef_"), ("classifier", "intercept_"), ("classifier", "n_iter_")):
        checks[f"{step}_{attribute}_equal"] = np.array_equal(getattr(models[0][step], attribute), getattr(models[1][step], attribute))
    if not all(checks.values()):
        raise ValueError("Reproducibility mismatch: " + ", ".join(key for key, passed in checks.items() if not passed))
    return {"passed": True, "checks": checks,
            "scope": "Exact equality on this environment; not a promise of identical floating-point results across platforms."}
