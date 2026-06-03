"""Compartido entre domain_tools.py y los módulos hermanos extraídos de él.
Existe para que cada hermano pueda hacer
`from .helpers import _X` a top-level — antes el patrón obligaba
a `from . import _X` LAZY dentro de cada función para evitar
ciclos. Eso pasaba el runtime (lazy resuelve) pero el analizador estático
veía ~26 ciclos falsos-positivos.

Reglas:
- TODO lo de acá no debe depender de ningún sibling. Si necesita algo de
  domain_tools.py, ese algo se mueve también acá (es cross-cutting por
  definición) o se queda en domain_tools.py si es lógica del módulo central.
- _ok/_err siguen viviendo en _shared.py (el tipo de retorno canónico).
- Cada helper se importa también desde domain_tools.py para compat con
  callers que hacen `from gemma4_agent import domain_tools as dt; dt._X`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "_existing_path",
    "_find_resource",
    "_find_routine",
    "_find_soundvolumeview",
    "_json_or_none",
    "_parse_due_iso",
    "_pid_alive",
    "_pid_owned_by",
    "_powershell_json",
    "_ps_quote",
    "_resources_by_kind",
    "_safe_name",
    "_update_resource_metadata",
]


def _existing_path(args: dict[str, Any]) -> Path | None:
    """Resuelve `args["path"]` a un Path absoluto si existe en disco.

    Devuelve None si falta el arg o el path no existe. Usado por office y
    source_manager para snapshots/inspección de archivos arbitrarios.

    Originalmente vivía en domain_tools.py; al extraer office se borró de allí
    pero los re-exports de office_tool/source_manager_tool seguían
    referenciándolo con lazy import, dejando un bug latente (AttributeError al
    primer uso). El sweep de tests no lo detectó porque ningún test invoca
    office.snapshot_file/inspect ni source_manager.snapshot_file directamente.
    """
    raw = str(args.get("path") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


def _find_resource(args: dict[str, Any], state: AgentState, kinds: str | list[str]) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    query = str(args.get("query") or args.get("name") or args.get("title") or "").strip().casefold()
    resources = state._load().get("resources", {})
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    if rid and rid in resources and resources[rid].get("kind") in wanted:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") not in wanted:
            continue
        if query and query in json.dumps(resource, ensure_ascii=False).casefold():
            return resource
    return None


def _find_routine(args: dict[str, Any], state: AgentState) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    name = str(args.get("name") or args.get("label") or "").strip().casefold()
    resources = state._load().get("resources", {})
    if rid and rid in resources:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") == "routine" and name and str(resource.get("label") or "").casefold() == name:
            return resource
    return None


def _find_soundvolumeview() -> Path | None:
    raw = os.environ.get("GEMMA4_SOUNDVOLUMEVIEW")
    candidates = [Path(raw)] if raw else []
    candidates.extend([
        Path.home() / ".gemma4" / "tools" / "SoundVolumeView.exe",
        Path.cwd() / "tools" / "SoundVolumeView.exe",
        Path.home() / "Downloads" / "SoundVolumeView.exe",
        Path("C:/Tools/SoundVolumeView/SoundVolumeView.exe"),
        Path("C:/Program Files/SoundVolumeView/SoundVolumeView.exe"),
    ])
    found = shutil.which("SoundVolumeView.exe")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _json_or_none(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_due_iso(value: Any) -> tuple[str | None, str | None]:
    """Intenta normalizar un `due` a ISO 8601. Devuelve (iso_str_or_None, error_msg_or_None).

    Acepta:
      - "2026-05-20" -> "2026-05-20T00:00:00"
      - "2026-05-20T15:30" -> "2026-05-20T15:30:00"
      - ya-ISO -> passthrough
      - None / "" -> (None, None)  (sin due es valido)

    Rechaza strings de lenguaje natural ("mañana", "tomorrow") con un mensaje
    claro para que el LLM resuelva el delta antes de llamar.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None, None
        if re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$", s):
            if "T" not in s:
                s = s + "T00:00:00"
            elif s.count(":") == 1:
                s = s + ":00"
            return s, None
        try:
            datetime.fromisoformat(s)
            return s, None
        except ValueError:
            pass
        return None, (
            f"due value {s!r} is not ISO 8601. Pass YYYY-MM-DD or YYYY-MM-DDTHH:MM; "
            "for relative dates ('tomorrow', 'next week') resolve the absolute "
            "date in the agent before calling."
        )
    return None, f"due must be a string, got {type(value).__name__}"


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ 1 }} else {{ 0 }}"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "1"
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_owned_by(pid: int, expected_exe_basename: str | None) -> tuple[bool, str | None]:
    """CC-104: Returns (matches, current_name). On Windows queries Get-Process
    and compares ProcessName against the expected basename (without extension).
    `matches` is True only if both checks succeed; False if PID does not exist
    OR is a different process. `current_name` may be None when unknown.
    """
    if os.name != "nt":
        try:
            os.kill(int(pid), 0)
            return True, None
        except (ProcessLookupError, PermissionError, OSError):
            return False, None
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue; "
         f"if ($p) {{ $p.ProcessName }} else {{ '' }}"],
        capture_output=True, text=True, timeout=10,
    )
    name = proc.stdout.strip()
    if not name:
        return False, None
    if not expected_exe_basename:
        return True, name
    expected = Path(expected_exe_basename).stem.casefold()
    return name.casefold() == expected or name.casefold().startswith(expected), name


def _powershell_json(script: str, field: str) -> dict[str, Any]:
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("powershell command failed", exit_code=proc.returncode, stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        data: Any = []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("failed to parse PowerShell JSON", stdout=raw[:1000])
    if isinstance(data, dict) and field.endswith("s"):
        data = [data]
    return _ok(**{field: data, "count": len(data) if isinstance(data, list) else (1 if data else 0)})


def _ps_quote(text: str) -> str:
    return text.replace("'", "''")


def _resources_by_kind(state: AgentState, kinds: str | list[str], include_closed: bool = False) -> list[dict[str, Any]]:
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    resources = state._load().get("resources", {}).values()
    out = []
    for resource in resources:
        if resource.get("kind") not in wanted:
            continue
        if not include_closed and resource.get("status") != "open":
            continue
        out.append(resource)
    return out


def _safe_name(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())[:50].strip("_")
    return clean or "archivo"


def _update_resource_metadata(state: AgentState, resource_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """CC-102: delega en la API pública atómica."""
    result = state.update_resource_metadata(resource_id, updates)
    if not result.get("ok"):
        return _err("resource not found", resource_id=resource_id)
    return _ok(resource=result.get("resource"))
