"""Prepare reviewed aggregates after two trusted local CV runs; never export row artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from teacherlens.comparison import verify_comparison


REPORT_FIELDS = (
    'protocol', 'data_kind', 'dataset', 'selection', 'taxonomy', 'models', 'binary_tfidf',
    'binary_references', 'folds', 'per_question', 'semantic_oracle_positive_retrieval',
    'oracle_positive_name_ranking', 'macro_policy', 'description_catalogue', 'limitations',
)
ENCODER_FIELDS = ('model', 'revision', 'asset_sha256', 'dimensions', 'max_tokens',
                  'truncated_rows', 'pooling', 'input')
CONFIG_FIELDS = ('data_kind', 'seed', 'max_features', 'ngram_max', 'max_iter', 'class_weight',
                 'outer_folds', 'inner_validation_fraction', 'C_candidates', 'screening_thresholds', 'temperatures')
FORBIDDEN = {'row_id', 'retained_index', 'retained_row_ids', 'fold_manifests', 'indices',
             'text_sha256', 'vectors_sha256', 'QuestionText', 'StudentExplanation', 'MC_Answer'}


def check_aggregate(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'column_types':
                if not isinstance(child, dict) or any(x not in ('string', 'string (integer-compatible identifiers)') for x in child.values()):
                    raise ValueError('Unexpected column-type metadata requires manual review')
                continue  # Schema field names are permitted; no row content is present.
            if key in FORBIDDEN:
                raise ValueError(f'Private field in aggregate: {key}')
            check_aggregate(child)
    elif isinstance(value, list):
        for child in value:
            check_aggregate(child)


def readable_json(value):
    """Keep matrix rows on one line, preserving every numeric value for review."""
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    numeric_array = r'\[\n(?:[ \t]+-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?,?\n)+[ \t]*\]'
    return re.sub(numeric_array, lambda match: json.dumps(json.loads(match.group()), ensure_ascii=False), text) + '\n'


def export(first, second, output, embedding_verification):
    verification = verify_comparison(first, second)
    root = Path(first)
    report = json.loads((root / 'report.json').read_text(encoding='utf-8'))
    metadata = json.loads((root / 'experiment.json').read_text(encoding='utf-8'))
    safe = {key: report[key] for key in REPORT_FIELDS}
    if 'reporting_correction' in report:
        safe['reporting_correction'] = report['reporting_correction']
    encoding = report['embedding']['encoding']
    safe['embedding'] = {key: encoding[key] for key in ENCODER_FIELDS}
    safe['embedding']['dataset_input'] = 'normalized StudentExplanation only; each row independently encoded'
    safe['computation'] = {key: metadata[key] for key in ('python', 'versions', 'source_sha256', 'dataset_sha256')}
    safe['computation']['publication_source_sha256'] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path(__file__).resolve().parents[1].joinpath('src/teacherlens').glob('*.py'))}
    safe['computation']['active_config'] = {key: metadata['config'][key] for key in CONFIG_FIELDS}
    safe['computation']['export_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    safe['reproducibility'] = verification
    safe['embedding_verification'] = json.loads(Path(embedding_verification).read_text(encoding='utf-8'))
    check_aggregate(safe)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(readable_json(safe), encoding='utf-8')
    return safe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--embedding-verification', required=True)
    args = parser.parse_args()
    export(args.first, args.second, args.output, args.embedding_verification)
    print('Verified aggregate export prepared; review before committing.')
