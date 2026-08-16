"""Live acceptance gate for BAXY's person-facing language.

This complements the operation and historical-runtime suites.  It exercises
the same local Gemma runtime used by the desktop and rejects replies that
change the actor/result, expose implementation jargon, mishandle a greeting,
or add a generic follow-up after a completed action.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.llm import LlmRuntime  # noqa: E402


FORBIDDEN_GLOBAL = (
    "planner",
    "router",
    "schema",
    "tool",
    "json",
    "datos verificables",
    "pasos verificables",
    "qué quieres hacer ahora",
    "necesitas algo más",
)


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value).casefold()
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )


@dataclass(frozen=True)
class Case:
    name: str
    mode: str
    text: str
    intent: str = ""
    situation: str = ""
    contains_any: tuple[str, ...] = ()
    contains_all: tuple[str, ...] = ()
    forbids: tuple[str, ...] = ()


CASES = (
    Case("saludo_es", "chat", "hOLA", contains_all=("hola",),
         forbids=("exactamente", "más concreta", "específica")),
    Case("saludo_en", "chat", "Hello BAXY", contains_any=("hello", "hi")),
    Case("saludo_spanglish", "chat", "hey BAXY, hola",
         contains_any=("hola", "hello", "hey", "hi")),
    Case("gracias", "chat", "Muchas gracias", contains_any=("nada", "gusto")),
    Case("identidad", "chat", "¿Quién eres?", contains_all=("baxy",)),
    Case("conocimiento", "chat", "¿Cuál es la capital de Japón?",
         contains_all=("tokio",)),
    Case("explicacion", "chat", "Explícame en una frase qué es la RAM",
         contains_any=("memoria", "datos")),
    Case("aritmetica", "chat", "¿Cuánto es 17 por 6?", contains_all=("102",)),
    Case("confusion", "chat", "que?", contains_any=("dime", "ayud")),
    Case("status_enfocar", "compose", "ABRE STEAM", "status",
         "Listo, enfoqué Steam.", contains_all=("enfoque", "steam"),
         forbids=("abriste", "abrio", "no pude")),
    Case("status_abrir", "compose", "abre Steam", "status",
         "Listo, abrí Steam.", contains_all=("abri", "steam"),
         forbids=("abriste", "abrio", "no pude")),
    Case("status_cerrar", "compose", "cierra Steam", "status",
         "Listo, cerré Steam.", contains_all=("cerre", "steam"),
         forbids=("cerraste", "cerro", "no pude")),
    Case("status_tecla", "compose", "presiona Escape", "status",
         "Listo, presioné Escape.", contains_all=("presione", "escape"),
         forbids=("presionaste", "presiono", "no pude")),
    Case("status_texto", "compose", "escribe hola", "status",
         "Listo, escribí «hola».", contains_all=("escribi", "hola"),
         forbids=("escribiste", "escribio", "no pude")),
    Case("status_mouse", "compose", "haz clic izquierdo", "status",
         "Listo, hice clic izquierdo.", contains_all=("clic", "izquierdo"),
         forbids=("hiciste", "no pude")),
    Case("status_volumen", "compose", "pon el volumen en 25", "status",
         "Listo, puse el volumen en 25 %.", contains_all=("25", "volumen"),
         forbids=("pusiste", "no pude")),
    Case("status_ram", "compose", "cuánta RAM tengo", "status",
         "RAM: 2.9 GiB disponibles de 15.4 GiB.",
         contains_all=("2.9", "15.4")),
    Case("status_hora", "compose", "qué hora es", "status",
         "La hora local es 23:45.", contains_all=("23:45",)),
    Case("status_perifericos", "compose", "qué mouse tengo", "status",
         "Mouse conectado: Logitech G305.", contains_all=("logitech", "g305")),
    Case("error_accion", "compose", "presiona Escape", "error",
         "No pude presionar Escape.", contains_all=("no pude", "escape")),
    Case("error_app", "compose", "abre una app inexistente", "error",
         "No pude abrir esa aplicación porque no está instalada.",
         contains_all=("no pude",), contains_any=("aplicacion", "instalada")),
    Case("aclarar_app", "compose", "abre eso", "clarification",
         "Falta saber qué aplicación quieres abrir.",
         contains_all=("aplicacion",), contains_any=("cual", "que")),
    Case("aclarar_archivo", "compose", "abre el archivo", "clarification",
         "Falta saber qué archivo quieres abrir.", contains_all=("archivo",)),
    Case("confirmacion", "compose", "borra el archivo", "confirmation",
         "Responde «confirmar / confirm» o «cancelar / cancel».",
         contains_all=("confirmar", "confirm", "cancelar", "cancel")),
    Case("bienvenida", "compose", "", "welcome",
         "Hola. Estoy lista para ayudarte con este equipo.",
         contains_all=("hola",), forbids=("exactamente", "mas concreta")),
)


def validate(case: Case, reply: str, elapsed: float) -> list[str]:
    errors: list[str] = []
    normalized = fold(reply)
    if not reply.strip():
        errors.append("respuesta vacía")
    if elapsed >= 4.0:
        errors.append(f"latencia {elapsed:.3f}s >= 4s")
    for value in FORBIDDEN_GLOBAL + case.forbids:
        if fold(value) in normalized:
            errors.append(f"incluye texto prohibido: {value}")
    for value in case.contains_all:
        if fold(value) not in normalized:
            errors.append(f"falta: {value}")
    if case.contains_any and not any(fold(value) in normalized for value in case.contains_any):
        errors.append(f"no contiene ninguna alternativa: {case.contains_any}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    os.environ["BAXY_MIND_LLM_ENDPOINT"] = args.endpoint
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "4"

    runtime = LlmRuntime()
    results: list[dict[str, object]] = []
    failures = 0
    for case in CASES:
        started = time.perf_counter()
        if case.mode == "chat":
            reply = runtime.chat(case.text, history=[], tools=None, temperature=0.2)[0]
        else:
            facts: dict[str, object] = {"situation": case.situation}
            if case.intent == "status":
                facts["mustNotAskFollowUp"] = True
                required_actions = (
                    "abrí", "enfoqué", "cerré", "presioné", "escribí",
                    "hice", "puse", "cambié", "activé", "desactivé",
                )
                required_action = next(
                    (
                        action
                        for action in required_actions
                        if fold(action) in fold(case.situation)
                    ),
                    None,
                )
                if required_action:
                    facts["actor"] = "BAXY (yo, primera persona)"
                    facts["mustPreserveFirstPerson"] = True
                    facts["requiredAction"] = required_action
                    facts["requiredActions"] = [required_action]
            elif case.intent == "confirmation":
                facts["requiredResponseWords"] = [
                    "confirmar", "confirm", "cancelar", "cancel"
                ]
            reply = runtime.compose_user_message(case.text, case.intent, facts)
        elapsed = time.perf_counter() - started
        errors = validate(case, reply, elapsed)
        failures += bool(errors)
        result = {
            "name": case.name,
            "mode": case.mode,
            "elapsedSeconds": round(elapsed, 3),
            "reply": reply,
            "passed": not errors,
            "errors": errors,
        }
        results.append(result)
        marker = "PASS" if not errors else "FAIL"
        print(f"{marker} {case.name} {elapsed:.3f}s :: {reply}", flush=True)
        for error in errors:
            print(f"  - {error}", flush=True)

    summary = {
        "schema": "baxy-user-behavior-gate-v1",
        "total": len(results),
        "passed": len(results) - failures,
        "failed": failures,
        "maximumLatencySeconds": max(
            float(result["elapsedSeconds"]) for result in results
        ),
        "results": results,
    }
    if args.json_output:
        output = Path(args.json_output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"SUMMARY {summary['passed']}/{summary['total']} passed; "
        f"max={summary['maximumLatencySeconds']:.3f}s"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
