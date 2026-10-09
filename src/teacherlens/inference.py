"""Batch inference interface reusable by a future API adapter."""

import joblib

from .text import build_text


def load_model(path):
    # joblib uses pickle: callers must supply a trusted local artifact.
    return joblib.load(path)


def predict_rows(artifact, rows):
    predictions = artifact["pipeline"].predict([build_text(row) for row in rows])
    return [{"row_id": row["row_id"], "Category:Misconception": str(label),
             "data_kind": artifact["data_kind"]} for row, label in zip(rows, predictions)]
