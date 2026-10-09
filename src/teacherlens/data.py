"""CSV loading without implicit NA conversion or silent row dropping."""

import csv
from pathlib import Path

FEATURES = ("QuestionText", "MC_Answer", "StudentExplanation")
CATEGORIES = {f"{correct}_{reason}" for correct in ("True", "False")
              for reason in ("Correct", "Misconception", "Neither")}


def load_dataset(path: str | Path, labeled: bool = True) -> list[dict[str, str]]:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Dataset not found: {path}. Obtain authorized Kaggle CSVs locally; no data is bundled.")
    required = {"row_id", "QuestionId", *FEATURES}
    if labeled:
        required |= {"Category", "Misconception"}
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            header = reader.fieldnames or []
            if len(header) != len(set(header)):
                raise ValueError("CSV has duplicate column names")
            missing = required - set(header)
            if missing:
                raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
            rows, ids, questions = [], set(), {}
            for line, raw in enumerate(reader, 2):
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError(f"Row {line}: malformed CSV field count")
                row = {key: value.strip() for key, value in raw.items()}
                for key in required:
                    if not row[key]:
                        raise ValueError(f"Row {line}: {key} is empty")
                if row["row_id"] in ids:
                    raise ValueError(f"Row {line}: duplicate row_id")
                ids.add(row["row_id"])
                qid, question = row["QuestionId"], row["QuestionText"]
                if qid in questions and questions[qid] != question:
                    raise ValueError(f"Row {line}: inconsistent QuestionText for a QuestionId")
                questions[qid] = question
                if labeled:
                    category, misconception = row["Category"], row["Misconception"]
                    if category not in CATEGORIES:
                        raise ValueError(f"Row {line}: unsupported Category")
                    has_misconception = category.endswith("_Misconception")
                    if has_misconception == (misconception == "NA"):
                        raise ValueError(f"Row {line}: Category/Misconception inconsistency (non-misconceptions require literal NA)")
                    if ":" in misconception:
                        raise ValueError(f"Row {line}: Misconception contains reserved colon")
                    row["label"] = f"{category}:{misconception}"
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Cannot read CSV {path}: {exc}") from exc
    if not rows:
        raise ValueError("Dataset has no rows")
    return rows
