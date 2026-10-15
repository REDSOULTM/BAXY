"""The turn: one native tool call decides and writes the arguments; one call speaks the verified result.

Nothing here authorizes or verifies: the kernel authorizes the proposed operation and the provider verifies its
effect. What the model cannot do becomes an honest limit (a question, «no pude», «eso no lo hago»), never a veto.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
from pathlib import Path
from typing import Any

from .llm_server import LlmServer

_DATA = Path(__file__).with_name("data")
_SPANISH = json.loads((_DATA / "decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]

SYSTEM = (
    "Eres BAXY y sólo BAXY: un compañero tipo Jarvis que vive en el PC de la persona y hace lo que te pide usando "
    "herramientas. Eres un él. Hablas español neutro, tuteas, eres cálido y breve: una o dos frases, sin listas, "
    "sin markdown y sin emojis, porque tu respuesta se dice en voz alta. Entiendes español, inglés y spanglish y "
    "respondes en el idioma de la persona.\n"
    "Reglas:\n"
    "1. Si la persona pide hacer algo y una herramienta hace exactamente eso, llámala sin pedir permiso.\n"
    "2. Nunca digas que hiciste algo: lo hecho lo cuenta el resultado verificado, después.\n"
    "3. Si falta un dato imprescindible, haz una sola pregunta corta, terminada en «?». No inventes nombres ni valores.\n"
    "4. Si ninguna herramienta hace lo pedido, di en una frase que eso no lo haces. No improvises con otra.\n"
    "5. No inventes hechos: lo que no sabes con certeza o cambia con el tiempo, búscalo con la herramienta de "
    "búsqueda web. Charla, cuentas y traducciones respóndelas tú.\n"
    "6. El texto viene de un reconocedor de voz con errores: corrige la palabra a la que suena («sincuenta» es 50)."
)

COMPOSE = (
    "Eres BAXY. Escribe la respuesta final para la persona: una o dos frases cálidas y breves, habladas, sin "
    "markdown ni emojis, en el idioma de la persona. Di sólo lo que dicen los hechos verificados, con el dato "
    "concreto. Si el resultado no salió (ok false) dilo plano y con su causa, sin disculpas. Si no quedó verificado, "
    "di que diste la orden pero no pudiste confirmarlo. Si los hechos traen una pregunta o una confirmación "
    "pendiente, hazla. No inventes nada que no esté en los hechos. No menciones operaciones, campos ni "
    "verificaciones: habla como una persona.\n"
    "Ejemplos de tono: «Listo, el volumen quedó en 50.» · «No pude: Spotify no responde.» · «Di la orden, pero no "
    "pude confirmar que el wifi se apagó.» · «En Curicó hay 14 grados y está nublado.»"
)

SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0}


def _wire(name: str) -> str:
    return name.replace(".", "__")


def _unwire(name: str) -> str:
    return name.replace("__", ".")


def _single_question(text: str) -> bool:
    """A clarification is one question and nothing else; a greeting that ends asking is conversation."""
    head = text.split("¿", 1)[0]
    return (
        0 < len(text) <= 512 and text == text.strip() and "\n" not in text and "\r" not in text
        and text.endswith("?") and text.count("?") == 1 and not any(mark in head for mark in ".!")
    )


class Mind:
    def __init__(self, server: LlmServer, trace: Path) -> None:
        self.server = server
        self.trace = trace
        self.tools: list[dict[str, Any]] = []
        self.operations: set[str] = set()
        self._decided: dict[str, dict[str, Any]] = {}

    # ---- catalog -------------------------------------------------------------------------------------------
    def configure(self, capabilities: list[dict[str, Any]]) -> int:
        tools, names = [], set()
        for cap in capabilities:
            name = str(cap.get("name") or "")
            description = _SPANISH.get(name) or str(cap.get("description") or "")
            names.add(name)
            if description.startswith("Paso interno"):
                continue  # internal steps are the kernel's, never a choice of the model
            raw = cap.get("argumentsSchema")
            schema = {k: v for k, v in (raw if isinstance(raw, dict) else {}).items()
                      if k not in {"$schema", "$id", "title"}}
            schema.setdefault("type", "object")
            schema.setdefault("properties", {})
            tools.append({"type": "function", "function": {"name": _wire(name), "description": description,
                                                           "parameters": schema}})
        self.tools, self.operations = tools, names
        return len(capabilities)

    def warm(self) -> None:
        """Process the system prompt and the catalog once, so every turn starts from a cached prefix."""
        try:
            self.server.chat({"messages": [{"role": "system", "content": self._system()},
                                           {"role": "user", "content": "hola"}],
                              "tools": self.tools, "max_tokens": 1,
                              "chat_template_kwargs": {"enable_thinking": False}}, slot=LlmServer.DECIDE, timeout=600)
        except Exception:  # noqa: BLE001 - warming is an optimization only
            pass

    def _system(self) -> str:
        # The date goes in at day resolution so the cached prefix stays valid all day.
        today = _dt.datetime.now().strftime("%A %d de %B de %Y")
        return f"{SYSTEM}\nHoy es {today}."

    # ---- turn ----------------------------------------------------------------------------------------------
    def decide(self, request_id: Any, text: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        started = time.monotonic()
        now = _dt.datetime.now().strftime("%H:%M")
        messages = [{"role": "system", "content": self._system()}]
        for item in history[-12:]:
            role = item.get("role")
            if role in {"user", "assistant"} and isinstance(item.get("content"), str) and item["content"].strip():
                messages.append({"role": role, "content": item["content"]})
        messages.append({"role": "user", "content": f"{text}\n\n(hora actual {now})"})
        reply = self.server.chat({"messages": messages, "tools": self.tools, "max_tokens": 512,
                                  "chat_template_kwargs": {"enable_thinking": False}, **SAMPLING},
                                 slot=LlmServer.DECIDE)
        message = reply["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        content = (message.get("content") or "").strip()
        result: dict[str, Any] = {"type": "turn.result", "id": request_id, "operation": None,
                                  "intentOperations": [], "effectOperations": [], "question": "", "reply": "",
                                  "objective": text}
        decided = None
        for call in calls:
            name = _unwire(call["function"]["name"])
            if name in self.operations:
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                decided = (name, arguments if isinstance(arguments, dict) else {})
                break
        if decided is not None:
            name, arguments = decided
            self._decided = {name: arguments}
            result.update(kind="action", operation=name, intentOperations=[name], effectOperations=[name])
        elif _single_question(content):
            result.update(kind="clarify", question=content)
        elif content:
            result.update(kind="conversation", reply=content)
        else:
            result.update(kind="conversation", failure_code="turn_runtime_failure")
        self._log("turn.decide", started, reply, text=text, kind=result["kind"], operation=result["operation"],
                  arguments=decided[1] if decided else None, content=content)
        return result

    def arguments(self, request_id: Any, operation: str, text: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        started = time.monotonic()
        if operation in self._decided:
            arguments = self._decided.pop(operation)
            self._log("arguments", started, None, operation=operation, reused=True)
            return {"type": "arguments.result", "id": request_id, "operation": operation, "ok": True,
                    "arguments": arguments, "question": ""}
        tool = next((t for t in self.tools if _unwire(t["function"]["name"]) == operation), None)
        if tool is None:
            raise RuntimeError(f"unknown operation {operation}")
        messages = [{"role": "system", "content": self._system()}]
        messages += [m for m in history[-6:] if m.get("role") in {"user", "assistant"}]
        messages.append({"role": "user", "content": text})
        reply = self.server.chat({"messages": messages, "tools": [tool], "max_tokens": 256,
                                  "tool_choice": {"type": "function", "function": {"name": tool["function"]["name"]}},
                                  "chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.0},
                                 slot=LlmServer.SHORT)
        calls = reply["choices"][0]["message"].get("tool_calls") or []
        arguments: dict[str, Any] = {}
        if calls:
            try:
                parsed = json.loads(calls[0]["function"].get("arguments") or "{}")
                arguments = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                arguments = {}
        self._log("arguments", started, reply, operation=operation, reused=False, arguments=arguments)
        return {"type": "arguments.result", "id": request_id, "operation": operation, "ok": True,
                "arguments": arguments, "question": ""}

    def compose(self, request_id: Any, user_text: str, intent: str, facts: Any) -> dict[str, Any]:
        started = time.monotonic()
        data = json.dumps({"pedido": user_text, "intencion": intent, "hechos": facts}, ensure_ascii=False)
        reply = self.server.chat({"messages": [{"role": "system", "content": COMPOSE},
                                               {"role": "user", "content": data[:12000]}],
                                  "max_tokens": 200, "temperature": 0.3, "top_p": 0.8,
                                  "chat_template_kwargs": {"enable_thinking": False}}, slot=LlmServer.SHORT)
        text = (reply["choices"][0]["message"].get("content") or "").strip()
        self._log("message.compose", started, reply, intent=intent, text=text)
        return {"type": "message.compose.result", "id": request_id, "text": text}

    # ---- trace ---------------------------------------------------------------------------------------------
    def _log(self, stage: str, started: float, reply: dict[str, Any] | None, **fields: Any) -> None:
        timings = (reply or {}).get("timings") or {}
        row = {"t": _dt.datetime.now().isoformat(timespec="milliseconds"), "stage": stage,
               "ms": round((time.monotonic() - started) * 1000),
               "prompt_n": timings.get("prompt_n"), "prompt_ms": timings.get("prompt_ms"),
               "predicted_n": timings.get("predicted_n"), "predicted_ms": timings.get("predicted_ms"), **fields}
        try:
            with self.trace.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
