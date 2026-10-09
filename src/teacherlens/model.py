"""No service dependencies: reusable sklearn baseline."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .config import ExperimentConfig


def create_model(config: ExperimentConfig) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=False, ngram_range=(1, config.ngram_max),
                                 max_features=config.max_features,
                                 token_pattern=r"(?u)\w+|[^\w\s]", sublinear_tf=True)),
        ("classifier", LogisticRegression(C=config.C, max_iter=config.max_iter,
                                          class_weight=config.class_weight,
                                          random_state=config.seed, solver="lbfgs")),
    ])
