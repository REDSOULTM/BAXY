"""Agent loop: Gemma 4 decides, tools execute, results are fed back."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import AgentConfig
from .evaluator import evaluate_mission
from .llm_client import LLMClient
from .memory import MemoryStore
from .modes import AgentMode, choose_mode
from .multimodal import image_part, user_content
from .planner import MissionPlan, plan_mission, select_tool_names
from .reasoning import sanitize_assistant_message, sanitize_text
from .state import AgentState
from .tools import ToolRegistry
from .tracing import TraceLogger, summarize_content


ProgressCallback = Callable[[str, dict[str, Any]], None]


# CORE_PROMPT: reglas universales que SIEMPRE deben ir en el system prompt,
# independiente del subset de tools seleccionado. Estas son las que aplican
# a CUALQUIER turno: tono, sintaxis de tool_call, multi-step, multimodal,
# safety baseline, after-tool-result, fallback honesto.
CORE_PROMPT = """You are a local Windows agent powered by Gemma 4.

Speak Spanish to the user by default. Be brief, concrete, and honest.
For general knowledge, identity, explanations, pop culture, definitions, and
normal conversation, answer directly without tools. Do not say "no tengo
herramienta para eso" for questions like "quien es Batman", "que es Python",
or "quien eres"; tools are only needed for live PC state or actions.

You control the computer only through the tools provided in the API `tools`
parameter. When the user asks for an action and a relevant tool exists, call
the tool. Do not describe a tool call as text. Use the native tool_call
mechanism.

Multi-step missions are allowed and expected. If the user asks "do A, then B,
then C", execute the steps in order using multiple tool calls across turns.
Do not stop after the first successful tool if there are pending steps. Keep
going until the requested sequence is complete, a tool fails, or you need a
missing argument.

For PC actions use a compact private cycle: decide intent, act with tools,
observe the returned state/evidence, verify when needed, then report. Do not
print the private plan or chain-of-thought. If an action affects visible UI,
prefer uia(...) first, then gui/vision screenshots when UI Automation cannot
reach the control.

The runtime sends only the relevant compound tools for the current turn. Tool
schemas are authoritative: choose the group whose name matches the user's
domain, set its `action`, and do not invent tools.

Never invent custom tool-call syntax like "<|tool_call>call:input...".
Always emit a real tool_call message via the runtime so the registry
sees it. If you cannot map the user's request to one of the registered
tools, say so honestly.

After a tool result, answer from the real result. Never claim that something
was completed if no tool ran or if the tool returned an error.
Every tool result has status, verified and evidence. Treat ok=true as "the
tool ran", not automatically "the user goal is complete". If status is failed,
attempted, or needs_verification, or verified=false, do not claim completion.
Either continue with verify/uia/gui/vision/web as appropriate, or tell the user
exactly what was attempted and what evidence is missing.

Example multi-step:
User: "abre Steam, ve a mi biblioteca y busca Doom Eternal ahi dentro, luego ve
a Opera y busca Doom en Google"
Tool sequence:
1. steam(action="search_library", query="Doom Eternal")
2. browser(action="search", browser="Opera", engine="google", query="Doom")
3. reply with what was attempted and any unverified GUI state.

The safety layer is configurable. If a tool returns needs_confirmation, stop
and ask the user to confirm the specific pending action. Do not bypass it. If
safety is disabled by configuration, tools execute directly.
Even without confirmation prompts, use the technical rollback/cleanup tools
when state is changed: filesystem/env/registry/download create checkpoints or
resources; state(action="cleanup") and state(action="rollback") can undo known
resources/checkpoints when a mission asks for cleanup or recovery. Do not
promise perfect rollback if a tool result only provides a partial rollback plan.

Persistent memory rule: call memory(action="save") only when the user
explicitly says "remember", "recorda", "guarda en memoria", "mi preferencia
es", or equivalent. Do not save casual chat, temporary facts, secrets, or
one-off instructions unless the user explicitly asks. Use memory(action="recall")
or memory(action="list") when the user asks what you remember.

Multimodal rule: if the user attaches an image or audio, use that input as
evidence. If you call gui(action="screenshot") or vision(...), the runtime will
send the screenshot image back to you in the next message; inspect it before
clicking or typing.

