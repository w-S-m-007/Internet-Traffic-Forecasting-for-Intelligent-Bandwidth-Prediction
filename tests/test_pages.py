"""Static builds must work without training data and reject corrupted exports."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_pages import build


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = self.root / 'web/data'
        data.mkdir(parents=True)
        (data / 'metadata.json').write_text('{}')
        (data / 'manifest.json').write_text(json.dumps({'files': {'metadata.json': hashlib.sha256(b'{}').hexdigest()}}))
        for name in ('index.html', 'styles.css', 'app.js', 'calculations.js'):
            (self.root / 'web' / name).write_text('test asset')
        (self.root / 'DATA_ATTRIBUTION.md').write_bytes(b'fixture')

    def test_build_without_raw_data_models_or_result_directories(self):
        output = build(self.root)
        self.assertEqual((output / 'index.html').read_text(), 'test asset')
        self.assertEqual([p.name for p in (output / 'downloads').iterdir()], ['dataset-attribution.md'])
        self.assertTrue((output / '.nojekyll').is_file())
        self.assertFalse((output / 'VirtEnv').exists())

    def test_rebuild_removes_old_published_documents_and_preserves_originals(self):
        documents = {
            'report.pdf': 'deliverables/report/project_report.pdf',
            'presentation.pptx': 'deliverables/presentation/project_presentation.pptx',
            'presentation.pdf': 'deliverables/presentation/project_presentation.pdf',
            'viva-guide.pdf': 'output/pdf/viva_and_code_guide.pdf',
        }
        output = self.root / '_site'
        downloads = output / 'downloads'
        downloads.mkdir(parents=True)
        for name, relative in documents.items():
            original = self.root / relative
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(b'original document')
            (downloads / name).write_bytes(b'previously published document')
        (downloads / 'unrelated.txt').write_text('keep')

        build(self.root)

        for name, relative in documents.items():
            self.assertFalse((downloads / name).exists())
            self.assertEqual((self.root / relative).read_bytes(), b'original document')
        self.assertEqual((downloads / 'unrelated.txt').read_text(), 'keep')
        self.assertEqual((downloads / 'dataset-attribution.md').read_bytes(), b'fixture')

    def test_changed_export_is_rejected(self):
        (self.root / 'web/data/metadata.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'Changed'):
            build(self.root)

    def test_windows_and_linux_line_endings_have_the_same_checksum(self):
        data = self.root / 'web/data'
        canonical = b'{\n  "value": 1\n}\n'
        (data / 'manifest.json').write_text(json.dumps({
            'files': {'metadata.json': hashlib.sha256(canonical).hexdigest()}
        }))
        for ending in (b'\n', b'\r\n'):
            with self.subTest(ending=ending):
                (data / 'metadata.json').write_bytes(canonical.replace(b'\n', ending))
                build(self.root)

    def test_changed_data_is_rejected_with_windows_line_endings(self):
        data = self.root / 'web/data'
        canonical = b'{\n  "value": 1\n}\n'
        (data / 'manifest.json').write_text(json.dumps({
            'files': {'metadata.json': hashlib.sha256(canonical).hexdigest()}
        }))
        (data / 'metadata.json').write_bytes(canonical.replace(b'1', b'2').replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(ValueError, 'Changed'):
            build(self.root)

    def test_manifest_path_cannot_escape_data_directory(self):
        path = self.root / 'web/data/manifest.json'
        path.write_text(json.dumps({'files': {'../../DATA_ATTRIBUTION.md': hashlib.sha256(b'fixture').hexdigest()}}))
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            build(self.root)

    def test_missing_site_asset_is_rejected(self):
        (self.root / 'web/app.js').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'app.js'):
            build(self.root)


if __name__ == '__main__':
    unittest.main()
