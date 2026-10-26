"""Nested question-group comparisons, including diagnostic rather than accuracy objectives."""

from collections import Counter
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from threadpoolctl import threadpool_limits

from .config import ExperimentConfig
from .data import load_dataset
from .descriptions import DESCRIPTIONS, SOURCE
from .embeddings import cached_embeddings
from .evaluation import question_groups
from .research import audit_and_deduplicate
from .text import build_text, normalize_text


@dataclass(frozen=True)
class ComparisonConfig(ExperimentConfig):
    outer_folds: int = 5
    inner_validation_fraction: float = .25
    C_candidates: tuple[float, ...] = (.5, 1., 2.)
    screening_thresholds: tuple[float, ...] = (.2, .35, .5, .65, .8)
    temperatures: tuple[float, ...] = (.05, .1, .2)
    model_dir: str = "data/models/minilm"
    embedding_cache: str = "outputs/embedding-cache.npz"

    def __post_init__(self):
        super().__post_init__()
        if type(self.outer_folds) is not int or self.outer_folds < 2:
            raise ValueError("outer_folds must be an integer >= 2")
        if self.seed + self.outer_folds - 1 > 2**32 - 1:
            raise ValueError('seed plus outer fold offsets must fit an unsigned 32-bit integer')
        if type(self.inner_validation_fraction) not in (int, float) or not 0 < self.inner_validation_fraction < 1:
            raise ValueError("inner_validation_fraction must lie between zero and one")
        for name in ("C_candidates", "screening_thresholds", "temperatures"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or not values or len(set(values)) != len(values):
                raise ValueError(f"{name} requires unique finite positive candidates")
            if any(type(x) not in (int, float) or not 0 < x < float("inf") for x in values):
                raise ValueError(f"{name} requires unique finite positive candidates")
        if any(x >= 1 for x in self.screening_thresholds):
            raise ValueError("screening_thresholds must be less than one")
        if any(not isinstance(x, str) or not x.strip() for x in (self.model_dir, self.embedding_cache)):
            raise ValueError("model_dir and embedding_cache must be nonempty paths")


def load_comparison_config(path):
    path = Path(path).resolve()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        config = ComparisonConfig(**values)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid comparison config: {exc}") from exc
    values = config.to_dict()
    for key in ("dataset_path", "output_dir", "model_dir", "embedding_cache"):
        values[key] = str((path.parent / values[key]).resolve())
    return ComparisonConfig(**values)


def is_misconception(label):
    return label.split(":", 1)[0].endswith("_Misconception")


def nested_splits(rows, config):
    groups = question_groups(rows)
    if len(set(groups)) < max(config.outer_folds, 4):
        raise ValueError("Nested evaluation requires enough question groups for outer and inner partitions")
    folds = []
    for fold, (development, test) in enumerate(GroupKFold(config.outer_folds).split(rows, groups=groups)):
        train_local, validation_local = next(GroupShuffleSplit(
            n_splits=1, test_size=config.inner_validation_fraction,
            random_state=config.seed + fold).split(development, groups=groups[development]))
        train, validation = development[train_local], development[validation_local]
        for left, right in ((train, validation), (train, test), (validation, test)):
            if set(groups[left]) & set(groups[right]):
                raise ValueError("Question-group leakage detected")
        folds.append({"train": train, "validation": validation, "development": development, "test": test})
    if sorted(np.concatenate([x["test"] for x in folds]).tolist()) != list(range(len(rows))):
        raise ValueError("Outer test partitions must cover each row exactly once")
    return folds, groups


class ConstantHead:
    """Explicit fallback for a genuinely single-class training partition."""
    def __init__(self, label):
        self.classes_ = np.array([label])

    def predict_proba(self, features):
        return np.ones((features.shape[0], 1))


def fit_head(features, targets, C, config):
    if len(set(targets)) == 1:
        return ConstantHead(targets[0])
    head = LogisticRegression(C=C, max_iter=config.max_iter, class_weight=config.class_weight,
                              random_state=config.seed, solver="lbfgs")
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            return head.fit(features, targets)
        except ConvergenceWarning as exc:
            raise ValueError("Comparison fit did not converge; increase max_iter") from exc


def fit_heads(rows, indices, C, config):
    texts = [build_text(rows[i]) for i in indices]
    vectorizer = TfidfVectorizer(lowercase=False, ngram_range=(1, config.ngram_max),
                                max_features=config.max_features, token_pattern=r"(?u)\w+|[^\w\s]",
                                sublinear_tf=True)
    features = vectorizer.fit_transform(texts)
    labels = [rows[i]["label"] for i in indices]
    positive = np.array([is_misconception(x) for x in labels])
    heads = {"composite": fit_head(features, labels, C, config),
             "binary": fit_head(features, [str(int(x)) for x in positive], C, config),
             "category": fit_head(features, [rows[i]["Category"] for i in indices], C, config)}
    heads["specific"] = (fit_head(features[positive], [rows[i]["Misconception"] for i in np.array(indices)[positive]], C, config)
                         if positive.any() else None)
    return vectorizer, heads


def hierarchy_probabilities(category_probabilities, categories, specific_probabilities, names):
    """P(category|x) P(name|misconception,x), sharing names across True/False prefixes."""
    columns, labels = [], []
    for j, category in enumerate(categories):
        if category.endswith("_Misconception"):
            if not len(names):
                continue
            for k, name in enumerate(names):
                labels.append(f"{category}:{name}")
                columns.append(category_probabilities[:, j] * specific_probabilities[:, k])
        else:
            labels.append(f"{category}:NA")
            columns.append(category_probabilities[:, j])
    if not labels:
        raise ValueError("No supported hierarchical targets in training fold")
    order = np.argsort(labels)
    probabilities = np.stack(columns, axis=1)[:, order]
    probabilities /= np.maximum(probabilities.sum(axis=1, keepdims=True), 1e-12)
    return probabilities, np.array(labels)[order]


def semantic_prototypes(rows, indices, embeddings):
    names = sorted({rows[i]["Misconception"] for i in indices if is_misconception(rows[i]["label"])})
    if not names:
        return np.empty((0, embeddings.shape[1])), np.array(names)
    prototypes = np.stack([embeddings[[i for i in indices if rows[i]["Misconception"] == name]].mean(axis=0)
                           for name in names])
    prototypes /= np.maximum(np.linalg.norm(prototypes, axis=1, keepdims=True), 1e-12)
    return prototypes, np.array(names)


def retrieval_probabilities(embeddings, prototypes, temperature):
    if len(prototypes) == 0:
        return np.empty((len(embeddings), 0))
    scores = embeddings @ prototypes.T / temperature
    scores -= scores.max(axis=1, keepdims=True)
    probabilities = np.exp(scores)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def description_prototypes(prototypes, description_vectors):
    """External descriptions override six names; others retain training-only centroids."""
    vectors = {name: vector for name, vector in zip(prototypes[1], prototypes[0])}
    vectors.update({name: description_vectors[i] for i, name in enumerate(sorted(DESCRIPTIONS))})
    names = sorted(vectors)
    values = np.stack([vectors[name] for name in names])
    values /= np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)
    return values, np.array(names)


