# MAP dataset research

Reviewed 2026-10-09. The project owner subsequently supplied a local MAP archive for this individual non-commercial experiment. The actual training CSV is now audited and evaluated; public documentation and observed characteristics are distinguished below.

## Documented task and schema

Eedi diagnostic multiple-choice responses include written justifications. Question content was extracted from images through human-reviewed OCR. Train/test fields include `QuestionId`, `QuestionText`, `MC_Answer`, and `StudentExplanation`; training adds `Category` and `Misconception`. Category pairs answer correctness (`True`/`False`) with explanation type (`Correct`, `Misconception`, `Neither`). Non-misconception rows use literal `NA`. [Kaggle data description](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data).

The submission identifier is `row_id`. Targets concatenate category and misconception with a colon. Evaluation uses MAP@3, allows three ranked candidates, and has one correct target per row. [Official evaluation and submission format](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/overview).

The actual UTF-8 CSV has `row_id`, `QuestionId`, `QuestionText`, `MC_Answer`, `StudentExplanation`, `Category`, `Misconception`: 36,696 labeled rows, 15 questions and 65 composite classes. All six category combinations appear, including correct selected answers with misconceptions and incorrect selected answers with correct explanations. No required field is empty and all row IDs are unique. IDs are integer-compatible but stored as strings; literal `NA` must not undergo automatic missing-value conversion. No language-identification measurement was performed, and multilingual representativeness is not claimed.

The loader rejects malformed rows, empty required cells and inconsistent labels/question text without dropping data. Exact duplicate annotations (all fields except row ID) number 736, leaving 35,960 retained rows. There are 82 normalized model-input groups with conflicting labels, involving 173 raw rows; retain them to avoid silently inventing annotation corrections. The archive's `test.csv` has only three unlabeled rows and is not an evaluation set. Full aggregate distributions and measured metrics are in [results](results.md) and [aggregate JSON](metrics/real-evaluation.json).

## License and access

The public data tab lists **MIT**, but the official rules distinguish **MIT for the winner's submission** (competition-specific terms section 6) from **CC BY-NC 4.0 for data access/use** (section 7). Competition-specific rules section 4 permits non-commercial research/education and imposes additional security and sharing restrictions, including no providing competition data to nonparticipants. The metadata does not override those explicit restrictions. TeacherLens treats MAP data as restricted: never commit, publish or redistribute it, and obtain separate permission before commercial use. [Official rules](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/rules), [data-tab metadata](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data), [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

The earlier text-only rules lookup returned no readable content; browser inspection resolved this limitation. At foundation time the inspected session lacked authenticated access. For this experiment, processing is based on the owner's supplied archive and explicit instruction to use authorized data for individual research. The owner must have appropriate access/eligibility and accepted applicable terms; archive possession alone is not independent proof of these matters, and no account audit is claimed. No Kaggle download, account creation, rule acceptance or restriction bypass occurred. The attached Downloads archive was copied into ignored `data/raw/` because the requested repository-local copy was absent. Only the three expected CSV basenames were extracted, without applying archive-provided instructions or extracting arbitrary paths.

Processing remains local and non-commercial. Raw/extracted data, fitted models, row manifests and error references remain under ignored folders. Only reviewed aggregate counts, labels, metrics and narrative findings are published. No student responses or question text are redistributed. No future commercial-use permission or classroom deployment permission is implied.

## Appropriately licensed alternative

[Eedi Misconceptions Graph v1.0](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph/blob/main/README.md) is an official CC BY 4.0 release containing misconception-to-curriculum-construct mappings and a construct catalogue. Its card permits reuse with attribution and requires identifying adaptations. It explicitly excludes diagnostic questions, distractors, images and student-level response data. It is suitable for taxonomy/retrieval research, but cannot replace labeled student explanations for this classifier's evaluation. Do not manufacture MAP rows or pretend taxonomy edges are student examples. No graph files were downloaded or bundled. If used later, pin a release, preserve attribution and implement a separate graph adapter rather than changing MAP label semantics.

## Research limitations and proposed checks

These are engineering risks to investigate, not measured claims about the dataset:

- Text may omit information contained in diagrams; inspect authorized samples before treating OCR text as a complete problem representation.
- Class imbalance and question-specific labels may leave rare or unseen targets in held-out questions. Audit label counts and question coverage before drawing conclusions.
- Question-family and student metadata may be insufficient to remove all related-example leakage. Exact question grouping is a minimum safeguard.
- Explanations can be ambiguous; an annotation is not proof of a student's stable misconception. Measure disagreement with expert review when feasible.
- Coverage of a particular educational platform does not establish performance on other classrooms, curricula, handwriting transcription or languages. Evaluate these domains independently.
- Sparse lexical models can exploit phrasing without mathematical reasoning. Test negation, equivalent math notation and paraphrases in future robustness work.

The primary sources describe candidate misconceptions, not a validated autonomous diagnosis system. TeacherLens currently provides research predictions; any future teacher workflow needs human review and domain evaluation. [Competition overview](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/overview).
