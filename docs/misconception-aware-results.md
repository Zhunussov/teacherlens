# Misconception-aware research, Milestone 3

Experiment date: 2026-10-11. All evaluations use held-out portions of the authorized local labeled MAP training file. The three unlabeled competition-test rows are excluded. This is development cross-validation following an inspected historical test, **not an untouched final test or evidence of production readiness**. No student responses, question content or row IDs are published.

## Audit and diagnostic task validity

The 36,696-row source becomes 35,960 rows after 736 exact duplicates are removed. There are 15 question groups, six categories, 65 observed composite labels and 35 misconception names. There are **9,607 misconception-bearing annotations (26.72%)** and 26,353 other responses. All positive categories have a non-NA name; all other categories have NA. The binary annotation and six-category/shared-name hierarchy are therefore well-defined. Correct selected answers may have error-bearing explanations, so answer correctness is not the screening target. MAP's positive class includes some procedural/instructionally relevant errors; it does not prove a persistent misconception.

**32 of 35 names occur on only one question.** Incomplete occurs on three, WNB on two and Irrelevant on two. The case-distinct Wrong_Fraction and Wrong_fraction names are retained. Question holdout therefore couples new-question transfer with missing-target coverage. A closed-set model cannot diagnose most single-question names after their question is held out. This is a genuine deployment limitation, not a reason to remove those rows from evaluation.

The historical model predicted False_Neither on 4,325/9,445 rows despite only 2,249 true instances. However, True_Correct was the largest predicted class (4,459), so False_Neither was overrepresented rather than the sole dominant class. Historical misconception accuracy, recall@3 and MAP@3 were all zero, even though 50.23% of positive targets were supported by training. Generic-label scores explain its nonzero aggregate accuracy/MAP@3.

Post-hoc historical screening illustrates score fragmentation: classifying by the winning composite label detects zero positives, but summing all misconception-class probabilities at threshold 0.5 yields precision 0.398120, recall 0.802614, F1 0.532235, AP 0.346907 and false-positive rate 0.581519. Many individually weak diagnosis scores can sum to high error probability while no exact name reaches top three. These are descriptive historical results, not new threshold selection or evidence of reliable screening. [Historical aggregate audit](metrics/historical-screening-audit.json).

Balanced weighting does not create evidence for absent labels and does not calibrate scores. The hierarchy shares name information across answer-correctness prefixes, but its soft joint ranking still distributes category mass across many specific candidates. That is a different decision rule from hard routing to the most probable category. A complete description catalogue could expose additional targets; the six verified descriptions tested here cover only 42.38% of positive rows.

## Fixed methodology

See the [protocol fixed before outer results](misconception-aware-protocol.md), [architecture](architecture.md) and [source research](research.md). Every outer partition holds three questions; each development set has 12 questions, subdivided into nine inner training and three inner validation groups. Outer folds are deterministic and balance row counts without target labels. Inner seeds are 42–46. The C, binary threshold and semantic temperature grids are fixed before evaluation. All selection is inside the development partition; refitting uses its 12 questions before testing the remaining three.

| Outer fold | Inner train | Inner validation | Refit development | Outer test | Positive test | Unseen composite test rows |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 19,932 | 8,610 | 28,542 | 7,418 | 1,941 | 404 |
| 2 | 23,857 | 5,184 | 29,041 | 6,919 | 1,973 | 1,576 |
| 3 | 21,787 | 6,791 | 28,578 | 7,382 | 1,949 | 1,949 |
| 4 | 19,659 | 9,339 | 28,998 | 6,962 | 1,852 | 1,737 |
| 5 | 19,144 | 9,537 | 28,681 | 7,279 | 1,892 | 1,873 |

Overall 7,539/35,960 rows (20.96%), all misconception-bearing, have a composite target absent from their corresponding training partition: **78.47% of positive responses**. Candidate coverage can exceed trained-label coverage for the shared-name hierarchy or fixed descriptions; this is recorded separately. Fold 3 has no seen positive composite labels. Inner validation may similarly have poor coverage, making some tuning objectives uninformative; deterministic tie rules avoid searching for favorable splits.

