"""What a bench run was measured with, written into its summary (audit w8-medir, 2026-10-23).

B-MED-5 of the notebook: a run's summary named the GGUF and little else, so two runs could not be told apart by what
they measured: the catalog (its sha256), the mind's source (its commit and the hash of its files, also for a copy
without git), the judge, the server binary, the KV types, the context, the seed and temperature, System One's settings,
the kernel's confirmation mode the mind reads, the aids (BAXY_AYUDAS) and every other BAXY_* switch. Large files (a GGUF)
are hashed once and the hash is kept by path, size and modification time in a cache beside the runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

CHUNK = 8 * 2**20


def _cache_path() -> Path | None:
    banks = os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1")
    folder = Path(banks) / "runs"
    return folder / ".sha256-cache.json" if folder.is_dir() else None


def sha256_file(path: str | Path, cache: Path | None = None) -> str | None:
    """The file's sha256, or None when it cannot be read. A hash already computed for the same path, size and
    modification time is taken from `cache` (a JSON file), and a new one is kept there."""
    target = Path(path)
    try:
        stat = target.stat()
    except OSError:
        return None
    key = f"{target.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    known: dict[str, str] = {}
    if cache is not None:
        try:
            known = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            known = {}
        if key in known:
            return known[key]
    digest = hashlib.sha256()
    try:
        with target.open("rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                digest.update(block)
    except OSError:
        return None
    value = digest.hexdigest()
    if cache is not None:
        known[key] = value
        try:
            cache.write_text(json.dumps(known, indent=0), encoding="utf-8")
        except OSError:
            pass
    return value


def fingerprint(path: str | Path | None, cache: Path | None = None) -> dict[str, Any] | None:
    """{path, bytes, sha256} of a file the run read (None when no path was given)."""
    if not path:
        return None
    target = Path(path)
    try:
        size = target.stat().st_size
    except OSError:
        return {"path": str(path), "bytes": None, "sha256": None}
    return {"path": str(path), "bytes": size, "sha256": sha256_file(target, cache)}


def tree_sha256(folder: str | Path, patterns: tuple[str, ...] = ("*.py", "*.json")) -> str | None:
    """One sha256 over a source folder's files (their paths relative to it and their bytes, in order): the same code
    gives the same hash, in a worktree or in a copy without git (holdout v4: the minds of 86991ca9d with their seed
    patched lived in F:\\BAXYeval\\renew_v4\\arr)."""
    root = Path(folder)
    if not root.is_dir():
        return None
    files = sorted({p for pattern in patterns for p in root.rglob(pattern)
                    if p.is_file() and "__pycache__" not in p.parts})
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_state(folder: str | Path) -> dict[str, Any] | None:
    """The commit a folder is checked out at and whether its tracked files differ from it (None outside git)."""
    def git(*args: str) -> str | None:
        try:
            done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    commit = git("rev-parse", "HEAD")
    if not commit:
        return None
    changed = git("status", "--porcelain", "--untracked-files=no", "--", ".")
    return {"commit": commit, "dirty": bool(changed)}


def baxy_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Every BAXY_* variable the run saw: the switches (BAXY_AYUDAS, BAXY_RENEW_PREFILL, BAXY_S1_*, BAXY_CONFIRM_FLOOR…)
    and the paths."""
    source = os.environ if environ is None else environ
    return {key: value for key, value in sorted(source.items()) if key.upper().startswith("BAXY_")}


def confirmation_mode(environ: dict[str, str] | None = None) -> str:
    """The kernel's confirmation mode as the mind reads it for System One's «corrige» (mind._bypass): the file
    «confirmation-mode» of BAXY_DATA_DIR, or of %LOCALAPPDATA%\\BAXY\\1 (the owner's own)."""
    source = os.environ if environ is None else environ
    root = (source.get("BAXY_DATA_DIR", "").strip()
            or str(Path(source.get("LOCALAPPDATA", ".")) / "BAXY" / "1"))
    try:
        word = (Path(root) / "confirmation-mode").read_text(encoding="utf-8-sig").strip().lower()
    except FileNotFoundError:
        return "normal"
    except (OSError, UnicodeDecodeError):
        return "unreadable"
    return "bypass" if word in ("bypass", "all") else "normal"


def machine() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname()
