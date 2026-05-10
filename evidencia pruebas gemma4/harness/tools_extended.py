"""Stubs determinísticos extendidos para Bloque B (cids reales Carter)."""
from tools import TOOL_SCHEMAS as BASE_SCHEMAS

# Tools nuevos solicitados por cids del Bloque B
EXTRA_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": "Persists a note or memory item for later recall.",
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}, "tag": {"type": "string"}},
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reminder_create",
            "description": "Creates a reminder for a specific time. Time can be relative ('in 1h') or absolute ('15:00').",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "when": {"type": "string"}},
                "required": ["text", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_paste",
            "description": "Pastes the current clipboard content into the focused window.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_copy",
            "description": "Copies given text to system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_read",
            "description": "Returns current clipboard content.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc_eval",
            "description": "Evaluates a math expression and returns the result.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "steam_search",
            "description": "Searches Steam (library or store) for a game.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "scope": {"type": "string", "enum": ["library", "store", "auto"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Performs a web search and returns top results.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Writes text content to a file inside the sandbox folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Reads a text file from sandbox.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "app_close",
            "description": "Closes a running application by name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gui_universal_action",
            "description": "Performs a UI action (click/type/scroll) on a target element of the active window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "type", "scroll", "select"]},
                    "target": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["action", "target"],
            },
        },
    },
]

ALL_SCHEMAS = BASE_SCHEMAS + EXTRA_SCHEMAS


def execute_tool_extended(name, args):
    """Returns deterministic stub responses for the extended catalog."""
    from tools import execute_tool as base_exec

    if name == "memory_save":
        return f'{{"status":"saved","tag":"{args.get("tag","default")}","id":"mem_42"}}'
    if name == "reminder_create":
        return f'{{"status":"created","reminder_id":"rem_7","when":"{args.get("when")}"}}'
    if name == "clipboard_paste":
        return '{"status":"pasted","chars":17}'
    if name == "clipboard_copy":
        return f'{{"status":"copied","chars":{len(args.get("text",""))}}}'
    if name == "clipboard_read":
        return '{"content":"texto previamente copiado"}'
    if name == "calc_eval":
        expr = args.get("expression", "")
        try:
            val = eval(expr, {"__builtins__": {}}, {})
            return f'{{"result":{val}}}'
        except Exception:
            return '{"error":"could not evaluate"}'
    if name == "steam_search":
        return '{"matches":[{"app":"Batman: Arkham Knight","scope":"library"}]}'
    if name == "web_search":
        return '{"results":[{"title":"Stub result","url":"https://example.com"}]}'
    if name == "file_write":
        return f'{{"status":"written","path":"sandbox/{args.get("path","")}","bytes":{len(args.get("content",""))}}}'
    if name == "file_read":
        return '{"content":"contenido fijo del archivo notes.txt para testing"}'
    if name == "app_close":
        return f'{{"status":"closed","app":"{args.get("name","")}"}}'
    if name == "gui_universal_action":
        return f'{{"status":"executed","action":"{args.get("action")}","target":"{args.get("target")}"}}'
    return base_exec(name, args)