TF-IDF preserves the existing full question/selected-answer/explanation construction. Each vectorizer fits only its training partition. Binary, category and composite heads share that partition's vocabulary; the name head learns positive training rows. Semantic embeddings use explanations alone with frozen English MiniLM, local CPU ONNX, 256-wordpiece truncation and attention-mask mean/L2 pooling. This input difference limits architecture-only interpretation. Pure centroids use training-positive examples; the description variant overrides six names using fixed public rubric paraphrases and uses centroids for the rest. No fine-tuning or external inference service is used.

Pooled OOF metrics weight responses, while means/standard deviations weight the five outer folds equally. Standard deviations describe those particular partitions, not confidence intervals. Primary composite macro F1 averages all 65 observed codes; secondary formal macro F1 includes nine additional permissible but unobserved category/name combinations (74 total). Unseen targets remain misses. MAP@3 is reciprocal rank within three; recall@3 is a hit indicator. Binary screening metrics have a separate target and must not be treated as exact diagnoses. Name-only oracle metrics use known-positive annotations and exclude screening/answer-correctness errors.

## Measured comparisons

Every row has one out-of-fold prediction. These are the fixed procedures selected inside training folds, not models retuned after seeing outer results. The majority reference emits only one candidate; frequency ranking emits the training-frequency order. Neither uses test frequencies.

| Approach | Accuracy | Macro F1 (65) | Weighted F1 | MAP@3 | Recall@3 |
|---|---:|---:|---:|---:|---:|
| Majority class | 0.402558 | 0.008831 | 0.231082 | 0.402558 | 0.402558 |
| Class-frequency ranking | 0.402558 | 0.008831 | 0.231082 | 0.540355 | 0.726529 |
| TF-IDF composite | 0.274305 | 0.016225 | 0.286428 | 0.416171 | 0.604422 |
| Hierarchical TF-IDF | 0.306396 | 0.015569 | 0.277950 | 0.456192 | 0.649082 |
| Semantic training centroids | 0.301363 | 0.015831 | 0.277063 | 0.436364 | 0.610317 |
| Semantic partial descriptions | 0.289766 | 0.015190 | 0.266393 | 0.416069 | 0.582481 |

The simple frequency reference has the highest overall MAP@3 (0.540355) and ties majority for the highest accuracy. This is a warning about the aggregate objective: it diagnoses no misconception. Composite TF-IDF has the highest overall macro F1 (0.016225), also with zero correct diagnoses. No approach is a reliable diagnostic winner.

| Approach | Positive correct / 9,607 | Positive recall@3 | Positive MAP@3 | Positive candidate coverage | Other accuracy | Other MAP@3 |
|---|---:|---:|---:|---:|---:|---:|
| Majority class | 0 | 0.000000 | 0.000000 | 0.000000 | 0.549311 | 0.549311 |
| Class-frequency ranking | 0 | 0.000000 | 0.000000 | 0.215260 | 0.549311 | 0.737342 |
| TF-IDF composite | 0 | 0.000000 | 0.000000 | 0.215260 | 0.374303 | 0.567886 |
| Hierarchical TF-IDF | 0 | 0.000000 | 0.000000 | 0.225981 | 0.418093 | 0.622497 |
| Semantic training centroids | 4 | 0.006037 | 0.002984 | 0.225981 | 0.411073 | 0.594354 |
| Semantic partial descriptions | 0 | 0.000416 | 0.000208 | 0.423754 | 0.395401 | 0.567671 |

Semantic centroids have the best measured end-to-end misconception MAP@3, **0.002984**, but identify only **4/9,607** cases correctly (0.0416%). Only 58 targets reach the top three. Partial descriptions increase candidate coverage from 22.60% to 42.38% but identify zero cases correctly; four targets reach rank two. Merely making a label available does not establish useful discrimination.

## Screening, rather than exact diagnosis

Binary thresholds maximize positive F1 in each inner validation partition; they are not adjusted using the outer tests. Pooled screening uses all 9,607 positive annotations.

| Procedure | Precision | Recall | Positive F1 | AP | False-positive rate | Accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Always negative | 0.000000 | 0.000000 | 0.000000 | 0.267158 | 0.000000 | 0.732842 |
| Always positive | 0.267158 | 1.000000 | 0.421665 | 0.267158 | 1.000000 | 0.267158 |
| TF-IDF binary, inner-selected thresholds | 0.279385 | 0.578953 | 0.376893 | 0.341265 | 0.544378 | 0.488571 |

