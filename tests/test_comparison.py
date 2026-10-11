from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from teacherlens.comparison import (ComparisonConfig, binary_metrics, description_prototypes,
    diagnostic_metrics, fit_heads, hierarchy_probabilities, load_comparison_config,
    nested_splits, ranking_summary, run_comparison, semantic_prototypes, verify_comparison)
from teacherlens.data import load_dataset
from teacherlens.descriptions import DESCRIPTIONS
from teacherlens.embeddings import cached_embeddings, mean_pool
from teacherlens.text import build_text

FIXTURE = Path(__file__).parent / 'fixtures' / 'synthetic.csv'


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = load_dataset(FIXTURE)
        self.config = ComparisonConfig(str(FIXTURE.resolve()), str(self.root / 'first'), data_kind='synthetic',
             outer_folds=2, C_candidates=(1.,), temperatures=(.1,), screening_thresholds=(.5,), max_features=1000)
        rng = np.random.default_rng(42)
        self.embeddings = rng.normal(size=(len(self.rows), 4))
        self.embeddings /= np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.descriptions = rng.normal(size=(len(DESCRIPTIONS), 4))

    def test_nested_groups_disjoint_cover_all_and_deterministic(self):
        folds, groups = nested_splits(self.rows, self.config)
        repeat, _ = nested_splits(self.rows, self.config)
        self.assertEqual(sorted(np.concatenate([x['test'] for x in folds]).tolist()), list(range(len(self.rows))))
        for split, again in zip(folds, repeat):
            for key in split:
                np.testing.assert_array_equal(split[key], again[key])
            for a, b in (('train', 'validation'), ('train', 'test'), ('validation', 'test')):
                self.assertFalse(set(groups[split[a]]) & set(groups[split[b]]))
        with self.assertRaisesRegex(ValueError, 'enough question groups'):
            nested_splits(self.rows[:4], self.config)

    def test_map_reciprocal_rank_differs_from_top_three_recall(self):
        classes = np.array(['False_Misconception:A', 'True_Correct:NA', 'True_Neither:NA'])
        truth = [classes[0], classes[0], 'False_Misconception:unseen']
        report, _, _ = diagnostic_metrics(truth, np.array([[.6,.3,.1],[.1,.6,.3],[.1,.6,.3]]), classes, classes, [*classes, truth[-1]])
        self.assertAlmostEqual(report['map_at_3'], (1 + 1/3)/3)
        self.assertAlmostEqual(report['top_3_recall'], 2/3)
        self.assertEqual(report['unseen']['top_1_accuracy'], 0)
        self.assertAlmostEqual(report['candidate_label_coverage'], 2/3)
        with self.assertRaisesRegex(ValueError, 'Invalid candidate'):
            diagnostic_metrics(truth, np.ones((3, 3)), classes, classes, classes)

    def test_ties_follow_candidate_order_not_global_zero_filled_columns(self):
        classes = np.array(['True_Correct:NA', 'False_Misconception:B'])
        report, predictions, _ = diagnostic_metrics([classes[0]], np.array([[.5,.5]]), classes, classes, sorted(classes))
        self.assertEqual(predictions[0], classes[0])
        self.assertEqual(report['accuracy'], 1)

    def test_hierarchy_can_transfer_seen_name_to_unseen_composite(self):
        probabilities, classes = hierarchy_probabilities(np.array([[.8,.2]]), ['False_Misconception', 'True_Misconception'],
                                                         np.array([[1.]]), ['WNB'])
        self.assertEqual(list(classes), ['False_Misconception:WNB', 'True_Misconception:WNB'])
        report, _, _ = diagnostic_metrics(['True_Misconception:WNB'], probabilities, classes,
                                          ['False_Misconception:WNB'], classes)
        self.assertEqual(report['unseen_label_row_rate'], 1)
        self.assertEqual(report['candidate_label_coverage'], 1)
        self.assertAlmostEqual(report['map_at_3'], .5)

    def test_single_class_and_no_positive_training_heads(self):
        indices = [i for i, row in enumerate(self.rows) if row['Category'] == 'True_Correct']
        vectorizer, heads = fit_heads(self.rows, indices, 1, self.config)
        self.assertIsNone(heads['specific'])
        self.assertEqual(list(heads['binary'].classes_), ['0'])
        np.testing.assert_array_equal(heads['composite'].predict_proba(vectorizer.transform([build_text(self.rows[0])])), [[1]])

    def test_prototypes_use_only_training_labels_and_vectors(self):
        first = semantic_prototypes(self.rows, [0, 1], self.embeddings)
        altered = self.embeddings.copy()
        altered[2:] = 999
        second = semantic_prototypes(self.rows, [0, 1], altered)
        np.testing.assert_array_equal(first[0], second[0])
        self.assertNotIn('Unknown', first[1])
        described = description_prototypes(first, self.descriptions)
        self.assertTrue(set(DESCRIPTIONS).issubset(described[1]))

    def test_new_heads_fit_vocabulary_only_on_training_rows(self):
        rows = [dict(row) for row in self.rows]
        rows[2]['StudentExplanation'] = 'holdout_only_token'
        vectorizer, _ = fit_heads(rows, [0, 1], 1., self.config)
        self.assertNotIn('holdout_only_token', vectorizer.vocabulary_)

    def test_external_description_can_support_an_unseen_name(self):
        from teacherlens.comparison import retrieval_probabilities
        vectors = np.eye(len(DESCRIPTIONS))
        described = description_prototypes((np.empty((0, len(DESCRIPTIONS))), np.array([])), vectors)
        target = sorted(DESCRIPTIONS).index('WNB')
        name_prob = retrieval_probabilities(vectors[[target]], described[0], .05)
        probabilities, classes = hierarchy_probabilities(np.array([[1.]]), ['False_Misconception'], name_prob, described[1])
        report, _, _ = diagnostic_metrics(['False_Misconception:WNB'], probabilities, classes, ['True_Correct:NA'], classes)
        self.assertEqual(report['unseen']['top_1_accuracy'], 1)
        self.assertEqual(report['candidate_label_coverage'], 1)

    def test_case_distinct_misconception_names_are_not_merged(self):
        original = self.rows[0]
        rows = [{**original, 'Category': 'False_Misconception', 'Misconception': name,
                 'label': f'False_Misconception:{name}'} for name in ('Wrong_Fraction', 'Wrong_fraction')]
        _, names = semantic_prototypes(rows, [0, 1], np.eye(2))
        self.assertEqual(list(names), ['Wrong_Fraction', 'Wrong_fraction'])

    def test_binary_target_is_annotation_not_answer_correctness(self):
        from teacherlens.comparison import is_misconception
        self.assertTrue(is_misconception('True_Misconception:WNB'))
        self.assertFalse(is_misconception('False_Neither:NA'))
        always_positive = binary_metrics([True, False, False], [1, 1, 1])
        self.assertEqual(always_positive['recall'], 1)
        self.assertAlmostEqual(always_positive['precision'], 1/3)
        self.assertEqual(always_positive['false_positive_rate'], 1)
        self.assertIsNone(binary_metrics([False], [0])['average_precision'])

    def test_selected_threshold_does_not_discard_continuous_score_ap(self):
        from teacherlens.comparison import selected_screening_metrics
        metrics = selected_screening_metrics([True, False], [.9, .7], [False, False])
        self.assertEqual(metrics['average_precision'], 1)
        self.assertEqual(metrics['recall'], 0)
        self.assertEqual(metrics['confusion_matrix'], [[1,0],[1,0]])

    def test_empty_subset_is_explicit_not_invented_zero(self):
        result = ranking_summary(np.array(['a']), np.array([['a', '', '']]), np.array([False]))
        self.assertIsNone(result['map_at_3'])
        self.assertEqual(result['rows'], 0)

    def test_pooling_ignores_padding_and_normalizes(self):
        vectors = mean_pool(np.array([[[1., 0.], [0., 1.], [999.,999.]]]), [[1,1,0]])
        np.testing.assert_allclose(vectors, [[2**-.5, 2**-.5]], rtol=1e-6)

    def test_truncation_audit_counts_tokens_before_batch_padding(self):
        import sys
        from types import SimpleNamespace
        from teacherlens.embeddings import encode_local

        class FakeTokenizer:
            padding = False
            maximum = None

            def enable_truncation(self, max_length):
                self.maximum = max_length

            def no_truncation(self):
                self.maximum = None

            def enable_padding(self, **kwargs):
                self.padding = True

            def encode_batch(self, texts):
                lengths = [min(len(text), self.maximum) if self.maximum else len(text) for text in texts]
                width = max(lengths)
                return [SimpleNamespace(ids=[1]*n + ([0]*(width-n) if self.padding else []),
                        attention_mask=[1]*n + ([0]*(width-n) if self.padding else []),
                        type_ids=[0]*(width if self.padding else n)) for n in lengths]

        class FakeSession:
            def get_inputs(self):
                return [SimpleNamespace(name=name) for name in ('input_ids', 'attention_mask', 'token_type_ids')]

            def run(self, output_names, feeds):
                return [np.ones((*feeds['input_ids'].shape, 384), dtype=np.float32)]

        fake_ort = SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=lambda *a, **k: FakeSession())
        fake_tokenizers = SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: FakeTokenizer()))
        with patch.dict(sys.modules, {'onnxruntime': fake_ort, 'tokenizers': fake_tokenizers}), \
                patch('teacherlens.embeddings.prepare_model', return_value={}):
            vectors, metadata = encode_local(['x'*300, 'y'*5], self.root)
        self.assertEqual(metadata['truncated_rows'], 1)
        self.assertEqual(vectors.shape, (2, 384))

    def test_embedding_cache_rejects_changed_input(self):
        cache = self.root / 'cache.npz'
        with patch('teacherlens.embeddings.encode_local', return_value=(np.ones((1,384)), {'data_kind': 'synthetic'})):
            cached_embeddings(['fixture'], self.root, cache)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            cached_embeddings(['changed'], self.root, cache)

    def test_embedding_cache_rejects_modified_vectors_and_wrong_extension(self):
        cache = self.root / 'cache.npz'
        with patch('teacherlens.embeddings.encode_local', return_value=(np.ones((1,384)), {'data_kind': 'synthetic'})):
            cached_embeddings(['fixture'], self.root, cache)
        with np.load(cache, allow_pickle=False) as value:
            metadata, vectors = str(value['metadata']), value['vectors']
        vectors[0, 0] = 2
        np.savez_compressed(cache, metadata=metadata, vectors=vectors)
        with self.assertRaisesRegex(ValueError, 'vector checksum'):
            cached_embeddings(['fixture'], self.root, cache)
        with self.assertRaisesRegex(ValueError, 'end with .npz'):
            cached_embeddings(['fixture'], self.root, self.root / 'wrong')

    def test_modified_model_assets_fail_before_inference(self):
        from teacherlens.embeddings import prepare_model
        (self.root / 'onnx').mkdir()
        (self.root / 'onnx' / 'model.onnx').write_bytes(b'synthetic invalid asset')
        (self.root / 'tokenizer.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'asset checksum'):
            prepare_model(self.root)

    def test_config_validation_and_relative_paths(self):
        for change in ({'C_candidates': ()}, {'outer_folds': 1}, {'screening_thresholds': (.5, .5)},
                       {'temperatures': (float('nan'),)}, {'inner_validation_fraction': 1}, {'seed': 2**32 - 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.config, **change)
        path = self.root / 'config.json'
        path.write_text(json.dumps({'dataset_path': 'train.csv', 'output_dir': 'out'}))
        self.assertEqual(load_comparison_config(path).dataset_path, str(self.root / 'train.csv'))

    def test_full_synthetic_cv_reproducible_safe_and_tuning_excludes_outer_test(self):
        from teacherlens.comparison import fit_heads as original
        folds, _ = nested_splits(self.rows, self.config)
        calls = []

        def fit(rows, indices, C, config):
            calls.append(set(indices))
            return original(rows, indices, C, config)

        with patch('teacherlens.comparison.fit_heads', side_effect=fit):
            first = run_comparison(self.config, self.embeddings, {'data_kind': 'synthetic'}, self.descriptions)
        self.assertEqual(calls, [set(indices) for fold in folds for indices in (fold['train'], fold['development'])])
        second_path = self.root / 'second'
        second = run_comparison(replace(self.config, output_dir=str(second_path)), self.embeddings,
                                {'data_kind': 'synthetic'}, self.descriptions)
        self.assertEqual(first, second)
        self.assertTrue(verify_comparison(self.root / 'first', second_path)['passed'])
        text = (self.root / 'first' / 'report.json').read_text(encoding='utf-8')
        self.assertNotIn(self.rows[0]['StudentExplanation'], text)
        self.assertNotIn(self.rows[0]['QuestionText'], text)
        self.assertNotIn('retained_index', text)
        self.assertEqual(len(first['per_question']), 8)
        self.assertEqual(first['dataset']['retained_rows'], 16)
        positive_count = first['taxonomy']['positive_rows']
        self.assertEqual(first['binary_tfidf']['positive_rows'], positive_count)
        self.assertEqual(sum(q['misconception_rows'] for q in first['per_question']), positive_count)
        pooled_matrix = np.sum([fold['binary_tfidf']['confusion_matrix'] for fold in first['folds']], axis=0)
        np.testing.assert_array_equal(first['binary_tfidf']['confusion_matrix'], pooled_matrix)
        for oracle in first['oracle_positive_name_ranking'].values():
            self.assertEqual(oracle['rows'], positive_count)
            self.assertEqual(sum(metric['support'] for name, metric in oracle['per_class'].items()
                                 if name not in ('accuracy', 'macro avg', 'weighted avg', 'micro avg')), positive_count)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            run_comparison(self.config, self.embeddings, {}, self.descriptions)
        np.savez_compressed(second_path / 'private_oof.npz', broken=np.array([1]))
        with self.assertRaisesRegex(ValueError, 'OOF arrays'):
            verify_comparison(self.root / 'first', second_path)

    def test_saved_oof_summary_repair_restores_all_question_positives(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('summary_repair',
            Path(__file__).resolve().parents[1] / 'scripts' / 'repair_comparison_summaries.py')
        repair_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repair_module)
        original = run_comparison(self.config, self.embeddings, {'data_kind': 'synthetic'}, self.descriptions)
        path = self.root / 'first' / 'report.json'
        broken = json.loads(path.read_text(encoding='utf-8'))
        broken['binary_tfidf']['positive_rows'] = 0
        for oracle in broken['oracle_positive_name_ranking'].values():
            oracle['rows'] = 0
        path.write_text(json.dumps(broken), encoding='utf-8')
        arrays = (self.root / 'first' / 'private_oof.npz').read_bytes()
        repair_module.repair(self.root / 'first')
        restored = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(restored['binary_tfidf'], original['binary_tfidf'])
        self.assertEqual(restored['oracle_positive_name_ranking'], original['oracle_positive_name_ranking'])
        self.assertEqual((self.root / 'first' / 'private_oof.npz').read_bytes(), arrays)
        self.assertTrue(restored['reporting_correction']['fits_selection_predictions_and_fold_metrics_unchanged'])
        with self.assertRaisesRegex(ValueError, 'already has correct'):
            repair_module.repair(self.root / 'first')


if __name__ == '__main__':
    unittest.main()
