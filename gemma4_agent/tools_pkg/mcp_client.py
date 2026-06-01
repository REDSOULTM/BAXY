"""Cliente MCP (Model Context Protocol) — B9 del backlog de competidores.

Adopta MCP como CLIENTE para conectar a servidores MCP existentes (filesystem,
git, APIs, etc.) sin escribir cada tool a mano. Usa el SDK oficial `mcp`
(ClientSession + stdio_client) — NO reimplementa el protocolo.

DISEÑO (informado por research/1_toolcalling.md: el router ya manda un SUBSET de
4-6 tools por turno, lo que MITIGA el riesgo R7 de "muchas tools degradan el
tool-calling del 4B"). Las tools MCP se DESCUBREN (list_tools), se registran con su
description, y el router semántico las incluye en el pool y las recorta a 4-6. NUNCA
se le dan todas las tools MCP al 4B de golpe.

GATING: GEMMA4_MCP (default off). Sin servidores configurados o gate off -> no-op
total (0 tools MCP, 0 overhead). Config en ~/.gemma4/mcp_servers.json:
  {"servers": [{"name": "fs", "command": "npx", "args": ["-y",
   "@modelcontextprotocol/server-filesystem", "C:/Users/.../Documents"]}]}

SYNC WRAPPER: el SDK es async; el agente es sync. Cada operación abre/cierra la
sesión en su propio event loop (simple y robusto; el costo de conexión se paga sólo
cuando el LLM realmente invoca una tool MCP, no en el caso feliz). Timeout duro.

SEGURIDAD: los servidores MCP son subprocesos locales que el USUARIO declara en su
config (no se descargan ni ejecutan servidores arbitrarios). El catálogo se cachea;
las llamadas tienen timeout. No se exponen servidores remotos sin que el user los liste.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path.home() / ".gemma4" / "mcp_servers.json"
_TOOLS_CACHE: list[dict[str, Any]] | None = None   # [{server,name,description,schema}]
_CALL_TIMEOUT_S = 30.0


def mcp_enabled() -> bool:
    """B9 gate. Default OFF (opt-in GEMMA4_MCP) — más tools = tool-calling más
    duro para el 4B (R7); se prende cuando el usuario quiere extender con servidores
    MCP y tras medir que el router no degrada."""
    return (os.environ.get("GEMMA4_MCP", "0") or "0").strip().lower() not in {
        "0", "false", "no", "off"}


def _load_config() -> list[dict[str, Any]]:
    """Lee la lista de servidores MCP declarados por el usuario. [] si no hay."""
    try:
        if not _CONFIG_PATH.is_file():
            return []
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        servers = data.get("servers") if isinstance(data, dict) else None
        return [s for s in (servers or []) if isinstance(s, dict) and s.get("name") and s.get("command")]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("mcp config unreadable: %s", exc)
        return []


def _run_async(coro_factory) -> Any:
    """Corre una corrutina desde contexto sync. Usa un thread con su propio event
    loop (robusto aunque exista un loop corriendo en el hilo actual). Recibe una
    FACTORY (callable que devuelve la coroutine) en vez de la coroutine ya creada,
    para que la corrutina nazca dentro del loop del worker (sin 'never awaited')."""
    result: dict[str, Any] = {}

    def _worker():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result["value"] = loop.run_until_complete(coro_factory())
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=_CALL_TIMEOUT_S + 5)
    if t.is_alive():
        raise TimeoutError("MCP operation exceeded timeout")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _server_params(server: dict[str, Any]):
    """Construye StdioServerParameters pasando el `env` del config MERGEADO con el
    entorno actual. Necesario para servers que requieren un token (p.ej. GitHub
    lee GITHUB_PERSONAL_ACCESS_TOKEN). Un valor vacío en el config NO pisa el del
    entorno (así el usuario puede setear el token por env var en vez del JSON)."""
    from mcp import StdioServerParameters
    env = dict(os.environ)
    for k, v in (server.get("env") or {}).items():
        if v:  # solo override si el config trae un valor no-vacío
            env[str(k)] = str(v)
    return StdioServerParameters(
        command=server["command"], args=server.get("args") or [], env=env)


async def _discover_async(server: dict[str, Any]) -> list[dict[str, Any]]:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    params = _server_params(server)
    out: list[dict[str, Any]] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                # Tool annotations del spec MCP (readOnlyHint/destructiveHint/...) —
                # la señal HONESTA del propio servidor sobre si la tool muta o no.
                # Las usamos en el gate de confirmación (classify_mcp_call). Muchos
                # servers viejos no las exponen -> {} y caemos a la heurística de nombre.
                ann_obj = getattr(t, "annotations", None)
                annotations: dict[str, Any] = {}
                if ann_obj is not None:
                    for key in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint", "title"):
                        val = getattr(ann_obj, key, None)
                        if val is not None:
                            annotations[key] = val
                out.append({
                    "server": server["name"],
                    "name": t.name,
                    "description": (t.description or "")[:400],
                    "schema": t.inputSchema if isinstance(t.inputSchema, dict) else {},
                    "annotations": annotations,
                })
    return out


def discover_mcp_tools(*, force: bool = False) -> list[dict[str, Any]]:
    """Descubre las tools de todos los servidores MCP configurados. Cacheado.
    [] si gate off / sin config / SDK ausente. Fallback seguro (nunca lanza)."""
    global _TOOLS_CACHE
    if not mcp_enabled():
        return []
    if _TOOLS_CACHE is not None and not force:
        return _TOOLS_CACHE
    discovered: list[dict[str, Any]] = []
    for server in _load_config():
        try:
            discovered.extend(_run_async(lambda s=server: _discover_async(s)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp discover failed for %s: %s", server.get("name"), exc)
    _TOOLS_CACHE = discovered
    return discovered


async def _call_async(server: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    params = _server_params(server)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool_name, arguments or {})
            texts = []
            for c in (res.content or []):
                t = getattr(c, "text", None)
                if t:
                    texts.append(t)
            return {"ok": not bool(getattr(res, "isError", False)),
                    "content": "\n".join(texts), "is_error": bool(getattr(res, "isError", False))}


def call_mcp_tool(server_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ejecuta una tool MCP por (servidor, nombre). Devuelve dict {ok, content}.
    Fallback honesto si falla (no lanza al runtime del agente)."""
    if not mcp_enabled():
        return {"ok": False, "error": "MCP disabled (GEMMA4_MCP off)", "status": "needs_user"}
    server = next((s for s in _load_config() if s.get("name") == server_name), None)
    if server is None:
        return {"ok": False, "error": f"unknown MCP server: {server_name}", "status": "needs_user"}
    try:
        return _run_async(lambda: _call_async(server, tool_name, arguments or {}))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"MCP call failed: {type(exc).__name__}: {exc}", "verified": False}