The dedicated screening model has lower pooled F1 than marking every response positive (0.376893 versus 0.421665). Its confusion matrix is **[[12,007, 14,346], [4,045, 5,562]]**, rows=true other/positive and columns=predicted other/positive. It misses 42.10% of annotated errors and flags 54.44% of other responses. Such a gate would both exclude students needing review and burden teachers with false alarms. Average precision is calculated from continuous scores, not threshold decisions. Pooled AP compares scores from different uncalibrated fold models and is descriptive; fold AP is also reported.

## Cross-validation variability and question transfer

| Approach | Accuracy, fold mean ± sample SD | Macro F1 (65), mean ± SD | All MAP@3, mean ± SD | Positive MAP@3, mean ± SD |
|---|---:|---:|---:|---:|
| Majority class | 0.402319 ± 0.065926 | 0.008789 ± 0.001034 | 0.402319 ± 0.065926 | 0.000000 ± 0.000000 |
| Class-frequency ranking | 0.402319 ± 0.065926 | 0.008789 ± 0.001034 | 0.540113 ± 0.041962 | 0.000000 ± 0.000000 |
| TF-IDF composite | 0.271603 ± 0.125351 | 0.013208 ± 0.005106 | 0.413735 ± 0.106722 | 0.000000 ± 0.000000 |
| Hierarchical TF-IDF | 0.303538 ± 0.129225 | 0.012587 ± 0.006303 | 0.453539 ± 0.116064 | 0.000000 ± 0.000000 |
| Semantic training centroids | 0.298489 ± 0.130621 | 0.012637 ± 0.006243 | 0.433730 ± 0.118499 | 0.002916 ± 0.006077 |
| Semantic partial descriptions | 0.286566 ± 0.138361 | 0.012024 ± 0.006764 | 0.412773 ± 0.132601 | 0.000203 ± 0.000453 |

Binary screening fold F1 is **0.279202 ± 0.218374**, recall **0.574047 ± 0.506105**, and AP **0.359118 ± 0.159435**. These are five folds, not 35,960 independent validation units. Pooled nonlinear F1 need not equal the average fold F1. The mean unseen-composite row rate is **0.210615 ± 0.088350**; the pooled rate is 0.209650.

| Fold | Binary C / threshold | Outer screening F1 | Positive centroid MAP@3 | Positive description MAP@3 |
|---|---:|---:|---:|---:|
| 1 | 0.5 / 0.2 | 0.486562 | 0.000000 | 0.000000 |
| 2 | 0.5 / 0.2 | 0.444469 | 0.013769 | 0.001014 |
| 3 | 1 / 0.5 | 0.078603 | 0.000000 | 0.000000 |
| 4 | 0.5 / 0.65 | 0.012357 | 0.000810 | 0.000000 |
| 5 | 0.5 / 0.2 | 0.374020 | 0.000000 | 0.000000 |

All composite and hierarchical TF-IDF inner objectives were zero, so all selected C=0.5 by the fixed tie rule. Centroid inner objectives were also zero, selecting C=0.5 and temperature=0.05. The description procedure selected C=2 in fold 4 (inner positive MAP@3=0.001451), otherwise C=0.5; every temperature was 0.05. This is weak model-selection evidence, not evidence that those hyperparameters are optimal.

The 15 anonymous question ordinals below are stable local report identifiers, without publishing original IDs or question content. Unseen rates apply to all rows in the question; all unseen targets are positive. Complete per-question scores for every approach are in the aggregate JSON.

| Question | Rows | Positive rows | Unseen row rate | Positive centroid MAP@3 | Positive description MAP@3 | Screening F1 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 4,713 | 1,553 | 0.003395 | 0.000000 | 0.000000 | 0.595819 |
| 2 | 3,072 | 621 | 0.202148 | 0.000000 | 0.000000 | 0.000000 |
| 3 | 2,735 | 386 | 0.099086 | 0.003886 | 0.000000 | 0.036735 |
| 4 | 3,584 | 1,405 | 0.281250 | 0.019336 | 0.001423 | 0.563239 |
| 5 | 2,048 | 269 | 0.131348 | 0.000000 | 0.000000 | 0.274210 |
| 6 | 3,056 | 1,089 | 0.356348 | 0.000000 | 0.000000 | 0.007148 |
| 7 | 2,287 | 371 | 0.162221 | 0.000000 | 0.000000 | 0.280635 |
| 8 | 1,524 | 425 | 0.266404 | 0.000000 | 0.000000 | 0.434691 |
| 9 | 2,775 | 642 | 0.231351 | 0.000000 | 0.000000 | 0.248716 |
| 10 | 1,752 | 682 | 0.389269 | 0.000000 | 0.000000 | 0.000000 |
| 11 | 1,171 | 377 | 0.321947 | 0.000000 | 0.000000 | 0.000000 |
| 12 | 2,980 | 825 | 0.276846 | 0.000000 | 0.000000 | 0.433640 |
| 13 | 2,558 | 646 | 0.252541 | 0.000000 | 0.000000 | 0.215139 |
| 14 | 657 | 119 | 0.181126 | 0.000000 | 0.000000 | 0.292105 |
| 15 | 1,048 | 197 | 0.187977 | 0.000000 | 0.000000 | 0.316466 |

