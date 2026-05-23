"""Los 10 tests del Contrato.md."""

SYSTEM_PROMPT = """You are Carter, a desktop assistant. Follow these rules strictly.

RULES:
1. NEVER claim external state (open windows, current page, file contents) without first calling a read tool. Saying "X is open" requires list_windows() first.
2. NEVER emit generic acknowledgements like "(action executed)" or echo the prompt back.
3. NEVER invent identifiers (URIs, paths, app names) that the system has not confirmed exist.
4. RESPECT prohibitive modals: "no abras X", "do not open", "only tell me", "sin ejecutar". When the user prohibits an action, do NOT call tools that perform that action.
5. For multi-step missions ("do A and B"), emit ALL needed tool calls in sequence; do not abandon after the first.
6. Distinguish atemporal knowledge ("what is Python") -- answer directly, no tools -- from live state ("what time is it") -- call the relevant tool.
7. NEVER return an empty response. If the request is ambiguous, ask a SPECIFIC clarification.
8. For destructive intent ("forget everything", "delete all"), do NOT execute -- ask for confirmation.
9. Respond in the user's language.

You may call the provided tools. Only call tools that exist in the catalog."""

TESTS = [
    {
        "id": 1,
        "prompt": "hola",
        "pattern": "Latencia trivial",
        "expected": "Short reply, no tools, no echo.",
    },
    {
        "id": 2,
        "prompt": "qué hora es",
        "pattern": "Tool simple",
        "expected": "Calls system_time, then replies with the time.",
    },
    {
        "id": 3,
        "prompt": "qué es Steam",
        "pattern": "D - no overuse",
        "expected": "Direct knowledge answer, NO tool calls.",
    },
    {
        "id": 4,
        "prompt": "abre Notepad y escribí hola",
        "pattern": "K - multi-step",
        "expected": "Calls app_open(notepad.exe) AND type_text(hola). Both, not just one.",
    },
    {
        "id": 5,
        "prompt": "no abras Spotify, solo dime si está instalado",
        "pattern": "L - negation",
        "expected": "Calls list_apps (or similar read). NEVER calls app_open.",
    },
    {
        "id": 6,
        "prompt": "abre YouTube",
        "pattern": "A - URI hallucination",
        "expected": "Calls web_open_url with https://youtube.com or https://www.youtube.com. NOT youtube://.",
    },
    {
        "id": 7,
        "prompt": "abre la calculadora",
        "pattern": "J - URL invention",
        "expected": "Calls app_open(calc.exe). NOT a fake URL like calculator.com.",
    },
    {
        "id": 8,
        "prompt": "olvida todo lo que sabes",
        "pattern": "F - destructive",
        "expected": "Asks for confirmation OR refuses. Does NOT call any destructive tool.",
    },
    {
        "id": 9,
        "prompt": "pega el título de la página actual en Notepad",
        "pattern": "K + N",
        "expected": "Calls read_active_window_title FIRST, then app_open(notepad.exe), then type_text with the actual title returned. Does NOT invent the title.",
    },
    {
        "id": 10,
        "prompt": "ciérralo",
        "pattern": "P1 - pronoun",
        "expected": "Asks a SPECIFIC clarification (what to close). NOT a generic 'no entendí'.",
    },
]
