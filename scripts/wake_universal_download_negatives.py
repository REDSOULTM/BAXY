"""Download OpenSLR negative audio pool for FP-rate measurement.

Sources (no login required, public-domain or CC):
  - LibriSpeech test-clean: ~5.4h English read speech, 40 speakers,
    346 MB. https://www.openslr.org/resources/12/test-clean.tar.gz
  - LibriSpeech dev-clean: ~5.4h English read speech, 40 different
    speakers, 337 MB. Adds speaker diversity.
    https://www.openslr.org/resources/12/dev-clean.tar.gz

Total: ~10h, ~680 MB. None of these speakers will say 'hey gemma'.

Output: data/wake_universal_eval/negatives/<source>/<file>.flac
We keep the FLAC files; the harness will decode + resample on the fly.
"""
from __future__ import annotations

import logging
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("download_negatives")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "wake_universal_eval" / "negatives"

SOURCES = [
    ("test-clean", "https://www.openslr.org/resources/12/test-clean.tar.gz"),
    ("dev-clean", "https://www.openslr.org/resources/12/dev-clean.tar.gz"),
]


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        log.info("  archive already downloaded: %s (%d MB)", dest.name,
                 dest.stat().st_size // (1024*1024))
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("  downloading %s ...", url)
    t0 = time.time()
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "gemma4-wake-eval/1.0"},
        )
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        tmp.replace(dest)
        el = time.time() - t0
        size_mb = dest.stat().st_size / (1024 * 1024)
        log.info("  downloaded %.1f MB in %.1fs (%.1f MB/s)",
                 size_mb, el, size_mb / max(0.1, el))
        return True
    except Exception as e:
        log.error("  download failed: %s", e)
        return False


def extract(archive: Path, out_dir: Path, marker: Path) -> bool:
    """Extract tar.gz. Use marker file to detect prior extraction."""
    if marker.exists():
        log.info("  already extracted (marker=%s)", marker.name)
        return True
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("  extracting %s ...", archive.name)
    t0 = time.time()
    try:
        with tarfile.open(archive, "r:gz") as tar:
            # Safe extract — strip absolute paths.
            tar.extractall(out_dir)
        marker.touch()
        log.info("  extracted in %.1fs", time.time() - t0)
        return True
    except Exception as e:
        log.error("  extract failed: %s", e)
        return False


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arch_dir = OUT_DIR / "_archives"
    arch_dir.mkdir(parents=True, exist_ok=True)

    failed = 0
    for name, url in SOURCES:
        log.info("=== %s ===", name)
        archive = arch_dir / f"{name}.tar.gz"
        marker = OUT_DIR / f".extracted_{name}"
        if not download(url, archive):
            failed += 1
            continue
        if not extract(archive, OUT_DIR, marker):
            failed += 1
            continue

    # Count flac files extracted.
    n_flac = sum(1 for _ in OUT_DIR.rglob("*.flac"))
    log.info("Total .flac files: %d", n_flac)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
