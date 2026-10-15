"""Estabilización B2 (uso real t4-c03 t2 «mandale a Ron92 que si se conecta a las 9 pa jugar» after «abre discord
porfa» → always message.draft with the deterministic decider; the elevation to a send of fable/estab-b-mandale was
rejected by its review for false sends).

In a follow-up the decider's draft stays a draft. When the readers without a model prove a send of one recipient in the
person's words and nothing in them or in the conversation holds it, the draft's final offers the send in those words
(«¿Le envío a Ron92 «…»?»); only a yes sends it, with that recipient and those words. Any doubt offers nothing. The
offer is the mind's, so it is a question in any confirmation mode.

Whole turns: the turn decided (``_prepare_turn_result``), expected (``_expect_decided_turn``), the draft verified and
its final told (``DialogueState.record``, ``_with_send_offer``), and the answer decided. Every row of the review of
fable/estab-b-mandale (revision_B: H1, H2, H4, T44, N, E, S, C, R, V), with the decider's draft without the tail and
with the person's whole words.
"""

from __future__ import annotations

import json
import re
import pathlib

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState, accepts_offer
from baxy_mind.semantic import messaging
from baxy_mind import turn_decide
from baxy_mind import send_offer

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿A qué hora?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def prepare_decision(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


TOOLS = {name: _tool(name) for name in OPERATIONS}
CATALOG = PlannerCatalog(list(TOOLS.values()))


def _action(request: str, *operations: str) -> ContextDecision:
    return ContextDecision(request=request, decision="action", operations=operations, question="")


TALK = ContextDecision(request="Charla.", decision="talk", operations=(), question="")


def _readers_send(request: str) -> bool:
    """The serve loop's check at the offer: the readers alone decide the send on the yes."""

    return turn_decide._readers_send(
        {"id": "b2", "text": request}, request, llm=_Decider(), planner_catalog=CATALOG, encoder=lambda _t: (),
        tool_by_name=TOOLS,
    ) is not None


class Conversation:
    """One conversation as the serve loop runs it, with the shell's verified draft in Discord."""

    def __init__(self, before: list[str]) -> None:
        self.state = DialogueState()
        self.history: list[dict] = []
        for said in before:
            self.history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]

    def turn(self, text: str, decided: ContextDecision | None) -> tuple[dict, str]:
        self.state.begin_turn()
        message = {"id": "b2", "text": text, "history": [*self.history, {"role": "user", "content": text}]}
        self.model = _Decider(decided)
        result = turn_decide._prepare_turn_result(
            message, llm=self.model, planner_catalog=CATALOG, encoder=lambda _t: (), tool_by_name=TOOLS,
            dialogue_state=self.state,
        )
        send_offer._expect_decided_turn(self.state, result, message, CATALOG, ())
        final = "Listo."
        if result.get("effectOperations") == ["message.draft"]:
            recipient, words = _drafted(decided.request if decided is not None else str(result.get("objective") or ""))
            self.state.record({
                "operation": "message.draft", "verified": True, "succeeded": True,
                "observed": {"channel": "discord", "displayName": recipient, "text": words, "sent": False},
            })
            final = send_offer._with_send_offer(
                f"Te lo dejé escrito a {recipient} en Discord, sin enviar.", self.state, _readers_send,
            )
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": final}]
        return result, final


def _drafted(restated: str) -> tuple[str, str]:
    """The recipient and the words of the decider's «Escríbele a X en Discord: «…».», «Write to X on Discord: «…».»."""

    found = re.match(r"^\S+\s+(?:a|to)\s+(.+?)\s+(?:en|on)\s+Discord:\s*«(.*)»\.?$", restated)
    return (found.group(1), found.group(2)) if found is not None else ("Ron92", restated)


def _sends(result: dict) -> bool:
    return "message.send" in (result.get("effectOperations") or [])


D = ["abre discord porfa"]

