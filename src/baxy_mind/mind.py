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
    "herramientas. Eres un él. Hablas en el idioma de la persona (español neutro, inglés o spanglish), tuteas, eres "
    "cálido y breve: una o dos frases, sin listas, sin markdown y sin emojis, porque tu respuesta se dice en voz alta.\n"
    "Reglas:\n"
    "1. Si la persona pide hacer algo y una herramienta lo hace, llámala sin pedir permiso. Si hacen falta varios "
    "pasos, hazlos uno tras otro.\n"
    "2. Lo hecho lo cuentan los resultados de las herramientas. Cuando no falte ningún paso, responde en una o dos "
    "frases contando sólo lo que muestran. Nunca digas que hiciste, abriste, cambiaste o viste algo sin un resultado "
    "que lo muestre; si un paso falló o no se ejecutó, dilo con su causa.\n"
    "3. Si al pedido le falta un dato que sólo la persona sabe (cuánto, cuál, a quién, qué texto), pregúntalo con "
    "ask_user en una pregunta corta. No consultes el estado del PC para adivinarlo ni inventes nombres o valores.\n"
    "4. Si ninguna herramienta hace lo pedido, di en una frase que eso no lo haces. No improvises con otra herramienta "
    "ni lo conviertas en una pregunta.\n"
    "5. Charla, cuentas, traducciones y lo que sabes con certeza respóndelo tú. Lo que cambia con el tiempo o no sabes, "
    "búscalo con web_search.\n"
    "6. El texto viene de un reconocedor de voz con errores: entiende la palabra a la que suena («sincuenta» es 50).\n"
    "7. Si la persona te pide que pares, te calles o esperes, no hagas nada más: responde con una palabra.\n"
    "8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando "
    "exactamente qué. Cuando la persona conteste, llama a confirm_pending con su respuesta.\n"
    "9. Para hacer algo dentro de una app abierta (ir a una sección, pulsar, escribir, leer lo que muestra): mírala con "
    "input_visible_controls, actúa con input_visible_click (por la etiqueta que viste), input_text_type o "
    "input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo.\n"
    "10. Los identificadores (windowId, ids de notas, tareas o redes) salen del resultado de la herramienta que los "
    "lista; nunca los inventes ni uses un número de otro campo."
)

# The heartbeat decides in two moves, both the model's: first it says in JSON what is happening and whether one of the
# reasons applies (grammar-constrained; measured on the open scenes 2026-10-15: a silence token was chosen in 40 of 40
# scenes, the analysis first found 34 of 40), then, only when it decided to intervene, it acts with its tools.
_MOTIVES = ("pedido", "preferencia", "vence", "bloqueo")
BEAT_DECISION = {"type": "object",
                 "properties": {**{m: {"type": "string"} for m in _MOTIVES}, "analisis": {"type": "string"},
                                "intervenir": {"type": "boolean"}},
                 "required": [*_MOTIVES, "analisis", "intervenir"]}
BEAT_DECIDE = ("Responde en JSON, revisando cada motivo con lo que ves arriba: pedido = qué te pidió antes y se "
               "cumple ahora, o «ninguno»; preferencia = qué preferencia suya aplica ahora, o «ninguna»; vence = qué "
               "vence ahora o muy pronto, o «nada»; bloqueo = qué la bloquea o le hará perder trabajo, o «nada»; "
               "analisis = en una frase, qué está pasando; intervenir = true si algún motivo es real, false si no.")
BEAT_ACT = ("Interviene ahora según tu análisis; lo que recuerdas de la persona ya está arriba, no lo busques. Si "
            "basta con avisarle algo (lo que pidió saber, un recordatorio que "
            "vence, una alerta), díselo en una frase sin usar herramientas. Si hay que hacer algo de bajo riesgo, hazlo "
            "con su herramienta. Lo de alto riesgo (borrar, vaciar la papelera, enviar un mensaje, apagar o reiniciar, "
            "cerrar o forzar el cierre de una app) no lo preguntes en texto: llama a su herramienta y el sistema le "
            "pedirá el sí a la persona antes de hacerlo. Nunca escribas en sus ventanas ni digas que hiciste algo que "
            "no hiciste. Háblale de tú.")