def binary_metrics(truth, scores, threshold=.5):
    truth = np.asarray(truth, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    prediction = scores >= threshold
    negatives = ~truth
    return {"rows": len(truth), "positive_rows": int(truth.sum()), "threshold": float(threshold),
            "accuracy": float(np.mean(truth == prediction)),
            "precision": float(precision_score(truth, prediction, zero_division=0)),
            "recall": float(recall_score(truth, prediction, zero_division=0)),
            "f1": float(f1_score(truth, prediction, zero_division=0)),
            "average_precision": float(average_precision_score(truth, scores)) if truth.any() else None,
            "false_positive_rate": float(prediction[negatives].mean()) if negatives.any() else None,
            "confusion_matrix": confusion_matrix(truth, prediction, labels=[False, True]).tolist()}


def selected_screening_metrics(truth, scores, decisions):
    """AP uses continuous scores; confusion/F1 use independently selected fold thresholds."""
    metrics = binary_metrics(truth, scores)
    decision_metrics = binary_metrics(truth, np.asarray(decisions, dtype=float))
    metrics.update({key: value for key, value in decision_metrics.items() if key not in ('average_precision', 'threshold')})
    metrics['threshold'] = 'selected independently inside each outer training fold'
    return metrics


def diagnostic_metrics(truth, probabilities, classes, training_labels, catalogue):
    """Single-target MAP@3 (reciprocal rank) and recall@3 (hit) are distinct."""
    truth, classes = np.asarray(truth), np.asarray(classes)
    probabilities = np.asarray(probabilities)
    if (probabilities.shape != (len(truth), len(classes)) or len(set(classes)) != len(classes)
            or not len(classes) or not np.isfinite(probabilities).all() or (probabilities < 0).any()
            or not np.allclose(probabilities.sum(axis=1), 1)):
        raise ValueError("Invalid candidate probabilities/classes")
    top = classes[np.argsort(-probabilities, axis=1, kind="stable")[:, :3]]
    prediction = top[:, 0]
    hits = top == truth[:, None]
    ranks = (hits * (1 / np.arange(1, top.shape[1] + 1))).sum(axis=1)
    coverage = np.isin(truth, classes)
    seen = np.isin(truth, list(set(training_labels)))
    positive = np.array([is_misconception(x) for x in truth])
    result = {"rows": len(truth), "accuracy": float(np.mean(prediction == truth)),
              "macro_f1": float(f1_score(truth, prediction, labels=catalogue, average="macro", zero_division=0)),
              "macro_f1_supported": float(f1_score(truth, prediction, labels=sorted(set(truth)), average="macro", zero_division=0)),
              "weighted_f1": float(f1_score(truth, prediction, average="weighted", zero_division=0)),
              "map_at_3": float(ranks.mean()), "top_3_recall": float(hits.any(axis=1).mean()),
              "candidate_label_coverage": float(coverage.mean()), "unseen_label_row_rate": float((~seen).mean()),
              'test_label_type_coverage_in_training': len(set(truth) & set(training_labels)) / len(set(truth)),
              'test_label_type_coverage_in_candidates': len(set(truth) & set(classes)) / len(set(truth)),
              "unseen_labels": sorted(set(truth) - set(training_labels)),
              "prediction_counts": dict(sorted(Counter(prediction).items())),
              "per_class": classification_report(truth, prediction, labels=catalogue, output_dict=True, zero_division=0),
              "labels": list(catalogue), "confusion_matrix": confusion_matrix(truth, prediction, labels=catalogue).tolist()}
    for name, mask in (("misconception", positive), ("other", ~positive), ("seen", seen), ("unseen", ~seen)):
        result[name] = {"rows": int(mask.sum()), "top_1_accuracy": float((prediction[mask] == truth[mask]).mean()) if mask.any() else None,
                        "top_3_recall": float(hits[mask].any(axis=1).mean()) if mask.any() else None,
                        "map_at_3": float(ranks[mask].mean()) if mask.any() else None,
                        "candidate_label_coverage": float(coverage[mask].mean()) if mask.any() else None}
    probability_positive = probabilities[:, [is_misconception(x) for x in classes]].sum(axis=1)
    result["screening_at_default_threshold"] = binary_metrics(positive, probability_positive)
    return result, prediction, probability_positive


def _positive_scores(head, probabilities):
    return probabilities[:, list(head.classes_).index("1")] if "1" in head.classes_ else np.zeros(len(probabilities))


def score_heads(rows, indices, fitted, prototypes, embeddings, temperature, description_vectors):
    vectorizer, heads = fitted
    features = vectorizer.transform([build_text(rows[i]) for i in indices])
    category = heads["category"].predict_proba(features)
    specific = heads["specific"]
    name_prob = specific.predict_proba(features) if specific is not None else np.empty((len(indices), 0))
    hierarchy = hierarchy_probabilities(category, heads["category"].classes_, name_prob,
                                        specific.classes_ if specific is not None else [])
    semantic = hierarchy_probabilities(category, heads["category"].classes_,
                                       retrieval_probabilities(embeddings[indices], prototypes[0], temperature), prototypes[1])
    described = description_prototypes(prototypes, description_vectors)
    semantic_descriptions = hierarchy_probabilities(category, heads['category'].classes_,
                             retrieval_probabilities(embeddings[indices], described[0], temperature), described[1])
    return {"tfidf_composite": (heads["composite"].predict_proba(features), heads["composite"].classes_),
            "hierarchical_tfidf": hierarchy, "semantic_prototypes": semantic, 'semantic_descriptions': semantic_descriptions,
            'name_hierarchical_tfidf': (name_prob, specific.classes_ if specific is not None else np.array([])),
            'name_semantic_prototypes': (retrieval_probabilities(embeddings[indices], prototypes[0], temperature), prototypes[1]),
            'name_semantic_descriptions': (retrieval_probabilities(embeddings[indices], described[0], temperature), described[1]),
            "binary_tfidf": _positive_scores(heads["binary"], heads["binary"].predict_proba(features))}


def select_diagnostic(candidates):
    # Primary objective specifically excludes generic/non-misconception accuracy.
    return max(candidates, key=lambda x: (x["score"], -x["C"], -x.get("temperature", .1)))


def fingerprint_fit(fitted, prototypes):
    vectorizer, heads = fitted
    digest = hashlib.sha256(json.dumps({key: int(value) for key, value in vectorizer.vocabulary_.items()}, sort_keys=True).encode())
    digest.update(vectorizer.idf_.tobytes())
    for name, head in sorted(heads.items()):
        digest.update(name.encode())
        if head is not None:
            digest.update(json.dumps(head.classes_.tolist()).encode())
            for attribute in ("coef_", "intercept_", "n_iter_"):
                if hasattr(head, attribute):
                    digest.update(getattr(head, attribute).tobytes())
    digest.update(prototypes[0].tobytes())
    digest.update(json.dumps(prototypes[1].tolist()).encode())
    return digest.hexdigest()


def run_comparison(config, embeddings=None, embedding_metadata=None, description_vectors=None):
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(Path(__file__).parent.glob('*.py'))}
    output = Path(config.output_dir)
    if output.exists():
        raise ValueError("Output directory already exists; use a new directory")
    rows, audit = audit_and_deduplicate(load_dataset(config.dataset_path))
    folds, groups = nested_splits(rows, config)
    truth = np.array([row["label"] for row in rows])
    positive_mask = np.array([is_misconception(x) for x in truth])
    if not positive_mask.any():
        raise ValueError('No misconception annotations; diagnostic comparison is undefined')
    observed_labels = sorted(set(truth))
    # Full formal taxonomy is reporting only, never supplied as fit targets/candidates.
    names = {row['Misconception'] for row in rows if is_misconception(row['label'])} | set(DESCRIPTIONS)
    catalogue = sorted(set(truth) | {f'{prefix}_Misconception:{name}' for prefix in ('True', 'False') for name in names})
    if embeddings is None:
        embeddings, embedding_metadata = cached_embeddings([normalize_text(row["StudentExplanation"]) for row in rows],
                                                          config.model_dir, config.embedding_cache)
    embeddings = np.asarray(embeddings)
    if embeddings.ndim != 2 or len(embeddings) != len(rows) or not np.isfinite(embeddings).all():
        raise ValueError("Embeddings must be finite vectors aligned to deduplicated rows")
    if description_vectors is None:
        description_vectors, _ = cached_embeddings([DESCRIPTIONS[name] for name in sorted(DESCRIPTIONS)], config.model_dir,
                                                    str(Path(config.embedding_cache).with_name('minilm-descriptions.npz')))
    description_vectors = np.asarray(description_vectors)
    if description_vectors.shape != (len(DESCRIPTIONS), embeddings.shape[1]) or not np.isfinite(description_vectors).all():
        raise ValueError('Description vectors must be finite and aligned to the six fixed descriptions')
    model_names = ("majority", "class_prior", "tfidf_composite", "hierarchical_tfidf", "semantic_prototypes", 'semantic_descriptions')
    probabilities_oof = {name: np.zeros((len(rows), len(catalogue))) for name in model_names}
    binary_oof = np.zeros(len(rows))
    binary_decisions = np.zeros(len(rows), dtype=bool)
    ranking_oof = {name: np.full((len(rows), 3), '', dtype='<U100') for name in model_names}
    coverage_oof = {name: np.zeros(len(rows), dtype=bool) for name in model_names}
    fit_counts_oof = np.zeros(len(rows), dtype=int)
    semantic_name_ranking = np.full((len(rows), 3), '', dtype='<U100')
    name_coverage_oof = np.zeros(len(rows), dtype=bool)
    name_ranking_oof = {name: np.full((len(rows), 3), '', dtype='<U100') for name in model_names[3:]}
    name_coverage = {name: np.zeros(len(rows), dtype=bool) for name in model_names[3:]}
    reports, manifests, errors = [], [], []
    group_ordinals = {group: number for number, group in enumerate(sorted(set(groups)), 1)}
    with threadpool_limits(limits=1):
        for number, split in enumerate(folds, 1):
            print(f"Fold {number}/{len(folds)}: inner tuning on {len(set(groups[split['train']]))} question groups; "
                  f"validation {len(set(groups[split['validation']]))}; outer test {len(set(groups[split['test']]))}", flush=True)
            train, validation, development, test = (split[x] for x in ("train", "validation", "development", "test"))
            if not any(is_misconception(x) for x in truth[validation]):
                raise ValueError("Inner validation has no misconception rows; diagnostic selection is undefined")
            inner_prototypes = semantic_prototypes(rows, train, embeddings)
            candidates = {name: [] for name in (*model_names[2:], "binary_tfidf")}
            for C in sorted(config.C_candidates):
                fitted = fit_heads(rows, train, C, config)
                scored = score_heads(rows, validation, fitted, inner_prototypes, embeddings, .1, description_vectors)
                for name in ("tfidf_composite", "hierarchical_tfidf"):
                    report, _, _ = diagnostic_metrics(truth[validation], *scored[name], truth[train], catalogue)
                    candidates[name].append({"C": C, "score": report["misconception"]["map_at_3"]})
                for temperature in sorted(config.temperatures):
                    # Reuse the category head, never test responses or test-derived prototypes.
                    features = fitted[0].transform([build_text(rows[i]) for i in validation])
                    category_probabilities = fitted[1]['category'].predict_proba(features)
                    for name, prototypes in (('semantic_prototypes', inner_prototypes),
                                             ('semantic_descriptions', description_prototypes(inner_prototypes, description_vectors))):
                        semantic = hierarchy_probabilities(category_probabilities,
                            fitted[1]["category"].classes_, retrieval_probabilities(embeddings[validation], prototypes[0], temperature), prototypes[1])
                        report, _, _ = diagnostic_metrics(truth[validation], *semantic, truth[train], catalogue)
                        candidates[name].append({"C": C, "temperature": temperature,
                                                "score": report["misconception"]["map_at_3"]})
                for threshold in sorted(config.screening_thresholds):
                    metric = binary_metrics([is_misconception(x) for x in truth[validation]], scored["binary_tfidf"], threshold)
                    candidates["binary_tfidf"].append({"C": C, "threshold": threshold, "score": metric["f1"]})
                print(f"  Finished inner C={C}", flush=True)
            selected = {name: select_diagnostic(candidates[name]) for name in model_names[2:]}
            selected["binary_tfidf"] = max(candidates["binary_tfidf"], key=lambda x: (x["score"], -x["C"], -abs(x["threshold"] - .5), -x["threshold"]))
            outer_prototypes = semantic_prototypes(rows, development, embeddings)
            fits = {C: fit_heads(rows, development, C, config) for C in sorted({x["C"] for x in selected.values()})}
            outputs = {}
            for name in model_names[2:]:
                scored = score_heads(rows, test, fits[selected[name]["C"]], outer_prototypes, embeddings,
                                     selected[name].get("temperature", .1), description_vectors)
                outputs[name] = scored[name]
                if name in name_ranking_oof:
                    name_probabilities, candidate_names = scored[f'name_{name}']
                    if len(candidate_names):
                        name_ranking = candidate_names[np.argsort(-name_probabilities, axis=1, kind='stable')[:, :3]]
                        name_ranking_oof[name][test, :name_ranking.shape[1]] = name_ranking
                        name_coverage[name][test] = np.isin([rows[i]['Misconception'] for i in test], candidate_names)
            chosen_binary = selected["binary_tfidf"]
            binary_scores = score_heads(rows, test, fits[chosen_binary["C"]], outer_prototypes, embeddings, .1, description_vectors)["binary_tfidf"]
            binary_oof[test] = binary_scores
            binary_decisions[test] = binary_scores >= chosen_binary["threshold"]
            counts = Counter(truth[development])
            fit_counts_oof[test] = [counts[x] for x in truth[test]]
            retrieval = retrieval_probabilities(embeddings[test], outer_prototypes[0], .1)
            if len(outer_prototypes[1]):
                name_top = outer_prototypes[1][np.argsort(-retrieval, axis=1, kind='stable')[:, :3]]
                semantic_name_ranking[test, :name_top.shape[1]] = name_top
                name_coverage_oof[test] = np.isin([rows[i]['Misconception'] for i in test], outer_prototypes[1])
            majority = sorted(counts, key=lambda x: (-counts[x], x))[0]
            outputs["majority"] = (np.ones((len(test), 1)), np.array([majority]))
            prior_classes = np.array(sorted(counts))
            prior = np.array([counts[x] / len(development) for x in prior_classes])
            outputs["class_prior"] = (np.tile(prior, (len(test), 1)), prior_classes)
            fold_report = {"fold": number, "selection": selected, "inner_candidates": candidates,
                           "partitions": {key: {"rows": len(indices), "groups": len(set(groups[indices])),
                                                 "classes": len(set(truth[indices])),
                    "misconception_rows": sum(is_misconception(x) for x in truth[indices]),
                    "label_counts": dict(sorted(Counter(truth[indices]).items()))}
                                          for key, indices in split.items()}, "models": {}}
            for name, (probabilities, classes) in outputs.items():
                metric, predictions, _ = diagnostic_metrics(truth[test], probabilities, classes, truth[development], catalogue)
                metric['macro_f1_observed'] = float(np.mean([metric['per_class'][label]['f1-score'] for label in observed_labels]))
                fold_report["models"][name] = metric
                ranking = classes[np.argsort(-probabilities, axis=1, kind='stable')[:, :3]]
                ranking_oof[name][test, :ranking.shape[1]] = ranking
                coverage_oof[name][test] = np.isin(truth[test], classes)
                for column, label in enumerate(classes):
                    if label in catalogue:
                        probabilities_oof[name][test, catalogue.index(label)] = probabilities[:, column]
                errors.extend({"model": name, "retained_index": int(i), "true_label": str(actual), "predicted_label": str(predicted)}
                              for i, actual, predicted in zip(test, truth[test], predictions) if actual != predicted)
            fold_report["binary_tfidf"] = binary_metrics([is_misconception(x) for x in truth[test]], binary_scores, chosen_binary["threshold"])
            reports.append(fold_report)
            manifests.append({"indices": {key: indices.tolist() for key, indices in split.items()},
                              "fits_sha256": {str(C): fingerprint_fit(fitted, outer_prototypes) for C, fitted in fits.items()}})
            print(f"  Outer screening F1={fold_report['binary_tfidf']['f1']:.4f}; misconception MAP@3: "
                  + ", ".join(f"{name}={fold_report['models'][name]['misconception']['map_at_3']:.4f}" for name in model_names[2:]), flush=True)
    pooled, per_question = {}, []
    # Aggregate additive counts and per-class confusion from folds, preserving original candidate rankings.
    positive_total = sum(is_misconception(x) for x in truth)
    for name in model_names:
        fold_metrics = [fold["models"][name] for fold in reports]
        matrix = np.sum([metric["confusion_matrix"] for metric in fold_metrics], axis=0)
        pooled[name] = pooled_from_confusions(matrix, catalogue)
        pooled[name]['macro_f1_observed'] = float(np.mean([pooled[name]['per_class'][label]['f1-score'] for label in observed_labels]))
        pooled[name]['screening_at_default_threshold'] = binary_metrics([is_misconception(x) for x in truth],
                              probabilities_oof[name][:, [is_misconception(x) for x in catalogue]].sum(axis=1))
        for key in ("accuracy", "map_at_3", "top_3_recall", "candidate_label_coverage", "unseen_label_row_rate"):
            pooled[name][key] = sum(metric[key] * metric["rows"] for metric in fold_metrics) / len(rows)
        for subset in ("misconception", "other", "seen", "unseen"):
            count = sum(metric[subset]["rows"] for metric in fold_metrics)
            pooled[name][subset] = {"rows": count, **{key: sum((metric[subset][key] or 0) * metric[subset]["rows"] for metric in fold_metrics) / count if count else None
                for key in ("top_1_accuracy", "top_3_recall", "map_at_3", "candidate_label_coverage")}}
        pooled[name]["fold_mean_std"] = {key: {"mean": float(np.mean([metric[key] for metric in fold_metrics])),
                                                         "std": float(np.std([metric[key] for metric in fold_metrics], ddof=1))}
                                                for key in ("accuracy", "macro_f1", 'macro_f1_observed', "map_at_3", "top_3_recall", "unseen_label_row_rate")}
        pooled[name]["misconception_fold_mean_std"] = {key: {"mean": float(np.mean([metric["misconception"][key] for metric in fold_metrics])),
                                                                      "std": float(np.std([metric["misconception"][key] for metric in fold_metrics], ddof=1))}
                                                             for key in ("top_1_accuracy", "top_3_recall", "map_at_3")}
        for subset in ('misconception', 'other'):
            labels = [x for x in observed_labels if is_misconception(x) == (subset == 'misconception')]
            pooled[name][subset]['macro_f1'] = float(np.mean([pooled[name]['per_class'][label]['f1-score'] for label in labels]))
        bins = {}
        for bucket, mask in (('unseen_0', fit_counts_oof == 0), ('rare_1_to_49', (fit_counts_oof > 0) & (fit_counts_oof < 50)), ('frequent_50_plus', fit_counts_oof >= 50)):
            bins[bucket] = {'all': ranking_summary(truth, ranking_oof[name], mask),
                            'misconception': ranking_summary(truth, ranking_oof[name], mask & np.array([is_misconception(x) for x in truth]))}
        pooled[name]['by_training_frequency'] = bins
        wrong = Counter((str(actual), str(predicted)) for actual, predicted in zip(truth, ranking_oof[name][:, 0]) if actual != predicted)
        pooled[name]['top_confusions'] = [{'true_label': a, 'predicted_label': p, 'count': n} for (a, p), n in wrong.most_common(20)]
    for group in sorted(set(groups)):
        mask = groups == group
        question_positive_mask = mask & positive_mask
        per_question.append({'anonymous_question': group_ordinals[group], 'rows': int(mask.sum()),
                             'misconception_rows': int(question_positive_mask.sum()), 'classes': len(set(truth[mask])),
                             'unseen_label_row_rate': float((fit_counts_oof[mask] == 0).mean()),
                             'models': {name: {'all': ranking_summary(truth, ranking_oof[name], mask),
                                               'misconception': ranking_summary(truth, ranking_oof[name], question_positive_mask),
                                               'candidate_label_coverage': float(coverage_oof[name][mask].mean())}
                                        for name in model_names},
                             'binary_tfidf': selected_screening_metrics(positive_mask[mask], binary_oof[mask], binary_decisions[mask])})
    screening = selected_screening_metrics(positive_mask, binary_oof, binary_decisions)
    screening["fold_mean_std"] = {key: {"mean": float(np.mean([x["binary_tfidf"][key] for x in reports])),
                                                "std": float(np.std([x["binary_tfidf"][key] for x in reports], ddof=1))}
                                       for key in ("precision", "recall", "f1", "average_precision", "false_positive_rate")}
    report = {"protocol": f"{config.outer_folds} outer GroupKFold folds; one fixed inner grouped holdout per fold; not an untouched test",
              "data_kind": config.data_kind, "dataset": audit, "embedding": embedding_metadata,
              "selection": "Diagnostic models: inner misconception-only MAP@3. Binary: inner positive-class F1. Deterministic ties prefer smaller C.",
              "taxonomy": {"categories": sorted({row['Category'] for row in rows}), "misconception_names": len({row['Misconception'] for row in rows if is_misconception(row['label'])}),
                           "positive_rows": positive_total, "positive_fraction": positive_total / len(rows),
                           "valid_binary_consistency": all((row['Misconception'] != 'NA') == is_misconception(row['label']) for row in rows)},
              "models": pooled, "binary_tfidf": screening, 'per_question': per_question,
              'semantic_oracle_positive_retrieval': {**ranking_summary(np.array([row['Misconception'] for row in rows]), semantic_name_ranking,
                          np.array([is_misconception(x) for x in truth])),
                          'candidate_name_coverage': float(name_coverage_oof[np.array([is_misconception(x) for x in truth])].mean()),
                          'interpretation': 'Oracle positive subset, name only; excludes detection and True/False prefix errors'},
              'oracle_positive_name_ranking': {name: {
                  **ranking_summary(np.array([row['Misconception'] for row in rows]), ranking, positive_mask),
                  'candidate_name_coverage': float(name_coverage[name][positive_mask].mean()),
                  'per_class': classification_report(np.array([row['Misconception'] for row in rows])[positive_mask], ranking[positive_mask, 0],
                           labels=sorted({row['Misconception'] for row in rows if is_misconception(row['label'])}), output_dict=True, zero_division=0),
                  'interpretation': 'Oracle positive annotations; excludes screening and chosen-answer correctness; never teacher-facing observed performance'}
                  for name, ranking in name_ranking_oof.items()},
              'macro_policy': {'formal_labels': len(catalogue), 'observed_labels': len(observed_labels),
                               'primary': 'macro_f1_observed averages empirical dataset labels; macro_f1 averages full formal Cartesian taxonomy; zero-support scores zero'},
              'description_catalogue': {'source': SOURCE, 'names': sorted(DESCRIPTIONS), 'mapped_names': len(DESCRIPTIONS),
                                        'positive_row_coverage': sum(row['Misconception'] in DESCRIPTIONS for row in rows) / positive_total,
                                        'policy': 'Six fixed public paraphrases override centroids; remaining names use training-fold examples only'},
              "binary_references": {"always_negative": binary_metrics([is_misconception(x) for x in truth], np.zeros(len(rows))),
                                    "always_positive": binary_metrics([is_misconception(x) for x in truth], np.ones(len(rows)))},
              "folds": reports,
              "limitations": ["Only 15 question proxies, no student/template IDs", "Outer results are development evidence, not independent final validation",
                              "Only six verified description mappings; other semantic candidates use training-fold response centroids",
                              "Frozen English encoder; no Kazakh/Russian evaluation", "No calibration or causal diagnosis claims"]}
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"config": config.to_dict(), "dataset_sha256": hashlib.sha256(Path(config.dataset_path).read_bytes()).hexdigest(),
                "python": platform.python_version(), "versions": {name: version(name) for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")},
                "source_sha256": source_hashes,
                'description_vectors_sha256': hashlib.sha256(description_vectors.tobytes()).hexdigest(),
                "fold_manifests": manifests, "retained_row_ids": [row['row_id'] for row in rows]}
    if config.data_kind == 'real':
        metadata['versions'].update({name: version(name) for name in ('onnxruntime', 'tokenizers')})
    for filename, value in (("report.json", report), ("experiment.json", metadata), ("private_errors.json", errors)):
        (output / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    np.savez_compressed(output / "private_oof.npz", **probabilities_oof, **{f'rank_{name}': value for name, value in ranking_oof.items()},
                        binary_scores=binary_oof, binary_decisions=binary_decisions, semantic_name_ranking=semantic_name_ranking,
                        training_counts=fit_counts_oof, **{f'name_rank_{name}': ranking for name, ranking in name_ranking_oof.items()})
    return report


def pooled_from_confusions(matrix, labels):
    matrix = np.asarray(matrix)
    support, predicted = matrix.sum(axis=1), matrix.sum(axis=0)
    precision = np.divide(matrix.diagonal(), predicted, out=np.zeros(len(labels)), where=predicted != 0)
    recall = np.divide(matrix.diagonal(), support, out=np.zeros(len(labels)), where=support != 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(len(labels)), where=precision + recall != 0)
    return {"rows": int(matrix.sum()), "macro_f1": float(f1.mean()), "weighted_f1": float((f1 * support).sum() / support.sum()),
            "labels": list(labels), "confusion_matrix": matrix.tolist(),
            "per_class": {label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1-score": float(f1[i]), "support": int(support[i])}
                          for i, label in enumerate(labels)}}


def ranking_summary(truth, ranking, mask):
    mask = np.asarray(mask)
    if not mask.any():
        return {'rows': 0, 'top_1_accuracy': None, 'top_3_recall': None, 'map_at_3': None}
    hits = ranking[mask] == np.asarray(truth)[mask, None]
    return {'rows': int(mask.sum()), 'top_1_accuracy': float(hits[:, 0].mean()),
            'top_3_recall': float(hits.any(axis=1).mean()),
            'map_at_3': float((hits * (1 / np.arange(1, ranking.shape[1] + 1))).sum(axis=1).mean())}


def verify_comparison(first, second):
    first, second = Path(first), Path(second)
    for filename in ("report.json", "private_errors.json"):
        if json.loads((first / filename).read_text(encoding="utf-8")) != json.loads((second / filename).read_text(encoding="utf-8")):
            raise ValueError(f"Reproducibility mismatch: {filename}")
    a = json.loads((first / "experiment.json").read_text(encoding="utf-8"))
    b = json.loads((second / "experiment.json").read_text(encoding="utf-8"))
    for value in (a, b):
        value["config"].pop("output_dir")
    if a != b:
        raise ValueError("Reproducibility mismatch: fit fingerprints/splits/config/versions")
    with np.load(first / "private_oof.npz", allow_pickle=False) as left, np.load(second / "private_oof.npz", allow_pickle=False) as right:
        if set(left.files) != set(right.files) or any(not np.array_equal(left[key], right[key]) for key in left.files):
            raise ValueError("Reproducibility mismatch: OOF arrays")
    return {"passed": True, "reports": True, "split_manifests": True, "fit_fingerprints": True, "oof_arrays": True}
