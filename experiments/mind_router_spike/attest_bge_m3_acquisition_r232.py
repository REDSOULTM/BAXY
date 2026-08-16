"""Attest the separately acquired BGE-M3 candidate without importing it."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_bge_m3_retrieval_r231 as r231


OUTPUT = REPO / "artifacts/audit/bge_m3_acquisition_r232.json"
EXCLUDED_PARTS = {".cache", ".locks"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not (set(path.relative_to(root).parts) & EXCLUDED_PARTS):
            yield path


def build() -> dict[str, object]:
    preregistration = json.loads(r231.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r231.build():
        raise RuntimeError("R231 preregistration identity changed")
    root = r231.CANDIDATE_ROOT
    if not root.is_dir():
        raise RuntimeError(f"candidate root missing: {root}")
    files = []
    digest = hashlib.sha256()
    for path in model_files(root):
        relative = path.relative_to(root).as_posix()
        item = {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
        files.append(item)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    config_path = root / "config.json"
    if not files or not config_path.is_file():
        raise RuntimeError("candidate download is incomplete")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return {
        "schema": "baxy.bge-m3.r232-acquisition-attestation.v1",
        "authority": "external_weights_attested_without_model_import_or_runtime_change",
        "candidate": {
            "model_id": r231.MODEL_ID,
            "revision": r231.MODEL_REVISION,
            "storage": str(root),
            "files": files,
            "file_count": len(files),
            "total_bytes": sum(int(item["bytes"]) for item in files),
            "content_merkle_sha256": digest.hexdigest(),
            "config_model_type": config.get("model_type"),
        },
        "source": {
            "preregistration": str(r231.OUTPUT.relative_to(REPO)),
            "preregistration_sha256": sha256(r231.OUTPUT),
        },
        "constraints": {
            "model_imported": False,
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": (
            "Freeze a fresh OOS population and a runner that retains raw retrieval, "
            "decision before veto and visible-text review before opening R228."
        ),
        "identities": {"program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
