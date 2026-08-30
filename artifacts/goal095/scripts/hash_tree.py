"""SHA-256 inventory of a directory tree. Read-only. Does not follow reparse points."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def sha256_file(path: str, bufsize: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(bufsize)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path(sys.argv[1])
    out_jsonl = Path(sys.argv[2])
    out_summary = Path(sys.argv[3])
    skip_git = "--skip-git" in sys.argv
    t0 = time.perf_counter()
    rows: list[dict] = []
    errors: list[str] = []
    bytes_ = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        if skip_git:
            dirnames[:] = [d for d in dirnames if d != ".git"]
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                st = os.lstat(full)
            except OSError as exc:
                errors.append(f"{rel}: lstat {exc}")
                continue
            if os.path.islink(full):
                rows.append(
                    {
                        "path": rel,
                        "kind": "symlink",
                        "size": 0,
                        "mtime_unix": st.st_mtime,
                        "sha256": None,
                        "target": os.readlink(full),
                    }
                )
                continue
            try:
                digest = sha256_file(full)
            except OSError as exc:
                errors.append(f"{rel}: hash {exc}")
                continue
            rows.append(
                {
                    "path": rel,
                    "kind": "file",
                    "size": st.st_size,
                    "mtime_unix": st.st_mtime,
                    "sha256": digest,
                }
            )
            bytes_ += st.st_size
    rows.sort(key=lambda r: r["path"])
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    manifest_hasher = hashlib.sha256()
    with out_jsonl.open("rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            manifest_hasher.update(chunk)
    summary = {
        "root_name": root.name,
        "files": len(rows),
        "bytes": bytes_,
        "error_count": len(errors),
        "errors": errors[:50],
        "manifest_sha256": manifest_hasher.hexdigest(),
        "manifest_lines": len(rows),
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "skip_git": skip_git,
    }
    out_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
