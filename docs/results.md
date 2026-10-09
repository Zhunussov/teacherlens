# Evaluation status

**Real evaluation: blocked.** No real labeled CSV is present in the repository. No accuracy, F1, confusion matrix or classroom-performance claim is reported for real data.

The tracked synthetic fixture contains 16 hand-written rows across eight toy decimal-comparison questions and two composite labels. It deliberately repeats easy explanation patterns to exercise the pipeline; it is not sampled from students or Kaggle. Tests use it to verify deterministic group splitting, training/inference consistency, artifact provenance and command behavior. Smoke-test metrics are written only to ignored local output directories and always marked synthetic.

## Foundation validation (2026-10-09)

- Fresh virtual environment installation succeeded on Windows with Python 3.11.9 and the pinned runtime dependencies.
- All 24 standard-library unit/integration tests passed, including MAP@3 ranks 1–3, the rank-4 cutoff, probability ties and unseen targets.
- The documented synthetic training and saved-model prediction commands completed successfully.
- Python compilation and dependency compatibility checks passed.
- Git ignore checks confirmed raw data, credentials and model outputs are excluded while the synthetic fixture is allowed.

This validates software behavior on synthetic inputs, not model quality on student work. The repository includes a CI workflow; remote CI has not yet been run.

Once authorized labeled data is available:

1. Obtain authorized Kaggle access as an eligible account holder for permitted non-commercial research; never redistribute the restricted data. Inspect actual schema, missing fields, counts, languages and duplicates.
2. Run `teacherlens train --config configs/baseline.json` and review split label counts and unseen test classes.
3. Report dataset hash, config, dependency versions and split protocol alongside accuracy, macro F1, per-class metrics, confusion matrix and MAP@3.
4. Add grouped cross-validation for uncertainty and nested grouped tuning, preserving a final untouched holdout.
5. Investigate hierarchical labels, character n-grams, question-family metadata and multilingual labeled data before adding a service interface.

The inspected browser session was signed out and required rule acceptance; conventional Kaggle credential files/environment were absent. No authenticated access or real training run was performed. The official Eedi Misconceptions Graph (CC BY 4.0) is a documented alternative for taxonomy work, but excludes student responses and cannot unblock this classifier's evaluation. See [research](research.md) for primary sources and license details.
