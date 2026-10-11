# ML foundation architecture

`config → CSV validation → exact deduplication/audit → question-group train/validation/test → training-only candidate fits → validation selection → refit train+validation → final test → local artifacts / reviewed aggregates`

## Modules and boundaries

- `config.py`: immutable JSON settings, strict validation, config-relative paths.
- `data.py`: CSV schema and label validation; no implicit conversion of literal `NA`, silent row dropping or inferred labels.
- `text.py`: common training/inference text construction.
- `model.py`: scikit-learn pipeline factory.
- `evaluation.py`: group holdout and metric computation.
- `experiment.py`: fit, evaluate and save local artifacts.
- `inference.py`: saved-model loading and batch prediction.
- `cli.py`: thin command-line adapter.
- `research.py`: audited three-way experiment, validation-only selection, final refit/evaluation and error aggregates.
- `reproducibility.py`: exact comparison of two trusted local runs, including fitted arrays and split manifests.

No web framework, database, authentication, external model service or UI dependency is introduced. A future FastAPI adapter can validate requests and call `predict_rows` with an artifact loaded at startup; it should not train per request.

Milestone 3 adds `comparison.py` for nested grouped evaluation, independent binary screening, hierarchical probability composition and semantic comparisons; `embeddings.py` for optional local frozen ONNX encoding/cache; and `descriptions.py` for six explicitly sourced public rubric mappings. The original TF-IDF factory and historical experiment remain available. Training orchestration stays separate from future request adapters. The new CV outputs are research evidence, not deployable inference artifacts.

## Features and labels

Features contain question text, selected answer and written explanation, with field markers. IDs and annotation fields are excluded. NFC normalization, lowercase and whitespace collapse preserve mathematical signs, numbers and punctuation. Tokenization includes single-character words/digits and math symbols. No stop-word removal or stemming: negation and small tokens can matter. Fraction/decimal punctuation stays present, though word tokenization still fragments expressions and does not understand algebra. `ngram_max` and `max_features` constrain vocabulary and memory.

The classifier predicts the composite category/misconception label, avoiding invalid combinations from independent classifiers. This simple closed-set approach shares no representation between related labels; rare labels may be hard to learn. A later hierarchical category classifier plus misconception ranking could share information but needs separate evaluation. Balanced class weighting gives minority classes more influence; it may reduce accuracy and does not solve unseen labels.

## Leakage control and evaluation policy

GroupShuffleSplit uses a fixed seed. Connected components merge identical QuestionIds and identical normalized QuestionText across different IDs; no component can enter more than one partition. Research reserves 20% of groups as final test, then 25% of the remaining groups as validation (20% overall). The current 15-question dataset produces 9/3/3 groups. TF-IDF vocabulary and IDF fit only on the training partition for each candidate. Selection uses validation MAP@3; exact ties use macro F1 then smaller C. Selection is frozen before final refitting on train+validation, which becomes the final training partition. Test rows never enter vocabulary, IDF, classifier fit or hyperparameter selection. The legacy `train` command keeps its simpler two-way foundation behavior; use `research` for real experiments.

Question IDs are the available proxy for original questions. Equivalent wording, paraphrases and original diagram/template families cannot be inferred reliably from CSV text alone. The holdout prevents exact question overlap, not all possible semantic overlap. If original-family metadata becomes available, group by that family instead. No student IDs are documented, so student-level leakage cannot be excluded. Do not tune repeatedly against this holdout; future tuning should use inner grouped folds and a separate final grouped test set.

A single group split does not guarantee class balance. The system reports split label counts and test-only labels, keeping every held-out row in evaluation even if its label was absent from training. Such labels are impossible for the closed-set model to predict; their recall and F1 are zero. Training with fewer than two labels fails instead of quietly choosing a favorable alternative split. Review the split before interpreting performance; add grouped cross-validation and uncertainty estimates when enough groups exist.

Macro F1 averages over the union of fitted and evaluated labels, including fitted labels with zero evaluation support (zero-division scores set to zero). Also report macro F1 over true evaluated classes with support, and support-weighted F1. Accuracy is top-1 correctness. Per-class support and the full confusion matrix expose imbalance. MAP@3 uses fitted-model probabilities: with a single true target it is reciprocal rank within the first three candidates, zero for a miss. Probability ties resolve in fitted class order. This local holdout is not comparable to a competition leaderboard without identical data/protocol.

Exact deduplication uses QuestionId, the three raw feature fields (after loader trimming), Category and Misconception, retaining the first record. Conflicting annotations for the same normalized model inputs remain. Duplicate counts and class counts are audited before fitting; no labels are changed. Keep question grouping even after deduplication because distinct responses to one question are still related. Student identifiers and original diagram/template-family metadata are unavailable, so exact grouping cannot guarantee removal of all semantic or student overlap.