def reset_cache() -> None:
    """Limpia el cache de tools (tests / reconfig)."""
    global _TOOLS_CACHE
    _TOOLS_CACHE = None


# --- Ola 3 (perfection roadmap B9, 2026-05-29): enrolamiento al router-subset ---
# En vez de obligar al 4B a hacer el baile mcp(action=list) -> leer -> mcp(action=
# call), las tools MCP descubiertas se ENROLAN como tools de primera clase: el
# router las rankea y RECORTA junto a las compound (mismo cap MAX_SELECTED_TOOLS=5),
# y el dispatcher las rutea por su nombre namespaced. NUNCA se le dan las N tools de
# golpe al 4B (la disciplina de subset es la mitigación del riesgo R7).

_MCP_NAME_PREFIX = "mcp__"  # namespacing: mcp__<server>__<tool> (evita colisiones)


def mcp_tool_id(server: str, tool: str) -> str:
    """Nombre namespaced y estable de una tool MCP para el catálogo del agente."""
    return f"{_MCP_NAME_PREFIX}{server}__{tool}"


def parse_mcp_tool_id(name: str) -> tuple[str, str] | None:
    """Inverso de mcp_tool_id: 'mcp__fs__read' -> ('fs','read'). None si no es MCP."""
    if not name.startswith(_MCP_NAME_PREFIX):
        return None
    rest = name[len(_MCP_NAME_PREFIX):]
    server, sep, tool = rest.partition("__")
    if not sep or not server or not tool:
        return None
    return server, tool


def is_mcp_tool_name(name: str) -> bool:
    return name.startswith(_MCP_NAME_PREFIX)


def mcp_tool_schemas() -> list[dict[str, Any]]:
    """Schemas OpenAI-compat de las tools MCP descubiertas, namespaced.

    [] si gate off / sin servidores / SDK ausente (fallback seguro). El agente
    los suma a su catálogo para que el router los rankee y el cap los limite."""
    out: list[dict[str, Any]] = []
    for t in discover_mcp_tools():
        schema = t.get("schema") if isinstance(t.get("schema"), dict) else {}
        params = schema if schema.get("type") == "object" else {
            "type": "object", "properties": {}}
        out.append({
            "type": "function",
            "function": {
                "name": mcp_tool_id(t["server"], t["name"]),
                "description": (
                    f"[MCP:{t['server']}] {t.get('description') or t['name']}"),
                "parameters": params,
            },
        })
    return out


def mcp_tool_annotations(name: str) -> dict[str, Any]:
    """Annotations del protocolo MCP para una tool namespaced ('mcp__server__tool').

    Las usa el gate de confirmación (classify_mcp_call) para decidir si confirmar.
    {} si la tool no se conoce, el discovery no las capturó, o el server no las
    expone (fallback seguro: el classifier cae a la heurística de nombre)."""
    parsed = parse_mcp_tool_id(name)
    if parsed is None:
        return {}
    server, tool = parsed
    for t in (_TOOLS_CACHE or []):
        if t.get("server") == server and t.get("name") == tool:
            ann = t.get("annotations")
            return ann if isinstance(ann, dict) else {}
    return {}


def call_mcp_by_id(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ejecuta una tool MCP por su nombre namespaced ('mcp__server__tool').

    El dispatcher del agente llama esto cuando ve un nombre con el prefijo MCP,
    de forma transparente (el LLM la llamó por su nombre, no via mcp(action=call))."""
    parsed = parse_mcp_tool_id(name)
    if parsed is None:
        return {"ok": False, "error": f"not an MCP tool name: {name}", "status": "failed"}
    server, tool = parsed
    return call_mcp_tool(server, tool, arguments or {})
