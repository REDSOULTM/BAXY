"""Servidor MCP de PRUEBA mínimo (stdio) para validar el cliente MCP del agente.

Local, reproducible, sin red ni descargas: usa el SDK `mcp` (FastMCP) ya instalado.
Expone 2 tools triviales para que el agente las descubra (list_tools) y ejecute
(call_tool) end-to-end. No toca el SO ni recursos del usuario.

Uso (lo lanza el cliente MCP del agente vía stdio, no se corre a mano):
  ~/.gemma4/mcp_servers.json -> {"servers":[{"name":"test","command":"python",
     "args":["<ruta>/scripts/_mcp_test_server.py"]}]}
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gemma4-test")


@mcp.tool()
def echo(text: str) -> str:
    """Devuelve el mismo texto recibido (prueba de ida y vuelta)."""
    return f"echo: {text}"


@mcp.tool()
def add_numbers(a: float, b: float) -> str:
    """Suma dos números y devuelve el resultado como texto."""
    return f"resultado: {a + b}"


if __name__ == "__main__":
    mcp.run()
