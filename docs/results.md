# First real-data experiment

Run date: 2026-10-09. This is non-commercial research using the owner-supplied MAP archive. **The baseline is not ready to diagnose student misconceptions.** On the grouped final test it correctly identified zero of 3,060 misconception-labeled rows. No student explanations, question text or row IDs appear in this document or the published aggregate JSON.

## Dataset audit

The labeled CSV has **36,696 rows, 15 questions and 65 composite labels**. All seven required columns are present; no empty required cells, duplicate row IDs or question-text inconsistencies were found. `row_id` and `QuestionId` are integer-compatible but deliberately stored as strings; remaining columns are text. Literal `NA` is an annotation value, not a missing value.

The archive contains `train.csv`, an unlabeled `test.csv` with only three rows, and a three-row sample submission. The competition test file was inspected for schema only and was excluded from fitting, selection and evaluation. All evaluation labels come from held-out partitions of the labeled training CSV.

Removed **736 exact duplicate records** ignoring row ID, retaining 35,960 rows. The original file had 1,090 excess rows sharing normalized model inputs, including 82 input groups with conflicting labels (173 rows). Conflicting labels were retained, not relabeled or dropped. Exact deduplication makes the experiment estimate performance on distinct annotated responses rather than weight identical repeated records multiple times.

Class sizes range from 1 to 14,802. 32 of 65 classes have fewer than 50 raw examples; 24 have fewer than 10. Full composite distributions are in [aggregate metrics](metrics/real-evaluation.json).

| Raw category | Rows |
|---|---:|
| False_Correct | 227 |
| False_Misconception | 9,457 |
| False_Neither | 6,542 |
| True_Correct | 14,802 |
| True_Misconception | 403 |
| True_Neither | 5,265 |

## Locked methodology

Seed 42; group fractions train/validation/test = 60%/20%/20%. Two deterministic GroupShuffleSplit steps reserve test first, then split the development groups. QuestionId and identical normalized QuestionText are merged transitively; no question group overlaps any partition. Fractions apply to groups, so row fractions differ. No stratification or retries were used to find a favorable class distribution. The experiment is limited to one seed and 15 question groups.

| Partition | Rows | Question groups | Classes / 65 |
|---|---:|---:|---:|
| train | 20,228 | 9 | 41 / 65 |
| validation | 6,287 | 3 | 18 / 65 |
| test | 9,445 | 3 | 16 / 65 |

The model uses NFC normalization, lowercase, collapsed whitespace, field markers, single-character/math-symbol tokens, TF-IDF word unigrams/bigrams, sublinear TF, a 50,000-feature cap, and balanced multinomial Logistic Regression with lbfgs and max_iter=1,000. The only selected setting was C from {0.5, 1, 2}. Each candidate fitted vocabulary, IDF and classifier only on the training partition. Selection maximized validation MAP@3, breaking ties by macro F1 then smaller C. Test scores were not consulted for selection.

| C | Validation MAP@3 |
|---:|---:|
| 0.5 | 0.542866 |
| 1 | 0.545093 |
| 2 | 0.537087 |

Selected **C=1**, then refitted preprocessing and classifier on the combined 26,515 training+validation rows (55 fitted classes). This combined partition is the final model's training data; final test rows never enter any fit. The final test was evaluated after selection was frozen. A complete repeat served only as a reproducibility audit; no configuration changed after examining test performance.

## Actual metrics

| Metric | Selected model: validation before refit | Final model: grouped test |
|---|---:|---:|
| Accuracy | 0.391125 | 0.393224 |
| Macro F1, fixed union policy | 0.020337 | 0.018057 |
| Macro F1, evaluated classes with support | 0.062140 | 0.073357 |
| Weighted F1 | 0.371705 | 0.290038 |
| MAP@3 | 0.545093 | 0.486995 |

Macro F1 under the foundation policy averages over the union of fitted and evaluated true labels, including classes absent from the evaluated partition, with zero_division=0. The final union has 65 classes; the test-supported alternative averages over the 16 true test classes. Both are reported because unsupported-class zeros make the fixed-union score much lower. Weighted F1 weights by evaluated support. MAP@3 is reciprocal rank at ranks 1–3 for the single true label, zero outside the first three or for unseen targets.

A descriptive majority-class reference, selected using final fitting-data frequency, predicts `True_Correct:NA` and achieves 0.276548 test accuracy. This reference was computed after the main experiment for context and was not used for selection. The sparse model improves aggregate accuracy, but that improvement does not demonstrate misconception diagnosis.

