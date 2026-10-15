"""Auditoría de uso real v3 del 2026-10-08 (estab/uso-real.md, hallazgos 3, 4 y 10), gemelos de las tandas reales.

- t1-c02-2 «no, el brillo te dije, no el volumen. bajalo mas», t2-c04-4 «te dije la escala no el brillo, regresa la
  escala a 100»: the contrast was read only at the end of the message (None); it is a run of the message's clauses and
  what follows it is the order about X. t3-c19-2 «que no, el lápiz, no el pincel»: «que no,» opens a denial.
- t4-c04-2 «joder que te he dicho brillo no volumen»: an oath and «que» before «te he dicho» reproach the last result.
- t4-c02-2 «me tiraste una lista enorme» after three quoted titles → «Lo siento, te di más de lo que pediste»: the inline
  quoted list is counted, and a reply that agrees to a false «more» or «fewer» contradicts the last answer.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import visible_defect
from baxy_mind import previous_answer
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, dialogue, listing
from baxy_mind import context_decision


# ------------------------------------------------------------------ 1. the contrast is a clause, an order may follow


@pytest.mark.parametrize(
    ("text", "wanted", "refused", "rest"),
    [
        ("no, el brillo te dije, no el volumen. bajalo mas", "brillo", "volumen", "bajalo mas"),  # t1-c02-2
        ("te dije la escala no el brillo, regresa la escala a 100", "escala", "brillo", "regresa la escala a 100"),
        ("que no, el lápiz, no el pincel", "lapiz", "pincel", ""),  # t3-c19-2
        ("el lápiz, no el pincel", "lapiz", "pincel", ""),  # the whole message is «X, no Y»
        ("I said the brightness, not the volume. turn it down more", "brightness", "volume", "turn it down more"),
        ("te dije el brightness, not el volume, bajalo", "brightness", "volume", "bajalo"),  # spanglish
        ("no po, en spotify te dije, no en youtube", "spotify", "youtube", ""),  # t4-c01-4 stays
        ("joder que te he dicho brillo no volumen", "brillo", "volumen", ""),  # t4-c04-2 stays
    ],
)
def test_the_contrast_is_read_in_any_clause(text: str, wanted: str, refused: str, rest: str) -> None:
    contrast = dialogue.contrastive_correction(text)
    assert contrast is not None and (contrast.wanted, contrast.refused, contrast.rest) == (wanted, refused, rest)


@pytest.mark.parametrize(
    "text",
    [
        "spotify no anda, ponlo en youtube",  # a sentence, then an order: no contrast
        "pon cumbia y no reggaeton mañana, gracias",
        "que no se te olvide",
        "no, a las 7, no a las 6",  # an hour: the hour reader's
        "no, a las 6.30, no a las 6.15",  # a decimal point is no pause
        "no cierres chrome, por favor",  # a prohibition
        "abre spotify, no tengo tiempo",
    ],
)
def test_counter_cases_of_the_contrast_in_a_clause(text: str) -> None:
    assert dialogue.contrastive_correction(text) is None


@pytest.mark.parametrize(
    ("last", "text", "corrected"),
    [
        # The order after the contrast takes X for its pronoun, or is itself when it names X.
        ("che baja el brillo que me esta quemando los ojos", "no, el brillo te dije, no el volumen. bajalo mas",
         "baja el brillo mas"),
        ("ahi ponle la escala en 125", "te dije la escala no el brillo, regresa la escala a 100",
         "regresa la escala a 100"),
        # Without an order after it, the last request with Y made X, or itself when it named X.
        ("abre el paint y elige el lápiz", "que no, el lápiz, no el pincel", "abre el paint y elige el lápiz"),
        ("pon el volumen al 40", "joder que te he dicho brillo no volumen", "pon el brillo al 40"),
    ],
)
def test_the_order_after_the_contrast_is_the_corrected_request(last: str, text: str, corrected: str) -> None:
    assert dialogue.corrected_request(last, text) == corrected


@pytest.mark.parametrize(
    "text",
    [
        "joder que te he dicho brillo no volumen",  # t4-c04-2
        "que no, el lápiz, no el pincel",  # t3-c19-2
        "pero te he dicho que en spotify",
    ],
)
def test_the_reproach_corrects_the_last_result(text: str) -> None:
    assert dialogue.corrects_or_insists(text)


@pytest.mark.parametrize("text", ["¿qué te dije ayer?", "que no se te olvide comprar pan", "y ahora sube el volumen"])
def test_a_question_or_a_new_request_is_no_reproach(text: str) -> None:
    assert not dialogue.corrects_or_insists(text)


OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.status", "media.play.query", "media.play.youtube", "media.status",
    "system.settings.set", "display.status", "web.search", "app.open", "app.close", "note.create", "note.delete",
)


class _Decider:
    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que haga?"


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


def _decided(turns: list[tuple[str, str]], text: str, model: _Decider) -> dict[str, object]:
    history = [{"role": role, "content": content} for role, content in turns] + [{"role": "user", "content": text}]
    return context_decision._context_decided_result(
        {"id": "estab", "text": text, "history": history},
        llm=model,
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
    )


LAST_BRIGHTNESS = [("user", "che baja el brillo que me esta quemando los ojos"), ("assistant", "¿A qué nivel lo bajo?")]


def test_t1_c02_2_a_decider_choice_of_the_volume_is_replaced_by_the_brightness() -> None:
    result = _decided(
        LAST_BRIGHTNESS,
        "no, el brillo te dije, no el volumen. bajalo a 20",
        _Decider("Baja el volumen a 20.", "action", ("audio.volume",)),
    )
    assert result["intentOperations"] == ["system.settings.set"]
    assert result["objective"] == "baja el brillo a 20"


def test_t1_c02_2_the_refused_volume_is_never_done_when_the_amount_is_missing() -> None:
    # «bajalo mas» has no amount (the owner's rule: a relative change without it is asked); the volume is not lowered.
    result = _decided(
        LAST_BRIGHTNESS,
        "no, el brillo te dije, no el volumen. bajalo mas",
        _Decider("Baja el volumen.", "action", ("audio.volume.adjust",)),
    )
    assert result["kind"] == "clarify"
    assert result["objective"] == "baja el brillo mas"
    assert not any(str(op).startswith("audio.") for op in result.get("intentOperations") or [])


def test_t2_c04_4_the_order_after_the_contrast_stays_when_the_decider_follows_it() -> None:
    result = _decided(
        [("user", "ahi ponle la escala en 125"), ("assistant", "No pude hacerlo.")],
        "te dije la escala no el brillo, regresa la escala a 100",
        _Decider("Pon la escala de la pantalla en 100.", "action", ("system.settings.set",)),
    )
    assert result["objective"] == "Pon la escala de la pantalla en 100."
    assert result["intentOperations"] == ["system.settings.set"]


def test_t2_c04_4_a_decider_choice_of_the_brightness_is_never_done() -> None:
    result = _decided(
        [("user", "ahi ponle la escala en 125"), ("assistant", "No pude hacerlo.")],
        "te dije la escala no el brillo, regresa la escala a 100",
        _Decider("Pon el brillo en 100.", "action", ("system.settings.set",)),
    )
    assert "brillo" not in str(result["objective"]).lower()
    assert "escala" in str(result["objective"]).lower()


# ------------------------------------------------------------------ review 2026-10-08 r2: counter-cases and twins


@pytest.mark.parametrize(
    "text",
    [
        "abre chrome, no firefox",  # X said with its own verb: a whole new request
        "sube el volumen, no el brillo",
        "borra la nota, no el recordatorio",
        "no, abre chrome te dije, no firefox",
        "el martes, no el lunes, recuerdamelo",  # an order is no X
        "perfecto, no gracias",  # courtesies
        "bueno, no importa",
        "tranqui, no problem",
        "sure, not a problem",
        "te había dicho que hoy no trabajo",  # «que» opens a clause of its own
    ],
)
def test_a_whole_order_or_a_courtesy_is_no_contrast(text: str) -> None:
    assert dialogue.contrastive_correction(text) is None


@pytest.mark.parametrize(
    ("text", "rest"),
    [
        ("no, la alarma te dije, no el recordatorio. ponla a las 10:30", "ponla a las 10:30"),
        ("no, netflix te dije, no youtube. abre netflix.com", "abre netflix.com"),
        ("no, el brillo te dije, no el volumen: ponlo al 37.5", "ponlo al 37.5"),
    ],
)
def test_an_hour_an_amount_or_an_address_after_the_contrast_stay_whole(text: str, rest: str) -> None:
    contrast = dialogue.contrastive_correction(text)
    assert contrast is not None and contrast.rest == rest


@pytest.mark.parametrize(
    ("last", "text", "corrected"),
    [
        ("pon el volumen al 40", "no, el brillo te dije, no el volumen. ponlo al 50", "pon el brillo al 50"),
        ("pon una alarma a las 7", "no, la alarma te dije, no el recordatorio. ponla a las 10:30",
         "pon la alarma a las 10:30"),
        # A second order joined by «y» follows the corrected last request.
        ("pon cumbia en youtube", "no, en spotify te dije, no en youtube. y sube el volumen",
         "pon cumbia en spotify y sube el volumen"),
        # What only closes it is no order.
        ("pon cumbia en youtube", "no, en spotify, no en youtube. gracias", "pon cumbia en spotify"),
        # An order that cannot be joined is never dropped for the last request.
        ("pon cumbia en youtube", "no, en spotify, no en youtube. subelo", None),
        ("cierra firefox", "abre chrome, no firefox", None),
        ("baja el brillo a 30", "sube el volumen, no el brillo", None),
        ("recuerdame el lunes comprar pan", "el martes, no el lunes, recuerdamelo", None),
    ],
)
def test_the_order_after_the_contrast_is_never_lost(last: str, text: str, corrected: str | None) -> None:
    assert dialogue.corrected_request(last, text) == corrected


@pytest.mark.parametrize(
    ("last", "text", "restated", "operations"),
    [
        ("cierra firefox", "abre chrome, no firefox", "Abre Chrome, no Firefox.", ("app.open",)),
        ("baja el brillo a 30", "sube el volumen, no el brillo", "Sube el volumen, no el brillo.", ("audio.volume.adjust",)),
        ("crea una nota que diga comprar pan", "borra la nota, no el recordatorio", "Borra la nota, no el recordatorio.",
         ("note.delete",)),
    ],
)
def test_a_whole_order_with_a_refusal_keeps_the_decider_choice(
    last: str, text: str, restated: str, operations: tuple[str, ...],
) -> None:
    result = _decided([("user", last), ("assistant", "Listo.")], text, _Decider(restated, "action", operations))
    assert result["objective"] == restated
    assert result["intentOperations"] == list(operations)


def test_the_value_after_the_contrast_is_done_on_x() -> None:
    result = _decided(
        [("user", "pon el volumen al 40"), ("assistant", "Listo, volumen al 40.")],
        "no, el brillo te dije, no el volumen. ponlo al 50",
        _Decider("Pon el volumen al 50.", "action", ("audio.volume",)),
    )
    assert result["objective"] == "pon el brillo al 50"
    assert result["intentOperations"] == ["system.settings.set"]


def test_the_second_order_after_the_contrast_stays() -> None:
    history = [("user", "pon cumbia en youtube"), ("assistant", "Listo.")]
    result = _decided(
        history,
        "no, en spotify te dije, no en youtube. y sube el volumen al 80",
        _Decider("Pon cumbia en YouTube y sube el volumen al 80.", "action", ("media.play.youtube", "audio.volume")),
    )
    assert result["objective"] == "pon cumbia en spotify y sube el volumen al 80"
    assert result["intentOperations"] == ["media.play.query", "audio.volume"]
    # Without its amount the volume is asked (owner's rule), and YouTube is never played.
    result = _decided(
        history,
        "no, en spotify te dije, no en youtube. y sube el volumen",
        _Decider("Pon cumbia en YouTube y sube el volumen.", "action", ("media.play.youtube", "audio.volume.adjust")),
    )
    assert result["kind"] == "clarify"
    assert result["objective"] == "pon cumbia en spotify y sube el volumen"


def test_the_contrast_is_read_in_linear_time() -> None:
    import time

    text = ", ".join(["pon la musica en la sala"] * 120)
    started = time.perf_counter()
    assert dialogue.contrastive_correction(text) is None
    assert time.perf_counter() - started < 0.5  # 3.16 s before the review


@pytest.mark.parametrize("text", ["te he dicho que me gusta el rock", "te había dicho que hoy no trabajo"])
def test_a_fact_told_before_is_no_reproach(text: str) -> None:
    assert not dialogue.corrects_or_insists(text)


# ------------------------------------------------------------------ 2. a false reproach about the count given

THREE_TITLES = 'Te recomiendo "El Aleph", "La supermanera" y "El fin de los tiempos" para empezar con Cortázar.'
ASKED_THREE = "dame 3 libros de cortazar para arrancar"
REPROACH = "no, te pedi 3 nomas y me tiraste una lista enorme"


def test_t4_c02_1_an_inline_list_of_quoted_titles_is_counted() -> None:
    assert listing.items_listed(THREE_TITLES) == 3
    assert listing.items_listed("“A”, “B” or “C”") == 3
    # Counter-cases: quoted words apart in a sentence, one quoted title, a list without quotes.
    assert listing.items_listed('Dijo "hola" y luego se fue a "casa".') is None
    assert listing.items_listed("Pon «Despacito» en Spotify.") is None
    assert listing.items_listed("Bolivia, Paraguay, Perú y Ecuador.") is None


@pytest.mark.parametrize(
    ("reply", "relation"),
    [
        ("Lo siento, te di más de lo que pediste.", "more"),
        ("Te di menos de lo que me pediste.", "fewer"),
        ("I gave you fewer than you asked for.", "fewer"),
        ("Hay más de lo que pediste en la tienda.", None),
        ("Te di la receta.", None),
        ("Perdón, te pasé más opciones de las que pediste.", "more"),
        # A denial says the reply did not give more or fewer (review 2026-10-08 r2).
        ("No te di más de lo que pediste: son las tres que pediste.", None),
        ("No, no te di más de lo que pediste.", None),
    ],
)
def test_a_reply_that_says_it_gave_more_or_fewer_is_read(reply: str, relation: str | None) -> None:
    assert listing.stated_given_relation(reply) == relation


def _facts(context: str) -> dict:
    return {
        "context": context,
        "priorRequests": [ASKED_THREE],
        "situation": json.dumps({"kind": "conversation", "polarity": "success"}),
    }


def test_t4_c02_2_agreeing_to_a_false_more_is_refused() -> None:
    reply = "Lo siento, te di más de lo que pediste. Aquí tienes los tres: El Aleph, La supermanera y El fin de los tiempos."
    assert visible_defect.compose_visible_defect(
        reply, "conversation", REPROACH, _facts(THREE_TITLES), said=REPROACH,
    ) == "contradicts_previous_answer"


def test_a_true_more_and_the_true_count_pass() -> None:
    five = '"A", "B", "C", "D" y "E"'
    assert not previous_answer._contradicts_previous_count("Te di más de lo que pediste.", _facts(five))
    assert not previous_answer._contradicts_previous_count("Te di 3: El Aleph, La supermanera y El fin de los tiempos.", _facts(THREE_TITLES))
    assert not previous_answer._contradicts_previous_count(
        "No te di más de lo que pediste: son las tres que pediste.", _facts(THREE_TITLES),
    )


@pytest.mark.parametrize(
    "answer",
    ['¿Quieres abrir "Spotify" o "Steam"?', "Abrí «Notas» y «Calculadora».", 'La nota dice "comprar pan" y "leche".'],
)
def test_two_quoted_names_are_no_list(answer: str) -> None:
    assert listing.items_listed(answer) is None
