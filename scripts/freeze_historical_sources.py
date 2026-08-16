"""Freeze the finite BAXY 1.0 historical-source boundary.

The manifest never copies source content.  Git-backed trees are identified by
commit/tree plus a hashed dirty overlay; non-Git historical roots are listed by
relative path, size and SHA-256 for message/evidence-capable files.  Large model
artifacts are summarized but intentionally excluded from the message corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CUTOFF_UTC = "2026-07-14T10:51:49.1612548Z"
BAXY_CUTOFF_COMMIT = "02d999dd5141cea4a022833df3c109aeeaec6266"
LEGACY_COMMIT = "ee06786"

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".jsonl", ".ndjson", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".csv", ".tsv", ".log", ".py", ".ps1",
    ".bat", ".cmd", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".xml", ".sql", ".vtt", ".srt", ".prompt",
}
EVIDENCE_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".wav", ".flac", ".mp3", ".m4a",
    ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".pptx",
}
INCLUDED_SUFFIXES = TEXT_SUFFIXES | EVIDENCE_SUFFIXES
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
MODEL_SUFFIXES = {
    ".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".model", ".npz",
    ".npy", ".dll", ".exe", ".lib", ".pyd", ".bin",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(data)


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return process.stdout.strip()


def git_ref_snapshot(root: Path, logical_id: str, ref: str) -> dict[str, Any]:
    commit = run_git(root, "rev-parse", f"{ref}^{{commit}}")
    tree = run_git(root, "rev-parse", f"{ref}^{{tree}}")
    return {
        "id": logical_id,
        "kind": "git_ref",
        "commit": commit,
        "tree": tree,
    }


def dirty_status(root: Path) -> list[dict[str, Any]]:
    process = subprocess.run(
        [
            "git", "-C", str(root), "-c", "core.quotepath=false",
            "status", "--porcelain=v1", "-z", "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
    )
    fields = process.stdout.split(b"\0")
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(fields):
        raw = fields[index]
        index += 1
        if len(raw) < 4:
            continue
        line = raw.decode("utf-8", errors="surrogateescape")
        status = line[:2]
        rel_text = line[3:]
        # Porcelain -z emits a second path field for rename/copy records.
        if status[0] in {"R", "C"} and index < len(fields):
            index += 1
        rel = Path(rel_text)
        path = root / rel
        record: dict[str, Any] = {
            "status": status,
            "path": rel.as_posix(),
            "exists": path.is_file(),
        }
        if path.is_file():
            stat = path.stat()
            suffix = path.suffix.lower()
            hash_content = suffix in INCLUDED_SUFFIXES or (
                not suffix and stat.st_size <= 5 * 1024 * 1024
            )
            record["size"] = stat.st_size
            if hash_content:
                record["sha256"] = sha256_file(path)
            else:
                record["content_hash_scope"] = "excluded_non_message_binary"
        records.append(record)
    return records


def git_worktree_snapshot(root: Path, logical_id: str) -> dict[str, Any]:
    head = run_git(root, "rev-parse", "HEAD")
    tree = run_git(root, "rev-parse", "HEAD^{tree}")
    overlay = dirty_status(root)
    return {
        "id": logical_id,
        "kind": "git_worktree",
        "head": head,
        "head_tree": tree,
        "overlay_entries": overlay,
        "overlay_count": len(overlay),
        "overlay_sha256": canonical_digest(overlay),
    }


def walk_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        base = Path(current)
        for name in sorted(files):
            yield base / name


def file_manifest(
    root: Path,
    logical_id: str,
    *,
    include_all: bool = False,
    excluded_top_dirs: set[str] | None = None,
) -> dict[str, Any]:
    excluded_top_dirs = excluded_top_dirs or set()
    files: list[dict[str, Any]] = []
    excluded: dict[str, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "bytes": 0}
    )
    for path in walk_files(root):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in excluded_top_dirs:
            continue
        suffix = path.suffix.lower()
        stat = path.stat()
        include = include_all or suffix in INCLUDED_SUFFIXES
        if not suffix and stat.st_size <= 5 * 1024 * 1024:
            include = True
        if include:
            files.append(
                {
                    "path": rel.as_posix(),
                    "size": stat.st_size,
                    "sha256": sha256_file(path),
                }
            )
        else:
            category = "model_or_runtime" if suffix in MODEL_SUFFIXES else suffix or "no_suffix"
            excluded[category]["count"] += 1
            excluded[category]["bytes"] += stat.st_size
    files.sort(key=lambda row: row["path"].casefold())
    return {
        "id": logical_id,
        "kind": "file_manifest",
        "file_count": len(files),
        "bytes": sum(row["size"] for row in files),
        "files": files,
        "files_sha256": canonical_digest(files),
        "excluded_summary": dict(sorted(excluded.items())),
    }


def current_thread_prefix(path: Path, cutoff: datetime) -> dict[str, Any]:
    selected: list[bytes] = []
    with path.open("rb") as handle:
        for raw_line in handle:
            try:
                event = json.loads(raw_line)
                timestamp = datetime.fromisoformat(
                    str(event["timestamp"]).replace("Z", "+00:00")
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if timestamp > cutoff:
                break
            selected.append(raw_line)
    data = b"".join(selected)
    return {
        "id": "current_codex_thread_prefix",
        "kind": "append_only_prefix",
        "thread_id": "019f603d-b175-7ad1-a3ee-befd83a3ecf1",
        "cutoff_utc": CUTOFF_UTC,
        "line_count": len(selected),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def codex_root_threads_snapshot(
    sessions_root: Path,
    cutoff: datetime,
    agent_manifest_path: Path,
    *,
    skip_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Hash relevant user-owned Codex roots, excluding agent descendants."""
    agent_manifest = json.loads(agent_manifest_path.read_text(encoding="utf-8"))
    agent_ids = {str(row["session_id"]) for row in agent_manifest["records"]}
    skip_session_ids = skip_session_ids or set()
    cwd_map = {
        "baxy": "baxy",
        "probando gemma 4": "probando_gemma4",
        "functiongemma": "functiongemma",
        "carter os ai": "carter_os_ai",
    }
    records: list[dict[str, Any]] = []
    for path in sorted(sessions_root.rglob("*.jsonl"), key=lambda item: item.as_posix()):
        try:
            with path.open("rb") as handle:
                first = json.loads(handle.readline())
            payload = first.get("payload") or {}
            # In forked Codex sessions, session_id may point at the root while
            # id is the concrete child session.  Prefer id to exclude agents.
            session_id = str(payload.get("id") or payload.get("session_id") or "")
            cwd = str(payload.get("cwd") or "")
            source = payload.get("source")
            is_descendant = bool(
                payload.get("parent_id")
                or payload.get("parent_thread_id")
                or payload.get("agent_path")
                or (isinstance(source, dict) and source.get("subagent"))
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            continue
        if is_descendant or not session_id or session_id in agent_ids or session_id in skip_session_ids:
            continue
        cwd_folded = cwd.replace("/", "\\").rstrip("\\").casefold()
        cwd_id = next(
            (logical for name, logical in cwd_map.items() if cwd_folded.endswith("\\" + name)),
            None,
        )
        if cwd_id is None:
            continue
        prefix = current_thread_prefix(path, cutoff)
        if prefix["line_count"] == 0:
            continue
        records.append(
            {
                "session_id": session_id,
                "cwd_id": cwd_id,
                "line_count": prefix["line_count"],
                "bytes": prefix["bytes"],
                "sha256": prefix["sha256"],
            }
        )
    records.sort(key=lambda row: row["session_id"])
    return {
        "id": "codex_relevant_root_threads",
        "kind": "append_only_prefix_set",
        "cutoff_utc": CUTOFF_UTC,
        "thread_count": len(records),
        "bytes": sum(row["bytes"] for row in records),
        "records": records,
        "records_sha256": canonical_digest(records),
    }


def fixed_file(path: Path, logical_id: str, *, private: bool = False) -> dict[str, Any]:
    stat = path.stat()
    return {
        "id": logical_id,
        "kind": "private_digest" if private else "fixed_file",
        "size": stat.st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(repo: Path) -> dict[str, Any]:
    programacion = repo.parent
    home = Path.home()
    # Windows emitted seven fractional digits; datetime stores microseconds.
    # Preserve the exact cutoff string in the manifest and truncate only for
    # event comparison.
    cutoff = datetime.fromisoformat("2026-07-14T10:51:49.161254+00:00")
    current_thread = next(
        (home / ".codex" / "sessions" / "2026" / "07" / "14").glob(
            "*019f603d-b175-7ad1-a3ee-befd83a3ecf1.jsonl"
        )
    )
    attachment = home / ".codex" / "attachments" / (
        "002e6882-e694-4b06-bcc2-cfbee6782402"
    ) / "pasted-text.txt"

    sources: list[dict[str, Any]] = [
        git_ref_snapshot(repo, "baxy_cutoff", BAXY_CUTOFF_COMMIT),
        git_ref_snapshot(repo, "baxy_legacy_checkpoint", LEGACY_COMMIT),
        git_worktree_snapshot(programacion / "Probando Gemma 4", "probando_gemma4"),
        # These two runtime corpora are intentionally Git-ignored in the
        # historical project, so a worktree overlay cannot see them.
        fixed_file(
            programacion / "Probando Gemma 4" / "gemma4_agent" / "data" /
            "router_corpus_real_logs.jsonl",
            "probando_router_corpus_real_logs",
        ),
        fixed_file(
            programacion / "Probando Gemma 4" / "gemma4_agent" / "data" /
            "traces.jsonl",
            "probando_runtime_traces",
        ),
        file_manifest(
            programacion / "Probando Gemma 4" / "_tesis_curso" /
            "entregables",
            "probando_thesis_deliverables",
            include_all=True,
        ),
        file_manifest(
            programacion / "Probando Gemma 4" / "documentacion",
            "probando_documentation",
        ),
        git_worktree_snapshot(programacion / "Carter OS AI", "carter_os_ai"),
        file_manifest(programacion / "FunctionGemma", "functiongemma"),
        file_manifest(programacion / "Carter OS", "carter_os", include_all=True),
        file_manifest(
            home / ".gemma4",
            "gemma4_local_history",
            include_all=True,
            excluded_top_dirs={"models", "cache"},
        ),
        current_thread_prefix(current_thread, cutoff),
        codex_root_threads_snapshot(
            home / ".codex" / "sessions",
            cutoff,
            repo / "documentacion" / "agentes" / "manifest.json",
            skip_session_ids={"019f603d-b175-7ad1-a3ee-befd83a3ecf1"},
        ),
        fixed_file(attachment, "current_user_request_attachment"),
        fixed_file(
            repo / "documentacion" / "agentes" / "manifest.json",
            "agent_public_manifest",
        ),
    ]

    private_dir = repo / "documentacion" / "agentes" / "privado"
    for name, logical_id in (
        ("manifest_private.json", "agent_private_manifest"),
        ("informes_finales.jsonl", "agent_final_reports"),
    ):
        path = private_dir / name
        if path.is_file():
            sources.append(fixed_file(path, logical_id, private=True))

    payload: dict[str, Any] = {
        "schema_version": 1,
        "cutoff_utc": CUTOFF_UTC,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "sha256",
        "source_roots_are_logical": True,
        "sources": sources,
        "policy": {
            "git_roots": "commit/tree plus SHA-256 dirty overlay",
            "non_git_roots": "relative paths, sizes and SHA-256 for text/evidence files",
            "private_agent_data": "digest only; public manifest contains per-segment hashes",
            "model_artifacts": "not part of the historical-message corpus",
            "manifest_digest": "canonical payload excluding generated_at",
        },
    }
    digest_payload = dict(payload)
    digest_payload.pop("generated_at", None)
    payload["manifest_payload_sha256"] = canonical_digest(digest_payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/corpus_cutoff/source_manifest.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parent.parent
    manifest = build_manifest(repo)
    output = args.output
    if not output.is_absolute():
        output = repo / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"manifest={output}")
    print(f"sources={len(manifest['sources'])}")
    print(f"sha256={manifest['manifest_payload_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
