"""Inspect a code_tests batch without dumping bodies to chat.

Read-only on the frozen sibling snapshot. Writes extract under
artifacts/goal095/extract/. Does not execute historical Python.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_goal095_queues import FROZEN_0950, PROGRAMACION
from scripts.goal095_docs_ledger import batch_from_batches, load_json, queue_paths

OUT = REPO / "artifacts" / "goal095" / "extract"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha256(source: Path, rel: str) -> tuple[str | None, str | None]:
    if not (source / ".git").exists() and not (source / ".git").is_file():
        return None, "no-git"
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel.replace(chr(92), '/')}"],
        cwd=source,
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
            "model",
            "final_verdict",
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
                for status_key in ("ok", "pass", "passed", "status"):
                    if status_key in value[0]:
                        counts = Counter(str(item.get(status_key)) for item in value)
                        digest[f"list_{key}_{status_key}"] = dict(counts)
                        break
            if isinstance(value, dict):
                digest[f"obj_{key}_keys"] = sorted(value.keys(), key=str)[:40]
    elif isinstance(data, list):
        digest["n"] = len(data)
        if data and isinstance(data[0], dict):
            digest["elem_keys"] = sorted(data[0].keys(), key=str)
    return digest


def wal_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header = handle.read(32)
    return {
        "magic": header[:16].hex(),
        "size": path.stat().st_size,
    }


def source_root_for(source_id: str) -> Path:
    if source_id == "baxy_schema_agent":
        source_id = "baxy"
    spec = FROZEN_0950.get(source_id)
    if spec is None:
        raise SystemExit(f"unknown source_id {source_id}")
    return PROGRAMACION / spec["folder"]


def inspect_batch(repo: Path, batch_id: str) -> dict[str, Any]:
    batches_path, _ledger, _summary = queue_paths(repo)
    batches = load_json(batches_path)
    batch = batch_from_batches(batches, batch_id)
    source = source_root_for(batch.get("source_id") or "carter")
    rows: list[dict[str, Any]] = []
    hash_ok = hash_miss = hash_drift = 0
    for item in batch["files"]:
        rel = item["path"]
        disk = source / rel
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
        head_sha, head_err = git_blob_sha256(source, rel)
        rec["head_sha256"] = head_sha
        rec["head_error"] = head_err
        if head_sha:
            rec["head_matches_queue"] = head_sha == item["sha256"]
        name = Path(rel).name
        if name.endswith(".db-shm") or name.endswith(".db-wal"):
            parent_name = (
                name[: -len(".db-shm")] + ".db"
                if name.endswith(".db-shm")
                else name[: -len(".db-wal")] + ".db"
            )
            parent = disk.with_name(parent_name)
            rec["parent_on_disk"] = parent.is_file()
            rec["parent_path"] = str(parent.relative_to(source)).replace("\\", "/")
            rec["parent_in_batch"] = any(
                other["path"] == rec["parent_path"] for other in batch["files"]
            )
            if name.endswith(".db-wal") and disk.is_file():
                rec["wal"] = wal_header(disk)
            if parent.is_file():
                rec["parent_sqlite"] = sqlite_summary(parent)
        elif disk.is_file() and name.endswith(".py"):
            rec["outline"] = py_outline(disk)
        elif disk.is_file() and name.endswith(".json"):
            rec["json"] = json_digest(disk)
        elif disk.is_file() and name.endswith(".db"):
            rec["sqlite"] = sqlite_summary(disk)
        rows.append(rec)
    payload = {
        "batch_id": batch_id,
        "source_id": batch.get("source_id"),
        "source_root": f"Programacion/{source.name}",
        "file_count": len(rows),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "subsystem": batch.get("subsystem"),
        "subsystems": batch.get("subsystems"),
        "files": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{batch_id}.inspect.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    index_lines = [
        f"batch={batch_id}",
        f"hash_ok={hash_ok} drift={hash_drift} miss={hash_miss}",
    ]
    for rec in rows:
        flag = "OK" if rec.get("hash_match") else "DRIFT"
        extra = ""
        if "json" in rec:
            extra = f" json_keys={rec['json'].get('keys')}"
        elif "outline" in rec:
            extra = (
                f" py_lines={rec['outline']['lines']} defs={len(rec['outline']['defs'])}"
            )
        elif rec["path"].endswith(".db-shm"):
            extra = f" shm parent_on_disk={rec.get('parent_on_disk')}"
        elif rec["path"].endswith(".db-wal"):
            extra = f" wal parent_on_disk={rec.get('parent_on_disk')}"
        index_lines.append(f"{flag} {rec['path']}{extra}")
    index_path = OUT / f"{batch_id}.index.txt"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8", newline="\n")
    return {
        "wrote": str(out),
        "index": str(index_path),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "file_count": len(rows),
        "subsystem": batch.get("subsystem"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = inspect_batch(args.repo.resolve(), args.batch_id)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
