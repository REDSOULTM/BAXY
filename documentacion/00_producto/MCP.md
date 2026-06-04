# Baxy as MCP Server

Baxy puede exponer sus **compound tools** como un servidor
[MCP (Model Context Protocol)](https://modelcontextprotocol.io/), el
standard de facto que usan Claude Desktop, Cursor, Goose, OpenHands
y otros agentes para hablar con tool providers.

**Que hace**: traducimos `COMPOUND_TOOL_SCHEMAS` (63 tools: `system`,
`app`, `steam`, `gui`, `filesystem`, etc.) al formato MCP y atendemos
las llamadas JSON-RPC `initialize` / `tools/list` / `tools/call`,
despachando a la misma `ToolRegistry.execute()` que usa el agent loop.

**Que NO hace**: este server NO ejecuta el LLM Gemma 4. Solo expone
las tools de bajo nivel para que otros agentes (con su propio LLM)
las usen como backend. Para una integracion full-stack con el LLM
local, usar `launcher.py`.

## Arrancarlo

### stdio (Claude Desktop, Cursor)

```bash
python -m gemma4_agent.tools_pkg.mcp_server
```

Lee JSON-RPC de stdin, escribe a stdout (line-delimited). Logs van a stderr.

### HTTP (debugging, integraciones lan)

```bash
python -m gemma4_agent.tools_pkg.mcp_server --port 8765
# health check:  curl http://127.0.0.1:8765/
# JSON-RPC:      curl -X POST http://127.0.0.1:8765/ -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Configurar Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gemma4": {
      "command": "python",
      "args": ["-m", "gemma4_agent.mcp_server"],
      "cwd": "C:/Users/usuario/Desktop/ETC/Programacion/Probando Gemma 4"
    }
  }
}
```

Reiniciar Claude Desktop. En el menu de herramientas deberian aparecer
las 63 compound tools de Baxy.

## Configurar Cursor

`.cursor/mcp.json` en el workspace:

```json
{
  "mcpServers": {
    "gemma4": {
      "command": "python",
      "args": ["-m", "gemma4_agent.mcp_server"]
    }
  }
}
```

## Configurar goose

```bash
goose configure
# Add MCP extension
# Type: STDIO
# Command: python -m gemma4_agent.tools_pkg.mcp_server
```

## Protocolo

Implementado: MCP `2024-11-05`.

| Method | Handler | Description |
|---|---|---|
| `initialize` | `_handle_initialize` | Handshake + capabilities |
| `tools/list` | `_handle_tools_list` | Lista 63 compound tools |
| `tools/call` | `_handle_tools_call` | Dispatcha a `ToolRegistry.execute` |
| `notifications/initialized` | (silenciado) | Notification post-handshake |

## Honestidad / seguridad

- **NO arranca el LLM** — solo expone las tools.
- **NO bypasa el safety**: las tools destructive (filesystem.delete,
  terminal.run, registry.delete, etc.) siguen pidiendo `confirmed=true`
  en sus args. El cliente MCP debe pasarlo explicitamente; si no, la
  tool retorna `needs_user`.
- **NO loggea a stdout en stdio mode** — eso corrompe el stream
  JSON-RPC. Todos los logs van a stderr.
- **localhost-only por default** en HTTP (`--host 127.0.0.1`). Si exponés
  a la LAN, sos vos quien decide; las tools acceden a archivos, registry,
  audio, etc., asi que pensa antes.

## Tests

```bash
python -m unittest gemma4_agent.test_mcp_server -v
```

14 tests: tool list shape, initialize handshake, JSON-RPC dispatch,
real tools/call (system.time read-only).

## Smoke test manual

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"system","arguments":{"action":"time"}}}' \
  | python -m gemma4_agent.tools_pkg.mcp_server
```

Esperás 3 respuestas: `initialize`, `tools/list` (63 tools), `tools/call`
con el tiempo actual.