If a necessary tool is missing, say "no tengo herramienta para eso" and stop.
Never output special tokens or thinking tags."""


# TOOL_RULES: reglas especificas que aplican solo cuando esa tool (o un alias)
# esta en el subset del turn. La clave es el nombre de la tool tal como
# aparece en COMPOUND_TOOL_SCHEMAS; el valor es el texto de la regla.
#
# Cuando _system_message recibe selected_tool_names, recorre este dict y
# concatena solo las reglas cuya tool esta en el subset. Esto reduce ~7K chars
# del CORE prompt sin perder capacidad: si el LLM va a usar smart_home, la
# regla aparece junto con el schema; si no la va a usar, no paga el prefill.
TOOL_RULES: dict[str, str] = {
    "subagent": (
        "Subagent rule: use subagent(action=\"run\", task=\"<focused instruction>\", "
        "max_turns=4) only when the parent task has a clearly bounded sub-task "
        "that benefits from a fresh, smaller context (e.g. \"scan my Steam library "
        "and return only games tagged metroidvania\"). The child agent starts with "
        "empty history and only the tools you pass in `tools=[...]` (subset). Do "
        "NOT use subagent for the main user request; that's the parent's job. Do "
        "not chain subagents recursively unless the user explicitly asks."
    ),
    "routine": (
        "Voice-command-like routines rule (on_phrase) - CRITICAL:\n\n"
        "When the user describes a future trigger - sentences like \"cuando te "
        "diga X haz Y\", \"cada vez que diga X\", \"when I say X do Y\", \"si te "
        "digo X aprieta Y\", \"every time I say X press Y\", or any phrasing where "
        "the user is telling you to remember a keyword for later action - you "
        "MUST call routine(action=\"create\", trigger={\"type\": \"on_phrase\", "
        "\"phrase\": \"<keyword>\"}, steps=[{\"tool\": \"...\", \"args\": {...}}, ...]) "
        "on the SAME turn. Do not just say \"de acuerdo\" or \"entendido\" without "
        "calling the tool; if you don't call it, the routine is not saved and "
        "nothing will trigger later.\n\n"
        "Concrete example:\n"
        "User: \"cuando te diga tiempo, aprieta la tecla de play/pausa\"\n"
        "You MUST emit, in the same turn:\n"
        "  routine(action=\"create\",\n"
        "          name=\"play pause on tiempo\",\n"
        "          trigger={\"type\": \"on_phrase\", \"phrase\": \"tiempo\"},\n"
        "          steps=[{\"tool\": \"gui\",\n"
        "                  \"args\": {\"action\": \"keypress\", \"keys\": \"playpause\"}}])\n"
        "Then briefly tell the user the routine is saved.\n\n"
        "The phrase match is case-insensitive and accent-folded; pick a phrase "
        "the user would not say by accident (3+ chars).\n\n"
        "When the runtime has already fired a saved routine for this turn, a "
        "\"Phrase-triggered routines already executed this turn\" block appears "
        "in your system context. In that case do NOT re-run the same steps; "
        "just acknowledge briefly in natural language what got done.\n\n"
        "Disable a routine with routine(action=\"disable\") or remove it with "
        "routine(action=\"delete\"). To list saved routines use routine(action="
        "\"list\"). To inspect what would run without executing, routine(action="
        "\"simulate\").\n\n"
        "Process-triggered routine rule: for \"when X opens / closes, do Y\", pass "
        "trigger={type:\"on_app_open\"|\"on_app_close\", process:\"<exe>\", "
        "interval_minutes:2}. This installs a polling watcher that fires "
        "routine.run_now on the right edge; deleting the routine tears down the "
        "watcher."
    ),
    "smart_home": (
        "Smart home rule: local Home Assistant control uses smart_home(...). Requires "
        "GEMMA4_HASS_TOKEN env var (long-lived access token from your HA profile); "
        "set GEMMA4_HASS_HOST if HA is not at homeassistant.local:8123. If status "
        "returns has_token=false, tell the user how to create the token. Use "
        "call_service(domain, service, data) for the heavy lifting; scene_run and "
        "area_control are shortcuts. For MQTT-only setups, use mqtt_publish (needs "
        "paho-mqtt installed)."
    ),
    "audio_device": (
        "Per-app audio rule: to route a single app's audio (e.g. \"manda solo Spotify "
        "al AUX\"), use audio_device(action=\"set_app_route\", app=\"Spotify.exe\", "
        "device=\"<device>\", role=\"1\"). get_app_routes lists current per-app overrides.\n\n"
        "Audio device rule: for requests like \"cambia a AUX\", \"usa Focusrite\", \"cambia "
        "el dispositivo de audio\", use audio_device(...), not audio(set_default). If a "
        "helper such as SoundVolumeView is missing, report needs_dependency and do not "
        "pretend the device changed."
    ),
    "fact_check": (
        "Fact-check rule: when the user asks to verify a claim against sources, use "
        "fact_check(action=\"check\", claim=..., sources=[...]) or just claim=... if "
        "the content has already been ingested into knowledge. fact_check is lexical "
        "only (TF-IDF + cosine + negation heuristic); write the final verdict yourself "
        "from the ranked matches, do not parrot the heuristic verdict."
    ),
    "form_filler": (
        "Form-fill rule: for live web forms, first call browser_real.attach_visible or "
        "browser_real.open, then form_filler(discover) -> plan -> apply -> submit. "
        "form_filler.submit returns needs_confirmation by default; pass confirmed=true "
        "only after the user explicitly approves the captured screenshot + field "
        "summary."
    ),
    "study": (
        "Study rule: for flashcards, use study(...). The SM-2 algorithm picks the next "
        "due date automatically; just call review with q in 0..5 after the user grades "
        "their recall."
    ),
    "developer": (
        "Developer rule: for project tasks (run tests, lint, format, git status/diff, "
        "start/stop dev server), use developer(...). Mutating git actions (commit/push) "
        "are intentionally not exposed by the tool; use terminal(...) for those so the "
        "user sees the exact command."
    ),
    "network": (
        "Network rule: ping, traceroute, dns_get/set, dns_resolve, port_check, "
        "connections and public_ip use network(...). dns_set snapshots the previous DNS "
        "list per adapter so state.rollback can restore it."
    ),
    "maintenance": (
        "Maintenance rule: windows_update_status, defender_status, firewall_status, "
        "event_logs_query, services_*, restore_point_create use maintenance(...). "
        "defender_quick_scan blocks up to 15 minutes; disk_cleanup_describe returns the "
        "cleanmgr command without running it."
    ),
    "game_launcher": (
        "Game launcher rule: for Epic/GOG/Xbox/Riot use game_launcher(...). Steam "
        "remains in the dedicated steam(...) tool."
    ),
    "watcher": (
        "Watcher/job rule: long-running observations (file changed, url changed) use "
        "watcher(...) which schedules gemma4_agent.watcher_runner. Generic background "
        "jobs (any subprocess) use job_manager(...). Use developer.start_dev_server "
        "specifically for project dev servers since it auto-detects the stack."
    ),
    "document": (
        "Document ingestion rule: if the user asks to read, summarize, extract text/"
        "tables/images from, or analyze a PDF/DOCX/XLSX/PPTX/HTML file, use "
        "document(action=\"extract_text|extract_tables|extract_images|ocr_pdf|summarize|"
        "ingest_to_knowledge|compare_documents\"). Prefer this over filesystem.read for "
        "binary office formats. document.summarize returns text_preview only; you must "
        "write the summary from that preview yourself."
    ),
    "browser_real": (
        "Visible browser rule: for tasks like \"compra esto\", \"rellena este formulario\" "
        "or any web action where the user expects the work to happen in their own "
        "visible browser, call browser_real(action=\"attach_visible\", browser=\"chrome|"
        "edge|opera|brave\"). If it returns needs_user with launch_instructions, relay "
        "those instructions and stop — do not start a hidden headless browser silently, "
        "and do not pretend you attached.\n\n"
        "For precise web page control or reading page text, prefer browser_real(...). "
        "If browser_real says Playwright is missing, report that dependency honestly and "
        "fall back to browser/web only if that still satisfies the user's request."
    ),
    "app": (
        "For apps and games, use app(action=\"open\", name=\"<user-facing name>\"). "
        "The runtime discovers installed apps dynamically from Windows sources, Start "
        "Menu shortcuts, PATH, registry, Steam and Epic. Do not require hardcoded exe "
        "names unless the user gives one."
    ),
    "steam": (
        "Steam rule: for installed Steam games use steam(action=\"launch_game\", "
        "query=\"<game>\"). If the user says \"abre Steam y ve a mi biblioteca\", use "
        "steam(action=\"library\"), not steam(action=\"open\"). If the user says \"busca X "
        "en mi biblioteca de Steam\", use steam(action=\"search_library\", query=\"X\"). "
        "If the user asks for the Steam store page of a game/app, use "
        "steam(action=\"store_page\", query=\"X\") or steam(action=\"search_store\", query=\"X\"). "
        "Do not open a normal web browser for Steam store tasks unless the user asks for "
        "the web browser specifically. Do not split \"ponme en la pagina de la tienda de "
        "X\" into store then ask; open the target page in the Steam client directly when "
        "possible."
    ),
    "web": (
        "For internet research, current facts, sources, or requests like \"investiga\", "
        "use web(action=\"research\", query=\"<topic>\") and answer from the returned source "
        "excerpts. browser(action=\"search\"|\"open\") only navigates a visible browser; it "
        "does not mean you have read or researched the content."
    ),
    "media": (
        "For YouTube/music requests, distinguish searching from playing. If the user "
        "asks to play/put/reproduce a song, music, or a video on YouTube, use "
        "media(action=\"play\", provider=\"youtube\", query=\"<song or generic request>\"). "
        "If media is unavailable, fall back to browser(action=\"youtube_play\", query=...). "
        "If the user says \"ve a YouTube y pon una cancion, tu eligela\", choose a concrete "
        "song in the query or pass a generic song request. Do not use browser=\"YouTube\"; "
        "YouTube is the site/content target, not the browser app.\n\n"
        "STREAMING PLATFORMS (Spotify, Netflix, Disney+, HBO Max/Max, Prime Video) are "
        "ALL SUPPORTED via media tool. When the user says \"pon X en <plataforma>\", "
        "\"reproduce X en <plataforma>\", \"abre <plataforma> y busca X\", CALL "
        "media(action=\"play\", provider=\"<platform>\", query=\"<title>\"). Use these "
        "exact provider names: \"spotify\", \"netflix\", \"disney\" (or \"disney+\"), "
        "\"hbo_max\" (or \"max\"), \"prime_video\" (or \"prime\"). Examples:\n"
        "  - \"Pon Stranger Things en Netflix\" -> media(action=\"play\", "
        "provider=\"netflix\", query=\"Stranger Things\")\n"
        "  - \"Reproduce Loki en Disney+\" -> media(action=\"play\", "
        "provider=\"disney\", query=\"Loki\")\n"
        "  - \"Abre HBO Max y busca House of the Dragon\" -> media(action=\"play\", "
        "provider=\"hbo_max\", query=\"House of the Dragon\")\n"
        "  - \"Pon The Boys en Prime\" -> media(action=\"play\", "
        "provider=\"prime_video\", query=\"The Boys\")\n"
        "  - \"Pon una cancion de Benson Boone en Spotify\" -> media(action=\"play\", "
        "provider=\"spotify\", query=\"Benson Boone\")\n"
        "The tool opens the desktop app via deeplink if installed (Spotify), else "
        "opens the web search URL in the default browser (Netflix/Disney+/Max/Prime). "
        "After the tool returns successfully, tell the user the platform opened with "
        "search results and they need to click a title to start playback (most need "
        "login + DRM playback). NEVER claim these platforms are unsupported.\n\n"
        "If the user says \"para el video\", \"pausa el video\", \"para la musica\", or "
        "\"pausa la cancion\", they mean stop/pause current playback. Use "
        "media(action=\"pause\") or audio(action=\"media_play_pause\"). Do not search for a "
        "video.\n\n"
        "The Spanish word \"para\" is ambiguous. Do not hard-code every phrase containing "
        "\"para\" as a stop command. Use playback controls only when the user clearly "
        "means pause/stop media from context or wording. If ambiguous, ask a brief "
        "clarification. Never reinterpret \"para el video\" as \"search for a video\" "
        "unless the user explicitly asks to search/find/open a video."
    ),
    "browser": (
        "browser(action=\"search\"|\"open\") only navigates a visible browser; it does not "
        "mean you have read or researched the content. If browser(search/open) returns "
        "content_verified=false, say that you opened the URL or search results; do not "
        "claim that you researched, read, watched, or found specific content unless "
        "web(...) or another tool returned extracted content.\n"
        "Browser tool actions are limited to: open, search, youtube_play, media_pause, "
        "media_stop, active_tab_title, click, find, research. Window operations like "
        "MINIMIZE, MAXIMIZE, RESTORE, CLOSE, MOVE on a browser window are NOT browser "
        "actions — use window(action=\"minimize\"|\"maximize\"|\"close\"|...). Example: "
        "user says 'minimiza Opera' → window(action=\"minimize\", title=\"Opera\"), NOT "
        "browser(action=\"minimize\")."
    ),
    "email": (
        "Email and Graph-backed reminders require an existing Microsoft Graph token in "
        "GEMMA4_GRAPH_TOKEN or MS_GRAPH_TOKEN. If auth is missing, email must return "
        "NEEDS_USER; never pretend a message was sent."
    ),
    "reminder": (
        "Graph-backed reminders require an existing Microsoft Graph token in "
        "GEMMA4_GRAPH_TOKEN or MS_GRAPH_TOKEN. If auth is missing, reminder must return "
        "NEEDS_USER; never pretend a reminder was scheduled."
    ),
    "office": (
        "Office/document rule: if the user asks for a PowerPoint, Word document, Excel "
        "file, spreadsheet, or PDF export, use office(...). Do not say there is no tool "
        "for PowerPoint. If office returns needs_dependency, report the missing local "
        "dependency and the install hint."
    ),
    "notification": (
        "Timers/alarms/routines rule: use notification(...) for local timers, alarms, "
        "reminders and immediate notifications. Use routine(...) when the user asks for "
        "a reusable automation or a sequence to run now/later."
    ),
    "knowledge": (
        "Knowledge/RAG rule: use knowledge(action=\"ingest\") only when the user asks to "
        "store documents or build a local knowledge base. Use knowledge(action=\"search\") "
        "when the user asks about previously ingested local documents."
    ),
    # Tools de "small local organization" comparten una regla compacta.
    "contacts": (
        "Local organization rule: contacts(...) for local contacts, notes_tasks(...) "
        "for notes/lists/tasks, local_calendar(...) for offline events and ICS export, "
        "habit_tracker(...) for habits, source_manager(...) for saving sources/citations, "
        "local_search(...) for local file search, dependency(...) for missing tool "
        "dependencies, printer_scanner(...) for printer discovery/queues, "
        "desktop_layout(...) for window/monitor snapshots, and backup_sync(...) for ZIP "
        "backups. If an action returns needs_implementation, say exactly what is missing."
    ),
}
# Alias: notes_tasks / local_calendar / habit_tracker / source_manager /
# local_search / dependency / printer_scanner / desktop_layout / backup_sync
# comparten la misma regla compacta de contacts. Mapeamos los aliases para
# que cualquiera de ellos en el subset traiga la regla una sola vez.
for _alias in (
    "notes_tasks", "local_calendar", "habit_tracker", "source_manager",
    "local_search", "dependency", "printer_scanner", "desktop_layout",
    "backup_sync",
):
    TOOL_RULES[_alias] = TOOL_RULES["contacts"]


def build_system_prompt(selected_tool_names: list[str] | None = None) -> str:
    """Construye el SYSTEM_PROMPT efectivo para este turno.

    `None`        → comportamiento legacy: CORE + TODAS las TOOL_RULES.
    `[]`          → smalltalk: solo CORE (no rules, no schemas).
    `[a,b,...]`   → CORE + solo las TOOL_RULES cuyas tools estan en el subset.

    Distinguir `None` vs `[]` es critico para latencia: smalltalk con None
    inyectaba 60+ TOOL_RULES innecesarias (~7K chars) y tools schemas (~46K
    chars) en cada turn, forzando full prompt reprocessing.
    """
    if selected_tool_names is None:
        # Legacy: incluir todas las reglas, deduplicadas, en orden estable.
        seen: set[int] = set()
        parts = [CORE_PROMPT]
        for name in sorted(TOOL_RULES.keys()):
            rule = TOOL_RULES[name]
            rid = id(rule)
            if rid in seen:
                continue
            seen.add(rid)
            parts.append(rule)
        return "\n\n".join(parts)

    if not selected_tool_names:
        # Smalltalk explicito: solo el CORE.
        return CORE_PROMPT

    # Subset: filtrar reglas por nombre de tool, deduplicar por identidad.
    seen_ids: set[int] = set()
    rules: list[str] = []
    for name in selected_tool_names:
        rule = TOOL_RULES.get(name)
        if rule is None:
            continue
        rid = id(rule)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        rules.append(rule)
    if not rules:
        return CORE_PROMPT
    return CORE_PROMPT + "\n\n" + "\n\n".join(rules)


# Backwards-compat: algunos modulos importan SYSTEM_PROMPT directo (tests, GUI,
# server.py /agent/system_prompt endpoint). Lo mantenemos como el prompt full
# para que GET /agent/system_prompt siga mostrando algo util al usuario.
SYSTEM_PROMPT = build_system_prompt()


@dataclass
class ToolEvent:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentReply:
    content: str
    tool_events: list[ToolEvent] = field(default_factory=list)
    error: str | None = None
    mission: dict[str, Any] | None = None


class Gemma4Agent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.memory = MemoryStore(self.config.memory_path)
        self.state = AgentState(self.config.state_path)
        self.client = LLMClient(self.config)
        self.tools = ToolRegistry(self.memory, self.config.captures_dir, self.state, safety_enabled=self.config.enable_safety)
        # Wire subagent delegation: the `subagent` tool needs to spawn a fresh
        # Gemma4Agent. We give the registry a back-reference so it can call us.
        self.tools.parent_agent = self  # type: ignore[attr-defined]
        self.trace = TraceLogger(self.config.trace_path, self.config.enable_tracing)
        from .experience import ExperienceMemory
        self.experience = ExperienceMemory(self.config.memory_path.parent / "experience.sqlite")
        self.history: list[dict[str, Any]] = []
        self._recent_recalls: list[dict[str, Any]] = []
        self._explicit_plan_text: str = ""
        self._explicit_plan_steps: list[str] = []
        self._phrase_fires: list[dict[str, Any]] = []
        # Summarization cooldown so we don't spend an extra LLM call every
        # turn when the conversation has just been compacted. Resets per-clear.
        self._summarize_last_run_turn: int = -10
        self._fact_extract_last_run_turn: int = -10
        self._turn_counter: int = 0
        # Diagnostics for the current turn (visible in traces; surfaced to the
        # user only when the final reply looks empty so they are not left in
        # the dark).
        self._explicit_plan_status: dict[str, Any] = {}
        # Persona: nudges system prompt + preferred tools. Default = no nudge.
        from .personas import from_env as _persona_from_env
        self._persona = _persona_from_env()
        # TIER 1 #3: cache de microagents seleccionados a lo largo de la sesion.
        # Cuando un microagent matchea un turn, se agrega al cache y persiste
        # para siguientes turns (mantiene el KV cache caliente). agent.clear()
        # lo resetea junto con history.
        self._cached_microagents: list = []
        # TIER 1 #4: skills menu + critical block. Cacheado a nivel-instancia
        # porque el catalogo de skills es estatico (folder skills/ no cambia
        # mid-session). El KV cache del llama-server reutiliza el prefix.
        self._cached_skills_menu: str | None = None
        self._cached_skills_critical: str | None = None

    def clear(self) -> None:
        self.history.clear()
        self._recent_recalls = []
        self._summarize_last_run_turn = -10
        self._fact_extract_last_run_turn = -10
        self._turn_counter = 0
        self._cached_microagents = []
        # Skills cache: reset para que scan_skills() vuelva a leer disk en el
        # proximo turn (util si el dev agrega/modifica un SKILL.md durante
        # desarrollo). En produccion el catalogo no cambia mid-session.
        self._cached_skills_menu = None
        self._cached_skills_critical = None

    def set_persona(self, name: str) -> dict[str, Any]:
        """Switch the agent's persona by name. Returns the new persona info or an error dict."""
        from .personas import PERSONAS, get
        if name and name.strip().casefold() not in PERSONAS:
            return {"ok": False, "error": f"unknown persona: {name!r}", "available": sorted(PERSONAS.keys())}
        self._persona = get(name)
        return {
            "ok": True,
            "persona": self._persona.name,
            "description": self._persona.description,
            "preferred_tools": list(self._persona.preferred_tools),
            "tone": self._persona.tone,
        }

    def get_persona(self) -> dict[str, Any]:
        return {
            "persona": self._persona.name,
            "description": self._persona.description,
            "preferred_tools": list(self._persona.preferred_tools),
            "tone": self._persona.tone,
        }

    def _system_message(
        self,
        mode: AgentMode | None = None,
        plan: MissionPlan | None = None,
        selected_tool_names: list[str] | None = None,
        user_text: str | None = None,
    ) -> dict[str, str]:
        mode_hint = f"\n\n# Current mode\n{mode.system_hint}" if mode else ""
        plan_hint = f"\n\n{plan.prompt_hint()}" if plan and plan.prompt_hint() else ""
        persona_hint = f"\n\n{self._persona.system_hint}" if self._persona.system_hint else ""
        from .experience import format_recall_for_prompt
        from .explicit_plan import format_for_prompt as _format_explicit_plan
        from .project_context import format_for_prompt as _format_project_context
        from .project_context import load_context
        project_block = _format_project_context(load_context())
        project_section = f"\n\n{project_block}" if project_block else ""
        recall_hint = format_recall_for_prompt(self._recent_recalls)
        recall_section = f"\n\n{recall_hint}" if recall_hint else ""
        explicit_block = _format_explicit_plan(self._explicit_plan_text)
        explicit_section = f"\n\n{explicit_block}" if explicit_block else ""
        phrase_section = _format_phrase_fires(self._phrase_fires)
        phrase_section = f"\n\n{phrase_section}" if phrase_section else ""
        # Sprint 1 / item I1 #7: bloque "Tool Schemas EXACT" del informe de
        # optimizacion. Patron Daniel Farina (OpenCode-on-Gemma-4): reduce
        # errores de tool selection y argument naming. Opt-out via env var
        # GEMMA4_DISABLE_TOOL_SCHEMAS_HINT por si el dev necesita prompts
        # mas cortos en debug. Cacheado a nivel-instancia para no recompilar
        # el markdown en cada turno (62 tools = ~6 KB de markdown).
        #
        # PERF: si el caller pasa selected_tool_names (el subset que el
        # semantic router eligio para este turn), filtramos el markdown a solo
        # esos tools. De ~46K chars (62 tools full) a ~3-5K (4-6 tools), 10x
        # menos prefill por turno.
        tools_section = self._tool_schemas_hint(selected_tool_names=selected_tool_names)
        # PERF: el system prompt base ahora se filtra por subset: CORE + solo
        # reglas de las tools que el router eligio. Reduce ~7K chars sin
        # perder capacidad (cuando el LLM use la tool, la regla aparecera).
        prompt_base = build_system_prompt(selected_tool_names)
        # TIER 1 #3: microagents — markdown files con frontmatter que se
        # inyectan al system_prompt cuando user_text matchea sus triggers.
        # Diferencia ortogonal con TOOL_RULES:
        #   TOOL_RULES["X"]: como usar la tool X (regla de uso, viene con
        #     selected_tool_names).
        #   microagent: que SIGNIFICA un concepto / como diagnosticar (conoc.
        #     de dominio, viene con user_text).
        # Cache a nivel-instancia: lo que matchea en un turn persiste para
        # los siguientes (KV cache caliente entre turns relacionados).
        try:
            from .microagents import build_microagents_section
            microagents_section, self._cached_microagents = build_microagents_section(
                user_text or "",
                cached=self._cached_microagents,
            )
        except Exception:
            microagents_section = ""
        # TIER 1 #4: skills menu (compact, una linea por skill) + critical
        # block (full body de skills con priority=critical). Cacheado a
        # nivel-instancia: el catalogo skills/ no cambia mid-session.
        if self._cached_skills_menu is None or self._cached_skills_critical is None:
            try:
                from .skills_registry import scan_skills, build_menu, build_critical_block
                skills_list = scan_skills()
                self._cached_skills_menu = build_menu(skills_list)
                self._cached_skills_critical = build_critical_block(skills_list)
            except Exception:
                self._cached_skills_menu = ""
                self._cached_skills_critical = ""
        skills_critical = self._cached_skills_critical or ""
        skills_menu = self._cached_skills_menu or ""
        return {
            "role": "system",
            "content": f"{prompt_base}{mode_hint}{tools_section}{persona_hint}{project_section}{plan_hint}{explicit_section}{recall_section}{phrase_section}{microagents_section}{skills_critical}{skills_menu}\n\n# Persistent memory\n{self.memory.prompt_summary()}",
        }

    def _tool_schemas_hint(self, selected_tool_names: list[str] | None = None) -> str:
        """Construye el bloque "Tool Schemas EXACT" una sola vez por agent.

        Sprint 1 del optimization_roadmap.md. Mode seleccionado por el
        context_size del perfil activo:
          - ctx >= 32K  -> full (~11.6K tokens) — best argument fidelity.
          - ctx >= 16K  -> compact (~5.9K tokens) — descripciones cortas.
          - ctx <  16K  -> off (no hint; el catalogo nativo de tools del
                          schema en --jinja sigue siendo el camino).
        Override via GEMMA4_TOOL_SCHEMAS_HINT_MODE = full|compact|off|auto.
        Cache a nivel-instancia porque los schemas son estaticos.
        """
        import os as _os
        env_mode = (_os.environ.get("GEMMA4_TOOL_SCHEMAS_HINT_MODE") or "auto").strip().lower()
        # legacy opt-out kept for backward compat
        legacy_off = (_os.environ.get("GEMMA4_DISABLE_TOOL_SCHEMAS_HINT") or "").strip().lower()
        if legacy_off in {"1", "true", "yes", "on"}:
            env_mode = "off"
        if env_mode == "off":
            return ""
        if env_mode not in {"full", "compact", "auto"}:
            env_mode = "auto"
        if env_mode == "auto":
            ctx = int(self.config.context_size or 0)
            # full: solo en perfiles con ctx >=32K (performance). El hint
            # full es ~11.6K tokens, ~35% de un context 32K — aceptable.
            # compact: ~5.9K tokens. Activo en ctx >=12K (balanced_8gb post
            # Polish P2 que bajo de 16K -> 12K por VRAM tight) para que
            # queden >=6K tokens libres para conversacion + memoria.
            # off: ctx <12K (balanced 8K, light 4K) — el catalogo nativo
            # de tools via --jinja sigue siendo el camino sin overhead.
            if ctx >= 32768:
                mode = "full"
            elif ctx >= 12288:
                mode = "compact"
            else:
                return ""
        else:
            mode = env_mode

        # PERF: si el caller paso selected_tool_names (lista explicita, aunque
        # sea vacia), respetamos el contrato — no inyectamos schemas que el
        # router decidio no necesitar. Esto evita el bug de smalltalk metiendo
        # ~46KB / 11.6K tokens de schemas en cada turn sin necesidad.
        # `None` significa "no subset path requested" → comportamiento legacy
        # (full catalogo). Lista vacia `[]` significa "smalltalk / no tools".
        if selected_tool_names is not None:
            if not selected_tool_names:
                # Smalltalk / no tools necesarias: 0 schemas, 0 tokens.
                return ""
            subset_key = ",".join(sorted(set(selected_tool_names)))
            cache_key = f"_cached_tool_schemas_md_{mode}_{subset_key}"
            cached = getattr(self, cache_key, None)
            if cached is None:
                try:
                    from .tools import COMPOUND_TOOL_SCHEMAS, compile_tools_to_markdown_exact
                    wanted = set(selected_tool_names)
                    subset_schemas = [
                        s for s in COMPOUND_TOOL_SCHEMAS
                        if isinstance(s, dict)
                        and isinstance(s.get("function"), dict)
                        and s["function"].get("name") in wanted
                    ]
                    if subset_schemas:
                        cached = compile_tools_to_markdown_exact(
                            schemas=subset_schemas,
                            compact=(mode == "compact"),
                        )
                    else:
                        # Subset solicitado pero no matchea ningun schema
                        # (router devolvio nombres invalidos). No inyectar
                        # full por defensa — log y devolver vacio.
                        logger.warning("tool_schemas_hint: subset %s no matchea ningun schema; devolviendo vacio",
                                       sorted(wanted))
                        cached = ""
                except Exception:
                    cached = ""
                setattr(self, cache_key, cached)
            return f"\n\n{cached}" if cached else ""

        # Sin subset (caller paso None explicito): comportamiento legacy.
        cache_key = f"_cached_tool_schemas_md_{mode}"
        cached = getattr(self, cache_key, None)
        if cached is None:
            try:
                from .tools import compile_tools_to_markdown_exact
                cached = compile_tools_to_markdown_exact(compact=(mode == "compact"))
            except Exception:
                cached = ""
            setattr(self, cache_key, cached)
        return f"\n\n{cached}" if cached else ""

    def _messages(
        self,
        mode: AgentMode | None = None,
        plan: MissionPlan | None = None,
        selected_tool_names: list[str] | None = None,
        user_text: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            self._system_message(
                mode, plan,
                selected_tool_names=selected_tool_names,
                user_text=user_text,
            ),
            *self.history,
        ]

    def run_text(
        self,
        text: str,
        images: list[Path] | None = None,
        audios: list[Path] | None = None,
        progress: ProgressCallback | None = None,
    ) -> AgentReply:
        content = user_content(text, images=images, audios=audios)
        return self.run_content(content, progress=progress)

    def run_content(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None) -> AgentReply:
        self._turn_counter += 1
        mode = choose_mode(content, self.config.agent_mode, self.config.max_tokens)
        plan = plan_mission(content)
        turn_id = self.trace.new_turn_id()
        # Phrase-triggered routines: check the user's plain text against
        # saved on_phrase routines BEFORE the LLM call. Each matching routine
        # runs its steps once; the results are inlined into the system prompt
        # so Gemma can confirm naturally without re-running the tools.
        self._phrase_fires = []
        raw_text_early = _extract_user_text(content)
        if raw_text_early:
            try:
                from .domain_tools import (_looks_destructive,
                                            active_phrase_triggers)
                folded_input = _fold_match(raw_text_early)
                # Per-step timeout so a hung tool never blocks the whole turn.
                # Configurable via env; default 30s per step.
                import os as _os
                step_timeout = float(_os.environ.get("GEMMA4_PHRASE_STEP_TIMEOUT_S") or 30)
                for routine in active_phrase_triggers(self.state):
                    needle = _fold_match(str(routine.get("phrase") or ""))
                    if not needle or needle not in folded_input:
                        continue
                    # Extra safety for destructive routines: do NOT fire if the
                    # user message looks like a question or hypothetical that
                    # merely *mentions* the phrase. We check the steps for a
                    # destructive command token; if found, require the message
                    # to NOT contain a question mark and NOT start with a
                    # hypothetical opener ("que pasa si", "what if", "como se",
                    # "how do i", etc).
                    steps_for_routine = routine.get("steps") or []
                    is_destructive = False
                    for step in steps_for_routine:
                        if isinstance(step, dict):
                            cmd = (step.get("args") or {}).get("command", "") if isinstance(step.get("args"), dict) else ""
                            if cmd:
                                hit, _ = _looks_destructive(str(cmd))
                                if hit:
                                    is_destructive = True
                                    break
                    if is_destructive:
                        if "?" in raw_text_early:
                            self.trace.event(turn_id, "phrase_trigger_skipped_destructive_question",
                                             routine_id=routine.get("id"), phrase=routine.get("phrase"))
                            continue
                        hypotheticals = ("que pasa si", "que ocurre si", "que sucede si",
                                          "y si digo", "y si pongo", "y si escribo",
                                          "what if", "what happens if",
                                          "how do i", "how would i",
                                          "is it ok if", "is it safe to")
                        starts_hypothetical = any(folded_input.startswith(h) for h in hypotheticals)
                        if starts_hypothetical:
                            self.trace.event(turn_id, "phrase_trigger_skipped_destructive_hypothetical",
                                             routine_id=routine.get("id"), phrase=routine.get("phrase"))
                            continue
                    step_results: list[dict[str, Any]] = []
                    for step in routine.get("steps") or []:
                        if not isinstance(step, dict):
                            step_results.append({"ok": False, "error": "invalid step"})
                            continue
                        tname = str(step.get("tool") or "").strip()
                        targs = step.get("args") if isinstance(step.get("args"), dict) else {}
                        if not tname or tname == "routine":
                            step_results.append({"ok": False, "error": "invalid or recursive tool", "tool": tname})
                            continue
                        step_result = _run_with_timeout(self.tools.execute, tname, targs, timeout_s=step_timeout)
                        if step_result.get("_timed_out"):
                            step_results.append({"tool": tname, "ok": False, "error": f"step timed out after {step_timeout}s", "timed_out": True})
                            self.trace.event(turn_id, "phrase_trigger_step_timeout", routine_id=routine.get("id"), tool=tname, timeout_s=step_timeout)
                        elif step_result.get("_error"):
                            step_results.append({"tool": tname, "ok": False, "error": f"step raised: {step_result['_error']}", "exception": True})
                            self.trace.event(turn_id, "phrase_trigger_step_exception", routine_id=routine.get("id"), tool=tname, error=step_result["_error"])
                        else:
                            result = step_result.get("result") or {}
                            step_results.append({"tool": tname, "ok": bool(result.get("ok")), "error": result.get("error"), "status": result.get("status")})
                    fire = {
                        "routine_id": routine.get("id"),
                        "label": routine.get("label"),
                        "phrase": routine.get("phrase"),
                        "results": step_results,
                    }
                    self._phrase_fires.append(fire)
                    self.trace.event(turn_id, "phrase_trigger_fired",
                                     routine_id=routine.get("id"),
                                     phrase=routine.get("phrase"),
                                     step_count=len(step_results),
                                     ok_count=sum(1 for r in step_results if r.get("ok")),
                                     timeouts=sum(1 for r in step_results if r.get("timed_out")))
            except Exception as exc:
                self.trace.event(turn_id, "phrase_trigger_error", error=str(exc))

        # Semantic memory: recall similar past turns. Hint-only, never blocks.
        self._recent_recalls = []
        raw_text = raw_text_early
        try:
            from .semantic_router import embed as _embed_text
            if raw_text and len(raw_text.split()) >= 2:
                self._recent_recalls = self.experience.recall(raw_text, embed_fn=_embed_text, k=3)
                if self._recent_recalls:
                    self.trace.event(turn_id, "experience_recall",
                                     query=raw_text[:200],
                                     count=len(self._recent_recalls),
                                     ids=[r["id"] for r in self._recent_recalls],
                                     distances=[r["distance"] for r in self._recent_recalls])
        except Exception as exc:
            self.trace.event(turn_id, "experience_recall_failed", error=str(exc))

        # Explicit Planner -> Executor (Goose-style). Only spend the extra LLM
        # call when the request is multi-step or the user asked for a plan.
        self._explicit_plan_text = ""
        self._explicit_plan_steps = []
        self._explicit_plan_status = {}
        # PERF: el explicit planner es una segunda llamada al LLM (45s timeout)
        # que se disparaba por heuristica (should_plan). Para queries simples
        # ("abre Steam") era overhead innecesario. Lo hacemos OPT-IN: default
        # OFF, se activa con GEMMA4_AGENT_EXPLICIT_PLAN=true. La capacidad
        # multi-step del LLM se preserva porque el sistema sigue usando el
        # MissionPlan implicito (plan_mission) + multi-turn tool calls.
        import os as _os_plan
        explicit_plan_enabled = (_os_plan.environ.get("GEMMA4_AGENT_EXPLICIT_PLAN") or "").strip().lower() in {"1", "true", "yes", "on"}
        if explicit_plan_enabled:
            try:
                from .explicit_plan import generate_plan, should_plan
                if raw_text and should_plan(raw_text, len(plan.steps)):
                    self.trace.event(turn_id, "explicit_plan_start", reason="multi_step")
                    result = generate_plan(
                        raw_text,
                        chat_fn=lambda msgs: self.client.chat(msgs, tools=None, enable_thinking=False, parallel_tool_calls=False, max_tokens=350, timeout_s=45.0),
                    )
                    if result.get("ok") and result.get("plan"):
                        self._explicit_plan_text = str(result["plan"])
                        self._explicit_plan_steps = list(result.get("steps") or [])
                        self._explicit_plan_status = {"state": "ready", "step_count": len(self._explicit_plan_steps)}
                        self.trace.event(turn_id, "explicit_plan_ready",
                                         step_count=len(self._explicit_plan_steps),
                                         plan_chars=len(self._explicit_plan_text))
                    elif result.get("skipped"):
                        self._explicit_plan_status = {"state": "skipped", "reason": "model_said_no_plan"}
                        self.trace.event(turn_id, "explicit_plan_skipped", reason="model_said_no_plan")
                    elif not result.get("ok"):
                        self._explicit_plan_status = {"state": "failed", "error": result.get("error")}
                        self.trace.event(turn_id, "explicit_plan_failed", error=result.get("error"))
            except Exception as exc:
                self._explicit_plan_status = {"state": "error", "error": str(exc)}
                self.trace.event(turn_id, "explicit_plan_error", error=str(exc))
        else:
            self._explicit_plan_status = {"state": "disabled", "reason": "env_var_off"}
        _progress(
            progress,
            "start",
            mode=mode.name,
            steps=len(plan.steps),
            thinking=mode.enable_thinking,
            max_turns=self.config.max_agent_turns,
        )
        self.trace.event(
            turn_id,
            "request_start",
            mode=mode.name,
            content=summarize_content(content),
            mission_plan=plan.as_dict(),
            thinking=mode.enable_thinking,
            parallel_tool_calls=mode.parallel_tool_calls,
            max_tokens=mode.max_tokens,
        )
        selected_tool_names = select_tool_names(content, plan, safety_enabled=self.config.enable_safety)
        semantic_fallback = bool(getattr(select_tool_names, "_last_fallback_used", False))
        # Persona nudge: ensure the persona's preferred tools are in the
        # subset. Append without duplicating; _cap_tools later trims if it
        # blows the limit. Default persona has no preferred tools so this is
        # a no-op for most users.
        if self._persona.preferred_tools:
            existing = set(selected_tool_names)
            for tool_name in self._persona.preferred_tools:
                if tool_name not in existing:
                    selected_tool_names.append(tool_name)
                    existing.add(tool_name)
        selected_schemas = self.tools.schemas_for_names(selected_tool_names)
        self.trace.event(turn_id, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas), semantic_fallback=semantic_fallback, persona=self._persona.name)
        _progress(progress, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas))
        self._compact_completed_history()
        self.history.append({"role": "user", "content": _compact_live_content(content)})
        events: list[ToolEvent] = []
        failure_log: list[dict[str, Any]] = []
        replan_done = False

        # Loop detector: registra cada tool execution con result canonicalizado y
        # detecta 5 patrones de stuck (repeat, unknown_tool, ping_pong, circuit
        # breaker, vision_not_found). Two-tier escalation: warning -> critical.
        # Vive por-turn (un user request); se evita carry-over que confunda al
        # LLM entre preguntas distintas.
        from .loop_detection import LoopState
        loop_state = LoopState()
        loop_aborted = False  # se setea True si detectamos critical

        # Structural per-tool verifier (TIER 1 #2). Cada tool ejecutada produce
        # un VerifierOutcome (confirmed True/False/None) que se acumula y al
        # final del turn se rinde como footer honesto en el reply. Si el
        # outcome trae evidence_keys, los inyecta al loop_state para resetear
        # warning_count en progreso real (integration con TIER 1 #1).
        from . import verifiers as _verifiers_registry  # noqa: F401  registra via decorators
        from .verify_core import verify as _verify, summarize_verifiers, VerifierOutcome
        verifier_outcomes: list[VerifierOutcome] = []

        # TIER 2 #5: MissionGoal — verifier estructural por-mision (Voyager pattern).
        # Construido al inicio del turn desde el user_text crudo. Cada tool call
        # marca su contribucion al objetivo via mission_goal.update_with_tool.
        # Al final, compute_mission_outcome combina con los per-tool verifier
        # outcomes para producir un MissionOutcome con status semantico
        # (COMPLETED/PARTIAL/FAILED/TOOL_OK_VERIFIER_INCONCLUSIVE/...).
        from .mission_goal import MissionGoal as _MissionGoal
        from .mission_outcome import (
            compute_mission_outcome as _compute_mission_outcome,
            mission_footer as _mission_footer,
            build_tool_records as _build_tool_records,
        )
        mission_goal = _MissionGoal.from_user_text(raw_text_early or "")

        for _turn in range(self.config.max_agent_turns):
            _progress(
                progress,
                "llm_start",
                turn=_turn + 1,
                max_turns=self.config.max_agent_turns,
                tools=len(events),
            )
            try:
                resp = self.client.chat(
                    self._messages(mode, plan, selected_tool_names=selected_tool_names, user_text=raw_text_early),
                    tools=selected_schemas,
                    enable_thinking=mode.enable_thinking,
                    parallel_tool_calls=mode.parallel_tool_calls,
                    max_tokens=mode.max_tokens,
                )
            except Exception as exc:
                if _looks_like_context_overflow(str(exc)):
                    _progress(progress, "context_retry", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "context_retry", error=str(exc), tool_events=len(events))
                    self._compact_active_history_for_retry()
                    # Drop the lowest-priority half of the subset, keeping at
                    # least 4. The planner already orders by priority (utility
                    # tools last), so this preserves the most relevant ones.
                    keep_count = max(4, len(selected_tool_names) // 2)
                    retry_tool_names = selected_tool_names[:keep_count]
                    selected_tool_names = retry_tool_names  # propagar al system prompt tambien
                    self.trace.event(turn_id, "subset_truncate_retry", original=len(selected_tool_names), kept=len(retry_tool_names))
                    selected_schemas = self.tools.schemas_for_names(retry_tool_names)
                    try:
                        resp = self.client.chat(
                            self._messages(mode, plan, selected_tool_names=selected_tool_names, user_text=raw_text_early),
                            tools=selected_schemas,
                            enable_thinking=mode.enable_thinking,
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=mode.max_tokens,
                        )
                    except Exception as retry_exc:
                        _progress(progress, "error", error=str(retry_exc), tools=len(events))
                        self.trace.event(turn_id, "llm_error", error=str(retry_exc), tool_events=len(events), after_context_retry=True)
                        return AgentReply(content="", tool_events=events, error=str(retry_exc))
                    else:
                        self.trace.event(turn_id, "context_retry_ok", schema_count=len(selected_schemas))
                        _progress(progress, "context_retry_ok", tools=len(events), schema_count=len(selected_schemas))
                else:
                    _progress(progress, "error", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "llm_error", error=str(exc), tool_events=len(events))
                    return AgentReply(content="", tool_events=events, error=str(exc))

            choice = (resp.get("choices") or [{}])[0]
            raw_msg = choice.get("message") or {}
            msg = sanitize_assistant_message(raw_msg)
            assistant_content = msg.get("content") or ""
            raw_tool_calls = msg.get("tool_calls") or []
            self.trace.event(
                turn_id,
                "llm_response",
                finish_reason=choice.get("finish_reason"),
                content_chars=len(assistant_content),
                tool_call_count=len(raw_tool_calls),
                stripped_reasoning=any(k in raw_msg for k in ("reasoning", "reasoning_content", "reasoning_details")),
            )
            _progress(
                progress,
                "llm_response",
                turn=_turn + 1,
                tool_calls=len(raw_tool_calls),
                tools=len(events),
            )

            if not raw_tool_calls:
                assistant_content = sanitize_text(assistant_content)
                assistant_content = self._guard_unverified_final(assistant_content, events)
                assistant_content = self._guard_phrase_confirm(assistant_content)
                assistant_content = self._guard_plan_status(assistant_content)
                # Defensa: si el LLM emitio en el reply mismo un footer estilo
                # "[N verificada(s)]" o "[misión: ...]" (porque vio uno en el
                # historial), lo strippeamos antes de pegar el nuestro. Sino,
                # el reply muestra footers duplicados.
                assistant_content = _strip_trailing_footers(assistant_content)
                # IMPORTANTE: guardamos en el history la version SIN footers.
                # Los footers son metadata para el usuario, no contenido. Si
                # los pegaramos al history, el LLM los veria como contenido
                # legitimo del asistente y los reproduciria proximo turn,
                # bloating context + duplicando texto.
                content_for_history = assistant_content
                # TIER 1 #2: footer estructural honest del verifier per-tool.
                # Solo aparece si hay failed o unverifiable; silencioso si todo OK.
                verifier_footer = summarize_verifiers(verifier_outcomes)
                if verifier_footer:
                    assistant_content = assistant_content + verifier_footer
                    self.trace.event(
                        turn_id, "verifier_footer",
                        confirmed=sum(1 for o in verifier_outcomes if o.confirmed is True),
                        failed=sum(1 for o in verifier_outcomes if o.confirmed is False),
                        unverifiable=sum(1 for o in verifier_outcomes if o.confirmed is None),
                    )
                # TIER 2 #5: MissionOutcome — status semantico final del turn.
                # Combina mission_goal (objective fulfilled?) con verifier counts
                # (per-tool measured effect) y emite footer SOLO si aporta info
                # (PARTIAL/FAILED/INTENT_NOT_FULFILLED/TOOL_OK_VERIFIER_INCONCLUSIVE).
                _tool_records_for_outcome = _build_tool_records(events, verifier_outcomes)
                mission_outcome = _compute_mission_outcome(
                    mission_goal, _tool_records_for_outcome, content_for_history,
                )
                _mission_extra_footer = _mission_footer(mission_outcome)
                if _mission_extra_footer:
                    assistant_content = assistant_content + _mission_extra_footer
                self.trace.event(
                    turn_id, "mission_outcome",
                    status=mission_outcome.status.value,
                    summary=mission_outcome.summary,
                    confirmed=mission_outcome.confirmed_count,
                    failed=mission_outcome.failed_count,
                    unverified=mission_outcome.unverified_count,
                    expected_total=mission_outcome.expected_total,
                    expected_satisfied=mission_outcome.expected_satisfied,
                )
                mission = evaluate_mission(events, assistant_content, plan)
                # Enriquecer el mission dict legacy con el outcome estructural
                # (no rompe consumidores existentes — agrega claves nuevas).
                if isinstance(mission, dict):
                    mission["mission_goal_status"] = mission_outcome.status.value
                    mission["mission_goal_summary"] = mission_outcome.summary
                    mission["mission_goal_progress"] = [
                        mission_outcome.expected_satisfied,
                        mission_outcome.expected_total,
                    ]
                # History recibe la version SIN footers (ver comentario arriba).
                self.history.append({"role": "assistant", "content": content_for_history})
                # Subset summary: which sent tools were actually used vs idle.
                used_tools = {e.name for e in events}
                router_stats = {
                    "subset_size": len(selected_tool_names),
                    "used_count": len(used_tools),
                    "unused_count": len(set(selected_tool_names) - used_tools),
                    "used": sorted(used_tools),
                    "unused": sorted(set(selected_tool_names) - used_tools),
                }
                self.trace.event(turn_id, "router_stats", **router_stats)
                self.trace.event(turn_id, "final", content=assistant_content, tool_events=len(events), mission=mission)
                # Persist this turn into semantic experience memory (hint-only,
                # never blocks). Best-effort: failure is logged and swallowed.
                try:
                    from .semantic_router import embed as _embed_text
                    raw_text = _extract_user_text(content)
                    used_tools = sorted({e.name for e in events})
                    mission_status = (mission or {}).get("mission_status") if isinstance(mission, dict) else None
                    rec = self.experience.record(
                        turn_id=turn_id,
                        user_input=raw_text,
                        tools_used=used_tools,
                        outcome=assistant_content[:1000],
                        mission_status=mission_status,
                        summary=assistant_content[:400],
                        embed_fn=_embed_text,
                    )
                    if rec.get("ok"):
                        self.trace.event(turn_id, "experience_recorded", id=rec.get("id"))
                except Exception as exc:
                    self.trace.event(turn_id, "experience_record_failed", error=str(exc))
                # Fact extraction: opt-in via env. Cooldown so we do not call
                # the LLM every turn. Skips short / trivial turns.
                if _fact_extraction_enabled():
                    cooldown = _fact_extraction_cooldown_turns()
                    if (self._turn_counter - self._fact_extract_last_run_turn) >= cooldown:
                        raw_text_now = _extract_user_text(content)
                        if raw_text_now and len(raw_text_now.split()) >= 5:
                            try:
                                facts = self._extract_facts(raw_text_now, assistant_content)
                                if facts:
                                    save_result = self.memory.auto_save(facts)
                                    self.trace.event(turn_id, "facts_extracted",
                                                     count=len(facts),
                                                     added=save_result.get("added"),
                                                     total_auto=save_result.get("total_auto"))
                                    self._fact_extract_last_run_turn = self._turn_counter
                                else:
                                    self.trace.event(turn_id, "facts_extraction_empty")
                                    self._fact_extract_last_run_turn = self._turn_counter
                            except Exception as exc:
                                self.trace.event(turn_id, "facts_extraction_failed", error=str(exc))
                self._compact_completed_history()
                _progress(progress, "final", tools=len(events), mission=mission)
                return AgentReply(content=assistant_content, tool_events=events, mission=mission)

            self.history.append(msg)

            image_results: list[tuple[Path, dict[str, Any]]] = []
            subset_set = set(selected_tool_names)

            # Phase 1: parse + classify all calls (no execution yet).
            prepared: list[dict[str, Any]] = []
            for raw_call in raw_tool_calls:
                fn = raw_call.get("function") or {}
                name = fn.get("name", "")
                args, parse_error = _parse_args(fn.get("arguments", {}))
                in_subset = name in subset_set
                self.trace.event(turn_id, "tool_call", name=name, args=args, in_subset=in_subset, parse_error=parse_error)
                if not in_subset:
                    self.trace.event(turn_id, "router_miss", name=name, sent=sorted(subset_set))
                prepared.append({
                    "raw_call": raw_call,
                    "name": name,
                    "args": args,
                    "parse_error": parse_error,
                })

            # Phase 2: execute. Parallel when enabled, multiple valid calls
            # and the LLM did not request a strict order.
            parallel_ok = _parallel_tools_enabled() and sum(1 for p in prepared if not p["parse_error"]) >= 2
            if parallel_ok:
                self.trace.event(turn_id, "tools_parallel_start", count=len(prepared))
                self._execute_calls_parallel(prepared, progress, len(events))
            else:
                self._execute_calls_sequential(prepared, progress, len(events))

            # Phase 3: apply results in original order to events, history,
            # traces, failure log, image collection.
            for prep in prepared:
                name = prep["name"]
                args = prep["args"]
                raw_call = prep["raw_call"]
                result = prep.get("result") or {}
                events.append(ToolEvent(name=name, args=args, result=result))
                self.trace.event(turn_id, "tool_result", name=name, result=result)
                # Loop detector: record y check antes de seguir con la siguiente
                # tool de este batch. exists=True salvo que el result diga
                # "unknown tool" en el error (tool no registrada). El detector
                # filtra timestamps/pids del result_sig para no confundir polling
                # legitimo con loop.
                err_str = str(result.get("error") or "")
                tool_exists = not err_str.startswith("unknown tool:")
                loop_state.record(name, args, exists=tool_exists, result=result)

                # Verifier estructural per-tool (TIER 1 #2): mide el efecto real
                # post-ejecucion. confirmed=True/False/None. Si trae
                # evidence_keys (e.g. "app:Steam") los inyectamos al loop_state
                # para que reset el warning_count en progreso real.
                v_outcome = _verify(name, args, result)
                verifier_outcomes.append(v_outcome)
                # TIER 2 #5: mission_goal tracking — marca el primer expected
                # outcome cuyo kind matchee esta call (segun action/args).
                # Pasa ok del result; el confirmed real lo decide el verifier
                # arriba y se combina en compute_mission_outcome.
                mission_goal.update_with_tool(name, args, bool(result.get("ok")))
                self.trace.event(
                    turn_id, "verifier",
                    tool=name,
                    confirmed=v_outcome.confirmed,
                    reason=v_outcome.reason,
                    evidence_keys=v_outcome.evidence_keys,
                )
                if v_outcome.confirmed is True:
                    for ek in (v_outcome.evidence_keys or []):
                        loop_state.record_evidence(ek)
                # Si la tool reporto ok=True pero el verifier dice confirmed=False,
                # algo es inconsistente — vale la pena loggearlo para debug.
                if v_outcome.confirmed is False and result.get("ok"):
                    self.trace.event(
                        turn_id, "verifier_disagrees",
                        tool=name, reason=v_outcome.reason,
                    )
                if not result.get("ok"):
                    status_norm = str(result.get("status") or "").casefold()
                    completion = str(result.get("completion_status") or "").casefold()
                    is_blocked = (
                        status_norm.startswith("needs_")
                        or completion.startswith("needs_")
                    )
                    if not is_blocked:
                        failure_log.append({"step": len(events), "tool": name, "error": str(result.get("error") or "")[:300]})
                    else:
                        self.trace.event(turn_id, "failure_excluded_from_replan", tool=name, status=status_norm, completion=completion)
                _progress(
                    progress,
                    "tool_end",
                    name=name,
                    ok=bool(result.get("ok")),
                    status=str(result.get("status") or ""),
                    verified=result.get("verified"),
                    index=len(events),
                )
                self.history.append({
                    "role": "tool",
                    "tool_call_id": raw_call.get("id", f"call_{name}"),
                    "content": json.dumps(_compact_tool_result(name, args, result), ensure_ascii=False),
                })

                image_path = result.get("image_path")
                if image_path:
                    image_results.append((Path(str(image_path)), result))

            for image_path, result in image_results:
                _progress(progress, "image_injected", path=str(image_path))
                self._inject_tool_image(image_path, result)

            # Honesty guard: if any tool in the just-processed batch returned
            # unverified/failed/needs_verification, inject an explicit user-role
            # note so Gemma cannot silently move on as if everything succeeded.
            unverified_in_batch = [
                (raw_call.get("function") or {}).get("name", "")
                for raw_call, ev in zip(raw_tool_calls, events[-len(raw_tool_calls):])
                if _is_unverified_result(ev.result)
            ]
            if unverified_in_batch:
                summary = ", ".join(unverified_in_batch[:6])
                self.history.append({
                    "role": "user",
                    "content": (
                        "[system note] In the previous step, these tools returned "
                        f"unverified/failed results: {summary}. Do NOT claim those "
                        "actions are complete. Either run a verify(...), retry with "
                        "different args, or tell the user honestly what could not be "
                        "verified."
                    ),
                })
                self.trace.event(turn_id, "unverified_intermediate_warning", tools=unverified_in_batch)

            # Loop detector check: si critical, abort el outer for y produci un
            # reply honesto. Si warning, inyecta el mensaje al historial para que
            # el LLM lo vea en el proximo client.chat() y corrija solo.
            stuck = loop_state.detect_stuck()
            if stuck is not None:
                self.trace.event(
                    turn_id, "loop_detector",
                    level=stuck.level, pattern=stuck.pattern, detail=stuck.detail,
                )
                _progress(progress, "loop_detector",
                          level=stuck.level, pattern=stuck.pattern)
                if stuck.level == "critical":
                    self.history.append({
                        "role": "user",
                        "content": stuck.message,
                    })
                    loop_aborted = True
                    break  # sale del outer `for _turn in range(max_agent_turns)`
                else:
                    # warning: nudge al LLM, sigue el loop normal
                    self.history.append({
                        "role": "user",
                        "content": stuck.message,
                    })

            # Replanning trigger: 2+ tool failures while we have an explicit
            # plan and have not replanned yet. Cheap: one extra LLM call.
            if (
                not replan_done
                and self._explicit_plan_text
                and len(failure_log) >= 2
            ):
                self.trace.event(turn_id, "replan_start", failures=len(failure_log))
                try:
                    from .explicit_plan import replan
                    revised = replan(
                        raw_text,
                        self._explicit_plan_text,
                        failure_log,
                        chat_fn=lambda msgs: self.client.chat(msgs, tools=None, enable_thinking=False, parallel_tool_calls=False, max_tokens=350, timeout_s=45.0),
                    )
                    if revised.get("ok") and revised.get("plan"):
                        self._explicit_plan_text = str(revised["plan"])
                        self._explicit_plan_steps = list(revised.get("steps") or [])
                        replan_done = True
                        self.trace.event(turn_id, "replan_ready",
                                         step_count=len(self._explicit_plan_steps),
                                         give_up=bool(revised.get("give_up")))
                    else:
                        self.trace.event(turn_id, "replan_failed", error=revised.get("error"))
                except Exception as exc:
                    self.trace.event(turn_id, "replan_error", error=str(exc))

        if loop_aborted:
            final = (
                "Detecte que estaba repitiendo la misma accion sin avanzar. "
                "Corte para no quemar tiempo. Decime que querias lograr o "
                "probemos otra estrategia."
            )
            reason = "loop_aborted"
        else:
            final = "No pude terminar la tarea dentro del limite de turnos."
            reason = "max_turns"
        mission = evaluate_mission(events, final, plan)
        self.history.append({"role": "assistant", "content": final})
        self.trace.event(turn_id, reason, content=final, tool_events=len(events), mission=mission)
        self._compact_completed_history()
        _progress(progress, "max_turns", tools=len(events), mission=mission)
        return AgentReply(content=final, tool_events=events, mission=mission)

    def _execute_calls_sequential(
        self,
        prepared: list[dict[str, Any]],
        progress: ProgressCallback | None,
        base_count: int,
    ) -> None:
        """Run prepared tool calls one by one, populating prep['result'].

        Mirrors the original single-thread behavior: emit tool_start before
        each execute, short-circuit malformed-args preps with a synthetic
        result. Phase-3 in the main loop handles tool_end / history append.
        """
        for index, prep in enumerate(prepared):
            name = prep["name"]
            args = prep["args"]
            parse_error = prep["parse_error"]
            if parse_error:
                prep["result"] = {
                    "ok": False,
                    "status": "failed",
                    "verified": False,
                    "error": (
                        f"tool args parse error: {parse_error}. Re-emit the call "
                        "with valid JSON for the 'arguments' field."
                    ),
                    "tool": name,
                    "evidence": "malformed_json_args",
                }
                continue
            _progress(progress, "tool_start", name=name, args=args, index=base_count + index + 1)
            prep["result"] = self.tools.execute(name, args)

    def _execute_calls_parallel(
        self,
        prepared: list[dict[str, Any]],
        progress: ProgressCallback | None,
        base_count: int,
    ) -> None:
        """Run prepared tool calls concurrently with a small thread pool.

        max_workers=4. Parse-error preps get a synthetic result without a
        thread submission. Order is preserved because phase-3 iterates
        `prepared` in original order; we just fill prep['result'] from each
        completed future.
        """
        import concurrent.futures
        valid_preps: list[tuple[int, dict[str, Any]]] = []
        for index, prep in enumerate(prepared):
            if prep["parse_error"]:
                prep["result"] = {
                    "ok": False,
                    "status": "failed",
                    "verified": False,
                    "error": (
                        f"tool args parse error: {prep['parse_error']}. Re-emit "
                        "the call with valid JSON for the 'arguments' field."
                    ),
                    "tool": prep["name"],
                    "evidence": "malformed_json_args",
                }
            else:
                valid_preps.append((index, prep))
        if not valid_preps:
            return
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, len(valid_preps)),
            thread_name_prefix="gemma4_par_tool",
        ) as pool:
            future_to_prep: dict[Any, dict[str, Any]] = {}
            for index, prep in valid_preps:
                _progress(progress, "tool_start", name=prep["name"], args=prep["args"], index=base_count + index + 1)
                future = pool.submit(self.tools.execute, prep["name"], prep["args"])
                future_to_prep[future] = prep
            for future in concurrent.futures.as_completed(future_to_prep):
                prep = future_to_prep[future]
                try:
                    prep["result"] = future.result()
                except Exception as exc:
                    prep["result"] = {
                        "ok": False,
                        "status": "failed",
                        "verified": False,
                        "error": f"tool raised in parallel exec: {exc}",
                        "tool": prep["name"],
                        "evidence": "parallel_exception",
                    }

    def _inject_tool_image(self, path: Path, result: dict[str, Any]) -> None:
        if not path.exists():
            return
        text = (
            "Esta imagen fue capturada por una tool visual. "
            f"Tamano reportado: {result.get('width')}x{result.get('height')} px. "
            "Usala como evidencia visual para continuar."
        )
        self.history.append({
            "role": "user",
            "content": [image_part(path), {"type": "text", "text": text}],
        })

    def _compact_completed_history(self) -> None:
        """Keep future turns small after a completed tool cycle.

        Two-stage strategy inspired by OpenHands:
        1. Cheap pass: drop tool messages and tool_calls, shorten strings.
        2. If estimated context usage is still > 75% of context_size, ask
           Gemma 4 itself to summarize the oldest half of the conversation
           into a single 'summary so far' assistant message. The most recent
           turns are kept verbatim.

        Bypassed entirely with GEMMA4_AGENT_SUMMARIZATION=false. Stage 1 always
        runs as a safety net even when summarization is disabled.
        """
        budget = _compute_context_budget(self.config.context_size)
        compacted: list[dict[str, Any]] = []
        for msg in self.history:
            role = str(msg.get("role") or "")
            if role == "tool":
                continue
            if role == "assistant" and msg.get("tool_calls"):
                continue
            if role not in {"user", "assistant"}:
                continue
            compacted.append({"role": role, "content": _compact_history_content(msg.get("content"))})
        self.history = compacted[-budget["soft_cap_messages"]:]

        if not _summarization_enabled():
            self.history = self.history[-budget["hard_cap_messages"]:]
            return

        # Stage 2: if the cleaned-up history is still large, summarize the
        # oldest half. We keep the last `keep_tail` messages verbatim. Both
        # the byte threshold and the keep_tail scale with context_size, so a
        # 4K model summarizes early while a 200K model can keep long history.
        threshold = budget["summarize_threshold_chars"]
        estimated = sum(len(_message_text_estimate(m)) for m in self.history)
        if estimated <= threshold or len(self.history) <= budget["keep_tail_messages"] + 2:
            return
        cooldown_turns = _summarization_cooldown_turns()
        if (self._turn_counter - self._summarize_last_run_turn) < cooldown_turns:
            self.trace.event(self.trace.new_turn_id(), "summarization_cooldown_skip",
                             since_last=self._turn_counter - self._summarize_last_run_turn,
                             cooldown=cooldown_turns)
            self.history = self.history[-budget["hard_cap_messages"]:]
            return
        keep_tail = budget["keep_tail_messages"]
        head = self.history[:-keep_tail]
        tail = self.history[-keep_tail:]
        summary_text = self._summarize_history_block(head)
        if not summary_text:
            self.history = self.history[-budget["hard_cap_messages"]:]
            return
        summary_msg = {
            "role": "assistant",
            "content": f"[Conversation summary so far]\n{summary_text}",
        }
        self.history = [summary_msg, *tail]
        self._summarize_last_run_turn = self._turn_counter

    def _extract_facts(self, user_text: str, assistant_text: str) -> list[dict[str, str]]:
        """Ask Gemma to extract 0-3 small facts about the user from this turn.

        Returns a list of {key, value} dicts. Empty list when nothing is worth
        saving (the LLM is instructed to return [] for trivial turns). Best
        effort: any JSON parse failure or LLM error returns [].

        We do NOT pass the existing memory to the LLM - this is a stateless
        single-turn extraction. Dedup happens in memory.auto_save (same key
        overwrites the older value).
        """
        prompt = (
            "Extrae 0 a 3 hechos pequenos sobre el usuario de este turno. "
            "Solo extrae si son hechos persistentes y utiles para futuras "
            "conversaciones: preferencias claras (idioma, hora, dispositivos), "
            "datos personales que el usuario menciono explicitamente (nombre, "
            "rol, ubicacion), o contexto recurrente (proyecto en el que trabaja, "
            "apps que usa). NO extraigas cosas efimeras (lo que pidio en este "
            "turno, lo que estas haciendo ahora). NO inventes. Si nada califica, "
            "devuelve exactamente '[]'.\n\n"
            "Formato de respuesta: JSON array de objetos con keys 'key' (slug "
            "corto snake_case) y 'value' (frase de menos de 100 chars). "
            "Ejemplo: [{\"key\":\"idioma\",\"value\":\"prefiere espanol\"},"
            "{\"key\":\"editor\",\"value\":\"usa VS Code\"}]. Responde SOLO el "
            "array JSON, sin markdown ni texto extra.\n\n"
            f"Turno del usuario:\n{user_text[:1500]}\n\n"
            f"Respuesta del asistente:\n{assistant_text[:1500]}\n\n"
            "JSON:"
        )
        try:
            resp = self.client.chat(
                [{"role": "user", "content": prompt}],
                tools=None,
                enable_thinking=False,
                parallel_tool_calls=False,
                max_tokens=200,
                timeout_s=20.0,
            )
        except Exception:
            return []
        choices = resp.get("choices") or []
        if not choices:
            return []
        raw = str((choices[0].get("message") or {}).get("content") or "").strip()
        from .reasoning import sanitize_text
        cleaned = sanitize_text(raw).strip()
        # The LLM sometimes wraps in ```json ... ``` despite instructions.
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        # Try to find the array bracket if there is prose around it.
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end < 0 or end < start:
            return []
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        facts: list[dict[str, str]] = []
        for item in parsed[:3]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if key and value and len(value) <= 200:
                facts.append({"key": key, "value": value})
        return facts

    def _summarize_history_block(self, messages: list[dict[str, Any]]) -> str:
        """Ask Gemma 4 to compress the given message block into ~200 words.

        Best-effort: returns '' on any LLM failure so the caller falls back
        to plain truncation.
        """
        if not messages:
            return ""
        # Render the block as plain prose; do NOT include role markers like
        # 'tool' that would confuse the summarizer.
        rendered_parts: list[str] = []
        for msg in messages:
            role = str(msg.get("role") or "user")
            text = _message_text_estimate(msg)
            if not text.strip():
                continue
            rendered_parts.append(f"{role}: {text[:1200]}")
        rendered = "\n".join(rendered_parts)[:12000]
        prompt = (
            "Resume la siguiente conversacion en espanol en aproximadamente "
            "200 palabras. Conserva: 1) lo que el usuario pidio en cada turno, "
            "2) que tools se usaron y con que resultado, 3) decisiones tomadas, "
            "4) datos concretos que el usuario aporto (paths, nombres, ids). "
            "Omite saludos, formato decorativo y razonamientos internos. "
            "Devuelve solo el resumen, sin titulos.\n\n"
            f"CONVERSACION:\n{rendered}\n\nRESUMEN:"
        )
        try:
            resp = self.client.chat(
                [{"role": "user", "content": prompt}],
                tools=None,
                enable_thinking=False,
                parallel_tool_calls=False,
                max_tokens=400,
                timeout_s=60.0,
            )
            choices = resp.get("choices") or []
            if not choices:
                return ""
            msg = choices[0].get("message") or {}
            summary = str(msg.get("content") or "").strip()
            # Strip any leaked thinking tags or assistant role prefix.
            from .reasoning import sanitize_text
            return sanitize_text(summary)[:2000]
        except Exception as exc:
            self.trace.event(self.trace.new_turn_id(), "summarization_failed", error=str(exc))
            return ""

    def _compact_active_history_for_retry(self) -> None:
        """Aggressive fallback when llama-server reports context overflow.

        Uses `_compute_context_budget(context_size)` to decide how many tail
        messages to keep and how aggressively to ellipsize tool/assistant
        contents. Keeps the budget tight (~30% of `hard_cap_messages`) so
        the retry has room for the new turn.
        """
        budget = _compute_context_budget(self.config.context_size)
        tail_count = max(4, budget["hard_cap_messages"] // 3)
        ellipsize_to = max(400, budget["history_chars"] // tail_count // 2)
        trimmed: list[dict[str, Any]] = []
        for msg in self.history[-tail_count:]:
            role = str(msg.get("role") or "")
            if role == "tool":
                trimmed.append({
                    "role": "tool",
                    "tool_call_id": str(msg.get("tool_call_id") or "call_compacted"),
                    "content": _middle_ellipsis(str(msg.get("content") or ""), ellipsize_to),
                })
            elif role == "assistant":
                clean = {"role": "assistant", "content": _middle_ellipsis(str(msg.get("content") or ""), ellipsize_to)}
                if msg.get("tool_calls"):
                    clean["tool_calls"] = _compact_json(msg.get("tool_calls"), max_items=4, max_string=500)
                trimmed.append(clean)
            elif role == "user":
                trimmed.append({"role": "user", "content": _compact_history_content(msg.get("content"))})
        while trimmed and trimmed[0].get("role") == "tool":
            trimmed.pop(0)
        self.history = trimmed

    def _guard_unverified_final(self, content: str, events: list[ToolEvent]) -> str:
        if not events:
            return content
        last = events[-1].result
        status = str(last.get("status") or "")
        verified = last.get("verified")
        if verified is not False and status not in {"attempted", "needs_verification", "failed"}:
            return content
        low = content.casefold()
        already_honest = any(token in low for token in ("intent", "verifi", "no pude", "no se pudo", "error", "fall"))
        if already_honest:
            return content
        evidence = last.get("evidence") or last.get("completion_status") or status or "sin evidencia"
        note = (
            "\n\nNota: la ultima tool no dejo evidencia suficiente de finalizacion "
            f"(status={status or 'desconocido'}, verified={verified}, evidence={evidence})."
        )
        return content.rstrip() + note

    def _guard_phrase_confirm(self, content: str) -> str:
        """If phrase-triggered routines fired but the assistant reply does not
        acknowledge them, prepend a brief confirmation so the user is never
        left wondering whether the saved action ran.

        Heuristic: a reply is considered "acknowledging" if any of the labels
        or phrases of the fires appears in the content (folded), or if the
        reply already contains common ack tokens ('hecho', 'listo', 'done',
        'ejecut', 'ya').
        """
        if not self._phrase_fires:
            return content
        folded = _fold_match(content)
        ack_tokens = ("hecho", "listo", "done", "ejecut", "completed", "fini", " ya ")
        already_ack = any(tok in folded for tok in ack_tokens)
        mentions_any = False
        for fire in self._phrase_fires:
            label = _fold_match(str(fire.get("label") or ""))
            phrase = _fold_match(str(fire.get("phrase") or ""))
            if (label and label in folded) or (phrase and phrase in folded):
                mentions_any = True
                break
        if already_ack or mentions_any:
            return content
        # Build a short, neutral prefix listing what fired.
        summaries: list[str] = []
        for fire in self._phrase_fires:
            label = fire.get("label") or "rutina"
            results = fire.get("results") or []
            ok = sum(1 for r in results if r.get("ok"))
            total = len(results)
            timed_out = sum(1 for r in results if r.get("timed_out"))
            suffix = ""
            if timed_out:
                suffix = f" ({timed_out} con timeout)"
            elif ok < total:
                suffix = f" ({total - ok} con error)"
            summaries.append(f"{label} {ok}/{total} pasos{suffix}")
        prefix = "Ejecute tu rutina: " + "; ".join(summaries) + ".\n\n"
        self.trace.event(self.trace.new_turn_id(), "phrase_confirm_injected",
                         fires=len(self._phrase_fires))
        return prefix + content

    def _guard_plan_status(self, content: str) -> str:
        """Surface explicit-plan failures to the user only when the reply is
        suspiciously empty (<30 chars). Plan being SKIPPED is silent because
        that's the LLM rejecting the planning step for good reasons.

        Failed/error states matter though: if the planner LLM call timed out
        or returned malformed output AND the agent's main reply is empty,
        the user would otherwise get a confusing one-liner. We tack on a
        single-sentence note so they know something was attempted.
        """
        status = self._explicit_plan_status or {}
        state = str(status.get("state") or "")
        if state not in {"failed", "error"}:
            return content
        if len(content.strip()) >= 30:
            return content
        err = str(status.get("error") or "unknown error")
        note = f"\n\nNota: intente generar un plan explicito para tu pedido pero fallo ({err[:120]}). Si quieres, repiteme la peticion o pasame el detalle paso a paso."
        self.trace.event(self.trace.new_turn_id(), "plan_status_surfaced", state=state)
        return content.rstrip() + note


LIVE_TEXT_LIMIT = 10000
HISTORY_TEXT_LIMIT = 3500
TOOL_RESULT_LIMIT = 3500


def _extract_user_text(content: str | list[dict[str, Any]]) -> str:
    """Return the plain-text portion of the user content (no images/audio)."""
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return " ".join(parts).strip()


def _fold_match(text: str) -> str:
    """Lowercase + drop combining marks for substring matching."""
    import unicodedata
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _is_unverified_result(result: dict[str, Any]) -> bool:
    """Return True if a tool result is failed, unverified, or needs follow-up.

    Mirrors the signals the SYSTEM_PROMPT tells Gemma to treat as 'not done':
    ok=False, verified=False, or status in {failed, needs_verification,
    attempted, needs_confirmation}. needs_user / needs_dependency are NOT
    flagged here because those require user action, not retry, and the
    failure_log filter handles them separately for replan triggering.
    """
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return True
    if result.get("verified") is False:
        return True
    status = str(result.get("status") or "").casefold()
    return status in {"failed", "needs_verification", "attempted", "needs_confirmation"}


def _run_with_timeout(fn: Any, *args: Any, timeout_s: float, **kwargs: Any) -> dict[str, Any]:
    """Run a sync function in a thread with a hard wall-clock timeout.

    Returns {'result': <fn return>, '_timed_out': False} on success or
    {'result': None, '_timed_out': True} when the deadline elapses.

    Implementation detail: we do NOT use ThreadPoolExecutor's context manager
    because its __exit__ joins all workers, defeating the timeout. We submit
    on a bare executor and call shutdown(wait=False) so a hanging task is
    abandoned (the thread stays alive in the background but the caller moves
    on). The thread is daemonized so it cannot block process exit.
    """
    import concurrent.futures
    import threading
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma4_timeout")
    # Mark spawned threads as daemons so they cannot keep the process alive.
    original_factory = threading.Thread

    try:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return {"result": future.result(timeout=timeout_s), "_timed_out": False}
        except concurrent.futures.TimeoutError:
            return {"result": None, "_timed_out": True}
        except Exception as exc:
            return {"result": None, "_timed_out": False, "_error": str(exc)}
    finally:
        # Do not wait for the worker; if it's hanging, we abandon it.
        executor.shutdown(wait=False)
        _ = original_factory  # silence linters


def _format_phrase_fires(fires: list[dict[str, Any]]) -> str:
    """Render fired phrase-triggered routines for the system prompt.

    Each entry has {label, phrase, steps_run, results}. We tell Gemma the
    routine already executed and ask it to confirm briefly to the user in
    natural language. When some steps failed or timed out we add an
    explicit honesty instruction so Gemma cannot say 'done' for a step that
    actually broke.
    """
    if not fires:
        return ""
    total_steps = 0
    failed_steps = 0
    timed_out_steps = 0
    lines = ["# Phrase-triggered routines already executed this turn"]
    lines.append("These routines fired BEFORE you got the message because the user's text matched their saved phrase. Do NOT re-run their steps.")
    for fire in fires:
        label = fire.get("label") or "routine"
        phrase = fire.get("phrase") or ""
        results = fire.get("results") or []
        oks = sum(1 for r in results if r.get("ok"))
        total = len(results)
        total_steps += total
        failed_steps += total - oks
        timed_out_steps += sum(1 for r in results if r.get("timed_out"))
        lines.append(f"- {label} (phrase='{phrase}') -> {oks}/{total} steps ok")
        for r in results[:6]:
            tool = r.get("tool", "?")
            ok = r.get("ok")
            err = r.get("error") if not ok else ""
            timed_out = " (TIMED OUT)" if r.get("timed_out") else ""
            extra = f" error={err}" if err else ""
            lines.append(f"   step: tool={tool} ok={ok}{timed_out}{extra}")
    # Behavior contract.
    if failed_steps == 0:
        lines.append("All steps succeeded. Acknowledge briefly to the user in natural language what was done, then handle the rest of the message normally.")
    else:
        msg = (f"WARNING: {failed_steps} of {total_steps} steps did NOT complete"
               + (f" ({timed_out_steps} timed out)" if timed_out_steps else "")
               + ". You MUST tell the user honestly which actions did not run. "
               "Do not say 'listo', 'hecho' or 'done' for the failed steps. "
               "Either suggest a retry, ask the user to investigate, or report the error verbatim.")
        lines.append(msg)
    return "\n".join(lines)


def _summarization_enabled() -> bool:
    """Compaction by LLM summarization. Default on; disable with GEMMA4_AGENT_SUMMARIZATION=false."""
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _summarization_cooldown_turns() -> int:
    """Minimum number of turns between two LLM-summarization calls.

    Default 6. Override via env GEMMA4_AGENT_SUMMARIZATION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 6
    except ValueError:
        return 6


def _fact_extraction_enabled() -> bool:
    """Auto fact extraction. OFF by default (privacy).

    Enable with GEMMA4_AGENT_FACT_EXTRACTION=true. When on, after each
    completed turn the agent asks Gemma to extract 0-3 small facts about
    the user (preferences, identifiers, recurring context) and saves them
    to memory with `auto:` prefix.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _fact_extraction_cooldown_turns() -> int:
    """Min turns between two fact-extraction LLM calls.

    Default 5. Override via env GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 5
    except ValueError:
        return 5


def _compute_context_budget(context_size: int) -> dict[str, int]:
    """Proportional context budget that adapts to the model size.

    Reserves ~30% of the context window for the *next* turn (system prompt,
    new user input, fresh tool results, and the assistant reply). The other
    ~70% is available for retained history. From that 70% we derive:

      - soft_cap_messages: post cheap-pass truncation (drop tool roles).
      - hard_cap_messages: final fallback truncation when summarization is
        off, fails, or is in cooldown.
      - keep_tail_messages: how many last messages to keep verbatim around
        the LLM-generated summary.
      - summarize_threshold_chars: when total history exceeds this many
        chars we trigger a Stage-2 summarization.

    The formulas scale roughly linearly with `context_size` but stay bounded
    so very small (1K) or very large (1M) models still produce sensible
    numbers. Char-to-token ratio is conservative (~3 chars/token).
    """
    ctx = max(1024, int(context_size or 16384))
    history_tokens = int(ctx * 0.70)
    history_chars = history_tokens * 3
    # 1 conversational round (user+assistant) averages ~300-1200 chars after
    # the cheap-pass. Use a soft anchor of 500 chars/message for budgeting.
    avg_msg_chars = 500
    soft_cap = max(10, min(history_chars // avg_msg_chars, 200))
    hard_cap = max(6, soft_cap // 2)
    keep_tail = max(4, min(soft_cap // 5, 30))
    threshold = int(history_chars * 0.75)
    return {
        "context_size": ctx,
        "history_tokens": history_tokens,
        "history_chars": history_chars,
        "soft_cap_messages": soft_cap,
        "hard_cap_messages": hard_cap,
        "keep_tail_messages": keep_tail,
        "summarize_threshold_chars": threshold,
    }


def _parallel_tools_enabled() -> bool:
    """Run multiple tool calls in the same batch concurrently.

    OFF by default: most local tools share state (filesystem, registry,
    apps_index, MCP clients) and ordering can matter for the model. Enable
    explicitly with GEMMA4_AGENT_PARALLEL_TOOLS=true. When on AND the model
    emitted >=2 valid tool calls in one assistant message, they run on a
    small ThreadPoolExecutor (max_workers=4). Order is preserved when the
    results are stitched back into history.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_PARALLEL_TOOLS") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _message_text_estimate(message: dict[str, Any]) -> str:
    """Return a flat string representation of a chat message for token budgeting."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text") or ""))
                elif item.get("type") == "image_url":
                    chunks.append("[image]")
                elif item.get("type") == "input_audio":
                    chunks.append("[audio]")
        return " ".join(chunks)
    if content is None:
        return ""
    return str(content)


def _compact_live_content(content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return _middle_ellipsis(content, LIVE_TEXT_LIMIT)
    out: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            out.append({"type": "text", "text": _middle_ellipsis(str(item.get("text") or ""), LIVE_TEXT_LIMIT)})
        else:
            out.append(item)
    return out


def _compact_history_content(content: Any) -> str:
    if isinstance(content, str):
        return _middle_ellipsis(content, HISTORY_TEXT_LIMIT)
    if isinstance(content, list):
        parts: list[str] = []
        omitted_media = 0
        for item in content:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind == "text":
                parts.append(str(item.get("text") or ""))
            elif kind in {"image_url", "input_audio"}:
                omitted_media += 1
        suffix = f"\n[{omitted_media} multimodal item(s) omitted from history]" if omitted_media else ""
        return _middle_ellipsis("\n".join(parts).strip() + suffix, HISTORY_TEXT_LIMIT)
    return _middle_ellipsis(str(content or ""), HISTORY_TEXT_LIMIT)


def _compact_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    compacted = _compact_json(result, max_items=5, max_string=700)
    if _json_len(compacted) <= TOOL_RESULT_LIMIT:
        return compacted if isinstance(compacted, dict) else {"value": compacted}

    core_keys = (
        "ok",
        "status",
        "verified",
        "completion_status",
        "error",
        "tool",
        "action",
        "evidence",
        "path",
        "url",
        "image_path",
        "title",
        "selected_title",
        "level",
        "query",
        "matched_game",
        "local_match_verified",
        "visual_verified",
        "playback_verified",
        "content_verified",
        "resource",
        "checkpoint",
    )
    core: dict[str, Any] = {
        "tool": name,
        "args": _compact_json(args, max_items=5, max_string=300),
        "context_compacted": True,
    }
    for key in core_keys:
        if key in result:
            core[key] = _compact_json(result[key], max_items=4, max_string=500)
    for key, value in result.items():
        if isinstance(value, list):
            core[f"{key}_count"] = len(value)
            core[key] = _compact_json(value[:3], max_items=3, max_string=350)
        elif isinstance(value, dict) and key not in core:
            core[f"{key}_keys"] = list(value.keys())[:12]
    return _compact_json(core, max_items=6, max_string=600)


def _compact_json(value: Any, *, max_items: int, max_string: int, depth: int = 0) -> Any:
    if depth > 5:
        return _middle_ellipsis(str(value), max_string)
    if isinstance(value, str):
        return _middle_ellipsis(value, max_string)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        list_out: list[Any] = [_compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1) for item in value[:max_items]]
        if len(value) > max_items:
            list_out.append({"_omitted": len(value) - max_items})
        return list_out
    if isinstance(value, dict):
        limit = 80 if depth == 0 else max_items
        items = list(value.items())
        dict_out: dict[str, Any] = {}
        for key, item in items[:limit]:
            dict_out[str(key)] = _compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1)
        if len(items) > limit:
            dict_out["_omitted_keys"] = len(items) - limit
        return dict_out
    return _middle_ellipsis(str(value), max_string)


def _json_len(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except TypeError:
        return len(str(value))


def _looks_like_context_overflow(message: str) -> bool:
    low = message.casefold()
    return "exceeds the available context size" in low or "context size" in low and "exceed" in low


# Footers added by the agent (TIER 1 #2 verifier + TIER 2 #5 mission). Si el
# LLM ve uno en el historial, lo va a reproducir en proximos turns, infando
# context + duplicando texto en pantalla. Strippeamos antes de guardar al
# history Y antes de devolver al display.
#
# 2026-05-15: user explicitly asked for "[misión: ...]" to NEVER appear. El
# patron es case-insensitive y captura variantes con / sin acento. Tambien
# detecta "Mision" (sin acento, Capitalizado) que el LLM podria emitir.
import re as _re_footers
_FOOTER_PATTERNS = [
    # "[misión: ...]" / "[Mision: ...]" — del mission_outcome
    _re_footers.compile(r"\n*\[\s*[Mm]isi[óo]n\s*:[^\]]*\]\s*$"),
    # "[N verificada(s), N no confirmada(s), N no verificable(s)]" — verifier
    _re_footers.compile(r"\n*\[\d+\s*verificada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+confirmada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+verificable\(s\)[^\]]*\]\s*$"),
]


def _strip_trailing_footers(text: str) -> str:
    """Remueve cualquier footer agregado por el agent del final del texto.

    Hace varias pasadas: si hay multiples footers stackeados (verifier +
    mission), los strippea todos. Idempotente (correr 2 veces da lo mismo).
    """
    if not text:
        return text
    prev = None
    cur = text.rstrip()
    while cur != prev:
        prev = cur
        for pat in _FOOTER_PATTERNS:
            cur = pat.sub("", cur).rstrip()
    return cur


def _middle_ellipsis(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep_start = max(0, limit // 2)
    keep_end = max(0, limit - keep_start - 80)
    return (
        text[:keep_start].rstrip()
        + f"\n...[omitted {len(text) - keep_start - keep_end} chars to keep context under limit]...\n"
        + text[-keep_end:].lstrip()
    )


def _parse_args(raw: Any) -> tuple[dict[str, Any], str | None]:
    """Parse a tool-call arguments field.

    Returns (args_dict, parse_error). parse_error is None on success; otherwise
    it's a short human-readable string suitable for surfacing to the LLM. The
    args_dict always returns something callable so the caller can still log a
    placeholder, but in the error case the caller MUST short-circuit and not
    invoke the tool with sucky data.
    """
    if isinstance(raw, dict):
        return raw, None
    if raw is None:
        return {}, None
    if isinstance(raw, str):
        raw_trim = raw.strip()
        if not raw_trim:
            return {}, None
        try:
            parsed = json.loads(raw_trim)
            if isinstance(parsed, dict):
                return parsed, None
            return {"value": parsed}, None
        except json.JSONDecodeError as exc:
            # Surface the column so Gemma can see what it sent wrong.
            preview = raw_trim if len(raw_trim) <= 200 else raw_trim[:200] + "..."
            return {"_raw_invalid_json": preview}, f"invalid_json: {exc.msg} at pos {exc.pos}"
    return {"value": raw}, f"unsupported_args_type: {type(raw).__name__}"


def _progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    """Forward a progress event. Errors in the user callback are swallowed
    but logged to stderr so they don't go fully silent."""
    if callback is None:
        return
    try:
        callback(event, payload)
    except Exception as exc:
        try:
            import sys
            print(f"[progress callback error in event={event}]: {exc}", file=sys.stderr)
        except Exception:
            pass
