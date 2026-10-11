"""Repair the question-mask reporting defect using verified, unchanged saved OOF arrays.

This migration is specific to the original Milestone 3 artifacts. It changes no
fits, selection, predictions or fold metrics and records reporting provenance.
It refuses to run on reports whose pooled positive counts are already correct.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report

from teacherlens.comparison import (is_misconception, ranking_summary,
                                    selected_screening_metrics, verify_comparison)
from teacherlens.data import load_dataset
from teacherlens.descriptions import DESCRIPTIONS
from teacherlens.research import audit_and_deduplicate


def repair(directory):
    directory = Path(directory)
    report_path = directory / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    metadata = json.loads((directory / 'experiment.json').read_text(encoding='utf-8'))
    dataset_path = Path(metadata['config']['dataset_path'])
    if hashlib.sha256(dataset_path.read_bytes()).hexdigest() != metadata['dataset_sha256']:
        raise ValueError('Dataset identity mismatch')
    rows, _ = audit_and_deduplicate(load_dataset(dataset_path))
    if [row['row_id'] for row in rows] != metadata['retained_row_ids']:
        raise ValueError('Retained row alignment mismatch')
    positive = np.array([is_misconception(row['label']) for row in rows])
    if report['binary_tfidf']['positive_rows'] == int(positive.sum()):
        raise ValueError('Report already has correct pooled positive count')
    original_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    name_truth = np.array([row['Misconception'] for row in rows])
    names = sorted(set(name_truth[positive]))
    with np.load(directory / 'private_oof.npz', allow_pickle=False) as arrays:
        screening = selected_screening_metrics(positive, arrays['binary_scores'], arrays['binary_decisions'])
        expected_matrix = np.sum([fold['binary_tfidf']['confusion_matrix'] for fold in report['folds']], axis=0)
        if not np.array_equal(screening['confusion_matrix'], expected_matrix):
            raise ValueError('Pooled screening does not agree with saved fold counts')
        screening['fold_mean_std'] = report['binary_tfidf']['fold_mean_std']
        report['binary_tfidf'] = screening
        for model, oracle in report['oracle_positive_name_ranking'].items():
            coverage = np.zeros(len(rows), dtype=bool)
            for fold in metadata['fold_manifests']:
                indices = fold['indices']
                candidates = {rows[i]['Misconception'] for i in indices['development']
                              if is_misconception(rows[i]['label'])}
                if model == 'semantic_descriptions':
                    candidates |= set(DESCRIPTIONS)
                test = indices['test']
                coverage[test] = np.isin(name_truth[test], sorted(candidates))
            ranking = arrays[f'name_rank_{model}']
            oracle.update(ranking_summary(name_truth, ranking, positive))
            oracle['candidate_name_coverage'] = float(coverage[positive].mean())
            oracle['per_class'] = classification_report(name_truth[positive], ranking[positive, 0],
                labels=names, output_dict=True, zero_division=0)
    report['reporting_correction'] = {
        'reason': 'Per-question local positive mask formerly replaced the full-data mask in pooled screening and oracle name summaries',
        'method': 'Recomputed from unchanged saved OOF scores/decisions/name rankings and verified dataset/split alignment',
        'original_report_sha256': original_sha,
        'repair_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'corrected_comparison_source_sha256': hashlib.sha256(
            Path(__file__).resolve().parents[1].joinpath('src/teacherlens/comparison.py').read_bytes()).hexdigest(),
        'fits_selection_predictions_and_fold_metrics_unchanged': True}
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    args = parser.parse_args()
    verify_comparison(args.first, args.second)
    repair(args.first)
    repair(args.second)
    verify_comparison(args.first, args.second)
    print('Corrected summaries agree exactly; saved fit/prediction artifacts unchanged.')
