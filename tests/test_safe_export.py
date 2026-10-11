import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('aggregate_export', Path(__file__).resolve().parents[1] / 'scripts' / 'export_comparison.py')
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class SafeExportTests(unittest.TestCase):
    def test_readable_matrix_serialization_preserves_exact_values(self):
        value = {'matrix': [[0, 1, 200], [4, 5, 6]], 'grid': [0.5, 1.0, 2.0],
                 'tiny': [1e-12, -2.3], 'text': ['synthetic', 'fixture']}
        serialized = EXPORT.readable_json(value)
        self.assertEqual(json.loads(serialized), value)
        self.assertIn('[0, 1, 200]', serialized)

    def test_private_fields_rejected_recursively_but_schema_allowed(self):
        EXPORT.check_aggregate({'dataset': {'column_types': {'row_id': 'string'}}})
        for field in EXPORT.FORBIDDEN:
            with self.subTest(field=field), self.assertRaises(ValueError):
                EXPORT.check_aggregate({'folds': [{field: 'synthetic private sentinel'}]})

    def test_export_excludes_private_hashes_and_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = {field: {} for field in EXPORT.REPORT_FIELDS}
            report['data_kind'] = 'synthetic'
            report['embedding'] = {'identity': {'text_sha256': 'private_input_sentinel'},
                                   'vectors_sha256': 'private_vector_sentinel',
                                   'encoding': {field: 'synthetic fixture metadata' for field in EXPORT.ENCODER_FIELDS}}
            metadata = {key: {} for key in ('python', 'versions', 'source_sha256', 'dataset_sha256')}
            metadata['config'] = {key: 'synthetic fixture setting' for key in EXPORT.CONFIG_FIELDS}
            metadata['retained_row_ids'] = ['private_row_sentinel']
            metadata['fold_manifests'] = [{'indices': [1,2]}]
            for name, value in (('report.json', report), ('experiment.json', metadata), ('verification.json', {'passed': True})):
                (root / name).write_text(json.dumps(value), encoding='utf-8')
            with patch.object(EXPORT, 'verify_comparison', return_value={'passed': True}):
                safe = EXPORT.export(root, root, root / 'safe.json', root / 'verification.json')
            text = (root / 'safe.json').read_text(encoding='utf-8')
            self.assertNotIn('private_input_sentinel', text)
            self.assertNotIn('private_vector_sentinel', text)
            self.assertNotIn('private_row_sentinel', text)
            self.assertNotIn('fold_manifests', text)
            self.assertEqual(safe['data_kind'], 'synthetic')


if __name__ == '__main__':
    unittest.main()
