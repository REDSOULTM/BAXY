"""Download curated Piper voices for the universal wake-word eval set.

Idempotent: re-runs skip voices already present. Uses urllib (stdlib,
no extra deps). Each voice is 2 files: <name>.onnx + <name>.onnx.json.

Output: data/wake_universal_eval/voices/<voice_name>.onnx[.json]
"""
from __future__ import annotations

import logging
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from wake_universal_voices import HELD_OUT_VOICES, base_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("download_voices")

OUT_DIR = ROOT / "data" / "wake_universal_eval" / "voices"


def download(url: str, dest: Path, max_retries: int = 3) -> bool:
    """Download with retry. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "gemma4-wake-eval/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return True
        except urllib.error.HTTPError as e:
            log.warning("HTTP %d on %s (attempt %d/%d)",
                        e.code, url, attempt, max_retries)
            if e.code == 404:
                return False
        except Exception as e:
            log.warning("error on %s: %s (attempt %d/%d)",
                        url, e, attempt, max_retries)
        time.sleep(2 ** attempt)
    return False


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %d voices to %s", len(HELD_OUT_VOICES), OUT_DIR)
    ok = 0
    fail = 0
    for i, spec in enumerate(HELD_OUT_VOICES, 1):
        onnx_dest = OUT_DIR / spec.filename
        json_dest = OUT_DIR / spec.config_filename
        already = onnx_dest.exists() and json_dest.exists()
        if already:
            log.info("[%d/%d] %s — already present", i, len(HELD_OUT_VOICES), spec.voice_name)
            ok += 1
            continue
        onnx_url = base_url(spec, "onnx")
        json_url = base_url(spec, "onnx.json")
        log.info("[%d/%d] %s ...", i, len(HELD_OUT_VOICES), spec.voice_name)
        s1 = download(onnx_url, onnx_dest)
        s2 = download(json_url, json_dest)
        if s1 and s2:
            ok += 1
            log.info("  OK (%d bytes)", onnx_dest.stat().st_size)
        else:
            fail += 1
            log.error("  FAILED (onnx=%s json=%s)", s1, s2)
            # Clean partial
            for p in (onnx_dest, json_dest):
                if p.exists() and p.stat().st_size == 0:
                    p.unlink()
    log.info("Done: %d ok, %d failed", ok, fail)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
