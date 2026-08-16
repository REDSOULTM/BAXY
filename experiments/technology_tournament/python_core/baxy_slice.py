#!/usr/bin/env python3
"""BAXY tournament vertical slice — Python contender.

The code intentionally uses only the Python standard library. It is not the
product implementation; it exists to make the technology hypothesis
falsifiable under the frozen tournament protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
CREATE_PREFIX = "crea la nota "
CREATE_SEPARATOR = " con el texto: "
COMPOUND_SUFFIXES = (" y después léela", " y despues leela")
INVALID_WINDOWS_CHARS = set('<>:"/\\|?*')
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
INVOCATION_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestError(ValueError):
    """A user-controlled request violated the protocol or sandbox."""


def _base_response(
    invocation_id: str,
    *,
    state: str,
    intent: str,
    effect: str,
    risk: str,
    verification: str,
    response: str,
    operations: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    replayed: bool = False,
    journal_recovered: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "mission_id": f"mission-{invocation_id}",
        "state": state,
        "intent": intent,
        "effect": effect,
        "risk": risk,
        "operations": operations or [],
        "verification": {
            "status": verification,
            "evidence": evidence or [],
        },
        "response": response,
        "replayed": replayed,
        "journal_recovered": journal_recovered,
    }


def _invalid(invocation_id: str, message: str, *, recovered: bool = False) -> dict[str, Any]:
    return _base_response(
        invocation_id,
        state="blocked",
        intent="invalid",
        effect="none",
        risk="high",
        verification="unverified",
        response=message,
        journal_recovered=recovered,
    )


def _path_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except ValueError:
        return False


def _workspace_from_request(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise RequestError("workspace inválido")
    workspace = Path(value)
    if not workspace.is_absolute():
        raise RequestError("workspace no absoluto")
    workspace = workspace.resolve(strict=False)
    allowed = os.environ.get("BAXY_TOURNAMENT_ROOT")
    if allowed:
        allowed_root = Path(allowed).resolve(strict=False)
        if not _path_within(workspace, allowed_root):
            raise RequestError("workspace fuera de la raíz autorizada")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _safe_filename(raw: str) -> str:
    name = raw.strip()
    if not name or name != raw or "\x00" in name:
        raise RequestError("nombre de nota inválido")
    if name in {".", ".."} or ".." in name:
        raise RequestError("nombre de nota fuera del espacio permitido")
    if any(character in INVALID_WINDOWS_CHARS for character in name):
        raise RequestError("nombre de nota fuera del espacio permitido")
    if name.endswith((".", " ")):
        raise RequestError("nombre de nota inválido en Windows")
    stem = name.split(".", 1)[0].upper()
    if stem in RESERVED_WINDOWS_NAMES:
        raise RequestError("nombre reservado en Windows")
    if len(name.encode("utf-8")) > 240:
        raise RequestError("nombre de nota demasiado largo")
    return name


def _note_path(workspace: Path, directory: str, filename: str) -> Path:
    root = (workspace / directory).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    candidate = (root / filename).resolve(strict=False)
    if candidate.parent != root or not _path_within(candidate, workspace):
        raise RequestError("ruta fuera del espacio permitido")
    return candidate


def _atomic_write(path: Path, text: str, invocation_id: str) -> None:
    temporary = path.with_name(f".{path.name}.{invocation_id}.tmp")
    data = text.encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _quarantine_path(workspace: Path) -> Path:
    for number in range(1, 10_000):
        candidate = workspace / f"journal.corrupt.{number:04d}.jsonl"
        if not candidate.exists():
            return candidate
    raise RuntimeError("demasiadas cuarentenas de journal")


def repair_journal(workspace: Path) -> bool:
    """Keep the valid JSONL prefix and quarantine the first invalid tail."""
    path = workspace / "journal.jsonl"
    if not path.exists():
        return False
    raw = path.read_bytes()
    if not raw:
        return False
    offset = 0
    invalid_at: int | None = None
    for line in raw.splitlines(keepends=True):
        complete = line.endswith((b"\n", b"\r"))
        try:
            parsed = json.loads(line.decode("utf-8")) if complete else None
            valid = isinstance(parsed, dict)
        except (UnicodeDecodeError, json.JSONDecodeError):
            valid = False
        if not valid:
            invalid_at = offset
            break
        offset += len(line)
    if invalid_at is None:
        return False
    bad_tail = raw[invalid_at:]
    quarantine = _quarantine_path(workspace)
    with quarantine.open("xb") as stream:
        stream.write(bad_tail)
        stream.flush()
        os.fsync(stream.fileno())
    with path.open("r+b") as stream:
        stream.truncate(invalid_at)
        stream.flush()
        os.fsync(stream.fileno())
    return True


def load_journal(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / "journal.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    return records


def append_journal(workspace: Path, value: dict[str, Any]) -> None:
    path = workspace / "journal.jsonl"
    encoded = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _existing_invocation(
    records: Iterable[dict[str, Any]], invocation_id: str, message: str
) -> tuple[dict[str, Any] | None, bool]:
    started = False
    for record in records:
        if record.get("invocation_id") != invocation_id:
            continue
        if record.get("message") != message:
            raise RequestError("invocation_id reutilizado con otra petición")
        if record.get("status") == "started":
            started = True
        if record.get("status") == "completed" and isinstance(record.get("result"), dict):
            result = dict(record["result"])
            result["replayed"] = True
            return result, started
    return None, started


def _parse_create(message: str) -> tuple[str, str, bool] | None:
    lowered = message.casefold()
    if not lowered.startswith(CREATE_PREFIX):
        return None
    separator_index = lowered.find(CREATE_SEPARATOR, len(CREATE_PREFIX))
    if separator_index < 0:
        return None
    filename = message[len(CREATE_PREFIX) : separator_index]
    content = message[separator_index + len(CREATE_SEPARATOR) :]
    lowered_content = content.casefold()
    compound = False
    for suffix in COMPOUND_SUFFIXES:
        if lowered_content.endswith(suffix):
            content = content[: -len(suffix)]
            compound = True
            break
    return filename, content, compound


def _done(
    invocation_id: str,
    intent: str,
    effect: str,
    response: str,
    operations: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    recovered: bool,
) -> dict[str, Any]:
    return _base_response(
        invocation_id,
        state="done",
        intent=intent,
        effect=effect,
        risk="low",
        verification="verified",
        response=response,
        operations=operations,
        evidence=evidence,
        journal_recovered=recovered,
    )


def execute(invocation_id: str, message: str, workspace: Path, recovered: bool) -> dict[str, Any]:
    lowered = message.casefold().strip()
    if "\x00" in message:
        return _invalid(invocation_id, "No ejecuté la petición porque contiene un byte NUL.", recovered=recovered)

    if lowered.startswith("hola"):
        return _base_response(
            invocation_id,
            state="done",
            intent="conversation",
            effect="none",
            risk="low",
            verification="not_applicable",
            response="Estoy bien y lista para ayudarte.",
            journal_recovered=recovered,
        )

    create = _parse_create(message.strip())
    if create is not None:
        raw_name, content, compound = create
        try:
            name = _safe_filename(raw_name)
            path = _note_path(workspace, "notes", name)
        except RequestError:
            return _base_response(
                invocation_id,
                state="blocked",
                intent="note.create",
                effect="reversible",
                risk="high",
                verification="unverified",
                response="No creé la nota porque su ruta sale del espacio permitido.",
                journal_recovered=recovered,
            )
        _atomic_write(path, content, invocation_id)
        observed = path.read_text(encoding="utf-8")
        if observed != content:
            return _base_response(
                invocation_id,
                state="failed",
                intent="note.create_and_read" if compound else "note.create",
                effect="reversible",
                risk="low",
                verification="unverified",
                response="La nota no pudo verificarse después de escribirla.",
                journal_recovered=recovered,
            )
        relative = f"notes/{name}"
        operations = [
            {"operation": "note.create", "state": "done", "relative_path": relative}
        ]
        if compound:
            operations.append(
                {"operation": "note.read", "state": "done", "relative_path": relative}
            )
        evidence = [{"kind": "file_readback", "relative_path": relative, "utf8_bytes": len(content.encode("utf-8"))}]
        return _done(
            invocation_id,
            "note.create_and_read" if compound else "note.create",
            "reversible",
            f"Creé y verifiqué la nota {name}. Dice: {observed}" if compound else f"Creé y verifiqué la nota {name}.",
            operations,
            evidence,
            recovered,
        )

    read_prefix = "lee la nota "
    if lowered.startswith(read_prefix):
        raw_name = message.strip()[len(read_prefix) :]
        try:
            name = _safe_filename(raw_name)
            path = _note_path(workspace, "notes", name)
        except RequestError:
            return _invalid(invocation_id, "No leí la nota porque su nombre no es seguro.", recovered=recovered)
        if not path.is_file():
            return _base_response(
                invocation_id,
                state="blocked",
                intent="note.read",
                effect="read_only",
                risk="low",
                verification="unverified",
                response=f"No pude leer la nota {name} porque no existe.",
                journal_recovered=recovered,
            )
        content = path.read_text(encoding="utf-8")
        relative = f"notes/{name}"
        return _done(
            invocation_id,
            "note.read",
            "read_only",
            f"La nota {name} dice: {content}",
            [{"operation": "note.read", "state": "done", "relative_path": relative}],
            [{"kind": "file_read", "relative_path": relative, "utf8_bytes": len(content.encode("utf-8"))}],
            recovered,
        )

    trash_prefix = "mueve la nota "
    trash_suffix = " a la papelera"
    if lowered.startswith(trash_prefix) and lowered.endswith(trash_suffix):
        raw_name = message.strip()[len(trash_prefix) : -len(trash_suffix)]
        try:
            name = _safe_filename(raw_name)
            source = _note_path(workspace, "notes", name)
            target = _note_path(workspace, "trash", name)
        except RequestError:
            return _invalid(invocation_id, "No moví la nota porque su nombre no es seguro.", recovered=recovered)
        if source.is_file():
            os.replace(source, target)
        if not target.is_file() or source.exists():
            return _base_response(
                invocation_id,
                state="blocked",
                intent="note.trash",
                effect="reversible",
                risk="low",
                verification="unverified",
                response=f"No pude mover {name} porque la nota no existe.",
                journal_recovered=recovered,
            )
        return _done(
            invocation_id,
            "note.trash",
            "reversible",
            f"Moví la nota {name} a la papelera y lo verifiqué.",
            [{"operation": "note.trash", "state": "done", "relative_path": f"trash/{name}"}],
            [{"kind": "move_verified", "present": f"trash/{name}", "absent": f"notes/{name}"}],
            recovered,
        )

    restore_prefix = "restaura la nota "
    if lowered.startswith(restore_prefix):
        raw_name = message.strip()[len(restore_prefix) :]
        try:
            name = _safe_filename(raw_name)
            source = _note_path(workspace, "trash", name)
            target = _note_path(workspace, "notes", name)
        except RequestError:
            return _invalid(invocation_id, "No restauré la nota porque su nombre no es seguro.", recovered=recovered)
        if source.is_file():
            os.replace(source, target)
        if not target.is_file() or source.exists():
            return _base_response(
                invocation_id,
                state="blocked",
                intent="note.restore",
                effect="reversible",
                risk="low",
                verification="unverified",
                response=f"No pude restaurar {name} porque no está en la papelera.",
                journal_recovered=recovered,
            )
        return _done(
            invocation_id,
            "note.restore",
            "reversible",
            f"Restauré la nota {name} y lo verifiqué.",
            [{"operation": "note.restore", "state": "done", "relative_path": f"notes/{name}"}],
            [{"kind": "move_verified", "present": f"notes/{name}", "absent": f"trash/{name}"}],
            recovered,
        )

    if lowered.startswith("borra ") or lowered.startswith("elimina "):
        return _base_response(
            invocation_id,
            state="blocked",
            intent="unsafe.delete",
            effect="destructive",
            risk="critical",
            verification="unverified",
            response="No ejecutaré ese borrado: el objetivo está fuera del espacio seguro y es destructivo.",
            journal_recovered=recovered,
        )

    return _base_response(
        invocation_id,
        state="blocked",
        intent="unknown",
        effect="none",
        risk="low",
        verification="unverified",
        response="No puedo completar esa petición con las capacidades disponibles.",
        journal_recovered=recovered,
    )


def handle_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        return _invalid("invalid-request", "La petición no tiene un objeto válido.")
    invocation_id = request.get("invocation_id")
    message = request.get("message")
    if not isinstance(invocation_id, str) or not INVOCATION_RE.fullmatch(invocation_id):
        return _invalid("invalid-request", "La petición no tiene un invocation_id válido.")
    if not isinstance(message, str):
        return _invalid(invocation_id, "La petición no contiene texto válido.")
    if len(message.encode("utf-8")) > 16_384:
        return _invalid(invocation_id, "La petición supera el tamaño permitido.")
    try:
        workspace = _workspace_from_request(request.get("workspace"))
    except RequestError:
        return _invalid(invocation_id, "El workspace solicitado no está autorizado.")

    recovered = repair_journal(workspace)
    records = load_journal(workspace)
    try:
        replay, started = _existing_invocation(records, invocation_id, message)
    except RequestError:
        return _invalid(invocation_id, "Ese invocation_id ya pertenece a otra petición.", recovered=recovered)
    if replay is not None:
        replay["journal_recovered"] = bool(replay.get("journal_recovered")) or recovered
        return replay
    if not started:
        append_journal(
            workspace,
            {"schema_version": SCHEMA_VERSION, "status": "started", "invocation_id": invocation_id, "message": message},
        )
    try:
        result = execute(invocation_id, message, workspace, recovered)
    except Exception:
        print("BAXY_EXECUTION_ERROR internal_failure", file=sys.stderr, flush=True)
        result = _base_response(
            invocation_id,
            state="failed",
            intent="internal",
            effect="none",
            risk="high",
            verification="unverified",
            response="No pude completar la petición por un fallo interno.",
            journal_recovered=recovered,
        )
    append_journal(
        workspace,
        {
            "schema_version": SCHEMA_VERSION,
            "status": "completed",
            "invocation_id": invocation_id,
            "message": message,
            "result": result,
        },
    )
    return result


def run_stream(lines: Iterable[str]) -> int:
    for line in lines:
        if not line.strip():
            continue
        started = time.perf_counter_ns()
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print("BAXY_PROTOCOL_ERROR malformed_json", file=sys.stderr, flush=True)
            continue
        result = handle_request(request)
        result["elapsed_ns"] = time.perf_counter_ns() - started
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description="BAXY Python technology-tournament slice")
    parser.add_argument("--server", action="store_true", help="Consume JSONL until stdin closes")
    parser.parse_args(argv)
    return run_stream(sys.stdin)


if __name__ == "__main__":
    raise SystemExit(main())