# The review's rows (cu-v3/estab/revision_B_datos/cases.py): id, before, text, recipient, the decider's words, expected.
ROWS = [
    ("H1-01", D, "escríbele a Ron92 que llego tarde pero déjalo en borrador", "Ron92", "llego tarde", "hold"),
    ("H1-02", D, "escríbele a Ron92 que llego tarde pero no envíes todavía", "Ron92", "llego tarde", "hold"),
    ("H1-03", D, "escríbele a Ron92 que llego tarde, sólo déjalo escrito", "Ron92", "llego tarde", "hold"),
    ("H1-04", D, "escríbele a Ron92 que llego tarde y yo lo reviso antes de mandarlo", "Ron92", "llego tarde", "hold"),
    ("H1-05", D, "mándale a Ron92 que llego tarde, no espera, mejor sólo déjalo escrito", "Ron92", "llego tarde", "hold"),
    ("H1-06", D, "write to Ron92 that I'm late but hold off on sending", "Ron92", "I'm late", "hold"),
    ("H1-07", D, "write to Ron92 that I'm late, just leave it as a draft", "Ron92", "I'm late", "hold"),
    ("H1-08", D, "write a draft to Ron92 saying I'm late", "Ron92", "I'm late", "hold"),
    ("H1-09", D, "escríbele a Ron92 un borrador que diga que llego tarde", "Ron92", "llego tarde", "hold"),
    ("H1-10", D, "escríbele a Ron92 que llego tarde pero espera, no envíes", "Ron92", "llego tarde", "hold"),
    ("H1-11", D, "escríbele a Ron92 que llego tarde, yo después lo envío", "Ron92", "llego tarde", "hold"),
    ("H1-12", D, "text Ron92 that I'm late but keep it as a draft", "Ron92", "I'm late", "hold"),
    ("H1-13", D, "mándale a Ron92 que llego tarde... ah no, mejor sólo escríbelo", "Ron92", "llego tarde", "hold"),
    ("H1-14", D, "write a note to self saying buy milk", "Ron92", "buy milk", "hold"),
    ("H2-1", ["te voy a dictar unos mensajes para Discord, no envíes ninguno, sólo déjalos escritos"],
     "escríbele a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("H2-2", ["déjale escrito a Ron92 en Discord que llego tarde"], "escríbele a Pedro que yo también", "Pedro",
     "yo también", "hold"),
    ("H2-3", ["déjale escrito a Ron92 en Discord que llego tarde"], "y escríbele a Pedro que yo también", "Pedro",
     "yo también", "hold"),
    ("H2-4", ["déjale escrito a Ron92 en Discord que llego tarde"], "mejor ponle que llego 10 minutos tarde", "Ron92",
     "llego 10 minutos tarde", "hold"),
    ("H2-5", ["déjale escrito a Ron92 en Discord que llego tarde"], "mándaselo", "Ron92", "llego tarde", "send"),
    ("H4-2", D, "mandale a Ron92 que le diga a Pedro que traiga el cable", "Ron92", "dile a Pedro que traiga el cable",
     "send"),
    ("H4-3", D, "mandale a Ron92 que nos vemos en Discord a las 9", "Ron92", "nos vemos en Discord a las 9", "send"),
    ("H4-4", ["qué hora es"], "mandale a Ron92 que si se conecta a las 9 pa jugar", "Ron92",
     "si se conecta a las 9 para jugar", "send"),
    ("T02", D, "escríbele a Ron92 que llego tarde", "Ron92", "llego tarde", "send"),
    ("T03", D, "déjale escrito a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("T05", D, "prepárale un mensaje a Ron92", "Ron92", "hola", "hold"),
    ("T06", D, "redacta un mensaje para Ron92 que diga llego tarde", "Ron92", "llego tarde", "hold"),
    ("T07", D, "anótale a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("T08", D, "ponle a Ron92 que llego tarde pero no lo mandes todavía", "Ron92", "llego tarde", "hold"),
    ("T16", D, "draft a message to Ron92 saying I'm late", "Ron92", "I'm late", "hold"),
    ("T18", D, "write Ron92 a message saying I'm late, don't send it yet", "Ron92", "I'm late", "hold"),
    ("T22", D, "type it out for Ron92", "Ron92", "hola", "hold"),
    ("T25", D, "escríbele a Ron92 que llego tarde y envíalo", "Ron92", "llego tarde", "send"),
    ("T26", D, "mándale el borrador que dejaste", "Ron92", "llego tarde", "send"),
    ("T27", D, "mándale a Ron92 el borrador que dejaste", "Ron92", "llego tarde", "send"),
    ("T28", D, "mándaselo a Ron92", "Ron92", "llego tarde", "send"),
    ("T29", D, "cuando termine mándale a Ron92 que ya está listo", "Ron92", "ya está listo", "hold"),
    ("T30", D, "mándale a Ron92 que ya está listo cuando termine la descarga", "Ron92", "ya está listo", "?"),
    ("T31", D, "¿le mandaste a Ron92 que llego tarde?", "Ron92", "llego tarde", "hold"),
    ("T32", D, "¿puedes mandarle a Ron92 que llego tarde?", "Ron92", "llego tarde", "send"),
    ("T33", D, "can you send Ron92 a message saying I'm late?", "Ron92", "I'm late", "send"),
    ("T34", D, "no le mandes nada a Ron92", "Ron92", "hola", "hold"),
    ("T35", D, "escríbele a Ron92: mándame la tarea", "Ron92", "mándame la tarea", "send"),
    ("T36", D, "escríbele a Ron92 que no lo mandes todavía", "Ron92", "no lo mandes todavía", "?"),
    ("T37", D, "mandale un msg a Ron92 que llego tarde", "Ron92", "llego tarde", "send"),
    ("T38", D, "y a Pedro también", "Pedro", "llego tarde", "?"),
    ("T39", D, "mandale a Ron92 por discord que ya voy saliendo", "Ron92", "ya voy saliendo", "send"),
    ("T41", D, "manda a Música en Discord que ya voy", "Música", "ya voy", "send"),
    ("T42", D, "escríbele a mamá por whatsapp que ya voy pero no lo mandes", "mamá", "ya voy", "hold"),
    ("T43", D, "abre discord y mándale a Ron92 que ya voy", "Ron92", "ya voy", "send"),
    ("N01", D, "escríbele a Ron92 que llego tarde y déjalo listo pa mandarlo después", "Ron92", "llego tarde", "hold"),
    ("N02", D, "escríbele a Ron92 que llego tarde, no lo mandes aún", "Ron92", "llego tarde", "hold"),
    ("N03", D, "escríbele a Ron92 que llego tarde y guárdalo", "Ron92", "llego tarde", "hold"),
    ("N04", D, "mándale a Ron92 que llego tarde pero guárdalo pa más tarde", "Ron92", "llego tarde", "hold"),
    ("N05", D, "escríbele a Ron92 que llego tarde y yo lo envío", "Ron92", "llego tarde", "hold"),
    ("N06", D, "escríbele a Ron92 que llego tarde y mándaselo mañana", "Ron92", "llego tarde", "hold"),
    ("N07", D, "escríbele a Ron92 que llego tarde y después se lo mandas", "Ron92", "llego tarde", "hold"),
    ("N08", D, "escríbele a Ron92 que nos vemos mañana y se lo mandas mañana", "Ron92", "nos vemos mañana", "hold"),
    ("N09", D, "escríbele a Ron92 que llego tarde pero no lo mandís todavía", "Ron92", "llego tarde", "hold"),
    ("N10", D, "escríbele a Ron92 que llego tarde, todavía no lo envíes", "Ron92", "llego tarde", "hold"),
    ("N11", D, "escríbele a Ron92 que llego tarde, espérate con mandarlo", "Ron92", "llego tarde", "hold"),
    ("N12", D, "escríbele a Ron92 que llego tarde pero no le pongas enviar", "Ron92", "llego tarde", "hold"),
    ("N13", D, "escríbele a Ron92 que llego tarde, lo dejai ahí no más", "Ron92", "llego tarde", "hold"),
    ("N14", D, "escríbele a Ron92 que llego tarde, ni se te ocurra mandarlo", "Ron92", "llego tarde", "hold"),
    ("N15", D, "mándale a Ron92 que llego tarde, ah no, espera, todavía no", "Ron92", "llego tarde", "hold"),
    ("N16", D, "escríbele a Ron92 que llego tarde pero se lo mandas en la noche", "Ron92", "llego tarde", "hold"),
    ("N17", D, "escríbele a Ron92 que llego en la noche y se lo mandas en la noche", "Ron92", "llego en la noche",
     "hold"),
    ("N18", D, "escríbele a Ron92 que llego tarde, yo se lo mando más tarde", "Ron92", "llego tarde", "hold"),
    ("N19", D, "escríbele a Ron92 que llego tarde pero guárdalo pa enviarlo más tarde", "Ron92", "llego tarde", "hold"),
    ("N20", D, "escríbele a Ron92 que llego tarde, después lo reviso y lo mando yo", "Ron92", "llego tarde", "hold"),
    ("N21", D, "déjalo listo pa mandarlo después: escríbele a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("N22", D, "escríbele a Ron92 que llego tarde pero no lo mandes hasta que te diga", "Ron92", "llego tarde", "hold"),
    ("N23", D, "escríbele a Ron92 que llego tarde, muéstramelo primero", "Ron92", "llego tarde", "hold"),
    ("E01", D, "text Ron92 that I'm late, hold it", "Ron92", "I'm late", "hold"),
    ("E02", D, "write to Ron92 that I'm late, don't send yet", "Ron92", "I'm late", "hold"),
    ("E03", D, "message Ron92 that I'm late and save it for later", "Ron92", "I'm late", "hold"),
    ("E04", D, "send Ron92 a message saying I'm late, but send it tomorrow", "Ron92", "I'm late", "hold"),
    ("E05", D, "send Ron92 a message saying we meet tomorrow, but only send it tomorrow", "Ron92", "we meet tomorrow",
     "hold"),
    ("E06", D, "write to Ron92 that I'm late, not yet though", "Ron92", "I'm late", "hold"),
    ("E07", D, "write to Ron92 that I'm late and wait for my ok to send it", "Ron92", "I'm late", "hold"),
    ("E08", D, "write Ron92 that I'm late, I'll review it first", "Ron92", "I'm late", "hold"),
    ("E09", D, "write Ron92 that I'm running late, hold it till I'm running late", "Ron92", "I'm running late", "hold"),
    ("E10", D, "write to Ron92 that I'm late, I'll send it later", "Ron92", "I'm late", "hold"),
    ("S01", D, "escríbele a Ron92 que llego tarde pero hold it", "Ron92", "llego tarde", "hold"),
    ("S02", D, "mándale a Ron92 que I'm late pero don't send yet", "Ron92", "I'm late", "hold"),
    ("S03", D, "escríbele a Ron92 que llego tarde, déjalo en drafts", "Ron92", "llego tarde", "hold"),
    ("S04", D, "escríbele a Ron92 que llego tarde y lo sendeo yo después", "Ron92", "llego tarde", "hold"),
    ("S05", D, "write to Ron92 que llego tarde, pero no lo mandes", "Ron92", "llego tarde", "hold"),
    ("S06", D, "escríbele y yo lo envío: a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("C01", D, "mándale a Ron92 que revise el informe antes de mandarlo", "Ron92", "revise el informe antes de mandarlo",
     "send"),
    ("C02", D, "mándale a Ron92: no mandes el informe todavía", "Ron92", "no mandes el informe todavía", "send"),
    ("C03", D, "escríbele a Ron92 que no envíes las fotos hasta mañana", "Ron92", "no envíes las fotos hasta mañana",
     "?"),
    ("C04", D, "mándale a Ron92 que déjalo escrito en la pizarra", "Ron92", "déjalo escrito en la pizarra", "send"),
    ("C05", D, "send Ron92 a message saying hold off on sending the files", "Ron92", "hold off on sending the files",
     "send"),
    ("C06", D, "mándale a Ron92 que el borrador está en la carpeta", "Ron92", "el borrador está en la carpeta", "send"),
    ("C07", D, "send Ron92 the draft", "Ron92", "the draft", "send"),
    ("C08", D, "envíale a Ron92 el borrador del informe", "Ron92", "el borrador del informe", "send"),
    ("C09", D, "mándale a Ron92 que no lo mande todavía", "Ron92", "no lo mande todavía", "send"),
    ("R01", D, "mándale a Juan Pablo que ya voy", "Juan Pablo", "ya voy", "send"),
    ("R02", D, "mándale a 🎮 Gamers que ya voy", "🎮 Gamers", "ya voy", "send"),
    ("R03", D, "mándale a la Coni que llego altiro", "Coni", "llego altiro", "send"),
    ("R04", D, "manda a Música que ya voy", "Música", "ya voy", "send"),
    ("R05", D, "escríbele a Ron92 y a Pedro que llego tarde", "Ron92 y a Pedro", "llego tarde", "send"),
    ("R06", D, "mándale a Ron92, Pedro y Ana que llego tarde", "Ron92, Pedro y Ana", "llego tarde", "send"),
    ("R07", D, "mándale a Ron92 y a Pedro que llego tarde", "Ron92", "llego tarde", "send"),
    ("R08", D, "mándale a Ron92 que «ya voy»", "Ron92", "ya voy", "send"),
    ("R09", D, "mándale a Ron92 que no voy a poder jugar hoy", "Ron92", "voy a poder jugar hoy", "send"),
    ("R10", D, "mándale a Mr. Smith que llego tarde", "Mr. Smith", "llego tarde", "send"),
    ("V01", ["te voy a dictar mensajes pa Ron92, no los mandís hasta que te diga", "abre discord"],
     "escríbele a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V02", ["guarda como borrador todo lo que te dicte, ¿ya?", "abre discord porfa"],
     "mándale a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V03", ["from now on don't send anything, just write it", "open discord"],
     "text Ron92 that I'm late", "Ron92", "I'm late", "hold"),
    ("V04", ["hold every message until I say so", "open discord"],
     "message Ron92 saying I'm late", "Ron92", "I'm late", "hold"),
    ("V05", ["no envíes nada sin que yo lo revise", "abre discord", "qué hora es"],
     "mándale a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V06", ["quiero revisar los mensajes antes de que salgan", "abre discord"],
     "mándale a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V07", ["prepárame unos mensajes pa Discord, que yo después los mando", "abre discord"],
     "mándale a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V08", ["escríbele a Ron92 que llego tarde pero no lo mandes", "abre discord"],
     "y a Pedro escríbele que yo también", "Pedro", "yo también", "hold"),
    ("V09", ["solo quiero borradores hoy, nada de enviar", "abre discord", "qué hora es"],
     "escríbele a Ron92 que llego tarde", "Ron92", "llego tarde", "hold"),
    ("V10", ["keep everything as drafts today", "open discord"],
     "write to Ron92 that I'm late", "Ron92", "I'm late", "hold"),
    ("V11", ["déjale escrito a Ron92 que llego tarde", "abre discord"],
     "ahora mándale a Pedro que ya voy", "Pedro", "ya voy", "send"),
    ("V12", ["no le mandes nada a Pedro todavía", "abre discord"],
     "escríbele a Pedro que llego tarde", "Pedro", "llego tarde", "hold"),
    # revisión B2 (revision_B2_datos/probe2.py): holds outside the first lexicon (H4) and words of the message (H5)
    ("X01", D, "escríbele a Ron92 que llego tarde, pero no lo despaches", "Ron92", "llego tarde", "hold"),
    ("X02", D, "escríbele a Ron92 que llego tarde, pero no apretís enter", "Ron92", "llego tarde", "hold"),
    ("X03", D, "write to Ron92 that I'm late, but don't hit enter", "Ron92", "I'm late", "hold"),
    ("X04", D, "write Ron92 that I'm late, I'll check it first", "Ron92", "I'm late", "hold"),
    ("X05", D, "escríbele a Ron92 que llego tarde, pero quiero verlo antes", "Ron92", "llego tarde", "hold"),
    ("X06", D, "write Ron92 that I'm late, let me see it first", "Ron92", "I'm late", "hold"),
    ("X07", D, "escríbele a Ron92 que llego tarde, yo lo apruebo", "Ron92", "llego tarde", "hold"),
    ("X08", D, "escríbele a Ron92 que llego tarde, no lo publiques", "Ron92", "llego tarde", "hold"),
    ("X09", D, "escríbele a Ron92 que llego tarde, que yo le doy al botón", "Ron92", "llego tarde", "hold"),
    ("X10", D, "escríbele a Ron92 que llego tarde (sin apretar enter)", "Ron92", "llego tarde", "hold"),
    ("X11", D, "escríbele a Ron92 que llego tarde pero no lo largues", "Ron92", "llego tarde", "hold"),
    ("X12", D, "write to Ron92 that I'm late, but don't post it", "Ron92", "I'm late", "hold"),
    ("X13", ["hoy nada sale sin mi visto bueno", "abre discord"], "escríbele a Ron92 que llego tarde", "Ron92",
     "llego tarde", "hold"),
    ("X14", ["only write, I'll press enter myself", "open discord"], "write to Ron92 that I'm late", "Ron92",
     "I'm late", "hold"),
    ("X15", ["a partir de ahora solo escribe, no publiques nada", "abre discord"], "escríbele a Ron92 que llego tarde",
     "Ron92", "llego tarde", "hold"),
    ("X16", ["el enter lo aprieto yo siempre", "abre discord"], "mándale a Ron92 que llego tarde", "Ron92",
     "llego tarde", "hold"),
    ("X17", D, "escríbele a Ron92 que llego tarde. Ojo, eso sí, no lo mandes", "Ron92", "llego tarde", "hold"),
    ("X18", D, "escríbele a Ron92 que llego tarde nomás, el resto lo veo yo", "Ron92", "llego tarde", "hold"),
    ("X19", D, "type Ron92 that I'm late but I'll hit send", "Ron92", "I'm late", "hold"),
    ("X20", D, "escríbele a Ron92 que llego tarde, después de comer se lo mando", "Ron92", "llego tarde", "hold"),
    ("X21", ["dictaré y tú solo tecleas", "abre discord"], "escríbele a Ron92 que llego tarde", "Ron92", "llego tarde",
     "hold"),
    ("X22", D, "escríbele a Ron92 que llego tarde, solo escríbelo", "Ron92", "llego tarde", "hold"),
    ("Y03", D, "mándale a Ron92 que llego tarde y abre spotify", "Ron92", "llego tarde", "?"),
    ("Y06", D, "mándale a Ron92 que llego tarde y pon música", "Ron92", "llego tarde", "?"),
    ("Y11", D, "mándale a Ron92 que llego tarde y a Pedro que ya voy", "Ron92", "llego tarde", "hold"),
    ("Y13", D, "mándale a Ron92 que no llego", "Ron92", "no llego", "send"),
    ("Y14", D, "mándale a Ron92 que: ya voy", "Ron92", "ya voy", "send"),
    ("Y15", D, "dile a Ron92 que ya voy", "Ron92", "ya voy", "send"),
    ("Y17", D, "mándale a Ron92 que ya voy, avísame si responde", "Ron92", "ya voy", "?"),
]


def _said(text: str) -> tuple[str, str, str | None] | None:
    return messaging.message_request_named_client(text) or messaging.message_request_any_channel(text)


def _drafts(row: tuple) -> list[str]:
    """The decider's draft without the tail, and with the person's whole words when the readers read them."""

    _, _, text, recipient, words, _ = row
    drafts = [f"Escríbele a {recipient} en Discord: «{words}»."]
    said = _said(text)
    if said is not None and said[1] != words:
        drafts.append(f"Escríbele a {recipient} en Discord: «{said[1]}».")
    return drafts


CASES = [(row, draft) for row in ROWS for draft in _drafts(row)]


@pytest.mark.parametrize(("row", "draft"), CASES, ids=[f"{row[0]}-{index}" for index, (row, _) in enumerate(CASES)])
def test_no_row_sends_without_the_yes(row: tuple, draft: str) -> None:
    case, before, text, _recipient, _words, expected = row
    conversation = Conversation(before)

    result, final = conversation.turn(text, _action(draft, "message.draft"))

    assert not _sends(result)
    offered = "¿Le envío a" in final or "Shall I send" in final
    if expected == "hold":
        # any doubt offers nothing, and a yes then sends nothing
        assert not offered, (case, final)
        after, _ = conversation.turn("sí", _action(draft, "message.draft"))
        assert not _sends(after)
    if offered:
        # what is offered is the person's own words, to the one recipient the readers read in them
        said = _said(text)
        assert final.endswith(f"¿Le envío a {said[0]} «{said[1]}»?") or final.endswith(
            f"Shall I send {said[0]} “{said[1]}”?"
        ), final


@pytest.mark.parametrize(
    "case",
    ["H1-03", "H1-07", "H1-11", "H1-13", "N10", "E10"],
)
def test_a_first_message_kept_written_after_a_comma_is_never_sent(case: str) -> None:
    # revisión B H4: the readers read the send in the first clause; the whole message keeps it written.
    row = next(row for row in ROWS if row[0] == case)
    draft = f"Escríbele a {row[3]} en Discord: «{row[4]}»."
    held = _action(draft.replace("Escríbele", "Manda", 1), "message.recipient.resolve", "message.send")

    result, _ = Conversation([]).turn(row[2], held)

    assert result["effectOperations"] == ["message.draft"]


TARGET = "mandale a Ron92 que si se conecta a las 9 pa jugar"
RESTATED = "Escríbele a Ron92 en Discord: «¿Te conectas a las 9 para jugar?»"


def test_the_draft_offers_the_send_and_the_yes_sends_the_persons_words() -> None:
    conversation = Conversation(D)

    drafted, final = conversation.turn(TARGET, _action(RESTATED, "message.draft"))
    sent, _ = conversation.turn("sí", None)

    assert drafted["effectOperations"] == ["message.draft"]
    assert final.endswith("¿Le envío a Ron92 «si se conecta a las 9 pa jugar»?")
    assert sent["effectOperations"] == ["message.recipient.resolve", "message.send"]
    objective = sent["objective"]
    assert _explicit_arguments_from_evidence("message.recipient.resolve", objective) == {
        "channel": "discord", "recipient": "Ron92",
    }
    assert messaging.message_body(objective) == "si se conecta a las 9 pa jugar"


@pytest.mark.parametrize("answer", ["sí", "dale, mándalo", "ok", "yes, send it"])
def test_each_yes_sends(answer: str) -> None:
    conversation = Conversation(D)
    conversation.turn(TARGET, _action(RESTATED, "message.draft"))

    sent, _ = conversation.turn(answer, None)

    assert sent["effectOperations"] == ["message.recipient.resolve", "message.send"]


NOT_A_YES = [
    "no", "no, déjalo así", "mejor no", "sí pero mañana", "qué hora es",
    # revisión B2 H1: a question, a doubt or a bare word that may not be a yes
    "¿sí?", "sí?", "¿ya?", "¿claro?", "yes?", "sure?", "dale?", "ok?", "please?", "¿mándalo?", "envialo?",
    "bueno...", "claro...", "ok...", "sí…", "ya", "please", "por favor", "bueno", "vale",
    "sí pero cambiale el texto", "sí, aunque mejor no", "sí, mándaselo a Pedro", "no sé, sí", "ya po", "👍",
]


@pytest.mark.parametrize("answer", NOT_A_YES)
def test_anything_but_the_yes_sends_nothing(answer: str) -> None:
    conversation = Conversation(D)
    conversation.turn(TARGET, _action(RESTATED, "message.draft"))

    after, _ = conversation.turn(answer, TALK)

    assert not _sends(after)


def test_the_offer_stands_for_one_turn() -> None:
    conversation = Conversation(D)
    conversation.turn(TARGET, _action(RESTATED, "message.draft"))
    conversation.turn("qué hora es", TALK)

    after, _ = conversation.turn("sí", TALK)

    assert not _sends(after)


def test_english_offer_and_yes() -> None:
    conversation = Conversation(["open discord"])

    _, final = conversation.turn("send Ron92 a message saying I'm on my way",
                                 _action("Write to Ron92 on Discord: «I'm on my way».", "message.draft"))
    sent, _ = conversation.turn("yes", None)

    assert final.endswith("Shall I send Ron92 “I'm on my way”?") or final.endswith("¿Le envío a Ron92 «I'm on my way»?")
    assert sent["effectOperations"] == ["message.recipient.resolve", "message.send"]
    assert messaging.message_body(sent["objective"]) == "I'm on my way"


def test_a_draft_to_someone_else_offers_nothing() -> None:
    # the verified draft went to another recipient than the one the person's words name
    conversation = Conversation(D)

    _, final = conversation.turn(TARGET, _action("Escríbele a Pedro en Discord: «si se conecta».", "message.draft"))

    assert final == "Te lo dejé escrito a Pedro en Discord, sin enviar."


def test_a_final_with_no_words_offers_nothing() -> None:
    state = DialogueState()
    state.expect("Escríbele a Ron92 en Discord: «hola».", ["message.draft"])
    state.offer_send(("Ron92", "hola", None))
    state.record({"operation": "message.draft", "verified": True, "succeeded": True,
                  "observed": {"channel": "discord", "displayName": "Ron92", "text": "hola"}})

    assert send_offer._with_send_offer("", state, _readers_send) == ""
    state.begin_turn()
    assert state.accepted_send("sí", [{"role": "assistant", "content": ""}, {"role": "user", "content": "sí"}]) is None


@pytest.mark.parametrize(
    "text",
    [
        # revisión B H5: a verb of sending with the draft as its object, and a message that says these words, send
        "mándale a Ron92 el borrador que dejaste",
        "send Ron92 the draft",
        "envíale a Ron92 el borrador del informe",
        "mándale a Ron92 que revise el informe antes de mandarlo",
        "mándale a Ron92: no mandes el informe todavía",
        "mándale a Ron92 que déjalo escrito en la pizarra",
        "send Ron92 a message saying hold off on sending the files",
        "escríbele a Ana por whatsapp que el borrador ya está listo",
        "dile a Ana por whatsapp que yo lo mando mañana",
    ],
)
def test_words_of_the_message_are_not_an_order_to_keep_it(text: str) -> None:
    assert not messaging.asks_not_to_send(text)


@pytest.mark.parametrize("answer", NOT_A_YES)
def test_one_reading_of_the_yes_for_every_offer(answer: str) -> None:
    # revisión B2 H1: the yes to the offer to send and to the offer to cancel the alarms (D39) is read by one reader.
    assert not accepts_offer(answer, "send")
    assert not accepts_offer(answer, "alarms")


@pytest.mark.parametrize(("answer", "act"), [
    ("sí", "send"), ("Sí.", "send"), ("dale, mándalo", "send"), ("sí, por favor", "send"), ("yes please", "send"),
    ("yes, send it", "send"), ("sí, cancélalas todas", "alarms"), ("yes, all of them", "alarms"), ("dale", "alarms"),
])
def test_an_unequivocal_yes_accepts(answer: str, act: str) -> None:
    assert accepts_offer(answer, act)


OFFERING = [(row, draft) for row, draft in CASES if row[5] != "hold"]


@pytest.mark.parametrize(
    ("row", "draft"), OFFERING, ids=[f"{row[0]}-{index}" for index, (row, _) in enumerate(OFFERING)],
)
def test_the_yes_to_every_offer_is_sent_by_the_readers_alone(row: tuple, draft: str) -> None:
    # revisión B2 H2: the yes never asks the decider; it sends the recipient and the words offered.
    conversation = Conversation(row[1])
    _, final = conversation.turn(row[2], _action(draft, "message.draft"))
    if "¿Le envío a" not in final and "Shall I send" not in final:
        return

    sent, _ = conversation.turn("sí", _action(draft, "message.draft"))

    said = _said(row[2])
    assert conversation.model.decisions == 0
    assert sent["effectOperations"] == ["message.recipient.resolve", "message.send"]
    assert messaging.message_body(sent["objective"]) == said[1]
    assert _explicit_arguments_from_evidence("message.recipient.resolve", sent["objective"])["recipient"] == said[0]


def test_a_yes_the_readers_cannot_send_alone_sends_nothing_and_says_so() -> None:
    # revisión B2 H2 (X01 «…, pero no lo despaches» read whole by the readers of the yes): never the decider's.
    state = DialogueState()
    state.expect("Escríbele a Ron92 en Discord: «llego tarde».", ["message.draft"])
    state.offer_send(("Ron92", "llego tarde, pero no lo despaches", None))
    state.record({"operation": "message.draft", "verified": True, "succeeded": True,
                  "observed": {"channel": "discord", "displayName": "Ron92", "text": "llego tarde"}})
    final = send_offer._with_send_offer("Te lo dejé escrito.", state, lambda _request: True)
    state.begin_turn()
    model = _Decider()
    history = [{"role": "user", "content": "escríbele a Ron92 que llego tarde, pero no lo despaches"},
               {"role": "assistant", "content": final}, {"role": "user", "content": "sí"}]

    result = turn_decide._prepare_turn_result(
        {"id": "b2", "text": "sí", "history": history}, llm=model, planner_catalog=CATALOG, encoder=lambda _t: (),
        tool_by_name=TOOLS, dialogue_state=state,
    )

    assert final.endswith("«llego tarde, pero no lo despaches»?")
    assert model.decisions == 0
    assert not _sends(result)
    assert result["kind"] == "conversation" and result["reply"].startswith("No lo envié")


def _offered_conversation() -> Conversation:
    conversation = Conversation(D)
    _, final = conversation.turn(TARGET, _action(RESTATED, "message.draft"))
    assert final.endswith("?")
    return conversation


def test_a_failed_turn_after_the_offer_leaves_it_behind() -> None:
    # revisión B2 H3: a turn.decide that fails (no expect, a recovery question) still starts a turn; a yes after it
    # answers that question, never the offer.
    conversation = _offered_conversation()
    conversation.state.begin_turn()
    conversation.history += [{"role": "user", "content": "eh?"}, {"role": "assistant", "content": "¿Me lo repites?"}]

    after, _ = conversation.turn("sí", TALK)

    assert not _sends(after)


def test_a_final_the_shell_replaced_offers_nothing() -> None:
    # revisión B2 H3: the shell published another final than the one with the offer; the yes is to what it saw.
    conversation = _offered_conversation()
    conversation.history[-1] = {"role": "assistant", "content": "Te lo dejé escrito a Ron92 en Discord."}

    after, _ = conversation.turn("sí", TALK)

    assert not _sends(after)
    assert conversation.model.decisions == 1


def test_a_final_that_already_asks_offers_nothing() -> None:
    # revisión B2 H3: «¿Quieres que le cambie algo?» and the offer after it: a yes would not say to which.
    state = DialogueState()
    state.expect("Escríbele a Ron92 en Discord: «llego tarde».", ["message.draft"])
    state.offer_send(("Ron92", "llego tarde", None))
    state.record({"operation": "message.draft", "verified": True, "succeeded": True,
                  "observed": {"channel": "discord", "displayName": "Ron92", "text": "llego tarde"}})

    final = send_offer._with_send_offer("Te lo dejé escrito. ¿Quieres que le cambie algo?", state, _readers_send)
    state.begin_turn()

    assert final == "Te lo dejé escrito. ¿Quieres que le cambie algo?"
    assert state.accepted_send("sí", [{"role": "assistant", "content": final}, {"role": "user", "content": "sí"}]) is None
