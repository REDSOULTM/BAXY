"""Inspect code_tests-002 without dumping bodies to chat.

Read-only on the Carter OS AI snapshot. Writes extract under
artifacts/goal095/extract/. Does not execute historical Python.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI")
OUT = REPO / "artifacts" / "goal095" / "extract"
BATCH_ID = "code_tests-002-carter-carter_legacy_Carter_v2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha256(rel: str) -> tuple[str | None, str | None]:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel.replace(chr(92), '/')}"],
        cwd=SOURCE,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[:200]
        return None, err
    return hashlib.sha256(proc.stdout).hexdigest(), None


def sqlite_summary(path: Path) -> dict[str, Any]:
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
        out: dict[str, Any] = {"tables": [], "table_count": len(tables)}
        for name in tables:
            info: dict[str, Any] = {"name": name}
            try:
                info["rows"] = conn.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
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


def py_outline(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    defs: list[str] = []
    imports: list[str] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            defs.append(f"{index}:{stripped[:140]}")
        elif stripped.startswith("import ") or stripped.startswith("from "):
            if len(imports) < 50:
                imports.append(f"{index}:{stripped[:140]}")
    return {
        "lines": len(lines),
        "bytes": path.stat().st_size,
        "imports": imports,
        "defs": defs,
        "head": lines[:40],
    }


def _summarize_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return type(value).__name__
    if isinstance(value, dict):
        return {
            "type": "object",
            "keys": sorted(value.keys(), key=str)[:80],
            "n_keys": len(value),
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "n": len(value),
            "elem0": _summarize_value(value[0], depth=depth + 1) if value else None,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 160:
            return value[:160] + "…"
        return value
    return type(value).__name__


def json_digest(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "error": str(exc),
            "lines": raw.count("\n") + (0 if raw.endswith("\n") else 1),
            "head": raw[:400],
        }
    digest: dict[str, Any] = {
        "lines": raw.count("\n") + (0 if raw.endswith("\n") else 1),
        "root_type": type(data).__name__,
    }
    if isinstance(data, dict):
        digest["keys"] = sorted(data.keys(), key=str)
        digest["n_keys"] = len(data)
        interesting = {}
        for key in (
            "ok",
            "pass",
            "passed",
            "fail",
            "failed",
            "status",
            "gate",
            "result",
            "verdict",
            "score",
            "n",
            "total",
            "cases",
            "checks",
            "model",
            "models",
            "backend",
            "hardcodes",
            "hits",
            "violations",
            "action_failed",
            "action_failed_count",
            "compound",
            "smoke",
            "recommendation",
            "winner",
            "chosen",
            "default",
            "latency",
            "p50",
            "p95",
            "p99",
        ):
            if key in data:
                interesting[key] = _summarize_value(data[key])
        digest["highlights"] = interesting
        leaf: dict[str, Any] = {}
        for key, value in data.items():
            if not isinstance(value, (dict, list)):
                leaf[key] = _summarize_value(value)
        digest["scalars"] = leaf
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                digest[f"list_{key}_n"] = len(value)
                digest[f"list_{key}_keys"] = sorted(value[0].keys(), key=str)
                if "ok" in value[0] or "pass" in value[0] or "status" in value[0]:
                    status_key = (
                        "ok"
                        if "ok" in value[0]
                        else "pass"
                        if "pass" in value[0]
                        else "status"
                    )
                    counts = Counter(str(item.get(status_key)) for item in value)
                    digest[f"list_{key}_{status_key}"] = dict(counts)
            if isinstance(value, dict):
                digest[f"obj_{key}_keys"] = sorted(value.keys(), key=str)[:40]
    elif isinstance(data, list):
        digest["n"] = len(data)
        if data and isinstance(data[0], dict):
            digest["elem_keys"] = sorted(data[0].keys(), key=str)
            for status_key in ("ok", "pass", "status", "result", "verdict"):
                if status_key in data[0]:
                    counts = Counter(str(item.get(status_key)) for item in data)
                    digest[status_key] = dict(counts)
    return digest


def snapshot_digest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return {
        "lines": len(lines),
        "bytes": path.stat().st_size,
        "head": lines[:30],
    }


def wal_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header = handle.read(32)
    return {
        "magic": header[:16].hex(),
        "ascii_prefix": header[:16].decode("ascii", errors="replace"),
        "size": path.stat().st_size,
    }


def main() -> int:
    batches = json.loads(
        (REPO / "artifacts" / "goal095" / "queue" / "batches.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(item for item in batches if item["batch_id"] == BATCH_ID)
    rows: list[dict[str, Any]] = []
    hash_ok = 0
    hash_miss = 0
    hash_drift = 0
    for item in batch["files"]:
        rel = item["path"]
        disk = SOURCE / rel
        rec: dict[str, Any] = {
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
        name = Path(rel).name
        if name.endswith(".db-shm") or name.endswith(".db-wal"):
            parent_name = (
                name[: -len("-shm")] if name.endswith(".db-shm") else name[: -len("-wal")]
            )
            parent = disk.with_name(parent_name)
            rec["parent_on_disk"] = parent.is_file()
            rec["parent_path"] = str(parent.relative_to(SOURCE)).replace("\\", "/")
            rec["parent_in_batch"] = False
            rec["parent_duplicate_of"] = (
                "legacy/Carter_v2/.matrix_LIVE_SAFE_skills.db"
            )
            if name.endswith(".db-wal") and disk.is_file():
                rec["wal"] = wal_header(disk)
            if parent.is_file():
                rec["parent_sqlite"] = sqlite_summary(parent)
        elif disk.is_file() and rel.endswith(".py"):
            rec["outline"] = py_outline(disk)
        elif disk.is_file() and rel.endswith(".json"):
            rec["json"] = json_digest(disk)
        elif disk.is_file() and rel.endswith(".snapshot"):
            rec["snapshot"] = snapshot_digest(disk)
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
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{BATCH_ID}.inspect.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    index_lines = [
        f"batch={BATCH_ID}",
        f"hash_ok={hash_ok} drift={hash_drift} miss={hash_miss}",
    ]
    for rec in rows:
        flag = "OK" if rec.get("hash_match") else "DRIFT"
        extra = ""
        if "json" in rec:
            extra = f" json_keys={rec['json'].get('keys')}"
        elif "outline" in rec:
            extra = f" py_lines={rec['outline']['lines']} defs={len(rec['outline']['defs'])}"
        elif rec["path"].endswith(".db-shm"):
            extra = f" shm parent_on_disk={rec.get('parent_on_disk')}"
        elif rec["path"].endswith(".db-wal"):
            extra = f" wal parent_on_disk={rec.get('parent_on_disk')}"
        index_lines.append(f"{flag} {rec['path']}{extra}")
    index_path = OUT / f"{BATCH_ID}.index.txt"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "wrote": str(out),
                "index": str(index_path),
                "hash_ok": hash_ok,
                "hash_drift": hash_drift,
                "hash_missing": hash_miss,
                "subsystem": batch.get("subsystem"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
