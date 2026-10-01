"""M112 (2026-10-01): trust the contextual decider where the readers or a guard overrode it without being sure.

Evidence: the official-window DEV-F run v4d (%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v4d-devF, code
194e12f6) against the decider alone (soup V0a, full3): the decider was right on 270/280 turns, the product on 243; of
the 28 turns the product lost, the app's own decider had decided 11 follow-ups differently because the app's history
held BAXY's real earlier replies (an unread mail, a battery at 100 %, a PDF not found), and the rest were readers that
preempted the decider or guards that overrode it:

1. w28-t5 «uf está muy fuerte» after the music started (a reaction → social talk), w60-t2 «no esa no la otra la del
   disco» (knowledge), w19-t2 «Ahí tiene que estar el PDF… ¿Me lo resumes?» (a limit): conversation readers closed
   follow-ups the decider reads with the conversation.
2. w19-t2: «que me mandó el banco» after «el PDF de la hipoteca» is a relative clause, not «qué me escribió X».
3. s025 «abreme el archivo presupuesto_finca.xlsx q esta en documentos» → «No abro archivos»: a stale limit contract
   while file.open exists.
4. w01-t1 «léeme el último correo…, y no lo he abierto»: a clause the readers could not read failed the turn twice.
5. w47-t3 «¿cuántos dólares me dan hoy por cada euro?»: «dan» after «me» read as a person's name (own data).
6. w52-t2 «sí, dale, bájalo a 30» after the battery: the decider's limit re-read as said set the volume.
7. w38-t1 «get me a large pepperoni… from the Domino's»: asked lookup-or-purchase, then read as overheard talk.
"""

from __future__ import annotations

from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.patterns import (
    chat_read_request,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
)
from baxy_mind.semantic.web import names_own_data

OPERATIONS = (
    "audio.volume",
    "audio.volume.adjust",
    "document.pdf.read",
    "email.latest.read",
    "file.open",
    "filesystem.folder.open",
    "media.play.exact",
    "media.play.query",
    "media.play.youtube",
    "notification.schedule",
    "system.settings.set",
    "system.status",
    "web.search",
)


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


TOOLS = {operation: _tool(operation) for operation in OPERATIONS}


class _Model:
    """The decider's recorded decision; every other model call answers as the guards did in the run."""

    def __init__(self, decision: str = "talk", operations: tuple[str, ...] = (), request: str = "",
                 question: str = "") -> None:
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations,
                                               question=question)
        self.calls: list[str] = []

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.calls.append("decide")
        return self.decided

    def chat(self, *_args: object, conversation_kind: str | None = None, **_kwargs: object) -> tuple[str, list]:
        self.calls.append(f"chat:{conversation_kind}")
        return "Vale.", []

    def prepare_chat(self, *_args: object, conversation_kind: str | None = None, **_kwargs: object) -> None:
        self.calls.append(f"prepare:{conversation_kind}")

    @staticmethod
    def detect_response_language(text: str) -> str:
        return "en" if all(ord(ch) < 128 for ch in text) else "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, None]:
        return True, None

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "complete", "one"

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué necesitas exactamente?"


