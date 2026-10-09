"""Question-family holdout, with explicit reporting of unseen labels."""

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit

from .text import normalize_text


def question_groups(rows):
    # Merge aliases of identical normalized question text, transitively with IDs.
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        for key in (("id", row["QuestionId"]), ("text", normalize_text(row["QuestionText"]))):
            if key in seen:
                parent[root(i)] = root(seen[key])
            else:
                seen[key] = i
    return np.array([root(i) for i in range(len(rows))])


def split_dataset(rows, config):
    groups = question_groups(rows)
    if len(set(groups)) < 2:
        raise ValueError("Question holdout requires at least two distinct question groups")
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=config.test_size,
                                        random_state=config.seed).split(rows, groups=groups))
    if len({rows[i]["label"] for i in train}) < 2:
        raise ValueError("Training holdout has fewer than two labels; add question groups or explicitly revise the split configuration")
    return train, test, groups


def evaluate(y_true, y_pred, probabilities, classes):
    labels = sorted(set(y_true) | set(classes))
    top = np.argsort(-probabilities, axis=1, kind="stable")[:, :3]
    reciprocal_ranks = []
    for truth, ranking in zip(y_true, top):
        reciprocal_ranks.append(next((1 / (rank + 1) for rank, index in enumerate(ranking)
                                      if classes[index] == truth), 0.0))
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_f1_test_supported": float(f1_score(y_true, y_pred, labels=sorted(set(y_true)), average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "map_at_3": float(np.mean(reciprocal_ranks)),
        "labels": labels,
        "per_class": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "unseen_test_labels": sorted(set(y_true) - set(classes)),
        "unseen_test_rows": sum(label not in set(classes) for label in y_true),
    }
