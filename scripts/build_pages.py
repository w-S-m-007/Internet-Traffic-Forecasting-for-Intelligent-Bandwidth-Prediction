"""Build GitHub Pages using only tracked static assets and the Python standard library."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(project=ROOT, output=None):
    project = Path(project).resolve()
    output = Path(output or project / '_site').resolve()
    source = project / 'web'
    manifest = json.loads((source / 'data/manifest.json').read_text())
    for name, digest in manifest['files'].items():
        path = (source / 'data' / name).resolve()
        # Ignore Git's CRLF/LF conversion, while still rejecting data edits.
        if not path.is_relative_to((source / 'data').resolve()) or hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != digest:
            raise ValueError(f'Changed or unsafe static export: {name}')
    for name in ('index.html', 'styles.css', 'app.js', 'calculations.js'):
        if not (source / name).is_file():
            raise FileNotFoundError(f'Missing site source: {name}')
    output.mkdir(parents=True, exist_ok=True)
    for name in ('index.html', 'styles.css', 'app.js', 'calculations.js'):
        shutil.copy2(source / name, output / name)
    shutil.copytree(source / 'data', output / 'data', dirs_exist_ok=True)
    downloads = output / 'downloads'
    downloads.mkdir(exist_ok=True)
    if not downloads.resolve().is_relative_to(output):
        raise ValueError(f'Unsafe published download directory: {downloads}')
    # Remove only documents published by earlier builds. Keep project originals.
    for name in ('report.pdf', 'presentation.pptx', 'presentation.pdf', 'viva-guide.pdf'):
        path = downloads / name
        if not path.resolve().is_relative_to(output):
            raise ValueError(f'Unsafe published download path: {path}')
        path.unlink(missing_ok=True)
    shutil.copy2(project / 'DATA_ATTRIBUTION.md', downloads / 'dataset-attribution.md')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    print(f'Pages site built: {output}')
    return output


if __name__ == '__main__':
    build()
