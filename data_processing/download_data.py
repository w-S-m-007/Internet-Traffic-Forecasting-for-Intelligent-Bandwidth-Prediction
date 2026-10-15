"""Restore the documented CESNET archives and institution 0 sample."""

import hashlib
import tarfile
import urllib.request
from pathlib import Path


ARCHIVES = {
    "institutions.tar.gz": "ab3e15fb8dc9b7120ddb2318795b6812",
    "times.tar.gz": "a03813763e07646ca38f17ffd53e549e",
}


def md5_file(path):
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(raw, name, checksum):
    target = raw / name
    if target.exists():
        if md5_file(target) != checksum:
            raise ValueError(f"Existing {name} has a different checksum; preserved for review")
        print(f"Already checksum verified: {name}", flush=True)
        return
    url = f"https://zenodo.org/records/13382427/files/{name}?download=1"
    partial = target.with_suffix(target.suffix + ".part")
    downloaded = last_report = 0
    digest = hashlib.md5()
    print(f"Downloading {name}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if downloaded - last_report >= 32 * 1024 * 1024:
                print(f"{name}: {downloaded / 1_000_000:.1f} MB received", flush=True)
                last_report = downloaded
    if digest.hexdigest() != checksum:
        raise ValueError(f"Checksum mismatch for {name}; partial file retained")
    partial.replace(target)
    print(f"Verified {name}: {downloaded:,} bytes", flush=True)


def extract_sample(raw, archive_name, member_name, filename):
    destination = raw / "sample" / filename
    with tarfile.open(raw / archive_name, mode="r:gz") as archive:
        for member in archive:
            if member.name != member_name:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"Cannot read {member_name}")
            with handle:
                content = handle.read()
            if destination.exists() and destination.read_bytes() != content:
                raise ValueError(f"Existing {filename} differs from archive; preserved for review")
            if not destination.exists():
                destination.write_bytes(content)
            print(f"Sample ready: {filename}; SHA256={hashlib.sha256(content).hexdigest()}", flush=True)
            return
    raise ValueError(f"Archive member absent: {member_name}")


def main():
    raw = Path(__file__).resolve().parents[1] / "data/raw/cesnet"
    (raw / "sample").mkdir(parents=True, exist_ok=True)
    for name, checksum in ARCHIVES.items():
        download(raw, name, checksum)
    extract_sample(raw, "institutions.tar.gz", "institutions/agg_10_minutes/0.csv", "institution_0.csv")
    extract_sample(raw, "times.tar.gz", "times/times_10_minutes.csv", "times_10_minutes.csv")


if __name__ == "__main__":
    main()
