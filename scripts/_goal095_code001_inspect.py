"""Inspect code_tests-001-carter without dumping bodies to chat.

Read-only on the Carter OS AI snapshot. Writes a small extract under
artifacts/goal095/extract/.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI")
OUT = REPO / "artifacts" / "goal095" / "extract"
BATCH_ID = "code_tests-001-carter"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha256(rel: str) -> tuple[str | None, str | None]:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel.replace('/', '/')}"],
        cwd=SOURCE,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[:200]
        return None, err
    return hashlib.sha256(proc.stdout).hexdigest(), None


def sqlite_summary(path: Path) -> dict:
    # Copy db + sidecars out of the source tree so WAL open cannot touch it.
    tmp = Path(tempfile.mkdtemp(prefix="goal095_sqlite_"))
    copied = tmp / path.name
    shutil.copy2(path, copied)
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    if wal.is_file():
        shutil.copy2(wal, tmp / (path.name + "-wal"))
    if shm.is_file():
        shutil.copy2(shm, tmp / (path.name + "-shm"))
    uri = copied.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"error": str(exc)}
    conn.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        out: dict = {"tables": [], "table_count": len(tables)}
        for name in tables:
            info = {"name": name}
            try:
                info["rows"] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[
                    0
                ]
            except sqlite3.Error as exc:
                info["rows_error"] = str(exc)
            try:
                cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
                info["columns"] = [dict(col)["name"] for col in cols]
            except sqlite3.Error as exc:
                info["columns_error"] = str(exc)
            out["tables"].append(info)
        return out
    finally:
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)


def py_outline(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    defs = []
    imports = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            defs.append(f"{index}:{stripped[:120]}")
        elif stripped.startswith("import ") or stripped.startswith("from "):
            if len(imports) < 40:
                imports.append(f"{index}:{stripped[:120]}")
    return {
        "lines": len(lines),
        "bytes": path.stat().st_size,
        "imports": imports,
        "defs": defs,
    }


def main() -> int:
    batches = json.loads(
        (REPO / "artifacts" / "goal095" / "queue" / "batches.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(item for item in batches if item["batch_id"] == BATCH_ID)
    rows = []
    hash_ok = 0
    hash_miss = 0
    hash_drift = 0
    for item in batch["files"]:
        rel = item["path"]
        disk = SOURCE / rel
        rec = {
            "path": rel,
            "queued_sha256": item["sha256"],
            "size_queued": item["size"],
            "exists": disk.is_file(),
        }
        if disk.is_file():
            rec["disk_sha256"] = sha256_file(disk)
            rec["disk_size"] = disk.stat().st_size
            rec["hash_match"] = rec["disk_sha256"] == item["sha256"]
            if rec["hash_match"]:
                hash_ok += 1
            else:
                hash_drift += 1
        else:
            hash_miss += 1
            rec["hash_match"] = False
        head_sha, head_err = git_blob_sha256(rel)
        rec["head_sha256"] = head_sha
        rec["head_error"] = head_err
        if head_sha:
            rec["head_matches_queue"] = head_sha == item["sha256"]
        suffix = disk.suffix.lower() if disk.is_file() else Path(rel).suffix.lower()
        name = Path(rel).name.lower()
        if disk.is_file() and (
            name.endswith(".db") or suffix in {".sqlite", ".db"}
        ):
            rec["sqlite"] = sqlite_summary(disk)
        elif disk.is_file() and rel.endswith((".py", ".ps1")):
            rec["outline"] = py_outline(disk)
        elif disk.is_file() and name.endswith(".env.example"):
            rec["outline"] = {
                "lines": len(disk.read_text(encoding="utf-8", errors="replace").splitlines())
            }
        rows.append(rec)

    payload = {
        "batch_id": BATCH_ID,
        "source_head_cmd": "git rev-parse HEAD",
        "file_count": len(rows),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "subsystem": batch.get("subsystem"),
        "subsystems": batch.get("subsystems"),
        "files": rows,
    }
    out = OUT / "code_tests-001-carter.inspect.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "wrote": str(out),
                "hash_ok": hash_ok,
                "hash_drift": hash_drift,
                "hash_missing": hash_miss,
                "subsystem": batch.get("subsystem"),
                "subsystems": batch.get("subsystems"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
