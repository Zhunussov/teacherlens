"""Conservative Unicode preprocessing shared by training and inference."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    # NFC preserves compatibility distinctions; retain math symbols and digits.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().lower()


def build_text(row: dict[str, str]) -> str:
    return "\n".join(f"{name}: {normalize_text(row[name])}" for name in
                     ("QuestionText", "MC_Answer", "StudentExplanation"))
