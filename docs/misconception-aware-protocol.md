# Milestone 3 comparison protocol

Fixed before inspecting these outer-fold model results, 2026-10-11. This is development research informed by the previously inspected holdout, not a new untouched final test. The historical test rows re-enter cross-validation. Generalization requires a future external question set.

## Data and tasks

Use the authorized local MAP training CSV, validated and exact-deduplicated by the existing loader/audit. No competition test labels or inferred student provenance. Keep conflicting annotations. Group connected QuestionIds and identical normalized question text. These are 15 question proxies, not verified template families or independent student samples.

Binary target: `Category` ends with `_Misconception`. Validate equivalence with `Misconception != NA`; a correct chosen answer can have an error-bearing explanation. This is detection of the dataset annotation, including instructionally relevant procedural errors, rather than a clinical claim about enduring knowledge.

Hierarchical target: six categories, then a shared misconception-name head on positive training rows. Multiply category and conditional-name probabilities; use `NA` exclusively for non-misconception categories. Share names across True/False prefixes; a composite unseen in training may remain predictible if its name and broad category were learned. Keep case-distinct codes unchanged.

## Comparisons and frozen design

- Majority: only the most common composite label; one prediction.
- Class prior: training frequencies, sorted descending; deterministic ties by label.
- Existing TF-IDF composite classifier, with its feature construction preserved.
- Binary TF-IDF screening head, with a separately selected threshold.
- Hierarchical TF-IDF category/name heads.
- Frozen MiniLM semantic centroids of positive training explanations, gated by the category head.
- Semantic descriptions: six explicit public rubric paraphrases override those centroids; all other names use training centroids. The six mappings are chosen for clarity in the authors' Table 1, not evaluation performance. No Eedi Graph-to-MAP mapping is assumed.
- Always-negative and always-positive binary references.

The frozen encoder is pinned to `sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`: local CPU ONNX, attention-mask mean pooling, L2 normalization, 256 wordpieces. Encode only the normalized explanation; exclusion of question text is an explicit input difference from TF-IDF, not an isolated architecture ablation. The whole-dataset embedding cache is safe because the pretrained transform operates independently on each row, without adaptation, label access, dataset normalization or fitting. All centroids/index labels are fit inside their training partition. Public-description vectors are fixed external knowledge.

## Splits, selection and metrics

Five outer `GroupKFold` splits balance row counts without labels. Every question and every retained row appears in one outer test partition. In each development partition, one `GroupShuffleSplit` holds out 25% of its groups with seed `42 + fold_index`. Every candidate fits only the remaining inner training rows, including vocabulary/IDF. Refit selected candidates on that outer development partition before evaluation. No outer metric enters selection; no architecture is declared the winner in advance. One inner holdout is a computational tradeoff, and its question choice can affect tuning.

Fixed C grid: 0.5, 1, 2. Binary threshold grid: 0.2, 0.35, 0.5, 0.65, 0.8. Semantic temperature grid: 0.05, 0.1, 0.2. Max features 50,000; unigram/bigram TF-IDF; balanced logistic heads; max iterations 1,000; one numerical thread. Fail on nonconvergence.

Diagnostic selection: misconception-only inner MAP@3, then smaller C, then smaller temperature. Binary selection: positive-class inner F1, then smaller C, threshold nearest 0.5, then smaller threshold. Reference models have no selection. Comparisons of screening and exact diagnosis have separate objectives; do not assign invented composite diagnoses to the binary model.

Report pooled out-of-fold metrics, unweighted outer-fold means and sample standard deviations. The latter describe five three-question partitions; they are not confidence intervals. Report all 15 anonymous question summaries, class coverage, unseen labels, frequency bins, full per-class precision/recall/F1 and confusion matrices. Separate misconception and other responses. MAP@3 is reciprocal rank up to three for a single true composite label; recall@3 counts hits without reciprocal weighting. Unsupported targets remain scored as misses. Preserve actual candidate order for ties, rather than inserting zero-probability global candidates.

Primary macro F1 averages the 65 observed composite codes (reporting taxonomy only). Also record a formal Cartesian taxonomy (35 names × two prefixes + four NA codes), since the hierarchy can predict valid combinations absent from the CSV. Zero-support classes contribute zero to that secondary macro. Global label names are never supplied as trained targets or centroid candidates. Row-weighted candidate coverage and class-type coverage are different measures, both recorded.

Use private row references for error review; publish only reviewed aggregate metrics. Repeated runs must match reports, folds, fit fingerprints and complete out-of-fold arrays. Frozen embedding caches and models, training data and manifests remain ignored. No result supports deployment, language transfer, intervention efficacy, student-level generalization or commercial use of restricted MAP artifacts.
