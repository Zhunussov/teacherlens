"""Strict, portable experiment configuration."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ExperimentConfig:
    dataset_path: str
    output_dir: str
    data_kind: str = "real"
    seed: int = 42
    test_size: float = 0.25
    max_features: int = 50000
    ngram_max: int = 2
    C: float = 1.0
    max_iter: int = 1000
    class_weight: str | None = "balanced"

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip() for x in (self.dataset_path, self.output_dir)):
            raise ValueError("dataset_path and output_dir must be nonempty strings")
        if self.data_kind not in {"real", "synthetic"}:
            raise ValueError("data_kind must be real or synthetic")
        for name in ("seed", "max_features", "ngram_max", "max_iter"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "seed" else 1):
                raise ValueError(f"{name} must be a valid nonnegative/positive integer")
        if self.seed > 2**32 - 1:
            raise ValueError("seed must fit an unsigned 32-bit integer")
        for name in ("test_size", "C"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not 0 < value < float("inf"):
                raise ValueError(f"{name} must be a finite positive number")
        if self.test_size >= 1:
            raise ValueError("test_size must be between zero and one")
        if self.class_weight not in (None, "balanced"):
            raise ValueError("class_weight must be null or balanced")

    def to_dict(self):
        return asdict(self)


def load_config(path: str | Path) -> ExperimentConfig:
    path = Path(path).resolve()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        config = ExperimentConfig(**values)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid experiment config {path}: {exc}") from exc
    values = config.to_dict()
    for field in ("dataset_path", "output_dir"):
        values[field] = str((path.parent / values[field]).resolve())
    return ExperimentConfig(**values)