## Reproducibility and privacy

Seeds, dependency pins, input hash, retained-row mapping, split indices and settings make runs auditable. Numerical libraries run with one thread during fitting/scoring for consistent local results. Fail on nonconvergence. Existing output directories cannot be overwritten. Research artifacts explicitly store the final model fitted on train+validation; its final test remains excluded. There is no production fit on the whole dataset. `verify-research` compares aggregate reports, config except output directory, dataset/split identity, package versions, vocabulary, IDF, classifier classes, coefficients, intercepts and iteration counts. Load only trusted artifacts. Git parent/dirty status reflects the state at execution; public aggregates include computational-source hashes for the committed working-tree implementation.

`report.json` has aggregate metrics; `experiment.json` and `private_errors.json` include local row references and must remain ignored. Error references deliberately omit student response and question text. Model artifacts are also derived restricted material and are not published. The reviewed `docs/metrics/real-evaluation.json` snapshot excludes row IDs, split indices and text; it contains aggregate counts, per-class metrics, confusion matrices, anonymous question-level accuracy and reproducibility checks.

Raw CSVs, credentials, serialized models and outputs are excluded from Git; only the named synthetic fixture is allowlisted. Ignore rules are not access controls: inspect staged files before committing and never force-add private data. Derived models can memorize data and require governance before sharing. Output files may remain incomplete if disk writes fail; discard the incomplete directory before rerunning to a new path.

The package keeps Unicode intact and does not assume English stop words, but that is not multilingual validation. Add language-specific datasets and preprocessing strategies, record locale, and evaluate by language before claiming multilingual support. Current single-process in-memory CSV loading and sparse TF-IDF target a small baseline, not large-scale streaming training.

## Misconception-aware comparison

`validated/deduplicated rows → frozen per-row embeddings → outer question folds → inner grouped selection → refit development rows → OOF diagnostics → reviewed aggregate report`

Each TF-IDF vectorizer sees only its fit partition. Within a fit, category, binary and composite heads share that training-only vocabulary/IDF; the specific-name classifier fits positive rows. Single-class heads explicitly emit the sole training class. The hierarchy multiplies the six-category posterior by a shared positive-name posterior, allowing a known name to transfer across True/False prefixes. It never combines NA with a misconception category. Without positive training rows, no learned name candidates are created.

Semantic centroids average only positive training vectors by exact misconception name, then normalize. Category probabilities gate cosine-softmax retrieval. Description retrieval replaces six named centroids with fixed public-description vectors and can introduce those names even when absent from a training fold. Other names require training examples. This partial external catalogue does not solve arbitrary unseen diagnoses. Cosine softmax and balanced logistic outputs are ranking scores, not calibrated probabilities of student knowledge.

The pretrained encoder is pinned by checkpoint revision and its actual local asset hashes are recorded. Ordered explanation-text hash and model/pooling recipe bind the ignored embedding cache. Frozen encoding uses no target labels or evaluation-data adaptation, so it can be cached once; prototypes and all supervised feature transforms remain fold-local. The optional `embeddings` dependency group uses ONNX Runtime and Tokenizers; ordinary tests/base installs require neither model downloads nor those packages. Network traffic downloads only public weights/tokenizer assets. Predictions, caches and centroids remain private.

The [fixed protocol](misconception-aware-protocol.md) specifies outer/inner splits, candidate grids, diagnostic selection metrics, tie policies and reporting taxonomy. Per-fold candidates are retained in the report. Pooled counts and confusion matrices are assembled from real outer predictions; actual ranking arrays preserve candidate ties without allowing padded zero columns to enter top three. Compare binary F1/recall/false positives separately from composite diagnosis. The binary classifier deliberately receives no invented specific target.

`report.json` contains aggregate counts, label taxonomy, metrics and local encoder provenance; it requires a reviewed export before publication. `experiment.json` retains private row IDs, split indices and hashes of fitted vocabulary/IDF/head arrays/centroids. `private_oof.npz` retains complete probabilities, candidate rankings, screening scores/decisions and fit counts; `private_errors.json` contains local retained indices and label pairs without text. `verify-comparison` requires exact reports, manifests/config/versions/source hashes, fitted fingerprints and OOF arrays across repeats. Public publication must omit the embedding input identity hash and every private artifact. The full model is not fit on all rows after CV, preventing an unvalidated deployment artifact from being mistaken for the evaluated models.

Global positive masks remain distinct from per-question masks. Pooled screening confusion counts must equal summed fold counts; oracle name-ranking support must equal all positive annotations. The results document a reporting-only correction of the first two real runs, reconstructed from their unchanged OOF predictions with explicit original-source and correction hashes. The migration script is for those historical artifacts; new runs use the corrected implementation directly.