All four exact centroid diagnoses occur on question 4. No broad question-transfer conclusion follows from this isolated gain. Screening recall is zero for questions 2, 10 and 11, while several others are almost always flagged. A global threshold selected on different questions transfers poorly.

## Name-ranking ablation with oracle positive annotations

This ablation supplies the true positive subset and removes the answer-correctness prefix requirement. It isolates name discrimination and **does not measure end-to-end diagnostic performance**. Candidate/temperature/C choices remain those of the fixed inner diagnostic procedure; oracle outer results do not drive selection.

| Name ranker | Top-1 accuracy | Recall@3 | MAP@3 | Name coverage |
|---|---:|---:|---:|---:|
| Hierarchical TF-IDF | 0.000000 | 0.002290 | 0.000937 | 0.225981 |
| Semantic training centroids | 0.007286 | 0.013324 | 0.009802 | 0.225981 |
| Semantic partial descriptions | 0.002186 | 0.005829 | 0.003730 | 0.423754 |

The strongest oracle name ranker, centroids, still gets only 70/9,607 names correct (all Irrelevant). Removing category routing exposes some signal but does not fix missing coverage or weak semantic transfer. Public-description ranking gets 21 names correct: 11 Adding_across, six Duplication and four WNB. This partial catalogue performs worse overall than centroids, despite more coverage. These are exploratory ablations, not a selected product model.

## Error analysis and teacher implications

No misconception is predicted reliably. The only nonzero end-to-end misconception class is centroid `False_Misconception:Irrelevant`: precision **0.057971**, recall **0.009975**, F1 **0.017021**, support 401, four true positives. Every other observed positive composite class has zero F1. Full per-class precision/recall/F1, support and confusion matrices (rows=true, columns=predicted) are published in [aggregate metrics](metrics/misconception-aware-cv.json); oracle name metrics are separately marked.

Safe examples are aggregate label-to-label counts, never student quotations:

- Centroids: `False_Misconception:Incomplete` → `False_Neither:NA`, 1,142 errors. Incomplete is often seen in training, so this is not only a missing-label problem.
- Centroids: `False_Misconception:Subtraction` → `True_Neither:NA`, 576 errors. The held-out target is unavailable to training-centroid candidates.
- Composite TF-IDF: `False_Misconception:Additive` → `False_Misconception:Not_variable`, 642 errors. Assigning a specific but unrelated known code can mislead remediation.
- Hierarchy: `True_Correct:NA` → `False_Neither:NA`, 6,810 errors. Category transfer itself fails; name improvements alone cannot rescue the joint pipeline.

For centroids, 7,539 unseen-positive rows have zero top-1 and top-3 recall. The 601 positive rows with 1–49 training examples have top-1 accuracy 0.006656, recall@3 0.088186 and MAP@3 0.044648. The 1,467 positive rows with at least 50 training examples have top-1 accuracy zero, recall@3 0.003408 and MAP@3 0.001250. Rarity is therefore **not monotonically responsible for failure** in this experiment: all four successes occur in the rare bucket. These bins mix question, label and coverage effects and cannot identify a causal sample-size effect. Abundant generic categories inflate weighted/overall scores, while frequent Incomplete cases still fail.

The soft hierarchy and semantic joint rankers spread positive-category probability over specific names while non-misconception NA categories retain their whole category mass. The oracle ablation quantifies part of this ranking penalty. Binary separability, exact-name discrimination and answer-prefix classification should remain separate research questions. Neither balanced weighting nor a frozen generic English encoder supplies missing mathematical rubrics.

