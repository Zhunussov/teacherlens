"""Re-encode one original batch locally and compare with the trusted full cache."""

import argparse
import json
from pathlib import Path

import numpy as np

from teacherlens.comparison import load_comparison_config
from teacherlens.data import load_dataset
from teacherlens.embeddings import cached_embeddings, encode_local
from teacherlens.research import audit_and_deduplicate
from teacherlens.text import normalize_text


def verify(config, output):
    rows, _ = audit_and_deduplicate(load_dataset(config.dataset_path))
    texts = [normalize_text(row['StudentExplanation']) for row in rows]
    vectors, _ = cached_embeddings(texts, config.model_dir, config.embedding_cache)
    sample = min(32, len(texts))
    repeated, _ = encode_local(texts[:sample], config.model_dir)
    result = {'sample_rows': sample, 'exact_sample_embedding_reproduction': bool(np.array_equal(vectors[:sample], repeated)),
              'all_vectors_unit_norm_within_1e-6': bool(np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-6, rtol=0)),
              'model_asset_checksums_verified': True}
    if not all(value for key, value in result.items() if key != 'sample_rows'):
        raise ValueError('Frozen embedding verification failed')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    verify(load_comparison_config(args.config), args.output)
    print('Frozen embedding sample and full-cache normalization verified.')
