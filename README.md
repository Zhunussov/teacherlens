# TeacherLens · Student strategy MVP

**Every student is different. Every student deserves a different strategy.**

Milestone 4 is a local student-first mathematics workflow: checked diagnostic → collaborative strategy choices → editable plan → deliberate practice → fresh follow-up → reflection. Next.js, TypeScript and Tailwind provide five responsive views; FastAPI and SymPy check an original 24-problem bank. Unreliable research classifiers are never used as diagnostic ground truth.

**Synthetic demo only.** Demo guidance is explicitly authored, not live AI. Actual checked answers, plans and attempts are stored locally. An optional local Ollama selector uses validated catalogue choices and topic aggregates; free text never goes to the model. Do not enter private student records. No production deployment or academic improvement is claimed.

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/mvp.txt -e ".[mvp]"
cd frontend
npm ci
cd ..
python scripts/dev_mvp.py
```

Open **http://127.0.0.1:3000**. For first-time environment creation, optional local AI, browser tests and an optimized local build, see [MVP instructions](docs/student-mvp.md). Read [student architecture](docs/student-architecture.md) and [verification status](docs/student-mvp-verification.md).

The complete Milestones 1–3 research workflow below remains available independently of the student app. Restricted Kaggle data is never required by the MVP.

---

## Research foundation (Milestones 1–3)

An individual AI research project for detecting mathematical misconceptions in students' written solutions. The foundation supplies a reproducible TF-IDF + Logistic Regression baseline; research adds grouped evaluation, binary screening, hierarchical classification and local semantic retrieval. No frontend or hosted service is included.

**Milestone 3 completed locally:** five nested question-group folds cover 35,960 deduplicated responses and all 15 questions. Semantic centroids correctly diagnose only 4/9,607 positive responses (positive MAP@3 0.002984); binary screening F1 0.376893 falls below always-positive F1 0.421665. No tested model is ready for teacher-facing diagnosis. See the [comparison and audit](docs/misconception-aware-results.md) and [historical first evaluation](docs/results.md). Restricted data and models are never bundled; the only tracked row-level data is a hand-authored synthetic test fixture.

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

The historical experiment can be reproduced with this command, which selects on validation data and refits before evaluating its question-group test. That test has now been inspected and informed development; it is not an untouched evaluation for future model selection:

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

## Misconception-aware research

Install the optional local embedding runtime (no GPU or paid service), then run the fixed nested comparison:

```powershell
python -m pip install -e ".[embeddings]"
teacherlens compare --config configs/misconception-aware.json
```

The first run downloads a pinned public English MiniLM checkpoint/tokenizer (~91 MB) and encodes responses locally. All subsequent training is local; no student text is uploaded. Five outer folds cover all 15 questions, with one independent inner grouped holdout for C/threshold/temperature selection. Exact TF-IDF diagnosis, binary screening, a shared-name hierarchy, semantic training centroids and a partial public-description catalogue are compared against frequency references. See the [fixed protocol](docs/misconception-aware-protocol.md). Existing outputs are protected; use a fresh directory for a repeat:

```powershell
teacherlens compare --config configs/misconception-aware.json --output-dir outputs/misconception-aware-repeat
teacherlens verify-comparison --first outputs/misconception-aware-cv --second outputs/misconception-aware-repeat
```

To repeat the independent frozen-embedding sample check and prepare a reviewed aggregate export:

```powershell
python scripts/verify_embeddings.py --config configs/misconception-aware.json --output outputs/embedding-verification.json
python scripts/export_comparison.py --first outputs/misconception-aware-cv --second outputs/misconception-aware-repeat --embedding-verification outputs/embedding-verification.json --output docs/metrics/misconception-aware-cv.json
```

The export verifies complete run equality and excludes private manifests and embedding input/vector hashes. Review its contents before publication. The encoder check re-encodes the first 32 rows with their original batch shape; it does not claim a second full encoding of all rows.

Full local reports, split manifests, OOF probabilities/rankings and error references remain under ignored `outputs/`. Embedding caches are bound to ordered inputs and the frozen recipe; change the cache path if data/preprocessing changes. Public reports must exclude row identifiers, embeddings and the private embedding-input hash. Cross-validation is development evidence on a very small question set, not independent classroom validation. Binary screening predicts MAP's error annotation; it does not establish a persistent misconception. No Kazakh/Russian support is claimed.

## Configuration and checks

Paths in JSON configs resolve relative to the config file, regardless of working directory. Copy a config to set the input/output paths, seed, group holdout fraction, vocabulary cap, word n-grams, regularization strength `C`, class weighting and iteration limit. Unknown settings and invalid values fail clearly. `test_size` is a fraction of groups, not rows. `data_kind` is a caller declaration, not an automatic authenticity detector.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
git diff --check
```

Read [architecture](docs/architecture.md), [dataset research](docs/research.md), and [evaluation status](docs/results.md) for decisions, limitations and next steps. This baseline has not been validated for classroom diagnosis or multilingual use.
