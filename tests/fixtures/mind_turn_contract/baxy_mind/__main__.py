"""Deterministic ``baxy.mind.v1`` fixture used only by integration tests.

This is deliberately a protocol oracle, not a language router.  The tests use
it to prove that ``MainWindowViewModel`` really crosses the process boundary
through ``MindSidecarClient`` before a typed operation reaches the real core.
Production never adds this directory to ``PYTHONPATH``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _write(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _trace(message: dict[str, Any]) -> None:
    configured = os.environ.get("BAXY_MIND_CONTRACT_TRACE", "").strip()
    if not configured:
        return
    path = Path(configured)
    selected: dict[str, Any] = {"type": message.get("type")}
    for key in (
        "text",
        "history",
        "operation",
        "objective",
        "purpose",
        "expectedOperations",
    ):
        if key in message:
            selected[key] = message[key]
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(selected, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _turn(message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    text = str(message.get("text") or "").strip()
    history = message.get("history")
    if not isinstance(history, list):
        history = []

    if text == "Hola":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation",
            "operation": None,
            "effectOperations": [],
            "question": "",
            "reply": "¡Hola! Estoy aquí para ayudarte.",
        }
    if text == "Explícame la fotosíntesis":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation",
            "operation": None,
            "effectOperations": [],
            "question": "",
            "reply": (
                "La fotosíntesis convierte luz, agua y dióxido de carbono "
                "en energía química para la planta."
            ),
        }
    if text == "¿Por qué?":
        has_context = any(
            isinstance(turn, dict)
            and turn.get("role") == "assistant"
            and "convierte luz" in str(turn.get("content") or "")
            for turn in history
        )
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation" if has_context else "clarify",
            "operation": None,
            "effectOperations": [],
            "question": "" if has_context else "¿A qué explicación te refieres?",
            "reply": (
                "Porque la clorofila captura la energía de la luz e impulsa "
                "esas reacciones."
                if has_context
                else ""
            ),
        }
    if text == "¿Qué?":
        has_context = any(
            isinstance(turn, dict)
            and turn.get("role") == "assistant"
            and "clorofila" in str(turn.get("content") or "")
            for turn in history
        )
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation" if has_context else "clarify",
            "operation": None,
            "effectOperations": [],
            "question": "" if has_context else "¿Qué parte quieres que aclare?",
            "reply": (
                "En simple: la planta usa la luz como fuente de energía."
                if has_context
                else ""
            ),
        }
    if text.startswith("Presento una palabra temporal: "):
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation",
            "operation": None,
            "effectOperations": [],
            "question": "",
            # Deliberately omit the value: recall must use the prior user turn,
            # not merely echo the latest assistant reply.
            "reply": "Entendido; la mantendré en el contexto de esta conversación.",
        }
    if text == "¿Qué palabra temporal presenté?":
        prefix = "Presento una palabra temporal: "
        remembered = next(
            (
                str(turn.get("content") or "")[len(prefix) :].strip().rstrip(".")
                for turn in reversed(history)
                if isinstance(turn, dict)
                and turn.get("role") == "user"
                and str(turn.get("content") or "").startswith(prefix)
            ),
            "",
        )
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "conversation" if remembered else "clarify",
            "operation": None,
            "effectOperations": [],
            "question": "" if remembered else "¿Qué palabra quieres que recuerde?",
            "reply": (
                f"La palabra temporal que presentaste fue {remembered}."
                if remembered
                else ""
            ),
        }
    if text == "Haz eso":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "clarify",
            "operation": None,
            "effectOperations": [],
            "question": "¿Qué acción concreta quieres que haga?",
            "reply": "",
        }
    if text == "Dime la hora actual":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "action",
            "operation": "system.time",
            "effectOperations": ["system.time"],
            "question": "",
            "reply": "",
        }
    if text == "Dime la hora y revisa la CPU":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "plan",
            "operation": None,
            "effectOperations": ["system.time", "system.status"],
            "question": "",
            "reply": "",
        }
    if text == "Revisa el estado general":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "plan",
            "operation": None,
            "effectOperations": [],
            "question": "",
            "reply": "",
        }
    if text == "Navega Opera a https://example.com/":
        return {
            "type": "turn.result",
            "id": request_id,
            "kind": "action",
            "operation": "browser.navigate.named",
            "effectOperations": ["browser.navigate.named"],
            "question": "",
            "reply": "",
        }
    return {
        "type": "turn.result",
        "id": request_id,
        "kind": "clarify",
        "operation": None,
        "effectOperations": [],
        "question": "¿Puedes concretar lo que necesitas?",
        "reply": "",
    }


def _plan(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "plan.result",
        "id": message.get("id"),
        "version": 1,
        "kind": "plan",
        "question": "",
        "steps": [
            {
                "id": "read_time",
                "operation": "system.time",
                "purpose": "Leer la hora local sin modificar el equipo.",
                "dependsOn": [],
                "argumentsMode": "literal",
                "arguments": {},
            },
            {
                "id": "read_cpu",
                "operation": "system.status",
                "purpose": "Leer el uso de CPU sin modificar el equipo.",
                "dependsOn": ["read_time"],
                "argumentsMode": "literal",
                "arguments": {"scope": "cpu"},
            },
        ],
    }


def main() -> int:
    _write(
        {
            "type": "hello",
            "protocol": "baxy.mind.v1",
            "mindVersion": "contract-fixture-v1",
            "models": {"llm": "deterministic-contract-fixture"},
            "requests": [
                "catalog.configure",
                "turn.decide",
                "plan",
                "plan.ground",
                "narrate",
                "voice.start",
                "voice.stop",
                "voice.status",
                "voice.speak",
                "voice.cancel",
                "shutdown",
            ],
        }
    )
    for raw_line in sys.stdin:
        if not raw_line.strip():
            continue
        message = json.loads(raw_line)
        _trace(message)
        request_id = message.get("id")
        kind = message.get("type")
        if kind == "catalog.configure":
            capabilities = message.get("capabilities")
            count = len(capabilities) if isinstance(capabilities, list) else 0
            _write({"type": "catalog.ready", "id": request_id, "count": count})
        elif kind == "turn.decide":
            _write(_turn(message))
        elif kind == "arguments":
            operation = message.get("operation")
            arguments = (
                {}
                if operation == "system.time"
                else {
                    "browser": "opera",
                    "url": "https://example.com/",
                }
                if operation == "browser.navigate.named"
                else None
            )
            _write(
                {
                    "type": "arguments.result",
                    "id": request_id,
                    "operation": operation,
                    "arguments": arguments,
                    "ok": arguments is not None,
                    "question": "",
                }
            )
        elif kind == "plan":
            _write(_plan(message))
        elif kind == "voice.status":
            _write(
                {
                    "type": "voice.status.result",
                    "id": request_id,
                    "status": {
                        "available": False,
                        "input": False,
                        "stt": False,
                        "vad": False,
                        "tts": False,
                        "aec": False,
                        "ducking": False,
                        "mode": "off",
                        "listening": False,
                        "speaking": False,
                    },
                }
            )
        elif kind == "message.compose":
            facts = message.get("facts")
            situation = (
                str(facts.get("situation") or "")
                if isinstance(facts, dict)
                else ""
            )
            _write(
                {
                    "type": "message.compose.result",
                    "id": request_id,
                    "text": situation or "La operación terminó y fue verificada.",
                }
            )
        elif kind == "shutdown":
            _write({"type": "shutdown.ack", "id": request_id})
            return 0
        else:
            _write(
                {
                    "type": "error",
                    "id": request_id,
                    "code": "unsupported_fixture_request",
                    "message": str(kind),
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
