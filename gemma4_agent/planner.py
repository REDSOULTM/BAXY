"""Lightweight mission planning and dynamic tool selection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


STEP_SPLIT_RE = re.compile(
    r"\b(?:luego|despues|después|entonces|y luego|y despues|y después|,\s*luego)\b|[;]\s*",
    re.IGNORECASE,
)
MAX_SELECTED_TOOLS = 16


@dataclass
class MissionStep:
    index: int
    text: str
    suggested_tools: list[str] = field(default_factory=list)
    verification_hint: str = ""


@dataclass
class MissionPlan:
    goal: str
    steps: list[MissionStep]
    cleanup_expected: bool = False
    needs_pc_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "cleanup_expected": self.cleanup_expected,
            "needs_pc_action": self.needs_pc_action,
            "steps": [
                {
                    "index": step.index,
                    "text": step.text,
                    "suggested_tools": step.suggested_tools,
                    "verification_hint": step.verification_hint,
                }
                for step in self.steps
            ],
        }

    def prompt_hint(self) -> str:
        if not self.steps:
            return ""
        lines = [
            "# Current Mission Draft",
            "This is a deterministic draft from the user request. Follow it when it matches the user's intent; do not expose it.",
            f"Goal: {self.goal}",
        ]
        for step in self.steps:
            tools = ", ".join(step.suggested_tools) if step.suggested_tools else "none"
            lines.append(f"{step.index}. {_short_text(step.text, 240)} | suggested_tools={tools} | verify={step.verification_hint or 'result evidence'}")
        if self.cleanup_expected:
            lines.append("Cleanup expected: use state(action='cleanup') or targeted close/delete after completing the mission.")
        return "\n".join(lines)


def plan_mission(content: str | list[dict[str, Any]]) -> MissionPlan:
    text = _content_text(content)
    parts = _split_steps(text)
    steps = [
        MissionStep(index=i + 1, text=part, suggested_tools=_suggest_tools(part), verification_hint=_verify_hint(part))
        for i, part in enumerate(parts)
    ]
    cleanup_expected = bool(re.search(r"\b(limpia|limpiar|cleanup|cierra todo lo que abriste|cerrar al final)\b", text, re.IGNORECASE))
    needs_pc_action = any(step.suggested_tools for step in steps)
    if len(steps) == 1 and not needs_pc_action:
        steps = []
    return MissionPlan(goal=text[:500], steps=steps, cleanup_expected=cleanup_expected, needs_pc_action=needs_pc_action)


def select_tool_names(content: str | list[dict[str, Any]], plan: MissionPlan, *, safety_enabled: bool = False) -> list[str]:
    """Return a small, ordered tool subset for the current turn."""

    text = _fold_text(_content_text(content))
    names: list[str] = []
    for step in plan.steps:
        names.extend(step.suggested_tools)
    if not names:
        names.extend(_suggest_tools(text))
    if not names:
        return ["safety"] if safety_enabled else []

    expanded: list[str] = []
    for name in _dedupe(names):
        expanded.append(name)
        expanded.extend(_related_tools(name, text))
    if plan.cleanup_expected or re.search(r"\b(cleanup|limpia|limpiar|cierra todo lo que abriste|rollback|restaura|deshacer)\b", text):
        expanded.append("state")
    if safety_enabled:
        expanded.append("safety")
    return _cap_tools(_dedupe(expanded), MAX_SELECTED_TOOLS)


def _content_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content.strip()
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return " ".join(chunks).strip()


def _split_steps(text: str) -> list[str]:
    raw_parts = [part.strip(" ,.") for part in STEP_SPLIT_RE.split(text) if part.strip(" ,.")]
    if len(raw_parts) <= 1:
        return [text.strip()] if text.strip() else []
    merged: list[str] = []
    for part in raw_parts:
        if len(part.split()) <= 2 and merged:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return merged[:8]


def _suggest_tools(step: str) -> list[str]:
    low = _fold_text(step)
    tools: list[str] = []

    if "steam" in low or re.search(r"\bbiblioteca\b|\btienda\b", low):
        tools.append("steam")
    if re.search(r"\b(youtube|cancion|musica|video|reproduce|ponme|pon|pausa|reanuda|resume|play|stop|siguiente|anterior)\b", low):
        tools.append("media")
    if re.search(r"\bvolumen|mute|silencio|audio\b", low):
        tools.append("audio")
    if re.search(r"\b(dispositivo de audio|salida de audio|entrada de audio|altavoz|altavoces|microfono|focusrite|aux|realtek|hyperx|scarlett)\b", low):
        tools.append("audio_device")

    if re.search(r"\b(opera|chrome|edge|firefox|youtube|google|navegador|browser|web|pagina|url|tab|pestana)\b", low):
        tools.append("browser")
        if re.search(r"\blee\b|\binvestiga\b|\bextrae\b|\bcontenido\b|\bfuente\b|\bnoticia\b|\bactual\b", low):
            tools.append("web")
            tools.append("browser_real")
    if re.search(r"\b(investiga|fuentes|citas|source|snapshot|referencia|guarda fuente)\b", low):
        tools.extend(["web", "source_manager"])

    if re.search(r"\b(archivo|carpeta|directorio|escribe|crea|borra|copia|mueve|renombra|zip|extrae|descomprime)\b", low):
        tools.append("filesystem")
    if re.search(r"\b(powerpoint|presentacion|diapositiva|pptx|word|docx|excel|xlsx|spreadsheet|hoja de calculo|pdf)\b", low):
        tools.append("office")
    if re.search(r"\b(csv|tabla|grafico|estadistica|analisis de datos|limpia datos)\b", low):
        tools.extend(["filesystem", "office"])

    if re.search(r"\babre|abrir|cierra|cerrar|app|programa|juego\b", low) and "steam" not in low:
        tools.append("app")
    if re.search(r"\bclick|clic|teclea|escribe en pantalla|pantalla|boton\b", low):
        tools.extend(["uia", "gui", "vision"])
    if re.search(r"\bregistro|registry|regedit\b", low):
        tools.append("registry")
    if re.search(r"\bvariable de entorno|env\b", low):
        tools.append("env")
    if re.search(r"\bdescarga|download|sha256|hash|firma\b", low):
        tools.append("download")

    if re.search(r"\b(recuerda|recorda|guarda en memoria|memoria)\b", low):
        tools.append("memory")
    if re.search(r"\b(documento|rag|conocimiento|knowledge base|base de conocimiento)\b", low):
        tools.extend(["memory", "knowledge"])
    if re.search(r"\b(dependencia|dependency|libreria|modulo|instala dependencia|falta)\b", low):
        tools.append("dependency")
    if re.search(r"\b(contacto|telefono|email de|correo de|vcard)\b", low):
        tools.append("contacts")
    if re.search(r"\b(nota|tarea|lista|checklist|pendiente)\b", low):
        tools.append("notes_tasks")
    if re.search(r"\b(calendario|agenda|evento|ics)\b", low):
        tools.append("local_calendar")
    if re.search(r"\b(habito|racha|streak)\b", low):
        tools.append("habit_tracker")
    if re.search(r"\b(busca en mis archivos|encuentra archivo|buscar archivo|reciente)\b", low):
        tools.append("local_search")
    if re.search(r"\b(impresora|imprime|imprimir|cola de impresion|scanner|escaner|escanear)\b", low):
        tools.append("printer_scanner")
    if re.search(r"\b(monitor|pantallas|layout|ventanas|escritorio|workspace)\b", low):
        tools.append("desktop_layout")
    if re.search(r"\b(backup|respaldo|copia de seguridad|restore|restaurar|dedupe|duplicados)\b", low):
        tools.append("backup_sync")
    if re.search(r"\b(timer|temporizador|alarma|avisame|notificacion|recordatorio)\b", low):
        tools.append("notification")
    if re.search(r"\b(rutina|automatiza|automatizacion|cuando pase|cada vez)\b", low):
        tools.append("routine")
    if re.search(r"\b(mail|email|correo|enviar mensaje)\b", low):
        tools.append("email")
    if re.search(r"\b(recordatorio graph|microsoft todo|to do)\b", low):
        tools.append("reminder")

    if re.search(r"\bproceso|cpu|ram|gpu|disco|bateria|hora\b", low):
        tools.append("system")
    if re.search(r"\b(portapapeles|clipboard|copiar al portapapeles|pega)\b", low):
        tools.append("clipboard")
    if re.search(r"\b(terminal|powershell|cmd|comando|ejecuta)\b", low):
        tools.append("terminal")
    if re.search(r"\b(teclado|idioma|layout|language|input method)\b", low):
        tools.append("input")
    if re.search(r"\b(winget|paquete|instalar app|desinstalar)\b", low):
        tools.append("package")
    return _dedupe(tools)


def _verify_hint(step: str) -> str:
    low = _fold_text(step)
    if "steam" in low:
        return "steam result, window focus, screenshot if GUI state is unclear"
    if "youtube" in low or "video" in low or "musica" in low:
        return "direct URL plus screenshot; playback may remain unverified"
    if "archivo" in low or "carpeta" in low:
        return "verify(action='file_exists') or filesystem diff/list"
    if "navegador" in low or "google" in low or "web" in low:
        return "browser_real/web content for reading; browser result only for navigation"
    if "cierra" in low or "cerrar" in low:
        return "verify app/window/process no longer exists"
    return "tool status/evidence"


def _related_tools(name: str, text: str) -> list[str]:
    if name == "steam":
        return ["app", "window", "verify"]
    if name == "app":
        return ["window", "verify"]
    if name == "browser":
        related = ["browser_real"] if re.search(r"\b(click|rellena|lee|texto|tab|pestana|descarga)\b", text) else []
        return related + ["verify"]
    if name == "browser_real":
        return ["browser", "web", "state"]
    if name == "web":
        return ["source_manager"]
    if name == "media":
        return ["browser", "audio"]
    if name == "audio_device":
        return ["audio", "state", "dependency"]
    if name in {"filesystem", "registry", "env", "download", "office", "backup_sync"}:
        return ["verify", "state"]
    if name in {"gui", "uia", "vision", "window", "desktop_layout"}:
        return ["gui", "uia", "vision", "window"]
    if name in {"notification", "routine", "contacts", "notes_tasks", "local_calendar", "habit_tracker", "source_manager"}:
        return ["state"]
    if name == "printer_scanner":
        return ["dependency"]
    return []


def _cap_tools(names: list[str], limit: int) -> list[str]:
    if len(names) <= limit:
        return names
    priority = {
        "steam": 0,
        "app": 1,
        "media": 2,
        "audio": 3,
        "audio_device": 4,
        "browser_real": 5,
        "browser": 6,
        "web": 7,
        "filesystem": 8,
        "office": 9,
        "gui": 10,
        "uia": 11,
        "vision": 12,
        "window": 13,
        "verify": 90,
        "state": 91,
        "dependency": 92,
        "safety": 99,
    }
    indexed = list(enumerate(names))
    indexed.sort(key=lambda pair: (priority.get(pair[1], 50), pair[0]))
    selected = {name for _, name in indexed[:limit]}
    return [name for name in names if name in selected]


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _fold_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + " ...[mission text trimmed]"
