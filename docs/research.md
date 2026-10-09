# MAP dataset research

Reviewed 2026-10-09. No CSV has been downloaded or inspected; the schema below comes from public Kaggle documentation, not a local dataset audit.

## Documented task and schema

Eedi diagnostic multiple-choice responses include written justifications. Question content was extracted from images through human-reviewed OCR. Train/test fields include `QuestionId`, `QuestionText`, `MC_Answer`, and `StudentExplanation`; training adds `Category` and `Misconception`. Category pairs answer correctness (`True`/`False`) with explanation type (`Correct`, `Misconception`, `Neither`). Non-misconception rows use literal `NA`. [Kaggle data description](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data).

The submission identifier is `row_id`. Targets concatenate category and misconception with a colon. Evaluation uses MAP@3, allows three ranked candidates, and has one correct target per row. [Official evaluation and submission format](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/overview).

The loader expects those documented feature/annotation fields plus `row_id`, preserving all values as strings. CSVs are UTF-8 (optional BOM). IDs must be nonempty and row IDs unique; question IDs must have consistent text. Empty required fields, inconsistent annotation pairs and malformed rows raise errors. Extra columns are allowed. Actual counts, unique questions, label frequencies, null rates and language distribution remain unmeasured.

## License and access

The public data tab lists **MIT**, but the official rules distinguish **MIT for the winner's submission** (competition-specific terms section 6) from **CC BY-NC 4.0 for data access/use** (section 7). Competition-specific rules section 4 permits non-commercial research/education and imposes additional security and sharing restrictions, including no providing competition data to nonparticipants. The metadata does not override those explicit restrictions. TeacherLens treats MAP data as restricted: never commit, publish or redistribute it, and obtain separate permission before commercial use. [Official rules](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/rules), [data-tab metadata](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data), [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

The earlier text-only rules lookup returned no readable content; browser inspection on 2026-10-09 resolved this limitation. The browser was signed out, and the data explorer required sign-in and acceptance of competition rules. No Kaggle credential environment variables or conventional local credential/token files were present, and no authorized labeled CSV was found in this checkout. No download was attempted, no terms were accepted, and no account/eligibility restrictions were bypassed. This establishes missing access in the inspected environment, not that every account is ineligible. An eligible account holder must obtain access through Kaggle and review the applicable terms personally; if unavailable, request sponsor permission. Raw data remains outside Git.

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