**Recommendation for the first teacher-facing prototype:** an expert-reviewed research workbench showing the authorized solution context and rubric, with optional clearly experimental candidate suggestions. Require teacher confirmation, preserve manual review of every response, and avoid using the binary gate to exclude cases. Do not automate grading, remediation, or reassuring Correct decisions. Build only after licensing and expert review of the next validation dataset; this milestone implements no frontend.

## Reproduction and verification

Install the pinned optional embedding runtime and place the authorized labeled CSV at `data/raw/train.csv`. From the repository root, a fresh complete experiment is:

```powershell
teacherlens compare --config configs/misconception-aware.json --output-dir outputs/milestone3-new
```

Existing directories are protected. The canonical completed runs are `outputs/misconception-aware-cv/` and `outputs/misconception-aware-repeat/`. Each stores `report.json` (full aggregates), `experiment.json` (private retained-row/split manifests, hashes and fit fingerprints), `private_oof.npz` (private predictions/rankings/scores), and `private_errors.json` (private row references without text). The public snapshot is `docs/metrics/misconception-aware-cv.json`. Full reproduction/export commands are in the README.

Both full fitting/selection runs matched exactly in this pinned Python 3.11.9 environment: fold metrics, selected settings, split manifests, fit fingerprints, probabilities, rankings and error references. They reused the same full frozen embedding cache. Independently re-encoding the first 32 original-batch rows reproduced those vectors exactly; all cached vectors had unit norm within 1e-6 and pinned asset checksums passed. This is not a second full encoding or cross-hardware reproducibility claim.

**Reporting correction:** audit found the per-question loop overwrote the global positive mask, corrupting pooled binary and oracle-name summaries while preserving fold metrics, fits and predictions. The code now uses a separate local mask. `scripts/repair_comparison_summaries.py` independently recomputed those summaries for each completed run from unchanged saved OOF arrays, checked dataset/retained-row alignment and verified pooled binary counts against summed fold confusion matrices. Corrected reports match exactly. Original computational-source hashes are retained; the public `reporting_correction` records the original report hash, repair-script hash and corrected comparison-source hash. No models or settings were changed after examining outer results. Publication-source hashes are recorded separately from original run-source hashes. A second audit fix counts tokenizer truncation before padding, preventing short members of a long batch from being reported as truncated; actual MAP truncation remains zero, and inference vectors are unchanged (the independent sample check passed again). Fresh runs use the corrected code directly; do not run the migration on them. Regression tests assert full-data positive counts, summed confusion matrices, oracle support, and faithful repair without prediction changes.

All **56 tests passed** after the correction, including leakage, unseen-label/tie/rank semantics, one-class/no-positive fits, cache integrity, padding-aware truncation auditing, safe export and Git artifact policy. Compilation, dependency and whitespace checks passed. CI uses synthetic fixtures and vectors, without restricted data or model downloads; it verifies software behavior, not the reported real-data accuracy.

For the next milestone, obtain a complete expert-reviewed code-description catalogue and more authorized question families per code. Freeze new partitions before results, then compare explanation/context and character-ngram ablations, complete catalogue retrieval, and bounded transformer experiments. Evaluate calibration/abstention and teacher review cost against always-positive screening. Collect native Kazakh/Russian annotations before language claims; keep translations and paraphrases grouped with their source family.

## Further limitations

Only 15 question proxies are available, without original-template or student IDs. Question-level variability is substantial, and responses are not independent samples of classroom generalization. No row-level confidence interval is claimed. Across questions, 76 normalized explanation-only strings repeat on 250 retained rows (0.70%); 50 such groups have conflicting labels. Generic repeated wording is not evidence of a shared student or family and is retained; body-only collisions are a residual limitation for semantic retrieval. No affected text is published.

The authors' broader benchmark includes original and paraphrased synthetic explanations, but the supplied CSV has no provenance flag; actual local authenticity proportions and authentic-only performance cannot be measured. OCR text, sparse educational coverage, annotation conflicts, missing diagrams, incomplete scoring rubrics and uncalibrated outputs limit interpretation. [Dataset authors](https://aclanthology.org/2025.aimecon-wip.3/).

MAP's restricted non-commercial terms and sharing controls remain in effect despite MIT data-tab metadata. Public weights' Apache licence does not grant commercial rights in MAP-derived caches/models. Only aggregate statistics and permitted research code are published. Neither Kazakh nor Russian has been evaluated.
