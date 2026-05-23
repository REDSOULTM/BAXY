"""Stubs deterministicos. Devuelven valores fijos para que el benchmark mida al modelo, no al SO."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "system_time",
            "description": "Returns the current system time. Use for live time queries like 'what time is it'.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_apps",
            "description": "Lists installed applications on the system. Use to check whether an app is installed without opening it.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Lists currently running processes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "Lists open windows with their titles.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "app_open",
            "description": "Opens a desktop application by executable name (e.g. 'notepad.exe', 'calc.exe').",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Executable name"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_open_url",
            "description": "Opens a URL in the default browser. Use for websites without a desktop app.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL including https://"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Types text into the currently focused window.",
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
            "name": "read_active_window_title",
            "description": "Reads the title of the currently focused window. Required before claiming what window/page is active.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Sets system volume to an integer 0-100.",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "Volume level 0-100"}},
                "required": ["level"],
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Returns a fixed deterministic response for each tool."""
    if name == "system_time":
        return "2026-05-09T14:32:11-03:00"
    if name == "list_apps":
        return '["notepad.exe","calc.exe","chrome.exe","code.exe","spotify.exe","steam.exe"]'
    if name == "list_processes":
        return '[{"pid":1234,"name":"chrome.exe"},{"pid":5678,"name":"explorer.exe"}]'
    if name == "list_windows":
        return '[{"hwnd":111,"title":"YouTube - Google Chrome"},{"hwnd":222,"title":"Untitled - Notepad"}]'
    if name == "app_open":
        return f'{{"status":"opened","app":"{args.get("name","")}"}}'
    if name == "web_open_url":
        return f'{{"status":"opened","url":"{args.get("url","")}"}}'
    if name == "type_text":
        return f'{{"status":"typed","chars":{len(args.get("text",""))}}}'
    if name == "read_active_window_title":
        return '{"title":"YouTube - Google Chrome"}'
    if name == "set_volume":
        return f'{{"status":"set","level":{args.get("level")}}}'
    return f'{{"error":"unknown tool {name}"}}'
