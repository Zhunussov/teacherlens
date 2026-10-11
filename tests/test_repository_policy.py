"""Prevent accidental publication of restricted data or derived model artifacts in CI."""

from pathlib import Path, PurePosixPath
import subprocess
import unittest


class RepositoryPolicyTests(unittest.TestCase):
    def test_git_index_contains_only_allowed_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
        extensions = {'.csv', '.tsv', '.parquet', '.zip', '.joblib', '.pkl', '.pickle', '.npz', '.npy',
                      '.onnx', '.safetensors', '.pt', '.bin', '.sqlite', '.sqlite3', '.db', '.log', '.tsbuildinfo'}
        forbidden = []
        for filename in filter(None, tracked):
            path = PurePosixPath(filename)
            if filename == 'tests/fixtures/synthetic.csv':
                continue
            if (filename.startswith(('data/', 'outputs/', 'reports/private/')) or path.suffix.lower() in extensions
                    or any(part in ('node_modules', '.next', 'test-results', 'playwright-report') for part in path.parts)
                    or path.name.lower() == 'kaggle.json' or path.name.startswith('.env')):
                forbidden.append(filename)
        self.assertEqual(forbidden, [], f'Restricted/artifact filenames in Git index: {forbidden}')


if __name__ == '__main__':
    unittest.main()
