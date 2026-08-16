"""Exporta de forma reproducible las sesiones de subagentes de un hilo Codex.

La copia privada conserva el segmento exacto de cada subagente desde su
NEW_TASK, incluyendo tool calls y outputs. El manifiesto versionable no copia
contenido de mensajes ni argumentos potencialmente sensibles.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ROOT_THREAD = "019f5027-c684-75a1-a47b-5af2edd2339b"


@dataclass(frozen=True)
class SessionMeta:
    session_id: str
    parent_id: str | None
    depth: int | None
    agent_path: str | None
    nickname: str | None
    timestamp: str | None
    cwd: str | None
    path: Path
    source_bytes: int


def _json(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _first_session_meta(path: Path) -> SessionMeta | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for _ in range(4):
                line = stream.readline()
                if not line:
                    break
                item = _json(line)
                if not item or item.get("type") != "session_meta":
                    continue
                payload = item.get("payload") or {}
                source = payload.get("source")
                spawn: dict[str, Any] = {}
                if isinstance(source, dict):
                    subagent = source.get("subagent")
                    if isinstance(subagent, dict):
                        candidate = subagent.get("thread_spawn")
                        if isinstance(candidate, dict):
                            spawn = candidate
                session_id = payload.get("id") or payload.get("session_id")
                if not isinstance(session_id, str):
                    return None
                return SessionMeta(
                    session_id=session_id,
                    parent_id=spawn.get("parent_thread_id"),
                    depth=spawn.get("depth"),
                    agent_path=spawn.get("agent_path"),
                    nickname=spawn.get("agent_nickname"),
                    timestamp=payload.get("timestamp"),
                    cwd=payload.get("cwd"),
                    path=path,
                    source_bytes=path.stat().st_size,
                )
    except OSError:
        return None
    return None


def _discover_sessions(root: Path) -> dict[str, SessionMeta]:
    sessions: dict[str, SessionMeta] = {}
    for path in root.rglob("*.jsonl"):
        meta = _first_session_meta(path)
        if meta is not None:
            sessions[meta.session_id] = meta
    return sessions


def _descendants(
    sessions: dict[str, SessionMeta], root_thread_id: str
) -> list[SessionMeta]:
    children: dict[str, list[SessionMeta]] = {}
    for meta in sessions.values():
        if meta.parent_id:
            children.setdefault(meta.parent_id, []).append(meta)

    result: list[SessionMeta] = []
    queue: deque[str] = deque([root_thread_id])
    seen: set[str] = set()
    while queue:
        parent = queue.popleft()
        for child in sorted(
            children.get(parent, []),
            key=lambda item: (item.timestamp or "", item.session_id),
        ):
            if child.session_id in seen:
                continue
            seen.add(child.session_id)
            result.append(child)
            queue.append(child.session_id)
    return result


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def _is_task_marker(item: dict[str, Any], agent_path: str | None) -> bool:
    if item.get("type") != "response_item":
        return False
    payload = item.get("payload") or {}
    if payload.get("type") != "agent_message":
        return False
    if agent_path and payload.get("recipient") != agent_path:
        return False
    text = _content_text(payload.get("content"))
    return "Message Type: NEW_TASK" in text


def _export_session(
    meta: SessionMeta, private_sessions: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    target = private_sessions / f"{meta.session_id}.jsonl.gz"
    digest = hashlib.sha256()
    started = False
    marker_found = False
    segment_lines = 0
    segment_bytes = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    messages: list[dict[str, str | None]] = []
    reasoning_summaries: list[str] = []
    tool_names: Counter[str] = Counter()
    task_complete_count = 0
    patch_count = 0

    with meta.path.open("r", encoding="utf-8", errors="replace") as source:
        with gzip.open(target, "wt", encoding="utf-8", newline="\n") as output:
            for line in source:
                item = _json(line)
                if not started and item and _is_task_marker(item, meta.agent_path):
                    started = True
                    marker_found = True
                if not started:
                    continue

                normalized = line if line.endswith("\n") else line + "\n"
                encoded = normalized.encode("utf-8")
                output.write(normalized)
                digest.update(encoded)
                segment_lines += 1
                segment_bytes += len(encoded)

                if not item:
                    continue
                timestamp = item.get("timestamp")
                if isinstance(timestamp, str):
                    first_timestamp = first_timestamp or timestamp
                    last_timestamp = timestamp
                kind = item.get("type")
                payload = item.get("payload") or {}
                payload_type = payload.get("type")

                if kind == "event_msg" and payload_type == "agent_message":
                    message = payload.get("message")
                    if isinstance(message, str):
                        messages.append(
                            {
                                "timestamp": timestamp,
                                "phase": payload.get("phase"),
                                "text": message,
                            }
                        )
                elif kind == "event_msg" and payload_type == "agent_reasoning":
                    summary = payload.get("text")
                    if isinstance(summary, str):
                        reasoning_summaries.append(summary)
                elif (
                    kind == "response_item"
                    and payload_type in {"custom_tool_call", "function_call"}
                ):
                    name = payload.get("name")
                    if isinstance(name, str):
                        tool_names[name] += 1
                elif kind == "event_msg" and payload_type == "task_complete":
                    task_complete_count += 1
                elif kind == "event_msg" and payload_type == "patch_apply_end":
                    patch_count += 1

    final_answers = [
        item["text"] for item in messages if item.get("phase") == "final_answer"
    ]
    status = "completed" if task_complete_count and final_answers else "interrupted"
    if not marker_found:
        status = "unrecovered"

    private_record = {
        "session_id": meta.session_id,
        "parent_id": meta.parent_id,
        "depth": meta.depth,
        "agent_path": meta.agent_path,
        "nickname": meta.nickname,
        "status": status,
        "source_path": str(meta.path),
        "source_bytes": meta.source_bytes,
        "segment_path": str(target),
        "segment_lines": segment_lines,
        "segment_bytes": segment_bytes,
        "segment_sha256": digest.hexdigest() if marker_found else None,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "messages": messages,
        "reasoning_summaries": reasoning_summaries,
        "tool_calls": dict(sorted(tool_names.items())),
        "patch_count": patch_count,
        "task_complete_count": task_complete_count,
        "final_answers": final_answers,
    }
    safe_record = {
        key: value
        for key, value in private_record.items()
        if key
        not in {
            "messages",
            "reasoning_summaries",
            "final_answers",
            "segment_path",
        }
    }
    safe_record["final_answer_count"] = len(final_answers)
    safe_record["message_count"] = len(messages)
    safe_record["reasoning_summary_count"] = len(reasoning_summaries)
    return safe_record, private_record


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def _write_index(
    path: Path,
    root_thread_id: str,
    records: list[dict[str, Any]],
    source_total: int,
    private_total: int,
) -> None:
    statuses = Counter(item["status"] for item in records)
    depths = Counter(str(item["depth"]) for item in records)
    lines = [
        "# Índice recuperado de subagentes Codex",
        "",
        f"- Hilo raíz: {root_thread_id}",
        f"- Sesiones descendientes: {len(records)}",
        f"- Tamaño bruto referenciado: {source_total / 1024**3:.2f} GiB",
        f"- Segmentos privados recuperados: {private_total / 1024**2:.2f} MiB sin comprimir",
        f"- Estados: {dict(sorted(statuses.items()))}",
        f"- Profundidades: {dict(sorted(depths.items()))}",
        "",
        "Los informes y segmentos completos están en documentacion/agentes/privado,",
        "ignorado por Git por contener comandos, outputs y contexto potencialmente",
        "sensible. Este índice y manifest.json son la vista sanitizada.",
        "",
        "| # | Agente | Alias | Prof. | Estado | Tools | Informes finales |",
        "|---:|---|---|---:|---|---:|---:|",
    ]
    for index, item in enumerate(records, start=1):
        lines.append(
            "| {index} | {agent} | {nickname} | {depth} | {status} | "
            "{tools} | {finals} |".format(
                index=index,
                agent=item.get("agent_path") or "",
                nickname=(item.get("nickname") or "").replace("|", "/"),
                depth=item.get("depth") or "",
                status=item["status"],
                tools=sum(item.get("tool_calls", {}).values()),
                finals=item.get("final_answer_count", 0),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-thread-id", default=DEFAULT_ROOT_THREAD)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    output = repo / "documentacion" / "agentes"
    private = output / "privado"
    private_sessions = private / "sesiones"

    repo_resolved = repo.resolve()
    private_resolved = private.resolve()
    try:
        private_resolved.relative_to(repo_resolved)
    except ValueError as exc:
        raise SystemExit(
            f"Ruta privada fuera del repositorio; se cancela: {private_resolved}"
        ) from exc
    if private_resolved.name != "privado":
        raise SystemExit(f"Destino privado inesperado; se cancela: {private_resolved}")

    if private.exists() and not args.force:
        raise SystemExit(
            f"{private} ya existe. Usa --force para regenerar el export privado."
        )
    if private.exists():
        shutil.rmtree(private)
    private_sessions.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    sessions = _discover_sessions(args.codex_home / "sessions")
    descendants = _descendants(sessions, args.root_thread_id)
    root_meta = sessions.get(args.root_thread_id)
    if root_meta is None:
        raise SystemExit(f"No se encontró el hilo raíz {args.root_thread_id}")

    with root_meta.path.open("rb") as source:
        with gzip.open(private / "hilo_raiz.jsonl.gz", "wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)

    safe_records: list[dict[str, Any]] = []
    private_records: list[dict[str, Any]] = []
    for position, meta in enumerate(descendants, start=1):
        safe, full = _export_session(meta, private_sessions)
        safe["position"] = position
        full["position"] = position
        safe_records.append(safe)
        private_records.append(full)

    generated_at = datetime.now(timezone.utc).isoformat()
    source_total = sum(item.source_bytes for item in descendants)
    private_total = sum(item["segment_bytes"] for item in safe_records)
    summary = {
        "schema_version": 1,
        "generated_at": generated_at,
        "root_thread_id": args.root_thread_id,
        "root_source_path": str(root_meta.path),
        "root_source_bytes": root_meta.source_bytes,
        "sessions_scanned": len(sessions),
        "descendant_sessions": len(descendants),
        "direct_children": sum(
            item.parent_id == args.root_thread_id for item in descendants
        ),
        "source_bytes": source_total,
        "private_segment_bytes_uncompressed": private_total,
        "records": safe_records,
    }
    _write_json(output / "manifest.json", summary)
    _write_json(private / "manifest_private.json", {**summary, "records": private_records})
    _write_jsonl(private / "informes_finales.jsonl", private_records)
    _write_index(
        output / "INDICE.md",
        args.root_thread_id,
        safe_records,
        source_total,
        private_total,
    )

    print(
        json.dumps(
            {
                "root_thread_id": args.root_thread_id,
                "descendants": len(descendants),
                "direct_children": summary["direct_children"],
                "source_gib": round(source_total / 1024**3, 2),
                "private_segment_mib": round(private_total / 1024**2, 2),
                "status_counts": dict(
                    sorted(Counter(item["status"] for item in safe_records).items())
                ),
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