Complete validation/final per-class metrics and confusion matrices are in [aggregate metrics](metrics/real-evaluation.json). Matrix rows are true labels, columns predicted labels, in the corresponding `labels` order. Observed final-test classes are shown below; all remaining classes have zero test support.

| Composite label | Precision | Recall | F1 | Test support |
|---|---:|---:|---:|---:|
| False_Correct:NA | 0.0103 | 0.0811 | 0.0183 | 37 |
| False_Misconception:Division | 0.0000 | 0.0000 | 0.0000 | 58 |
| False_Misconception:Incomplete | 0.0000 | 0.0000 | 0.0000 | 1296 |
| False_Misconception:Positive | 0.0000 | 0.0000 | 0.0000 | 539 |
| False_Misconception:Subtraction | 0.0000 | 0.0000 | 0.0000 | 617 |
| False_Misconception:Tacking | 0.0000 | 0.0000 | 0.0000 | 124 |
| False_Misconception:WNB | 0.0000 | 0.0000 | 0.0000 | 241 |
| False_Neither:NA | 0.3503 | 0.6736 | 0.4609 | 2249 |
| True_Correct:NA | 0.4719 | 0.8055 | 0.5951 | 2612 |
| True_Misconception:Division | 0.0000 | 0.0000 | 0.0000 | 5 |
| True_Misconception:Incomplete | 0.0000 | 0.0000 | 0.0000 | 8 |
| True_Misconception:Positive | 0.0000 | 0.0000 | 0.0000 | 2 |
| True_Misconception:Subtraction | 0.0000 | 0.0000 | 0.0000 | 2 |
| True_Misconception:Tacking | 0.0000 | 0.0000 | 0.0000 | 160 |
| True_Misconception:WNB | 0.0000 | 0.0000 | 0.0000 | 8 |
| True_Neither:NA | 0.2521 | 0.0619 | 0.0994 | 1487 |

## Error analysis and distribution shift

**No tested misconception class was predicted reliably.** Every misconception class present in test had zero top-1 precision/recall/F1. The strongest supported non-misconception class was True_Correct:NA (precision 0.4719, recall 0.8055); False_Neither:NA had precision 0.3503 and recall 0.6736. These category results are not mathematical misconception identification.

Safe examples below are aggregate label-to-label errors, not quoted student responses:

- `False_Misconception:Incomplete` → `False_Neither:NA`: 1,034 errors.
- `True_Neither:NA` → `False_Neither:NA`: 695 errors.
- `True_Neither:NA` → `True_Correct:NA`: 673 errors.
- `False_Neither:NA` → `True_Correct:NA`: 568 errors.
- `True_Correct:NA` → `False_Neither:NA`: 387 errors.
- `False_Misconception:Subtraction` → `True_Correct:NA`: 325 errors.

For example, 1,034 of 1,296 False_Misconception:Incomplete cases were assigned False_Neither:NA, and 203 were assigned True_Correct:NA. Incomplete is present in the fitting data yet has zero recall on new questions. This exposes question-context transfer failure beyond merely missing classes. Subtraction and Positive are unseen targets and cannot be emitted by this closed-set model at all.

Validation had 14 labels unseen in the initial training partition, affecting 1,386/6,287 rows (22.05%). Final test had **10 labels unseen in the final fit**, affecting **1,523/9,445 rows (16.12%)**. Retaining these rows is essential: excluding them would inflate apparent generalization. Their achievable top-1 accuracy and MAP@3 are zero for this model; the resulting overall accuracy ceiling from unseen targets alone is 83.88%.

| Label frequency in final fitting data | Test rows | Accuracy |
|---|---:|---:|
| unseen_0 | 1,523 | 0.000000 |
| rare_1_to_49 | 241 | 0.000000 |
| frequent_50_plus | 7,681 | 0.483531 |

The rare seen bucket contains only False_Misconception:WNB (37 fitting examples, 241 test cases), so its zero accuracy is suggestive, not broad causal proof that rarity alone explains failure. Frequent labels also fail for specific misconceptions. Performance varies across the three anonymous test question groups: 0.4640, 0.3031 and 0.3342 accuracy. Row-level confidence intervals would treat related responses as independent and be misleading; three groups are insufficient for strong generalization claims. No uncertainty interval is claimed.

For a teacher-facing product, missed misconceptions and wrongly reassuring Correct predictions are serious failure modes. Use neither these predictions nor the aggregate accuracy for grading or automated diagnosis. Future work needs open-set or catalogue-based ranking, uncertainty/abstention, expert review and robust question-family evaluation. Confidence calibration and classroom effectiveness have not been established.

## Local artifacts and reproduction

From the activated Python 3.11 environment in the repository:

```powershell
teacherlens research --config configs/real-evaluation.json
```

