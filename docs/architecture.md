# ML foundation architecture

`config → CSV validation → text assembly → question-group split → training-only TF-IDF fit → logistic regression → evaluation/artifacts`

## Modules and boundaries

- `config.py`: immutable JSON settings, strict validation, config-relative paths.
- `data.py`: CSV schema and label validation; no implicit conversion of literal `NA`, silent row dropping or inferred labels.
- `text.py`: common training/inference text construction.
- `model.py`: scikit-learn pipeline factory.
- `evaluation.py`: group holdout and metric computation.
- `experiment.py`: fit, evaluate and save local artifacts.
- `inference.py`: saved-model loading and batch prediction.
- `cli.py`: thin command-line adapter.

No web framework, database, authentication, external model service or UI dependency is introduced. A future FastAPI adapter can validate requests and call `predict_rows` with an artifact loaded at startup; it should not train per request.

## Features and labels

Features contain question text, selected answer and written explanation, with field markers. IDs and annotation fields are excluded. NFC normalization, lowercase and whitespace collapse preserve mathematical signs, numbers and punctuation. Tokenization includes single-character words/digits and math symbols. No stop-word removal or stemming: negation and small tokens can matter. Fraction/decimal punctuation stays present, though word tokenization still fragments expressions and does not understand algebra. `ngram_max` and `max_features` constrain vocabulary and memory.

The classifier predicts the composite category/misconception label, avoiding invalid combinations from independent classifiers. This simple closed-set approach shares no representation between related labels; rare labels may be hard to learn. A later hierarchical category classifier plus misconception ranking could share information but needs separate evaluation. Balanced class weighting gives minority classes more influence; it may reduce accuracy and does not solve unseen labels.

## Leakage control and evaluation policy

GroupShuffleSplit uses a fixed seed. Connected components merge identical QuestionIds and identical normalized QuestionText across different IDs; no component can enter both train and test. TF-IDF vocabulary and IDF fit only on training rows inside the pipeline. No labels, test rows, or label-derived correctness features enter training preprocessing.

Question IDs are the available proxy for original questions. Equivalent wording, paraphrases and original diagram/template families cannot be inferred reliably from CSV text alone. The holdout prevents exact question overlap, not all possible semantic overlap. If original-family metadata becomes available, group by that family instead. No student IDs are documented, so student-level leakage cannot be excluded. Do not tune repeatedly against this holdout; future tuning should use inner grouped folds and a separate final grouped test set.

A single group split does not guarantee class balance. The system reports split label counts and test-only labels, keeping every held-out row in evaluation even if its label was absent from training. Such labels are impossible for the closed-set model to predict; their recall and F1 are zero. Training with fewer than two labels fails instead of quietly choosing a favorable alternative split. Review the split before interpreting performance; add grouped cross-validation and uncertainty estimates when enough groups exist.

Macro F1 averages over the union of training and test labels, including training labels with zero test support (zero-division scores set to zero). This explicit policy is conservative and can differ from tools that average only over observed test labels. Accuracy is top-1 correctness. Per-class support and the full confusion matrix expose imbalance. MAP@3 uses fitted-model probabilities: with a single true target it is reciprocal rank within the first three candidates, zero for a miss. Probability ties resolve in fitted class order. This local held-out score is not comparable to a competition leaderboard without identical data/protocol.

## Reproducibility and privacy

Seeds, dependency pins, input hash, split indices and settings make runs auditable. Fail on nonconvergence; increase iterations explicitly. Existing output directories cannot be overwritten. Training artifacts retain the model fit on the training partition; there is no hidden refit on evaluation data. A separately configured full-data production fit would be a later step after evaluation.

Raw CSVs, credentials, serialized models and outputs are excluded from Git; only the named synthetic fixture is allowlisted. Ignore rules are not access controls: inspect staged files before committing and never force-add private data. Derived models can memorize data and require governance before sharing. Output files may remain incomplete if disk writes fail; discard the incomplete directory before rerunning to a new path.

The package keeps Unicode intact and does not assume English stop words, but that is not multilingual validation. Add language-specific datasets and preprocessing strategies, record locale, and evaluate by language before claiming multilingual support. Current single-process in-memory CSV loading and sparse TF-IDF target a small baseline, not large-scale streaming training.
