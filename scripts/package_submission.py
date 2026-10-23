"""Create a local submission ZIP with a SHA256 manifest, without credentials or environments."""
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.verify_results import check_verification_manifest

ROOT = Path(__file__).resolve().parents[1]


def main():
    required = ['deliverables/report/project_report.docx', 'deliverables/report/project_report.pdf',
                'deliverables/presentation/project_presentation.pptx',
                'deliverables/demo/dashboard_demo.webm', 'results/comparison/final_verification.json']
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError('Submission not complete: ' + ', '.join(missing))
    verify = json.loads((ROOT / 'results/comparison/final_verification.json').read_text())
    if verify.get('status') != 'PASS' or not verify.get('checkpoint_replay'):
        raise ValueError('Checkpoint verification must pass before packaging')
    check_verification_manifest(ROOT, verify)
    folders = ('data_processing','models','experiments','dashboard','scripts','tests','.streamlit','docs',
               'deliverables/report','deliverables/presentation','deliverables/demo','results/baselines',
               'results/lstm','results/gru','results/transformer','results/allocation/10min',
               'results/comparison','results/dashboard','data/prepared','data/raw/cesnet/sample')
    files = set()
    for folder in folders:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.log') and not any(part in ('node_modules','build','.build','_build','renders','preview') for part in path.relative_to(ROOT).parts):
                files.add(path)
    for pattern in ('*.md','*.txt','.gitignore','.gitattributes','requirements*.txt'):
        files.update(p for p in ROOT.glob(pattern) if p.is_file())
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    out = ROOT / 'deliverables/submission'
    out.mkdir(parents=True, exist_ok=True)
    record = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'files': manifest,
              'note': 'Local submission bundle; raw sample attribution in DATA_ATTRIBUTION.md. No environment, Git metadata, credentials or full source archives.'}
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    target = out / 'traffic_forecasting_submission.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(out / 'manifest.json', 'manifest.json')
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity check failed')
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f'Packaged file hash mismatch: {name}')
    print(f'Packaged and verified {len(files)} files: {target} ({target.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
