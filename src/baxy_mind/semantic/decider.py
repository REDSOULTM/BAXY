"""The contextual decider: the model reads the whole conversation and the catalog and decides the turn.

Fase 3.5b «comprensión natural» (F2–F3, 2026-09-25): the model deciding alone, with the conversation as it is,
the catalog of every operation and the owner's rules, decided better than the readers, the shortlist, the native
selector and the gates put together (DEV-B 204/253 against 182/253; follow-ups that depend on the previous turn
61/66 against 40/66). It first restates the last message as a complete request (what the arguments step reads),
then decides: operations of the catalog, one short question, conversation, or a limit said plainly. It proposes;
the kernel still authorizes and the provider executes (invariant 1).

This module is the reading: the policy, the catalog as the decider sees it and the closed output. The model call
is ``llm.LlmRuntime.decide_in_context``.
"""

from __future__ import annotations

import functools
import json
import pathlib
from dataclasses import dataclass
from typing import Any, Iterable

DECISIONS = ("action", "clarify", "talk", "limit")

# The owner's rules (00_IDENTIDAD, REGLAS_ORO of the comprensión sets): what is public is looked up, what is the
# person's is never looked up, a complete request is not asked again, a relative amount without a number is asked,
# a limit is said plainly, a missing personal datum is asked.
POLICY = (
    "Eres el decisor de BAXY, un asistente tipo Jarvis que vive en un PC con Windows. Lees la conversación y "
    "decides qué hacer con el ÚLTIMO mensaje de la persona. No ejecutas nada: sólo decides.\n\n"
    "Decisiones posibles:\n"
    "- \"action\": ejecutar una o varias operaciones del catálogo (lista abajo) que cubren lo pedido.\n"
    "- \"clarify\": hacer UNA pregunta corta porque falta de verdad algo que cambia el resultado.\n"
    "- \"talk\": contestar hablando, sin tocar el PC: conocimiento estable, charla, escribir contenido (código, "
    "recetas, listas, cuentos, traducciones), cálculos y conversiones, consejos, hablar de ti mismo, agradecer.\n"
    "- \"limit\": decir en llano que eso no lo haces (no está en el catálogo).\n\n"
    "Reglas:\n"
    "1. Lo público se busca: lo que cambia o no se sabe de memoria con seguridad (clima, noticias, deportes, "
    "precios, dólar, horarios, estrenos, datos de una persona, empresa o lugar concretos, opiniones sobre una obra) "
    "→ action con web.search (o weather.current para el clima, web.news.headlines para titulares). Lo estable "
    "(definiciones, cómo se hace algo, matemáticas, traducir, convertir unidades) → talk. Si la persona pide "
    "buscar o investigar algo público, es action con web.search.\n"
    "2. Lo propio no se busca en la web: datos de la persona (sus notas, recordatorios, alarmas, tareas, agenda, "
    "archivos, lo que suena en su PC), preguntas sobre ti o sobre lo que acabas de decir → la operación que lo lee, "
    "o talk, o clarify.\n"
    "3. Lo completo no se repregunta: si el mensaje trae lo necesario, action. Un valor por defecto razonable (el "
    "clima de aquí, algo de música) no es una duda.\n"
    "4. Cantidad relativa sin número («súbele un poco», «baja el brillo», «más fuerte») → clarify (cuánto). Con "
    "número o nivel → action.\n"
    "5. Vives en un PC: no controlas luces ni aparatos de la casa, no haces llamadas telefónicas ni SMS, no pides "
    "comida, taxis, compras ni reservas, no manejas el móvil ni relojes → limit. Lo que una operación del catálogo "
    "sí hace (por ejemplo mensajes por una app del PC, reproducir en un servicio de streaming, abrir una app) se "
    "hace con esa operación.\n"
    "6. Si falta un dato de la persona («¿llueve donde vive mi hermana?») → clarify.\n"
    "7. Erratas, sin tildes, dictado sin puntuación y spanglish se entienden como la persona quiso decir.\n"
    "8. Un mensaje que depende de lo anterior («¿y en Santiago?», «ahora en javascript», «20 minutos antes de "
    "eso», «súbele otro poco», «esa no, otra», «sí, dale», «10») se decide con la conversación: la misma operación "
    "con el valor nuevo, o talk que reusa lo que respondiste. Si acabas de preguntar algo y la persona contesta, "
    "completa ese pedido.\n"
    "9. Charla, gracias, quejas y reacciones → talk.\n\n"
    "Catálogo (operación: qué hace):\n"
)

