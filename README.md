# TeacherLens

An individual AI research project for detecting mathematical misconceptions in students' written solutions. The foundation supplies a reproducible TF-IDF + Logistic Regression baseline; the first real-data experiment adds separate grouped model selection and final evaluation. No frontend or hosted service is included.

**First real evaluation completed locally:** grouped test accuracy 0.393224, weighted F1 0.290038 and MAP@3 0.486995. No misconception-labeled test row was classified correctly. This baseline is not ready for teacher-facing diagnosis. Restricted data and models are never bundled; the only tracked row-level data is a hand-authored synthetic test fixture. See [measured results](docs/results.md).

## Setup

Use Python 3.11 (validated with 3.11.9). From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

On Linux/macOS activate with `source .venv/bin/activate`. Runtime dependencies are pinned in `pyproject.toml`; the test suite uses Python's standard library. Installation requires access to a package index. Reproducibility assumes the same Python and dependency versions; numerical results may differ across hardware.

## Synthetic smoke test

```powershell
teacherlens train --config configs/synthetic.json
teacherlens predict --model outputs/synthetic-seed42/model.joblib --data tests/fixtures/synthetic.csv --output outputs/synthetic-predictions.csv
```

All synthetic artifacts carry `data_kind=synthetic`. Outputs are ignored by Git. Choose a new `output_dir` for another run; commands refuse to overwrite existing artifacts.

## Real training and evaluation

The [data tab](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data) lists MIT, but the [official rules](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/rules) specify CC BY-NC 4.0 data use plus additional sharing restrictions. MIT is separately listed for the winning submission. Review your eligibility and the rules, then obtain CSVs through your own authorized Kaggle access for permitted non-commercial research. Place `train.csv` under `data/raw/`; data is never downloaded automatically. Credentials stay outside the repository. Never commit or redistribute restricted competition data. See the licensing/access findings in [research](docs/research.md).

After setup and authorized data placement, this **single command selects on validation data, refits on train+validation and evaluates the final question-group test**:

```powershell
teacherlens research --config configs/real-evaluation.json
```

Use `--output-dir outputs/new-run` for a fresh run; existing output directories cannot be overwritten. Verify a repeat with:

```powershell
teacherlens verify-research --first outputs/real-evaluation-seed42 --second outputs/new-run
```

The older `teacherlens train --config configs/baseline.json` remains available for foundation two-way smoke checks. Optional saved-model batch prediction:

```powershell
teacherlens predict --model outputs/real-evaluation-seed42/model.joblib --data data/raw/test.csv --output outputs/predictions.csv
```

Research `report.json` contains validation selection, accuracy, both macro F1 policies, weighted F1, MAP@3, per-class precision/recall/F1/support, confusion matrices, class coverage and error aggregates. Matrices use rows=true, columns=predicted in `labels` order. `experiment.json` records config, dataset SHA-256, versions, Git parent/dirty status, retained-row references and split indices. `private_errors.json` stores error row references without response text. `model.joblib` contains the final fitted pipeline and provenance. These artifacts stay under ignored `outputs/`. Reviewed aggregate metrics are published in [docs/metrics/real-evaluation.json](docs/metrics/real-evaluation.json).

Prediction emits a research CSV with `row_id`, `Category:Misconception`, and model `data_kind`. It is not a competition submission exporter. Only load model files you created or trust: joblib deserialization can execute code.

## Configuration and checks

Paths in JSON configs resolve relative to the config file, regardless of working directory. Copy a config to set the input/output paths, seed, group holdout fraction, vocabulary cap, word n-grams, regularization strength `C`, class weighting and iteration limit. Unknown settings and invalid values fail clearly. `test_size` is a fraction of groups, not rows. `data_kind` is a caller declaration, not an automatic authenticity detector.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

Read [architecture](docs/architecture.md), [dataset research](docs/research.md), and [evaluation status](docs/results.md) for decisions, limitations and next steps. This baseline has not been validated for classroom diagnosis or multilingual use.
