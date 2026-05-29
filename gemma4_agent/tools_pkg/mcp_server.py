"""Gemma 4 Agent as MCP server — expose compound tools to other agents (TIER 2 #7).

Pattern from goose (Block / Linux Foundation AAIF): MCP (Model Context Protocol)
es el standard de facto para agent-tool interop. Al exponer Gemma 4 como un
servidor MCP, otros agentes (Cursor, Claude Desktop, OpenHands, goose) pueden
usar nuestras compound tools como backend para automation de Windows local.

Implementa JSON-RPC sobre stdio o HTTP. La lista de tools sale de
COMPOUND_TOOL_SCHEMAS y el dispatch va a `ToolRegistry.execute(name, args)`.

Usage:
    python -m gemma4_agent.tools_pkg.mcp_server                # stdio mode (Claude Desktop default)
    python -m gemma4_agent.tools_pkg.mcp_server --port 8765    # HTTP mode

Cliente (Claude Desktop / Cursor / goose) config:
    {
      "mcpServers": {
        "gemma4": {
          "command": "python",
          "args": ["-m", "gemma4_agent.mcp_server"]
        }
      }
    }

References:
- MCP spec: https://modelcontextprotocol.io/
- goose extensions: https://block.github.io/goose/docs/category/extensions/
- Carter v5 mcp_server.py — reference implementation porteada aca

Honestidad: este server NO ejecuta el LLM Gemma 4. Solo expone las tools
de bajo nivel para que OTROS agentes (con su propio LLM) las usen como
backend. La razon: agent-loop de Gemma 4 incluye logica que no aplica
a clientes externos (router, microagents, skills, mission_goal,
verifier per-tool). Para una integracion full-stack agent + LLM, usar
launcher.py directamente.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any


logger = logging.getLogger(__name__)

# MCP protocol version (snapshot of the spec we target).
MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "gemma4_agent"
SERVER_VERSION = "0.9.1"


# ---------------------------------------------------------------------------
# Lazy singleton — ToolRegistry es pesado (carga AppResolver + KnowledgeStore).
# Lo instanciamos una sola vez al primer tools/call.
# ---------------------------------------------------------------------------


_REGISTRY = None
# Serializes the lazy build. run_http today uses a serial HTTPServer so the
# race can't trigger, but the ToolRegistry build is heavy (AppResolver +
# KnowledgeStore) and double-building it would be wasteful if anyone ever
# switches to ThreadingHTTPServer. Double-checked locking, same pattern as the
# other lazy loaders (semantic_router/reranker/tool_head/abstain_head).
import threading as _threading
_REGISTRY_LOCK = _threading.Lock()


def _get_registry():
    """Lazy build the ToolRegistry on first tools/call (thread-safe)."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is not None:
            return _REGISTRY
        from ..infra.config import AgentConfig
        from ..memory_pkg.memory import MemoryStore
        from ..memory_pkg.state import AgentState
        from .tools import ToolRegistry

        cfg = AgentConfig.from_env()
        memory = MemoryStore(path=cfg.memory_path)
        state = AgentState(path=cfg.state_path)
        registry = ToolRegistry(
            memory=memory,
            captures_dir=cfg.captures_dir,
            state=state,
            safety_enabled=True,
        )
        logger.info("ToolRegistry initialized (%d compound tools)",
                    len(registry.schema_names))
        _REGISTRY = registry
    return _REGISTRY


def _build_tool_list() -> list[dict[str, Any]]:
    """Build MCP-compliant tool list from COMPOUND_TOOL_SCHEMAS.

    Format: list of {name, description, inputSchema}. inputSchema = los
    parameters de cada compound tool (JSON Schema).
    """
    from .tools import COMPOUND_TOOL_SCHEMAS
    mcp_tools: list[dict[str, Any]] = []
    for entry in COMPOUND_TOOL_SCHEMAS:
        fn = entry.get("function", {})
        name = fn.get("name")
        if not name:
            continue
        mcp_tools.append({
            "name": name,
            "description": fn.get("description", ""),
            "inputSchema": fn.get("parameters", {"type": "object"}),
        })
    return mcp_tools


# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------


def _handle_initialize(params: dict) -> dict:
    """MCP `initialize` — handshake con protocolo + capabilities."""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
    }


def _handle_tools_list(params: dict) -> dict:
    """MCP `tools/list` — devuelve el catalogo entero."""
    return {"tools": _build_tool_list()}


def _handle_tools_call(params: dict) -> dict:
    """MCP `tools/call` — dispatch a ToolRegistry.execute(name, args).

    MCP espera el resultado como `{content: [{type, text}], isError}`. Si
    la tool devuelve dict, lo serializamos a JSON formateado para que el
    cliente externo lo pueda leer sin re-parsear nada.
    """
    name = params.get("name", "")
    args = params.get("arguments", {}) or {}
    try:
        registry = _get_registry()
        result = registry.execute(name, args)
    except Exception as exc:
        logger.exception("tools/call %s failed", name)
        return {
            "content": [{"type": "text", "text": f"error: {exc}"}],
            "isError": True,
        }
    text_result = json.dumps(result, ensure_ascii=False, default=str, indent=2)
    is_error = bool(result.get("ok") is False or result.get("error"))
    return {
        "content": [{"type": "text", "text": text_result}],
        "isError": is_error,
    }


_HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    # MCP notifications (no response expected) — log only.
    "notifications/initialized": lambda params: None,
}


def _handle_request(req: dict) -> dict | None:
    """Dispatch un JSON-RPC request a su handler.

    Returns None for notification methods (id ausente o handler retorna None).
    """
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {}) or {}

    # Notifications: no id, no response.
    is_notification = req_id is None

    handler = _HANDLERS.get(method)
    if handler is None:
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {
                "code": -32601,
                "message": f"method not found: {method}",
            },
        }
    try:
        result = handler(params)
        if is_notification or result is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    except Exception as exc:
        logger.exception("handler %s failed", method)
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32603, "message": str(exc)},
        }


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------


def run_stdio() -> int:
    """MCP server leyendo de stdin / escribiendo a stdout (line-delimited JSON-RPC).

    Esto es lo que Claude Desktop spawnea por default cuando configurás
    `command: python -m gemma4_agent.tools_pkg.mcp_server` en `claude_desktop_config.json`.
    """
    logger.info("%s MCP server starting (stdio mode)", SERVER_NAME)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("bad JSON in stdin: %s", exc)
            continue
        resp = _handle_request(req)
        if resp is not None:
            sys.stdout.write(
                json.dumps(resp, ensure_ascii=False, default=str) + "\n"
            )
            sys.stdout.flush()
    return 0


def run_http(port: int = 8765, host: str = "127.0.0.1") -> int:
    """MCP server sobre HTTP (POST /mcp con JSON-RPC body).

    Util para integraciones non-stdio (testing, debugging, lan).
    """
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer
    except ImportError:  # never on cpython
        return 1

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
            try:
                req = json.loads(body) if body else {}
                resp = _handle_request(req)
            except Exception as exc:
                resp = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": str(exc)},
                }
            payload = json.dumps(
                resp or {}, ensure_ascii=False, default=str
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            # Health-check endpoint.
            payload = json.dumps({
                "ok": True,
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "protocol": MCP_PROTOCOL_VERSION,
                "tools": len(_build_tool_list()),
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            logger.info("[http] " + fmt, *args)

    server = HTTPServer((host, port), MCPHandler)
    logger.info("%s MCP server starting (http://%s:%d)", SERVER_NAME, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("MCP server interrupted")
    finally:
        server.server_close()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gemma4-mcp",
        description="Run gemma4_agent as an MCP server (stdio or HTTP).",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="If set, run over HTTP on this port. Default: stdio.",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="HTTP bind host. Default 127.0.0.1 (localhost only).",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    # IMPORTANT: stdio mode MUST NOT log to stdout (it would corrupt the
    # JSON-RPC stream). Force logs to stderr always.
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s %(name)s] %(message)s",
        stream=sys.stderr,
    )

    if args.port:
        return run_http(args.port, args.host)
    return run_stdio()


if __name__ == "__main__":
    sys.exit(main())