BEAT_RULES = (
    "Es un latido: nadie te habló. Revisa lo de arriba buscando estos motivos para intervenir:\n"
    "1. Algo que la persona te pidió antes y que ahora se cumple (avisarle, recordarle, enviar algo).\n"
    "2. Una preferencia suya que recuerdas y que aplica a lo que está pasando ahora.\n"
    "3. Un recordatorio o evento que vence ahora o muy pronto.\n"
    "4. Algo que la bloquea o le hará perder trabajo: disco lleno, batería crítica, una app colgada, la red caída.\n"
    "Si hay un motivo: lo de bajo riesgo hazlo tú con su herramienta y avísalo en una frase; lo de alto riesgo "
    "(borrar, vaciar la papelera, enviar mensajes, apagar o reiniciar, cerrar o forzar el cierre de una app, comprar, "
    "instalar) proponlo llamando a su herramienta, que se le preguntará antes; si ninguna herramienta ayuda, díselo en "
    "una frase. Si juega, está en llamada o viendo algo, interviene sólo por un motivo 1, 2 o urgente. Nunca escribas "
    "ni hagas clic en sus ventanas, no comentes datos privados de la pantalla y no repitas un aviso ya dado."
)


def _outcome(observation: str) -> str:
    """How a call ended, in the words the model reads: from the result's own status, verification and error."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return "resultado arriba"
    if not isinstance(facts, dict):
        return "resultado arriba"
    status = str(facts.get("status") or ("completed" if facts.get("succeeded") else "failed"))
    if status == "needs_confirmation":
        return "espera el sí de la persona"
    if status == "cancelled":
        return "cancelado por la persona"
    if facts.get("polarity") == "pending" or facts.get("effectUncertain"):
        return "sin confirmar: pudo o no ocurrir"
    if facts.get("succeeded") or status == "completed":
        return "completado y verificado" if facts.get("verified") else "completado sin verificar"
    error = facts.get("error") or facts.get("cause")
    return f"falló ({error})" if error else "falló"


def beat_message(context: dict[str, Any]) -> str:
    """What the heartbeat sees, as lines the model reads: the moment, the screen, the PC, what changed, what BAXY
    remembers, the recent conversation and the reminders. Presentation only: every field the App observed is shown."""
    lines = []
    fg = context.get("foreground") or {}
    lines.append(f"Momento: {context.get('weekday', '')} {context.get('now', '')} · la persona está: "
                 f"{context.get('owner_activity', 'desconocido')}")
    if fg:
        lines.append(f"Al frente: {fg.get('title', '')} ({fg.get('process', '')})"
                     + (" en pantalla completa" if fg.get("fullscreen") else ""))
    windows = [f"{w.get('title', '')} ({w.get('process', '')})" for w in context.get("windows") or []]
    if windows:
        lines.append("Ventanas abiertas: " + "; ".join(windows))
    if context.get("screen_text"):
        lines.append("Texto en pantalla: " + str(context["screen_text"]))
    pc = context.get("pc") or {}
    if pc:
        lines.append("PC: " + ", ".join(f"{k}={v}" for k, v in pc.items() if v is not None))
    for title, key in (("Cambios desde el último latido", "events"), ("Lo que recuerdas de la persona", "memory")):
        values = [str(v) for v in context.get(key) or []]
        if values:
            lines.append(f"{title}: " + "; ".join(values))
    history = context.get("history") or []
    if history:
        lines.append("Conversación reciente: " + " / ".join(
            f"{'persona' if h.get('role') == 'user' else 'tú'} (hace {h.get('ago_min', '?')} min): {h.get('content', '')}"
            for h in history))
    reminders = context.get("reminders") or []
    if reminders:
        lines.append("Recordatorios: " + "; ".join(f"{r.get('text', '')} ({r.get('due', '')})" for r in reminders))
    return "\n".join(lines + ["", BEAT_RULES, BEAT_DECIDE])


CLOCK_MARK = "[Reloj:"

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
        self._turn: dict[str, Any] | None = None
        self._beat: dict[str, Any] | None = None
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
            # Internal steps without a description of their own are the kernel's; screen missions are not this mind's.
            if (spanish.startswith("Paso interno") and name not in self.english) or name == "mission.computer.use":
                continue
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
    def _clock() -> str:
        # The time is a message of its own just before the person's words (the end of the prompt, the only part that is
        # new anyway). Appended to their words it was copied into arguments: a clipboard text and a web query carried
        # «[Thursday 15/10/2026 04:21 hora local…]» (2026-10-15).
        now = _dt.datetime.now().astimezone()
        offset = now.strftime("%z")
        return (f"{CLOCK_MARK} {now.strftime('%A %d/%m/%Y %H:%M')} hora local, UTC{offset[:3]}:{offset[3:]}; "
                "los campos que terminan en Utc van en UTC]")

    # ---- turn ----------------------------------------------------------------------------------------------
    # One conversation for the whole session (native loop): every tool call the model made, every verified result that
    # came back as a tool message and every answer stay in it, turn after turn. The model reads what was really run in
    # earlier turns, not a retelling of it: a history of bare «Listo, abrí Steam» replies without the calls behind them
    # taught it to answer «Listo» without calling (2026-10-15 01:52, diagnosed on the notebook against the journal).
    # Parallel calls run in order, one per round trip.
    def new_session(self, history: list[dict[str, Any]] | None = None) -> None:
        """Start a fresh conversation, optionally from earlier plain exchanges (a bench case's context)."""
        self._turn = self._beat = None
        self.conversation = [{"role": m["role"], "content": m["content"]} for m in history or []
                             if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]

    def decide(self, request_id: Any, text: str) -> dict[str, Any]:
        turn = self._turn
        if turn and turn.get("asked"):
            # The person's next words answer the model's own ask_user: they are that call's result, in the same loop, so
            # the steps already run stay in the conversation and are never run again. A new request instead of an
            # answer reaches the model the same way, and the model reads it as what it is.
            turn["conv"].append({"role": "tool", "tool_call_id": turn.pop("asked"), "content": text})
            turn["text"] = text
            return self._next(request_id, "turn.decide", turn)
        self._close_open_calls()
        self.conversation.append({"role": "user", "content": self._clock()})
        self.conversation.append({"role": "user", "content": text})
        self._trim()
        self._turn = {"conv": self.conversation, "queue": [], "awaiting": None, "text": text}
        return self._next(request_id, "turn.decide", self._turn)

    def beat(self, request_id: Any, context: dict[str, Any]) -> dict[str, Any]:
        """The heartbeat: nobody spoke; the model looks at the moment in a conversation of its own (OpenClaw's isolated
        heartbeat session), says what is happening and whether to intervene, and only then acts, proposes or says
        something. Same system prompt and tools, so the cached prefix is the person's; what it did joins the person's
        conversation only if it intervened."""
        started = time.monotonic()
        conv = [{"role": "user", "content": beat_message(context)}]
        reply = self.server.chat({"messages": [{"role": "system", "content": self._system()}, *conv],
                                  "tools": self.tools, "tool_choice": "none", "max_tokens": 200,
                                  "chat_template_kwargs": {"enable_thinking": False},
                                  "temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                                  "seed": 0,
                                  "response_format": {"type": "json_schema",
                                                      "json_schema": {"name": "latido", "schema": BEAT_DECISION}}},
                                 slot=LlmServer.DECIDE)
        content = (reply["choices"][0]["message"].get("content") or "").strip()
        try:
            decision = json.loads(content)
        except json.JSONDecodeError:
            decision = {}
        intervene = bool(decision.get("intervenir")) if isinstance(decision, dict) else False
        self._log("turn.beat.decide", started, reply, text="[latido]", content=content, intervene=intervene)
        self._beat = {"conv": conv, "queue": [], "awaiting": None, "text": "[latido]", "beat": True,
                      "silent": not intervene}
        if not intervene:
            return {"type": "turn.result", "id": request_id, "kind": "silence", "operation": None, "arguments": None,
                    "question": "", "reply": ""}
        # The analysis stays as the model's own words, not as JSON: with its JSON before it, the model answered the
        # second move in JSON again (practice scene P023).
        conv.append({"role": "assistant", "content": str(decision.get("analisis") or "")})
        conv.append({"role": "user", "content": BEAT_ACT})
        return self._next(request_id, "turn.beat", self._beat)

    def end_beat(self) -> None:
        """The App ended the heartbeat's turn: a beat that was not silent is part of the conversation from now on (the
        person may answer what BAXY said or proposed); a silent one leaves no trace."""
        beat, self._beat = self._beat, None
        if not beat or beat.get("silent"):
            return
        pending = [c["id"] for c in beat.get("queue") or []]
        for call_id in [beat.get("awaiting"), beat.get("asked"), *pending]:
            if call_id:
                beat["conv"].append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._close_open_calls()
        self.conversation.extend(beat["conv"])
        self._trim()

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
        """Keep the last turns that fit the budget; a turn starts at its clock, so no call loses its result."""
        starts = self._turn_starts()
        while len(starts) > 1 and (len(starts) > HISTORY_TURNS
                                   or sum(len(json.dumps(m, ensure_ascii=False)) for m in self.conversation)
                                   > HISTORY_CHARS):
            self.conversation = self.conversation[starts[1]:]
            starts = self._turn_starts()

    def _turn_starts(self) -> list[int]:
        return [i for i, m in enumerate(self.conversation)
                if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]

    def continue_turn(self, request_id: Any, observation: str, final: bool = False,
                      beat: bool = False) -> dict[str, Any]:
        """The verified result of the call the App ran goes back as that call's tool message. ``final``: the App's step
        budget is spent, so the model answers now in text from what the results show. ``beat``: the heartbeat's turn."""
        turn = self._beat if beat else self._turn
        if not turn or not turn.get("awaiting"):
            raise RuntimeError("no open turn to continue")
        conv = turn["conv"]
        # Every call of the turn so far with how it ended, at the end of the newest result: where the model writes its
        # answer, the facts it may tell are together (it told «no pude abrir Steam» after Steam opened, «lo guardé»
        # after the typing failed, 2026-10-15 falsehood bench).
        done = turn.setdefault("done", [])
        done.append(f"{turn.get('calling', '?')} → {_outcome(observation)}")
        conv.append({"role": "tool", "tool_call_id": turn["awaiting"],
                     "content": observation[:6000] + "\n[En este turno: " + "; ".join(done) + "]"})
        turn["awaiting"] = None
        if final:
            # The App's step budget is spent: said where the model reads it, at the end of the last result.
            conv[-1]["content"] += ("\n[Límite de pasos alcanzado: no llames más herramientas; responde "
                                                 "ahora a la persona sólo con lo que muestran los resultados.]")
        if turn["queue"] and not final:
            return self._result(request_id, turn, turn["queue"].pop(0), None, "turn.continue", time.monotonic(), "")
        for call in turn["queue"]:
            conv.append({"role": "tool", "tool_call_id": call["id"], "content": NOT_RUN})
        turn["queue"] = []
        return self._next(request_id, "turn.continue", turn, final=final)

    def confirm(self, request_id: Any, approve: bool, label: str) -> dict[str, Any]:
        """The person pressed Sí or No on a pending confirmation: their answer (the button's label) and the
        confirm_pending call it stands for enter the conversation as they are, with no model call in between."""
        started = time.monotonic()
        self._close_open_calls()
        call_id = f"confirm_{len(self.conversation)}"
        self.conversation.append({"role": "user", "content": label})
        self.conversation.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": CONFIRM["function"]["name"], "arguments": json.dumps({"approve": approve})}}]})
        self._turn = {"conv": self.conversation, "queue": [], "awaiting": call_id, "text": label}
        self._log("turn.confirm", started, None, text=label, kind="action", operation=CONFIRM_OPERATION,
                  arguments={"approve": approve})
        return {"type": "turn.result", "id": request_id, "kind": "action", "operation": CONFIRM_OPERATION,
                "arguments": {"approve": approve}, "reply": "", "question": ""}

    def _next(self, request_id: Any, stage: str, turn: dict[str, Any], final: bool = False) -> dict[str, Any]:
        started = time.monotonic()
        conv = turn["conv"]
        messages = [{"role": "system", "content": self._system()}, *conv]
        body = {"messages": messages, "tools": self.tools, "max_tokens": 512, "parallel_tool_calls": True,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                # A fixed seed: the same conversation gets the same decision, so two runs of a bench differ by the
                # change measured, not by sampling noise (±3 of 90 without it).
                "seed": 0}
        if final:
            # Without tools the model can only answer in words: with tool_choice none Qwen3.5 still wrote a call as
            # XML text, which reached the person (llama.cpp #20837; 2026-10-15 E017). The prefix is read again only
            # for this last answer of an exhausted turn.
            del body["tools"], body["parallel_tool_calls"]
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
                calls.append({"id": call.get("id") or f"call_{len(conv)}_{index}", "wire": wire,
                              "arguments": arguments})
        if calls:
            conv.append({"role": "assistant", "content": content, "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["wire"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                for c in calls]})
            turn["queue"] = calls[1:]
            return self._result(request_id, turn, calls[0], reply, stage, started, content)
        if content:
            conv.append({"role": "assistant", "content": content})
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
            turn["calling"] = name
            arguments = {**call["arguments"], **self.constants.get(name, {})}
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