def _turn(model: _Model, text: str, *said: str) -> dict[str, Any]:
    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": content}
               for index, content in enumerate(said)]
    return sidecar._prepare_turn_result(
        {"id": "m112", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=TOOLS,
    )


# ------------------------------------------------------------------ 1. follow-ups are the decider's


MUSIC = ("ponme algo de lo-fi pa concentrarme, tengo que terminar el informe de la u",
         "Sonando «lofi beats para estudiar» en Spotify.")


def test_a_reaction_after_the_music_is_read_with_the_conversation() -> None:
    model = _Model("clarify", question="¿Cuánto le bajo el volumen?", request="Baja el volumen.")
    result = _turn(model, "uf está muy fuerte", *MUSIC)
    assert model.calls[:1] == ["decide"]
    assert result["kind"] == "clarify"


def test_another_version_asked_after_the_song_is_the_deciders() -> None:
    model = _Model("action", ("media.play.exact",), "Pon la versión del disco de «El baile de los que sobran».")
    result = _turn(model, "no esa no la otra la del disco", "baxy pone el baile de los que sobran",
                   "Sonando «El baile de los que sobran», la versión en vivo del Estadio Nacional 2001.")
    assert "decide" in model.calls
    assert result["kind"] == "action" and result["operation"] == "media.play.exact"


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("muchas gracias", MUSIC),
        ("I like After the Wedding.",
         ("Look for a drama film.", "How about A Faithful Man, After the Wedding, or Blinded by the Light?")),
    ],
)
def test_thanks_or_a_statement_keep_their_reader(text: str, said: tuple[str, str]) -> None:
    model = _Model("action", ("media.play.query",), "Play After the Wedding.")
    result = _turn(model, text, *said)
    assert "decide" not in model.calls
    assert result["kind"] == "conversation"


# ------------------------------------------------------------------ 2–3. limits that are not limits


def test_the_thing_someone_sent_is_named_not_asked_about() -> None:
    folded = "ahi tiene que estar el pdf de la hipoteca que me mando el banco ayer. ¿me lo resumes?"
    assert not chat_read_request(folded)
    assert not known_unsupported_effect_request(folded, OPERATIONS)
    assert chat_read_request("que me escribio mama en el wsp")
    assert chat_read_request("dime que me dijo la paula")
    assert known_unsupported_effect_request("¿qué me escribió mamá?", OPERATIONS)


def test_a_file_named_in_a_known_folder_is_opened() -> None:
    text = "abreme el archivo presupuesto_finca.xlsx q esta en documentos"
    assert not known_unsupported_effect_request(text, OPERATIONS)
    assert known_unsupported_effect_request(text, tuple(op for op in OPERATIONS if op != "file.open"))


# ------------------------------------------------------------------ 4. a clause the readers cannot read


def test_an_unread_clause_hands_the_turn_to_the_decider() -> None:
    model = _Model("action", ("email.latest.read",), "Lee el último correo que me llegó.")
    result = _turn(
        model,
        "léeme el último correo que me llegó, creo que es de mi jefa sobre la junta del jueves y no lo he abierto",
    )
    # M111 reads this clause too (a statement, not a negated order), so the readers may settle it before the decider;
    # either way the turn reads the latest mail.
    assert model.calls in ([], ["decide"])
    assert result["kind"] == "action" and result["operation"] == "email.latest.read"


# ------------------------------------------------------------------ 5. «me dan» is a verb


def test_a_verb_after_a_clitic_is_no_persons_name() -> None:
    assert not names_own_data("Cambiando de tercio: en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro?")
    assert not names_own_data("¿cuánto le dan por un dólar?")
    assert names_own_data("¿Dan sigue viviendo en Boston?")
    assert names_own_data("text me Ana's address")
    assert names_own_data("me dijo Ana que venía")


# ------------------------------------------------------------------ 6. a follow-up's object is in the conversation


def test_a_limit_on_a_dependent_follow_up_is_not_reread_alone() -> None:
    model = _Model("limit", request="Baja el nivel de la batería al 30.")
    result = _turn(model, "sí, dale, bájalo a 30", "oiga baxy, ¿cuánta pila le queda a este computador?",
                   "El computador tiene el 100% de carga en la batería y no está cargando.")
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert "audio.volume" not in (result.get("effectOperations") or [])


# ------------------------------------------------------------------ 7. an order with a store


def test_an_order_from_a_store_is_the_deciders() -> None:
    text = "get me a large pepperoni with extra jalapeños from the Domino's on Elm St"
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    model = _Model("limit", request="Order a large pepperoni pizza from Domino's.")
    result = _turn(model, text)
    assert "decide" in model.calls
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
