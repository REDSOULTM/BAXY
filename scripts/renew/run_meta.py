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


S1_DEFAULTS = {"BAXY_S1_DOUBT": "0.4", "BAXY_S1_VETO": "0.6", "BAXY_S1_CORRECT": "1"}


def system_one_setting(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """System One as scripts/run_renew.cmd starts the product for a bench: with the switch file
    %LOCALAPPDATA%\\BAXY\\renew\\system_one.off (scripts\\system_one.cmd off, the owner's) the launcher sets nothing and
    only what the bench's own environment carries counts; without it, every BAXY_S1_* not given takes the launcher's
    default (its GGUF is per machine: «default of run_renew.cmd»). The owner's switch decided whether an e2e arm ran
    with System One."""
    source = os.environ if environ is None else environ
    off_file = (Path(source.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "system_one.off").exists()
    given = {key: source[key] for key in (*S1_DEFAULTS, "BAXY_S1_GGUF", "BAXY_S1_THREADS") if source.get(key)}
    setting = dict(given) if off_file else {**S1_DEFAULTS, "BAXY_S1_GGUF": "default of run_renew.cmd", **given}
    return {"off_file": off_file, "on": bool(setting.get("BAXY_S1_GGUF")), "setting": setting}


def llama_log_facts(log: Path, started: float) -> dict[str, Any] | None:
    """What Qwen's llama-server says it loaded, from the head of its log, when the log is this run's (written after
    `started`): the GGUF, the projector and the slot's context. The log holds no text of the person."""
    try:
        if log.stat().st_mtime < started:
            return None
        with log.open(encoding="utf-8", errors="replace") as handle:
            head = [next(handle, "") for _ in range(60)]
    except OSError:
        return None
    facts: dict[str, Any] = {}
    for line in head:
        if "load_model: loading model '" in line:
            facts["gguf"] = line.split("loading model '", 1)[1].rsplit("'", 1)[0]
        elif "loaded multimodal model, '" in line:
            facts["mmproj"] = line.split("multimodal model, '", 1)[1].rsplit("'", 1)[0]
        elif "n_ctx_slot = " in line:
            value = line.split("n_ctx_slot = ", 1)[1].split(",", 1)[0].strip()
            facts["n_ctx_slot"] = int(value) if value.isdigit() else value
    return facts


def product_record(root: str | Path, run_dir: str | Path, started: float, environ: dict[str, str] | None = None,
                   ) -> dict[str, Any]:
    """What a bench that drives the real product (run_renew.cmd through the conductor) ran: the checkout, the mind's
    source, the seed, Qwen's GGUF (with its sha256), projector and context as its server's log says them, System One (as
    the launcher decides it, and whether its server really started: its log was written after `started`, a
    time.time()), the catalog the App sent (the run's mente\\catalog.configure.json) and every BAXY_* switch."""
    source = os.environ if environ is None else environ
    root = Path(root)
    mind = Path(source.get("BAXY_MIND_PYTHONPATH") or root / "src") / "baxy_mind"
    logs = Path(source.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"
    try:
        s1_started = (logs / "system-one.log").stat().st_mtime >= started
    except OSError:
        s1_started = False
    qwen = llama_log_facts(logs / "llama-server.log", started)
    if qwen and qwen.get("gguf"):
        qwen["gguf"] = fingerprint(qwen["gguf"], _cache_path())
    return {"machine": machine(), "root": str(root), "git": git_state(root), "mind_sha256": tree_sha256(mind),
            "seed": source.get("BAXY_RENEW_SEED") or "0 (default)", "qwen": qwen,
            "system_one": {**system_one_setting(source), "server_started": s1_started},
            "catalog": fingerprint(Path(run_dir) / "mente" / "catalog.configure.json"),
            "env": baxy_env(source)}