FORMAT = (
    "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con lo que "
    "aporta la conversación, en el idioma de la persona, \"decision\": ..., \"operations\": [...] (vacía si no es "
    "action), \"question\": la pregunta corta si es clarify, si no \"\"}."
)

FAMILY_TITLES = {
    "app": "aplicaciones", "audio": "sonido", "backup": "copias", "bluetooth": "bluetooth", "browser": "navegador",
    "calculator": "calculadora", "calendar": "agenda", "capture": "capturas", "clipboard": "portapapeles",
    "display": "pantalla", "email": "correo", "filesystem": "archivos", "game": "juegos", "input": "teclado y clics",
    "media": "música y video", "memory": "memoria privada", "message": "mensajes", "network": "red", "note": "notas",
    "notification": "alarmas y recordatorios", "ocr": "leer texto en pantalla", "office": "documentos",
    "package": "programas", "peripheral": "periféricos", "reminder": "recordatorios", "routine": "rutinas",
    "streaming": "streaming", "system": "sistema", "task": "tareas y listas", "vision": "describir la pantalla",
    "weather": "clima", "web": "web", "wifi": "wifi", "window": "ventanas",
}

# Model turns kept from the conversation, and characters per turn: the prompt stays inside one server slot.
HISTORY_TURNS = 4
HISTORY_CHARACTERS = 1500


@dataclass(frozen=True, slots=True)
class ContextDecision:
    request: str
    decision: str
    operations: tuple[str, ...]
    question: str


_PLAIN_CATALOG = pathlib.Path(__file__).resolve().parents[1] / "data" / "decider_catalog.es.v1.json"


@functools.cache
def plain_descriptions() -> dict[str, str]:
    """One line per operation in the words a person uses (F4 M2).

    The technical description confused siblings («sesión SMTC» for pause and next, absolute and relative
    volume, opening an app and playing inside it). Written in a clean room from the technical catalog only;
    an operation it lacks keeps its own first sentence.
    """

    try:
        data = json.loads(_PLAIN_CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    operations = data.get("operations") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in operations.items()} if isinstance(operations, dict) else {}


def catalog_prompt(tools: Iterable[tuple[str, str]]) -> str:
    """The system prompt for ``(name, description)`` operations, the same bytes for the same catalog."""

    plain = plain_descriptions()
    families: dict[str, list[str]] = {}
    for name, description in sorted(tools):
        first = plain.get(name) or description.split(". ")[0].rstrip(".")
        families.setdefault(name.split(".", 1)[0], []).append(f"- {name}: {first[:140]}")
    catalog = "\n".join(f"[{FAMILY_TITLES.get(f, f)}]\n" + "\n".join(lines) for f, lines in families.items())
    return POLICY + catalog + FORMAT


def response_schema(operations: Iterable[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "request": {"type": "string", "maxLength": 300},
            "decision": {"type": "string", "enum": list(DECISIONS)},
            "operations": {"type": "array", "items": {"type": "string", "enum": sorted(operations)}, "maxItems": 3},
            "question": {"type": "string", "maxLength": 200},
        },
        "required": ["request", "decision", "operations", "question"],
        "additionalProperties": False,
    }


def messages(system: str, text: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """The conversation as it was, without the current message when the history already ends with it."""

    prior = [turn for turn in (history or []) if turn.get("role") in {"user", "assistant"} and turn.get("content")]
    if prior and prior[-1].get("role") == "user" and prior[-1].get("content") == text:
        prior = prior[:-1]
    prior = prior[-HISTORY_TURNS:]
    return [
        {"role": "system", "content": system},
        *({"role": turn["role"], "content": str(turn["content"])[:HISTORY_CHARACTERS]} for turn in prior),
        {"role": "user", "content": text},
    ]


def parse(content: str, operations: Iterable[str]) -> ContextDecision:
    """The decision the model wrote; an action whose operations are not served is not an action."""

    raw = json.loads(content)
    served = set(operations)
    decision = raw.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"decisión desconocida: {decision!r}")
    chosen = tuple(dict.fromkeys(op for op in raw.get("operations") or [] if op in served))
    if decision == "action" and not chosen:
        raise ValueError("una acción sin operaciones del catálogo")
    return ContextDecision(
        request=" ".join(str(raw.get("request") or "").split()),
        decision=decision,
        operations=chosen if decision == "action" else (),
        question=" ".join(str(raw.get("question") or "").split()),
    )

