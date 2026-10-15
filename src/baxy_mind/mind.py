"""The turn: one native tool call decides and writes the arguments; one call speaks the verified result.

Nothing here authorizes or verifies: the kernel authorizes the proposed operation and the provider verifies its
effect. What the model cannot do becomes an honest limit (a question, «no pude», «eso no lo hago»), never a veto.
Everything the model needs comes from how the catalog is presented to it (names, descriptions, the installed
applications and games), not from code that decides for it.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time
from pathlib import Path
from typing import Any

from .llm_server import LlmServer

_DATA = Path(__file__).with_name("data")
_SPANISH = json.loads((_DATA / "decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
_ENGLISH_FILE = _DATA / "tool_descriptions.en.v1.json"

SYSTEM = (
    "Eres BAXY y sólo BAXY: un compañero tipo Jarvis que vive en el PC de la persona y hace lo que te pide usando "
    "herramientas. Eres un él. Hablas español neutro, tuteas, eres cálido y breve: una o dos frases, sin listas, "
    "sin markdown y sin emojis, porque tu respuesta se dice en voz alta. Entiendes español, inglés y spanglish y "
    "respondes en el idioma de la persona.\n"
    "Reglas:\n"
    "1. Si la persona pide hacer algo y una herramienta hace exactamente eso, llámala sin pedir permiso.\n"
    "2. Nunca digas que hiciste algo: lo hecho lo cuenta el resultado verificado, después.\n"
    "3. Si falta un dato imprescindible, llama a ask_user con una sola pregunta corta. No inventes nombres ni valores.\n"
    "4. Si ninguna herramienta hace lo pedido, di en una frase que eso no lo haces. No improvises con otra.\n"
    "5. No inventes hechos: lo que no sabes con certeza o cambia con el tiempo, búscalo con web_search. Charla, "
    "cuentas y traducciones respóndelas tú.\n"
    "6. El texto viene de un reconocedor de voz con errores: corrige la palabra a la que suena («sincuenta» es 50).\n"
    "7. Cuando recibas el resultado de una herramienta: si al pedido todavía le falta un paso, llama a la herramienta de "
    "ese paso (también si el pedido lo condiciona a un resultado que ya se cumplió); cuando no falte nada, responde en "
    "una o dos frases contando sólo lo que muestran los resultados, nunca un paso que no se ejecutó.\n"
    "8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando "
    "exactamente qué. Cuando la persona conteste, llama a confirm_pending con su respuesta."
)

# The session's conversation keeps the last turns that fit both bounds; it is only ever cut at a turn's start (the
# model is hybrid: its cache is reused from the front, so the middle of the prompt is never edited).
HISTORY_TURNS = 8
HISTORY_CHARS = 24000

NOT_RUN = json.dumps({"status": "not_run", "reason": "the turn ended before this call ran"})

# The operation the App reads as «the person answered the pending confirmation» (the kernel's challenge): the App sends
# the exact invocation the kernel challenged again with its token, or drops it.
CONFIRM_OPERATION = "confirmation.answer"
CONFIRM = {
    "type": "function",
    "function": {
        "name": "confirm_pending",
        "description": (
            "Give the person's answer to the confirmation you asked them for (an action that needed their «sí»). "
            "Use when: you asked «¿Lo borro?» and they said «sí, dale» (approve true) or «no, déjalo» (approve false). "
            "Do not use when: nothing is waiting for confirmation, or they asked for something new instead."
        ),
        "parameters": {"type": "object", "properties": {"approve": {"type": "boolean"}}, "required": ["approve"]},
    },
}

ASK_USER = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the person ONE short question, in their language, when a value an action needs is missing or the "
            "request could mean two different actions. Use when: «pon una alarma» (no time), «mándale un mensaje» "
            "(no recipient or text). Do not use when: the request is complete, or to chat."
        ),
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
}


# What the model sees of an argument schema: meaning only. Validation-only keywords stay with the kernel, which
# validates the exact schema anyway; contract constants (a const or a one-value enum) are not the model's to write and
# are added back when its call is handed to the App (measured 2026-10-15: −4k tokens of prefix; memory.save wrote 114
# output tokens, its constants among them).
_MEANING_KEYS = {"type", "properties", "required", "items", "enum", "description", "minimum", "maximum", "anyOf",
                 "oneOf", "default", "format"}


def _model_schema(schema: Any, constants: dict[str, Any] | None = None) -> Any:
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _MEANING_KEYS:
            continue
        if key == "type" and isinstance(value, list):
            kinds = [kind for kind in value if kind != "null"]
            value = kinds[0] if len(kinds) == 1 else kinds
        if key == "properties" and isinstance(value, dict):
            props = {}
            for name, prop in value.items():
                if constants is not None and isinstance(prop, dict) and (
                        "const" in prop or (isinstance(prop.get("enum"), list) and len(prop["enum"]) == 1)):
                    constants[name] = prop["const"] if "const" in prop else prop["enum"][0]
                    continue
                props[name] = _model_schema(prop)
            value = props
        elif key == "items":
            value = _model_schema(value)
        elif key in {"anyOf", "oneOf"} and isinstance(value, list):
            value = [_model_schema(item) for item in value]
        out[key] = value
    if constants and isinstance(out.get("required"), list):
        out["required"] = [name for name in out["required"] if name not in constants]
    return out


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Mind:
    def __init__(self, server: LlmServer, trace: Path) -> None:
        self.server = server
        self.trace = trace
        self.tools: list[dict[str, Any]] = []
        self.wire_to_op: dict[str, str] = {}
        self.op_to_tool: dict[str, dict[str, Any]] = {}
        self._decided: dict[str, dict[str, Any]] = {}
        self._turn: dict[str, Any] | None = None
        self.conversation: list[dict[str, Any]] = []
        self.constants: dict[str, dict[str, Any]] = {}
        language = os.environ.get("BAXY_RENEW_DESCRIPTIONS", "en")
        self.english = (
            json.loads(_ENGLISH_FILE.read_text(encoding="utf-8"))["tools"]
            if language == "en" and _ENGLISH_FILE.is_file() else {}
        )
        self.decide_temperature = _env_float("BAXY_RENEW_DECIDE_TEMPERATURE", 0.2)

    # ---- catalog -------------------------------------------------------------------------------------------
    def configure(self, message: dict[str, Any]) -> int:
        capabilities = list(message.get("capabilities") or [])
        try:  # the exact catalog the App sent, for offline measurement of the presentation
            (self.trace.parent / "catalog.configure.json").write_text(
                json.dumps(message, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        apps = [str(n) for n in ((message.get("applicationCatalog") or {}).get("names") or []) if str(n).strip()]
        games = sorted({f'{e.get("name")} (appId {e.get("appId")}, {e.get("provider")})'
                        for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                        if isinstance(e, dict) and e.get("name")})
        tools, wire_to_op, op_to_tool = [ASK_USER, CONFIRM], {}, {}
        for cap in capabilities:
            name = str(cap.get("name") or "")
            spanish = _SPANISH.get(name) or str(cap.get("description") or "")
            if spanish.startswith("Paso interno") or name == "mission.computer.use":
                continue  # internal steps are the kernel's; screen missions are not served by this mind
            description = self.english.get(name) or spanish
            if name == "app.open" and apps:
                description += " Installed applications (use one of these names as appId): " + "; ".join(apps) + "."
            if name == "game.launch" and games:
                description += " The person's game library: " + "; ".join(games) + "."
            raw = cap.get("argumentsSchema")
            constants: dict[str, Any] = {}
            schema = _model_schema(raw if isinstance(raw, dict) else {}, constants)
            if constants:
                self.constants[name] = constants
            schema["type"] = "object"
            schema.setdefault("properties", {})
            wire = name.replace(".", "_")
            tool = {"type": "function", "function": {"name": wire, "description": description, "parameters": schema}}
            tools.append(tool)
            wire_to_op[wire] = name
            op_to_tool[name] = tool
        self.tools, self.wire_to_op, self.op_to_tool = tools, wire_to_op, op_to_tool
        return len(capabilities)

    def warm(self) -> None:
        """Process the tools and the system prompt once, so every turn starts from a cached prefix."""
        self.server.chat({"messages": [{"role": "system", "content": self._system()},
                                           {"role": "user", "content": "hola"}],
                              "tools": self.tools, "max_tokens": 1,
                          "chat_template_kwargs": {"enable_thinking": False}}, slot=LlmServer.DECIDE, timeout=600)

    def _system(self) -> str:
        # Constant, so the prefix (tools, system, earlier messages) never changes between turns and is never re-read.
        return SYSTEM

    @staticmethod
    def _with_clock(text: str) -> str:
        # The time travels at the end of the person's message: the only part of the prompt that is new anyway.
        now = _dt.datetime.now().astimezone()
        offset = now.strftime("%z")
        return (f"{text}\n\n[{now.strftime('%A %d/%m/%Y %H:%M')} hora local, UTC{offset[:3]}:{offset[3:]}; "
                "los campos que terminan en Utc van en UTC]")

    # ---- turn ----------------------------------------------------------------------------------------------
    # One conversation for the whole session (native loop): every tool call the model made, every verified result that
    # came back as a tool message and every answer stay in it, turn after turn. The model reads what was really run in
    # earlier turns, not a retelling of it: a history of bare «Listo, abrí Steam» replies without the calls behind them
    # taught it to answer «Listo» without calling (2026-10-15 01:52, diagnosed on the notebook against the journal).
    # Parallel calls run in order, one per round trip.
    def new_session(self, history: list[dict[str, Any]] | None = None) -> None:
        """Start a fresh conversation, optionally from earlier plain exchanges (a bench case's context)."""
        self._turn = None
        self.conversation = [{"role": m["role"], "content": m["content"]} for m in history or []
                             if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]

    def decide(self, request_id: Any, text: str) -> dict[str, Any]:
        self._decided = {}
        turn = self._turn
        if turn and turn.get("asked"):
            # The person's next words answer the model's own ask_user: they are that call's result, in the same loop, so
            # the steps already run stay in the conversation and are never run again. A new request instead of an
            # answer reaches the model the same way, and the model reads it as what it is.
            self.conversation.append({"role": "tool", "tool_call_id": turn.pop("asked"), "content": text})
            turn["text"] = text
            return self._next(request_id, "turn.decide")
        self._close_open_calls()
        self.conversation.append({"role": "user", "content": self._with_clock(text)})
        self._trim()
        self._turn = {"queue": [], "awaiting": None, "text": text}
        return self._next(request_id, "turn.decide")

    def _close_open_calls(self) -> None:
        """A call the App never answered (the turn ended first) gets its honest result, so the conversation stays a
        valid tool transcript and the model never reads an unanswered call as done."""
        turn = self._turn or {}
        pending = [c["id"] for c in turn.get("queue") or []]
        for call_id in [turn.get("awaiting"), turn.get("asked"), *pending]:
            if call_id:
                self.conversation.append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._turn = None

    def _trim(self) -> None:
        """Keep the last turns that fit the budget; a turn starts at a person's message, so no call loses its result."""
        starts = [i for i, m in enumerate(self.conversation) if m["role"] == "user"]
        while len(starts) > 1 and (len(starts) > HISTORY_TURNS
                                   or sum(len(json.dumps(m, ensure_ascii=False)) for m in self.conversation)
                                   > HISTORY_CHARS):
            self.conversation = self.conversation[starts[1]:]
            starts = [i for i, m in enumerate(self.conversation) if m["role"] == "user"]

    def continue_turn(self, request_id: Any, observation: str, final: bool = False) -> dict[str, Any]:
        """The verified result of the call the App ran goes back as that call's tool message. ``final``: the App's step
        budget is spent, so the model answers now in text from what the results show."""
        turn = self._turn
        if not turn or not turn.get("awaiting"):
            raise RuntimeError("no open turn to continue")
        self.conversation.append({"role": "tool", "tool_call_id": turn["awaiting"], "content": observation[:6000]})
        turn["awaiting"] = None
        if turn["queue"] and not final:
            return self._result(request_id, turn, turn["queue"].pop(0), None, "turn.continue", time.monotonic(), "")
        for call in turn["queue"]:
            self.conversation.append({"role": "tool", "tool_call_id": call["id"], "content": NOT_RUN})
        turn["queue"] = []
        return self._next(request_id, "turn.continue", final=final)

    def confirm(self, request_id: Any, approve: bool, label: str) -> dict[str, Any]:
        """The person pressed Sí or No on a pending confirmation: their answer (the button's label) and the
        confirm_pending call it stands for enter the conversation as they are, with no model call in between."""
        started = time.monotonic()
        self._decided = {}
        self._close_open_calls()
        call_id = f"confirm_{len(self.conversation)}"
        self.conversation.append({"role": "user", "content": label})
        self.conversation.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": CONFIRM["function"]["name"], "arguments": json.dumps({"approve": approve})}}]})
        self._turn = {"queue": [], "awaiting": call_id, "text": label}
        self._log("turn.confirm", started, None, text=label, kind="action", operation=CONFIRM_OPERATION,
                  arguments={"approve": approve})
        return {"type": "turn.result", "id": request_id, "kind": "action", "operation": CONFIRM_OPERATION,
                "arguments": {"approve": approve}, "reply": "", "question": ""}

    def _next(self, request_id: Any, stage: str, final: bool = False) -> dict[str, Any]:
        started = time.monotonic()
        turn = self._turn
        assert turn is not None
        messages = [{"role": "system", "content": self._system()}, *self.conversation]
        body = {"messages": messages, "tools": self.tools, "max_tokens": 512, "parallel_tool_calls": True,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                # A fixed seed: the same conversation gets the same decision, so two runs of a bench differ by the
                # change measured, not by sampling noise (±3 of 90 without it).
                "seed": 0}
        if final:
            body["tool_choice"] = "none"
        reply = self.server.chat(body, slot=LlmServer.DECIDE)
        message = reply["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            wire = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            arguments = arguments if isinstance(arguments, dict) else {}
            if wire in {"ask_user", CONFIRM["function"]["name"]} or wire in self.wire_to_op:
                calls.append({"id": call.get("id") or f"call_{len(self.conversation)}_{index}", "wire": wire,
                              "arguments": arguments})
        if calls:
            self.conversation.append({"role": "assistant", "content": content, "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["wire"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                for c in calls]})
            turn["queue"] = calls[1:]
            return self._result(request_id, turn, calls[0], reply, stage, started, content)
        if content:
            self.conversation.append({"role": "assistant", "content": content})
        return self._result(request_id, turn, None, reply, stage, started, content)

    def _result(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any] | None, reply: dict | None,
                stage: str, started: float, content: str) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "turn.result", "id": request_id, "kind": "conversation", "operation": None,
                                  "arguments": None, "question": "", "reply": ""}
        if call is not None and call["wire"] == "ask_user":
            question = " ".join(str(call["arguments"].get("question") or "").split())
            turn["queue"], turn["awaiting"], turn["asked"] = [], None, call["id"]
            if question:
                result.update(kind="clarify", question=question)
            else:
                result.update(failure="empty_question")
        elif call is not None:
            name = CONFIRM_OPERATION if call["wire"] == CONFIRM["function"]["name"] else self.wire_to_op[call["wire"]]
            turn["awaiting"] = call["id"]
            arguments = {**call["arguments"], **self.constants.get(name, {})}
            self._decided = {name: arguments}
            result.update(kind="action", operation=name, arguments=arguments)
        elif content:
            result.update(reply=content)
        else:
            result.update(failure="empty_reply")
        self._log(stage, started, reply, text=turn["text"], kind=result["kind"], operation=result["operation"],
                  arguments=call["arguments"] if call else None, content=content)
        return result

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
