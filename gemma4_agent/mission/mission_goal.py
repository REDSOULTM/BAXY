"""MissionGoal — verifier por-mision estructural (TIER 2 #5).

Voyager NeurIPS 2023 pattern: "Self-verification verifies the OBJECTIVE,
not the action." En otras palabras, una tool retornando ok=True NO
significa que la INTENCION del usuario se cumplio. El verifier per-tool
(verify_core.py / TIER 1 #2) mide el efecto de cada llamada. Este
verifier mide si lo que el usuario PIDIO quedo cumplido.

Diferencia con verify_core.py:
  - verify_core (per-tool): "abriste algo"? si/no/no medible.
  - mission_goal (per-mission): "abriste lo que pediste"? si/no.

Adaptado de carter_v5/mission/goal.py a las compound tools de Gemma 4:
en Gemma 4 las tools son compuestas (`app`, `steam`, `gui`, `web`...) con
un campo `action` que discrimina sub-comportamiento. _kinds_for_call()
inspecciona action + otros args para decidir qué ExpectedOutcome.kind
satisface cada llamada concreta.

Honestidad por construccion: un `gui_deeplink(intent="search")` NO
satisface "abrir X" — solo abre la pagina de busqueda. Un
`steam(action="store_page")` NO satisface destructive_install — el
usuario abrio la ficha pero no clickeo "Install". Marcar estos como
fulfilled seria deshonesto.

Opt-out: GEMMA4_MISSION_OFF=1 desactiva el sistema (build retorna
MissionGoal vacio, compute_mission_outcome devuelve UNVERIFIED).
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Outcome contracts (mirror Carter v5 types — local to avoid import cycles)
# ---------------------------------------------------------------------------


class OutcomeStatus(str, Enum):
    """Estado final del turn — 9 valores explicitos (Carter v4 inheritance)."""
    COMPLETED = "COMPLETED"                                          # mission fulfilled + verifiers OK
    PARTIAL = "PARTIAL"                                              # progress but not all
    FAILED = "FAILED"                                                # tried, verifiers said No
    UNVERIFIED = "UNVERIFIED"                                        # read-only / conversational
    NEEDS_USER = "NEEDS_USER"                                        # clarification pending
    NEEDS_PERMISSION = "NEEDS_PERMISSION"                            # OS perm denied
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"                          # safety blocked
    TOOL_OK_VERIFIER_INCONCLUSIVE = "TOOL_OK_VERIFIER_INCONCLUSIVE"  # async dispatch
    INTENT_NOT_FULFILLED = "INTENT_NOT_FULFILLED"                    # tools ran but mismatched


@dataclass(frozen=True)
class ExpectedOutcome:
    """A sub-goal derived from the user prompt.

    `kind` is STRUCTURAL (independent of which app/tool). Examples:
      - "open_target"        : user said "abre/pone/launch X"
      - "close_target"       : user said "cerra/close X"
      - "filesystem_write"   : user said "crea archivo / escribi"
      - "filesystem_read"    : user said "lee / muestrame / list"
      - "navigate"           : user said "busca / ve a / search"
      - "set_state"          : user said "subi volumen / mute / brightness"
      - "read_state"         : user said "que hora / cuanta RAM / dime"
      - "report"             : user wants a written answer (fallback)
      - "destructive_delete" : user said "borra / elimina"
      - "destructive_install": user said "instala"
    """
    kind: str
    target: str = ""
    matched_by: str | None = None        # tool name that satisfied this
    confirmed: bool | None = None        # tool's verifier outcome


@dataclass(frozen=True)
class MissionOutcome:
    """Final state of a turn — feeds the assistant footer + telemetry."""
    status: OutcomeStatus
    summary: str
    confirmed_count: int = 0
    failed_count: int = 0
    unverified_count: int = 0
    expected_total: int = 0
    expected_satisfied: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Verb patterns -> ExpectedOutcome.kind
# ---------------------------------------------------------------------------
# Multilingue ES/EN/PT/FR/IT. `\w*` captura conjugaciones (abr-e/abr-ir/abr-as)
# y derivados sin enumerar cada forma. Orden importa: el patron media-play va
# ANTES de open_target para que "pon un video" no caiga en "pon" solo.

_VERB_KIND_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Media play (pon/reproduc/play + video/musica/etc) — antes de open_target.
    (re.compile(
        r"\b(pon\w*|repro\w*|play|put|met[ae]?)\b"
        r"[^.]{0,30}?"
        r"\b(video|videos|musica|m[uú]sica|cancion\w*|song\w*|audio|"
        r"pelicula|pel[íi]cula\w*|movie\w*|serie\w*|show\w*|episod\w*|"
        r"tema|tracks?|playlist\w*|album\w*|sonido|sound)\b"
    ),
     "open_target"),
    # Open / launch / show app or url
    (re.compile(r"\b(abr\w*|open\w*|ouvr\w*|apri\w*|launch\w*|inicia\w*|run)\b"),
     "open_target"),
    # Close
    (re.compile(r"\b(cerr\w*|cierr\w*|close\w*|ferm\w*|fech\w*|salir|exit)\b"),
     "close_target"),
    # Filesystem create / write
    (re.compile(r"\b(crea\w*|cre\w+r|nuev[oa]|escrib\w*|writ\w*|sav\w*|guard\w*|anot\w*)\b"),
     "filesystem_write"),
    # Filesystem read / list / show
    # `lee\w*` cubre "lee", "leelo", "leeme", "leela"; "leer" cubre infinitivo.
    (re.compile(r"\b(lee\w*|leer|read\w*|cat|type|muestr\w*|show\w*|list\w*|dir|ls)\b"),
     "filesystem_read"),
    # Navigate / search
    (re.compile(r"\b(busc\w*|search|find|navega\w*|ve\s+a|go\s+to|ir\s+a)\b"),
     "navigate"),
    # Set system state (volume / brightness / mute)
    (re.compile(r"\b(sub\w+|baj\w+|rais\w*|lower\w*|mut\w*|silenc\w*|pon\w*\s+(?:el\s+)?vol)\b"),
     "set_state"),
    # State query
    (re.compile(r"\b(dim\w*|qu[eé]?\s*hora|cuant\w*|how\s+(?:many|much)|tell\s+me)\b"),
     "read_state"),
    # Report / summary
    (re.compile(r"\b(resum\w*|cuent\w*|report\w*)\b"),
     "report"),
    # Check / verify
    (re.compile(r"\b(revis\w*|verif\w*|confirm\w*|check\w*|chequ\w*)\b"),
     "read_state"),
    # Delete
    (re.compile(r"\b(borr\w*|elimin\w*|delet\w*|remov\w*)\b"),
     "destructive_delete"),
    # Install
    (re.compile(r"\b(instal\w*|install\w*)\b"),
     "destructive_install"),
]


# ---------------------------------------------------------------------------
# Compound tool -> default kinds it can satisfy
# ---------------------------------------------------------------------------
# IMPORTANTE: estos son los kinds POSIBLES de cada compound tool. La
# decision concreta de cuales kinds satisface *esta llamada especifica*
# (segun action + args) la toma _kinds_for_call() abajo. Esto evita
# falsos positivos como "search_store satisfizo open_target".

_TOOL_TO_KINDS: dict[str, tuple[str, ...]] = {
    # Apps installed/discovered (search/open/close/uninstall)
    "app": ("open_target", "close_target", "destructive_delete", "read_state"),
    # Steam compound (open/library/store/list_games/launch_game/install/...)
    "steam": ("open_target", "destructive_install", "navigate", "read_state"),
    # Windows management (list/focus/close/minimize/...)
    "window": ("read_state", "set_state", "close_target"),
    # GUI (screenshot/click/type/keypress/...) — kinds vary heavily per action
    "gui": ("read_state", "navigate", "filesystem_write"),
    # Vision / OCR — only read_state
    "vision": ("read_state",),
    # UI Automation
    "uia": ("read_state", "navigate", "set_state"),
    # Filesystem (list/read/write/delete/copy/move/mkdir/archive/...)
    "filesystem": ("filesystem_write", "filesystem_read", "destructive_delete", "open_target"),
    # System (time/processes/cpu/disk/battery/brightness_*)
    "system": ("read_state", "set_state"),
    # Audio (volume/mute/devices/play_pause)
    "audio": ("set_state", "read_state"),
    # Terminal (run) — read_state for reads, set_state otherwise
    "terminal": ("read_state", "set_state"),
    # Clipboard
    "clipboard": ("filesystem_write", "read_state"),
    # Memory (save/recall/list/delete)
    "memory": ("filesystem_write", "read_state", "destructive_delete"),
    # Web (search/read/research/open)
    "web": ("navigate", "read_state", "open_target"),
    # Browser GUI (open/search/youtube_play/...)
    "browser": ("open_target", "navigate", "read_state"),
    # Browser real (Playwright) — many sub-actions
    "browser_real": ("open_target", "navigate", "read_state"),
    # Verify tool — by nature reads state
    "verify": ("read_state",),
    # Download
    "download": ("filesystem_write", "read_state"),
    # Office (create/edit presentations/docs)
    "office": ("filesystem_write",),
    # Notification / routine / reminder — set_state-ish
    "notification": ("set_state", "read_state"),
    "routine": ("set_state", "read_state"),
    "reminder": ("set_state", "read_state"),
    # Maintenance / packages / registry / env — read_state default
    "registry": ("read_state", "set_state"),
    "env": ("read_state", "set_state"),
    "maintenance": ("read_state", "set_state"),
    "package": ("destructive_install", "destructive_delete", "read_state"),
    # Media / game launchers
    "media": ("open_target", "set_state"),
    "game_launcher": ("open_target", "read_state"),
    # Knowledge / document / source_manager / fact_check
    "knowledge": ("read_state", "filesystem_write"),
    "document": ("read_state",),
    "source_manager": ("filesystem_write", "read_state"),
    "fact_check": ("read_state",),
    # Developer / job_manager / watcher / state
    "developer": ("read_state", "set_state"),
    "job_manager": ("set_state", "read_state"),
    "watcher": ("set_state", "read_state"),
    "state": ("read_state", "set_state"),
    # Notes / contacts / calendar / habit / study
    "notes_tasks": ("filesystem_write", "read_state", "destructive_delete"),
    "contacts": ("filesystem_write", "read_state", "destructive_delete"),
    "local_calendar": ("filesystem_write", "read_state", "destructive_delete"),
    "habit_tracker": ("filesystem_write", "read_state"),
    "study": ("filesystem_write", "read_state"),
    # Skill loader (no semantic outcome but allowed)
    "skill_load": ("read_state",),
    # Misc — minimal coverage
    "email": ("set_state",),
    "whatsapp": ("set_state", "navigate"),
    "input": ("set_state", "read_state"),
    "smart_home": ("set_state", "read_state"),
    "subagent": ("read_state",),
    "safety": ("read_state",),
    "network": ("read_state",),
    "local_search": ("read_state",),
    "printer_scanner": ("set_state", "read_state"),
    "desktop_layout": ("set_state", "read_state"),
    "backup_sync": ("filesystem_write", "filesystem_read", "destructive_delete"),
    "device_settings": ("set_state", "read_state"),
    "media_edit": ("filesystem_write", "read_state"),
    "form_filler": ("set_state", "read_state"),
    "creative_local": ("set_state", "filesystem_write"),
    "peripheral": ("set_state", "read_state"),
    "accessibility": ("set_state", "read_state"),
    "container": ("set_state", "read_state"),
    "database": ("filesystem_write", "filesystem_read"),
    "dependency": ("read_state",),
    "data_analysis": ("filesystem_write", "read_state"),
    "audio_device": ("set_state", "read_state"),
    "photo_library": ("filesystem_write", "read_state"),
}


# Actions that READ state (no mutation). Used to filter set_state out.
_READ_ACTIONS = frozenset({
    "list", "read", "search", "get_volume", "devices", "time", "processes",
    "cpu_ram_gpu", "disk", "battery", "brightness_get", "active", "tree",
    "find", "describe_screen", "ocr", "find_element", "compare_before_after",
    "tabs", "active_tab", "active_tab_title", "extract", "get_state",
    "list_tables", "schema", "query", "ps", "ps_all", "images", "inspect",
    "logs", "compose_ps", "status", "states", "discover", "history",
    "exif", "scan", "find_by_date", "wifi_list", "wifi_scan", "wifi_status",
    "bluetooth_status", "display_list", "power_plan_list", "power_plan_get",
    "ping", "traceroute", "dns_get", "dns_resolve", "port_check",
    "connections", "public_ip", "csv_profile", "csv_describe", "csv_query",
    "csv_head", "probe", "subtitles_extract", "now_playing", "queue_list",
    "search_local_library", "preview",
})

# Actions that DELETE / are destructive. Always satisfy destructive_delete.
_DELETE_ACTIONS = frozenset({
    "delete", "remove", "uninstall", "device_disable", "wifi_delete_profile",
    "deck_delete", "card_delete", "card_remove", "compose_down",
})

# Actions that explicitly INSTALL software.
_INSTALL_ACTIONS = frozenset({
    "install", "play_or_install",
})


def _kinds_for_call(tool_name: str, args: dict) -> tuple[str, ...]:
    """Return the ExpectedOutcome.kinds that this *specific call* satisfies.

    Equivalent a _TOOL_TO_KINDS[tool_name] MAS filtros condicionales por
    action y otros args. Honestidad por construccion:
      - app(action="search") -> read_state, NO open_target.
      - app(action="open") -> open_target.
      - steam(action="search_store") -> navigate, NO open_target ni install.
      - steam(action="install" / "play_or_install") -> destructive_install.
      - gui(action="click", target="Install") -> destructive_install.
      - filesystem(action="delete") -> destructive_delete (no filesystem_write).
      - audio(action="get_volume") -> read_state (no set_state).
    """
    base_all = set(_TOOL_TO_KINDS.get(tool_name, ()))
    if not base_all:
        return ()

    action = str((args or {}).get("action", "")).lower()

    # Sin action => devolver todos los kinds posibles del tool (best-effort).
    if not action:
        return tuple(base_all)

    # ============ Filter by action semantics ============

    selected: set[str] = set()

    # READ actions: solo read_state.
    if action in _READ_ACTIONS:
        if "read_state" in base_all:
            selected.add("read_state")
        if action == "read" and "filesystem_read" in base_all:
            selected.add("filesystem_read")
        # search puede tambien ser "navigate" si la tool es web/browser
        if action == "search" and tool_name in ("web", "browser", "browser_real"):
            selected.add("navigate")
        if action == "list" and "filesystem_read" in base_all:
            selected.add("filesystem_read")
        return tuple(selected) if selected else tuple(base_all & {"read_state"})

    # DELETE actions: destructive_delete y ya.
    if action in _DELETE_ACTIONS:
        if "destructive_delete" in base_all:
            selected.add("destructive_delete")
        return tuple(selected) if selected else ()

    # INSTALL actions: destructive_install + open_target (instalar abre).
    if action in _INSTALL_ACTIONS:
        if "destructive_install" in base_all:
            selected.add("destructive_install")
        if "open_target" in base_all:
            selected.add("open_target")
        return tuple(selected) if selected else ()

    # ============ Tool-specific dispatch ============

    if tool_name == "app":
        if action == "open":
            selected.add("open_target")
        elif action == "close":
            selected.add("close_target")
        elif action == "uninstall":
            selected.add("destructive_delete")

    elif tool_name == "steam":
        # open/library/launch_game -> open_target.
        # search_store/search_library -> navigate.
        # store_page -> navigate + open_target (la pagina ES un target visible).
        # install -> destructive_install (manejado arriba).
        if action in ("open", "launch_game"):
            selected.add("open_target")
        elif action == "library":
            selected.add("open_target")
        elif action in ("search_store", "search_library"):
            selected.add("navigate")
        elif action == "store_page":
            selected.add("navigate")
            selected.add("open_target")
        elif action == "list_games":
            selected.add("read_state")
        elif action == "store":
            selected.add("open_target")  # abre tienda visible

    elif tool_name == "window":
        if action in ("focus", "restore", "maximize", "minimize", "move_resize"):
            selected.add("set_state")
        elif action == "close":
            selected.add("close_target")

    elif tool_name == "gui":
        # type -> filesystem_write (escribe contenido) o navigate (entra URL)
        # click -> navigate por default; destructive_install si target dice install
        # screenshot/locate_*/wait_for -> read_state
        target = str((args or {}).get("target") or (args or {}).get("text") or "").lower()
        if action in ("screenshot", "locate_text", "click_text", "locate_image", "wait_for"):
            selected.add("read_state")
        elif action == "type":
            selected.add("filesystem_write")
        elif action in ("click", "double_click", "right_click", "hotkey", "keypress"):
            selected.add("navigate")
            if any(w in target for w in (
                "instalar", "install", "comprar", "buy",
                "purchase", "pay", "subscribe", "suscribir",
            )):
                selected.add("destructive_install")
        elif action == "scroll":
            selected.add("navigate")
        elif action == "drag":
            selected.add("set_state")

    elif tool_name == "filesystem":
        # write/copy/move/mkdir/rename -> filesystem_write
        # read -> filesystem_read
        # archive/unarchive -> filesystem_write
        # open -> open_target + filesystem_read
        if action in ("write", "copy", "move", "mkdir", "rename", "archive", "unarchive"):
            selected.add("filesystem_write")
        elif action == "diff":
            selected.add("filesystem_read")
        elif action == "open":
            selected.add("open_target")
            selected.add("filesystem_read")

    elif tool_name == "system":
        if action in ("shutdown", "restart", "sleep", "brightness_set"):
            selected.add("set_state")

    elif tool_name == "audio":
        if action in ("set_volume", "mute", "set_default", "media_play_pause",
                      "media_stop", "next", "previous"):
            selected.add("set_state")

    elif tool_name == "terminal":
        # No podemos saber sin parse del command. Asumimos set_state si es run.
        if action == "run":
            selected.add("set_state")
            selected.add("read_state")

    elif tool_name == "clipboard":
        if action == "write":
            selected.add("filesystem_write")

    elif tool_name == "memory":
        if action == "save":
            selected.add("filesystem_write")

    elif tool_name == "web":
        # research/read -> read_state; open con url install/buy -> destructive_install
        url = str((args or {}).get("url", "")).lower()
        if action in ("research", "read"):
            selected.add("read_state")
        elif action == "open":
            selected.add("open_target")
            selected.add("navigate")
            if any(p in url for p in (
                "steam://install/", "steam://run/", "/install/",
                "/buy/", "ms-windows-store://pdp",
            )):
                selected.add("destructive_install")

    elif tool_name == "browser":
        # open/search -> navigate; youtube_play -> open_target (reproduce algo)
        if action == "open":
            selected.add("open_target")
            selected.add("navigate")
        elif action in ("search", "find"):
            selected.add("navigate")
        elif action == "youtube_play":
            selected.add("open_target")
        elif action in ("media_pause", "media_stop"):
            selected.add("set_state")

    elif tool_name == "browser_real":
        if action in ("open", "goto", "tab_open"):
            selected.add("open_target")
            selected.add("navigate")
        elif action in ("click", "fill", "press", "click_text"):
            selected.add("navigate")
        elif action in ("close", "tab_close"):
            selected.add("close_target")
        elif action == "screenshot":
            selected.add("read_state")

    elif tool_name in ("notification", "routine", "reminder"):
        if action in ("create", "toast_now", "toast_schedule",
                      "timer_start", "alarm_create", "reminder_create"):
            selected.add("set_state")
        elif action in ("delete", "timer_cancel", "alarm_cancel"):
            selected.add("destructive_delete")

    elif tool_name == "verify":
        # Verify por naturaleza lee estado.
        selected.add("read_state")

    elif tool_name == "media":
        if action in ("play", "resume", "play_pause", "open_local"):
            selected.add("open_target")
        elif action in ("pause", "stop", "next", "previous", "volume_for_app"):
            selected.add("set_state")

    elif tool_name == "game_launcher":
        if action == "launch":
            selected.add("open_target")
        elif action == "open_library_page":
            selected.add("open_target")

    elif tool_name == "package":
        # install/uninstall manejados arriba; otras actions read_state.
        pass

    elif tool_name == "download":
        if action == "fetch":
            selected.add("filesystem_write")
        else:
            selected.add("read_state")

    # Fallback: si action existe pero no caemos en ningun caso, devolvemos
    # los kinds posibles del tool (best-effort, sin filtros). Esto preserva
    # comportamiento razonable para tools no explicitamente cubiertas.
    if not selected:
        return tuple(base_all)
    return tuple(selected)


# ---------------------------------------------------------------------------
# Multistep parser (structural separators — no per-language list)
# ---------------------------------------------------------------------------

_MULTISTEP_SEPARATORS = (
    ",", ";", " y ", " e ", " then ", " luego ", " despues ", " después ",
    " puis ", " et ", " ed ",
)


def _fold(text: str) -> str:
    """NFKD + lowercase para matching estable de acentos."""
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in norm if not unicodedata.combining(c)).lower()


def _split_clauses(text: str) -> list[str]:
    """Split prompt en clausulas por separadores estructurales."""
    if not text:
        return []
    folded = _fold(text)
    sep = "|||"
    for s in _MULTISTEP_SEPARATORS:
        folded = folded.replace(s, sep)
    return [c.strip() for c in folded.split(sep) if c.strip()]


def _detect_outcomes_in_clause(clause: str) -> list[ExpectedOutcome]:
    """Detect uno o mas outcomes en una sola clausula.

    NO emite fallback "report" — un smalltalk como "Hablame en gitano" o
    "Insultame" NO tiene expected outcome estructural. Si ningun patron
    matchea, devolvemos lista vacia y el turn se cuenta como UNVERIFIED
    (sin footer ruidoso).
    """
    outcomes: list[ExpectedOutcome] = []
    seen_kinds: set[str] = set()
    for pat, kind in _VERB_KIND_PATTERNS:
        if pat.search(clause) and kind not in seen_kinds:
            outcomes.append(ExpectedOutcome(kind=kind, target=clause[:80]))
            seen_kinds.add(kind)
    return outcomes


# ---------------------------------------------------------------------------
# MissionGoal
# ---------------------------------------------------------------------------


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_MISSION_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


@dataclass
class MissionGoal:
    """Captures user intent + tracks fulfillment via tool execution.

    Usage:
        goal = MissionGoal.from_user_text("abri Steam y busca Hollow Knight")
        goal.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        goal.update_with_tool("steam", {"action": "search_store", "query": "Hollow Knight"}, ok=True)
        goal.is_fulfilled()  # -> True (open_target + navigate cumplidos)
    """
    user_text: str
    expected: list[ExpectedOutcome] = field(default_factory=list)
    executed_tools: list[tuple[str, dict, bool]] = field(default_factory=list)

    @classmethod
    def from_user_text(cls, user_text: str) -> "MissionGoal":
        """Build a MissionGoal from the user prompt.

        Si GEMMA4_MISSION_OFF=1, devuelve un goal vacio (sin expected
        outcomes); compute_mission_outcome lo tratara como UNVERIFIED.
        """
        if not _enabled() or not user_text:
            return cls(user_text=user_text or "", expected=[])
        clauses = _split_clauses(user_text)
        expected: list[ExpectedOutcome] = []
        seen: set[tuple[str, str]] = set()
        for clause in clauses:
            for outcome in _detect_outcomes_in_clause(clause):
                # Dedup por (kind, primeros 30 chars del target).
                key = (outcome.kind, outcome.target[:30])
                if key not in seen:
                    expected.append(outcome)
                    seen.add(key)
        return cls(user_text=user_text, expected=expected)

    def update_with_tool(self, tool_name: str, args: dict, ok: bool) -> None:
        """Marca el primer expected outcome cuyo kind matchea esta call.

        Solo el PRIMER unmatched outcome por kind se actualiza por call,
        para que multiples calls del mismo tipo (ej. dos filesystem_write)
        puedan satisfacer expected outcomes distintos en orden.
        """
        self.executed_tools.append((tool_name, dict(args or {}), ok))
        kinds = _kinds_for_call(tool_name, args or {})
        if not kinds:
            return
        for i, outcome in enumerate(self.expected):
            if outcome.matched_by is not None:
                continue
            if outcome.kind in kinds:
                self.expected[i] = ExpectedOutcome(
                    kind=outcome.kind,
                    target=outcome.target,
                    matched_by=tool_name,
                    confirmed=ok,
                )
                break

    def is_fulfilled(self) -> bool:
        """True solo si todos los expected outcomes fueron matched con confirmed != False."""
        if not self.expected:
            return False
        return all(
            o.matched_by is not None and o.confirmed is not False
            for o in self.expected
        )

    def progress(self) -> tuple[int, int]:
        total = len(self.expected)
        satisfied = sum(
            1 for o in self.expected
            if o.matched_by is not None and o.confirmed is not False
        )
        return satisfied, total

    def missing_kinds(self) -> list[str]:
        return [o.kind for o in self.expected if o.matched_by is None]

    def summary(self) -> str:
        s, t = self.progress()
        if t == 0:
            return "sin objetivos detectados"
        if self.is_fulfilled():
            return f"misión cumplida ({s}/{t})"
        missing = self.missing_kinds()
        if missing:
            human = ", ".join(_humanize_kind(k) for k in missing[:5])
            return f"misión parcial ({s}/{t}); falta: {human}"
        return f"misión parcial ({s}/{t})"


_KIND_HUMAN = {
    "destructive_install": "completar la instalación/lanzamiento",
    "destructive_delete":  "completar el borrado",
    "open_target":         "abrir lo que pediste",
    "close_target":        "cerrar lo que pediste",
    "filesystem_write":    "escribir el archivo",
    "filesystem_read":     "leer el archivo",
    "navigate":            "navegar al destino",
    "set_state":           "cambiar el estado del sistema",
    "read_state":          "leer el estado",
    "report":              "informar el resultado",
}


def _humanize_kind(kind: str) -> str:
    return _KIND_HUMAN.get(kind, kind)
