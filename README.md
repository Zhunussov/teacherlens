# TeacherLens

An individual AI research project for detecting mathematical misconceptions in students' written solutions. Milestone 1 supplies a reproducible TF-IDF + Logistic Regression baseline; no frontend or hosted service is included.

**Real evaluation is blocked: no authorized labeled Kaggle CSV is available in this checkout.** The only bundled data is an explicitly synthetic, hand-authored test fixture. Its smoke-test scores are not research results.

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

After setup and authorized data placement, this **single command trains and evaluates** the real-data baseline:

```powershell
teacherlens train --config configs/baseline.json
```

Optional saved-model batch prediction:

```powershell
teacherlens predict --model outputs/baseline-seed42/model.joblib --data data/raw/test.csv --output outputs/predictions.csv
```

`metrics.json` contains accuracy, macro F1, precision/recall/F1/support per class, a confusion matrix (rows=true, columns=predicted, ordered by `labels`), MAP@3, and unseen-label counts. `experiment.json` records resolved config, dataset SHA-256, dependency versions, Git revision/dirty status, split indices and label counts. `model.joblib` contains the fitted preprocessing/classifier pipeline and provenance. No student explanations are copied into reports, but models and label inventories are derived data and remain local.

Prediction emits a research CSV with `row_id`, `Category:Misconception`, and model `data_kind`. It is not a competition submission exporter. Only load model files you created or trust: joblib deserialization can execute code.

## Configuration and checks

Paths in JSON configs resolve relative to the config file, regardless of working directory. Copy a config to set the input/output paths, seed, group holdout fraction, vocabulary cap, word n-grams, regularization strength `C`, class weighting and iteration limit. Unknown settings and invalid values fail clearly. `test_size` is a fraction of groups, not rows. `data_kind` is a caller declaration, not an automatic authenticity detector.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

Read [architecture](docs/architecture.md), [dataset research](docs/research.md), and [evaluation status](docs/results.md) for decisions, limitations and next steps. This baseline has not been validated for classroom diagnosis or multilingual use.