The default outputs already exist locally; run a new copy without overwriting them:

```powershell
teacherlens research --config configs/real-evaluation.json --output-dir outputs/real-evaluation-new
teacherlens verify-research --first outputs/real-evaluation-seed42 --second outputs/real-evaluation-new
```

- `outputs/real-evaluation-seed42/report.json`: full local aggregate report and candidate metrics.
- `outputs/real-evaluation-seed42/experiment.json`: resolved config, dataset hash, pinned versions, retained row IDs and split indices; private.
- `outputs/real-evaluation-seed42/private_errors.json`: 20 incorrect-prediction references with local row IDs/indices and labels, no response text; private.
- `outputs/real-evaluation-seed42/model.joblib`: locally trained model; private, load only if trusted.
- `outputs/real-evaluation-seed42-repeat/`: independent repeat of the entire fitting/selection/refit protocol.
- `docs/metrics/real-evaluation.json`: reviewed public-safe aggregate snapshot; excludes row identifiers, split indices and response/question text.

Dataset SHA-256: `f347a34f62be3b1bc188b11290f5615b5bf050a7b7c3aeb21b1966feed7615a0`. Python 3.11.9; one numerical thread. Version pins and computational-source hashes are in the aggregate snapshot. The runs occurred on the working tree based on foundation commit ab66d53; their local metadata truthfully records that parent commit and dirty status. The source used is subsequently committed on feature/real-data-evaluation. Dataset identity was checked by local hash, not independently verified against a Kaggle checksum.

## Historical verification and proposed Milestone 3

All 32 tests passed, including deduplication with conflicting annotations, disjoint three-way partitions, validation-only selection, final-fit isolation, weighted/test-supported macro F1, repeat comparison and detection of deliberately changed metrics. Python compilation and dependency checks passed. Two complete real experiments had exactly equal aggregate reports, retained-row/split manifests, vocabulary, IDF, class ordering, coefficients, intercepts and iteration counts. This is exact reproducibility on the tested environment, not across arbitrary hardware. No restricted files are staged or committed.

Priorities for Milestone 3:

1. Pre-register grouped outer evaluation (with inner grouped selection), report per-question outcomes and uncertainty at the question level, and obtain additional question families. Keep this test split as a historical benchmark; do not tune against it repeatedly.
2. Compare character n-grams, explanation-only/context ablations and a hierarchical category-plus-catalogue misconception ranker. Evaluate seen and unseen targets separately while preserving an all-row primary score.
3. Compare a licensed local transformer on identical deduplicated partitions and fixed search budgets; fit only development data, freeze selection before outer tests, and record tokenizer/checkpoint version, cost and seeds. Do not assume a transformer solves missing-label coverage.
4. Obtain authorized multilingual explanations and expert labels; measure each language and cross-language transfer. Group translated/paraphrased versions with the original question family. Translation-only tests do not establish natural multilingual classroom performance.
5. Investigate annotation conflicts with qualified reviewers without publishing student text; evaluate calibration, abstention and teacher review before any service or frontend integration.

## Milestone 3 follow-up (2026-10-11)

The historical test above has been inspected and informed further research; it is not an untouched future test. New nested question-group development cross-validation covers all 15 available questions, with all model selection inside the five outer training folds. See the [complete misconception-aware comparison](misconception-aware-results.md) and [reviewed aggregate snapshot](metrics/misconception-aware-cv.json).

| Approach | Pooled accuracy | Macro F1 (65 observed codes) | Positive MAP@3 | Correct positive / 9,607 |
|---|---:|---:|---:|---:|
| Majority class | 0.402558 | 0.008831 | 0.000000 | 0 |
| Class-frequency ranking | 0.402558 | 0.008831 | 0.000000 | 0 |
| TF-IDF composite | 0.274305 | 0.016225 | 0.000000 | 0 |
| Hierarchical TF-IDF | 0.306396 | 0.015569 | 0.000000 | 0 |
| Semantic training centroids | 0.301363 | 0.015831 | 0.002984 | 4 |
| Semantic partial descriptions | 0.289766 | 0.015190 | 0.000208 | 0 |

Binary screening pooled precision/recall/F1 are 0.279385 / 0.578953 / 0.376893; fold F1 is 0.279202 ± 0.218374. Always-positive F1 is 0.421665. Overall unseen-composite rate is 20.96%, affecting 78.47% of positive responses. No model is reliable for diagnosis, and no Kazakh/Russian validation has occurred. Complete per-question and per-class results, oracle-name ablations, reporting-correction provenance, reproducibility evidence and next-milestone recommendations appear in the follow-up report.
