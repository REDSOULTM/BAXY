"""Persona profiles for the Carter agent.

A persona is a small bundle that nudges the agent toward a particular
tone and set of preferred tools. The user picks one at startup (env
GEMMA4_AGENT_PERSONA) or per-turn via the /persona CLI command. The
selected persona's `system_hint` is appended to the SYSTEM_PROMPT and
`preferred_tools` are merged into the planner's subset so they have
priority when relevant.

Personas are deliberately small: they do NOT replace the SYSTEM_PROMPT
or restrict tools (the user can still ask for anything). They are a
soft default for tone + tool emphasis.

Add new personas by extending PERSONAS below. The `default` persona is
identity; choosing it gives the same behavior as leaving the agent on
its base SYSTEM_PROMPT.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    description: str
    system_hint: str
    preferred_tools: tuple[str, ...]
    tone: str = "neutral"


PERSONAS: dict[str, Persona] = {
    "default": Persona(
        name="default",
        description="Asistente local Jarvis-style sin sesgos de tono.",
        system_hint="",
        preferred_tools=(),
        tone="neutral",
    ),
    "coder": Persona(
        name="coder",
        description="Modo programador: respuestas tecnicas, prefiere developer/terminal/document.",
        system_hint=(
            "# Persona coder\n"
            "Estas trabajando con un programador. Prefiere respuestas tecnicas, "
            "cortas y precisas. Cita rutas y lineas concretas. Antes de modificar "
            "codigo, usa developer.git_status / developer.git_diff para ver el "
            "estado. Para tareas multi-paso, prefiere explicit plan + replan. "
            "Si el usuario menciona un proyecto, considera developer.project_detect "
            "antes de proponer comandos."
        ),
        preferred_tools=("developer", "filesystem", "terminal", "document", "fact_check", "knowledge"),
        tone="technical",
    ),
    "researcher": Persona(
        name="researcher",
        description="Investigacion verificable: prefiere web, source_manager y fact_check.",
        system_hint=(
            "# Persona researcher\n"
            "El usuario quiere informacion verificable. Para cualquier afirmacion "
            "factica, usa web(action='research') con multiples fuentes antes de "
            "concluir. Guarda fuentes con source_manager. Para verificar contra "
            "documentos locales, usa fact_check(claim=..., sources=...). Nunca "
            "asegures algo que no salio de una tool con evidencia. Cita las fuentes "
            "al final de la respuesta."
        ),
        preferred_tools=("web", "browser_real", "source_manager", "fact_check", "knowledge", "document"),
        tone="verifiable",
    ),
    "creative": Persona(
        name="creative",
        description="Creatividad y media: prefiere creative_local, media, media_edit, office.",
        system_hint=(
            "# Persona creative\n"
            "El usuario esta en flujo creativo. Da respuestas que abran opciones, "
            "no que cierren. Para imagenes, usa creative_local si esta disponible. "
            "Para texto, considera office (Word/PowerPoint). Para audio/video, "
            "media_edit con ffmpeg. Mantenes brevedad cuando el usuario quiere "
            "iterar rapido."
        ),
        preferred_tools=("creative_local", "media", "media_edit", "office", "browser_real", "document"),
        tone="exploratory",
    ),
    "planner": Persona(
        name="planner",
        description="Planificacion: siempre genera plan explicito antes de actuar.",
        system_hint=(
            "# Persona planner\n"
            "El usuario quiere ver el plan antes de la accion. Para cualquier "
            "pedido con dos o mas pasos, SIEMPRE genera un plan numerado primero "
            "(aun cuando should_plan no lo dispare automaticamente). Pide "
            "confirmacion antes de ejecutar steps con side effects (descargas, "
            "registry, apps, archivos). Reporta avance step-by-step."
        ),
        preferred_tools=("routine", "notification", "local_calendar", "notes_tasks", "state"),
        tone="deliberate",
    ),
    "casual": Persona(
        name="casual",
        description="Conversacional: respuestas cortas, sin tools para chat trivial.",
        system_hint=(
            "# Persona casual\n"
            "Conversacion casual. Respuestas breves, naturales, en una o dos "
            "oraciones cuando alcance. Solo invoca tools cuando el usuario "
            "claramente pide una accion del PC; para preguntas de conocimiento "
            "general o conversacion, responde directo sin llamar tools."
        ),
        preferred_tools=(),
        tone="relaxed",
    ),
}


def get(name: str | None) -> Persona:
    """Resolve a persona by name. Falls back to 'default' silently."""
    key = (name or "default").strip().casefold()
    return PERSONAS.get(key, PERSONAS["default"])


def from_env() -> Persona:
    return get(os.environ.get("GEMMA4_AGENT_PERSONA"))


def list_names() -> list[str]:
    return sorted(PERSONAS.keys())
