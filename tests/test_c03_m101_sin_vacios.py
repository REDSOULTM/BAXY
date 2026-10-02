"""M101 (2026-10-01): an empty visible final is impossible.

DEV-D run v3z (code 38d03aa2) still ended four turns with terminal composition_failed and reply "": D-s037 and D-s042
(a decided limit), D-p31-t2 (talk whose wording failed) and D-w10-t4 (YouTube opened, playback unverified). In each
the App composed the final through the mind's message.compose, every draft was vetoed, the mind's last resort had
nothing to say and the App's queue exhausted with «no_response;retry_exhausted». The evidence of the four turns is in
tests/data/c03_m101_evidence.json. Every phrasing below is our own, of the same shape as the rows it stands for.

1. Vetoes that refused acceptable drafts: «tomar una foto» is not the person drinking (limit_persons_act); a limit that
   named the thing asked and then denied it again keeps what it named; «no logré interpretar…» says the failure (twin
   of the App); a YouTube page that opened is the cause fact of an unconfirmed playback, not a reversed result.
2. The floor: a limit says «Eso no lo hago» with the thing asked as the person said it; an unconfirmed YouTube
   playback is reported naming its target; talk whose recovered reply tells a failure asks back instead of reaching
   the App's turn failure, which keeps no fixed final (owner's review of M75, test_c03_m75 D-w02-t2).
3. Owner script v3z2 t45 «silencia mi microfono» (already muted, ⚠ no_response;retry_exhausted): «estaba ya» and «no
   hubo ningún cambio» tell the state that held; when every draft dies, the state read is told from the facts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic.conversation import asked_act_clause, wants_to_consume

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m101_evidence.json").read_text(encoding="utf-8"))

LIMIT = json.dumps({"kind": "failure", "polarity": "failure", "cause": "out_of_catalog"})
TURN_FAILURE = json.dumps({"kind": "failure", "polarity": "failure", "cause": "turn_runtime_failure",
                           "operationAttempted": False, "retryable": True})


def _youtube_unverified(target: str) -> str:
    reason = {"kind": "operation", "operation": "media.play.youtube", "polarity": "failure", "verified": False,
              "succeeded": False, "error": "youtube_playback_not_verified_watch_ready0_playing_network2_source_none",
              "cause": "external_effect_ambiguous", "effectUncertain": True, "target": target}
    return json.dumps({"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0,
                       "steps": [], "reason": reason}, ensure_ascii=False)


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _final(text: str, situation: str, drafts: list[str], intent: str = "error") -> str:
    return _Scripted(drafts).compose_user_message(text, intent, {"situation": situation, "mustNotAskFollowUp": True})


def test_the_evidence_is_the_four_empty_turns() -> None:
    turns = {turn["id"]: turn for turn in EVIDENCE["turns"]}
    assert set(turns) == {"D-s037", "D-s042", "D-p31-t2", "D-w10-t4"}
    assert all(turn["reply"] == "" and turn["error"] == "composition_failed: no_response;retry_exhausted"
               for turn in turns.values())


# ------------------------------------------------------------------ 1. vetoes that refused acceptable drafts


@pytest.mark.parametrize("text", ["quiero tomar una foto del atardecer", "quiero tomarme una selfie en la playa",
                                  "necesito tomar apuntes de la clase", "quisiera tomar una captura del mapa"])
def test_taking_a_photo_or_a_note_is_not_consuming(text: str) -> None:
    assert not wants_to_consume(text), text


@pytest.mark.parametrize("text", ["quiero tomar un café", "quiero tomar algo fresco", "I want to watch a movie"])
def test_drinking_or_watching_still_is(text: str) -> None:
    assert wants_to_consume(text), text


def test_a_limit_on_taking_a_photo_is_not_the_persons_act() -> None:
    # D-s037: «No tomo fotos de playas.» died three times as limit_persons_act.
    asked = "quiero tomar una foto del volcán, mejor que salga el lago"
    assert llm.limit_voice_defect("No saco fotos de volcanes.", asked) == ""
    assert llm.limit_voice_defect("No tomo fotos de volcanes.", asked) == ""
    # Drinking asked is still the person's own act.
    assert llm.limit_voice_defect("No tomo café.", "quiero tomar un café") == "limit_persons_act"


@pytest.mark.parametrize(
    ("draft", "asked", "kept"),
    [
        ("Eso no lo hago: sacar una foto del volcán no es algo que yo realice.",
         "quiero sacar una foto del volcán, mejor que salga el lago",
         "Eso no lo hago: sacar una foto del volcán."),
        ("Eso no lo hago: encargar empanadas a una panadería del barrio no lo preparo yo.",
         "quiero empanadas de una panadería del barrio",
         "Eso no lo hago: encargar empanadas a una panadería del barrio."),
        ("I don't do that: booking a table on Titan is not something I do.",
         "can you book a table on Titan?",
         "I don't do that: booking a table on Titan."),
    ],
)
def test_a_limit_that_named_the_thing_keeps_it_without_the_second_denial(draft: str, asked: str, kept: str) -> None:
    assert llm._unsupported_answer_contract_failure(draft, asked) != ""
    assert llm.limit_without_its_echo(draft) == kept
    assert llm._unsupported_answer_contract_failure(kept, asked) == ""


@pytest.mark.parametrize(
    "draft",
    [
        "Eso no lo hago: tomar una foto que no salga movida.",  # cut inside its own clause
        "No tomo fotos: sacar fotos no es lo mío.",  # not the opening of the plain limit
        "Eso no lo hago: fotos no.",  # one word named
    ],
)
def test_a_limit_of_another_shape_is_not_clipped(draft: str) -> None:
    assert llm.limit_without_its_echo(draft) == ""


def test_the_composed_limit_keeps_what_it_named() -> None:
    asked = "quiero sacar una foto del volcán"
    final = _final(asked, LIMIT, ["Eso no lo hago: sacar una foto del volcán no es una función que realice yo."])
    assert final == "Eso no lo hago: sacar una foto del volcán."


def test_not_managing_to_understand_is_the_failure_told() -> None:
    # D-p31-t2: «…porque no logré interpretar correctamente lo que dijiste.» died in missing_failure; the App reads
    # «no logré» as a failure.
    asked = "¿y estás completamente seguro de eso?"
    facts = {"situation": TURN_FAILURE, "mustNotAskFollowUp": True}
    draft = "No logré interpretar bien lo que me dijiste."
    assert llm.compose_visible_defect(draft, "error", asked, facts) == ""
    assert _final(asked, TURN_FAILURE, [draft]) == draft


def test_an_opened_youtube_page_is_the_cause_fact_not_a_reversed_result() -> None:
    # D-w10-t4: «He abierto YouTube, pero no he podido confirmar si … está sonando.» died as reversed_polarity.
    asked = "ponme cumbia villera en YouTube mientras cocino"
    draft = "He abierto YouTube, pero no he podido confirmar si la cumbia villera está sonando."
    situation = _youtube_unverified("cumbia villera")
    assert llm.compose_visible_defect(draft, "error", asked, {"situation": situation}) == ""
    # A claimed success is still reversed, and another failure keeps the open veto.
    assert llm.compose_visible_defect("Listo, ya suena la cumbia villera.", "error", asked,
                                      {"situation": situation}) == "reversed_polarity"
    other = json.dumps({"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0,
                        "steps": [], "reason": {"kind": "operation", "operation": "app.open", "polarity": "failure",
                                                "verified": False, "succeeded": False, "error": "app_not_found"}})
    assert llm.compose_visible_defect("He abierto Spotify, pero no pude confirmar nada.", "error", "abre spotify",
                                      {"situation": other}) == "reversed_polarity"


# ------------------------------------------------------------------ 2. the floor


@pytest.mark.parametrize(
    ("asked", "language", "clause"),
    [
        ("Quiero sacar una foto del volcán, mejor que salga el lago.", "es", "sacar una foto del volcán"),
        ("recomprar el pasaje de bus a Temuco", "es", "recomprar el pasaje de bus a Temuco"),
        ("quiero empanadas de una panadería del barrio", "es", "lo de empanadas de una panadería del barrio"),
        ("oye, quisiera el pastel de la esquina", "es", "lo del pastel de la esquina"),
        ("por favor, quiero recargar la tarjeta del metro", "es", "recargar la tarjeta del metro"),
        ("can you book a table on Titan?", "en", "book a table on Titan"),
        ("I want a cherry pie from the corner bakery", "en", "a cherry pie from the corner bakery"),
    ],
)
def test_the_thing_asked_is_said_as_the_person_said_it(asked: str, language: str, clause: str) -> None:
    assert asked_act_clause(asked, language) == clause


@pytest.mark.parametrize(
    ("asked", "language"),
    [
        ("¿puedes comprarme un pastel?", "es"),  # the clitic is the person's
        ("compra mi pasaje de bus", "es"),  # an order, and «mi» would change person
        ("que me traigan el pan", "es"),
        ("book a table on Titan", "en"),  # no lead: an order cannot be told from a statement
        ("hola", "es"),
    ],
)
def test_what_cannot_be_said_as_the_person_said_it_is_left_out(asked: str, language: str) -> None:
    assert asked_act_clause(asked, language) == ""


@pytest.mark.parametrize(
    ("asked", "language", "final"),
    [
        ("Quiero sacar una foto del volcán, mejor que salga el lago.", "es",
         "Eso no lo hago: sacar una foto del volcán."),
        ("quiero empanadas de una panadería del barrio", "es",
         "Eso no lo hago: lo de empanadas de una panadería del barrio."),
        ("¿puedes comprarme un pastel?", "es", "Eso no lo hago."),
        ("can you book a table on Titan?", "en", "I don't do that: book a table on Titan."),
    ],
)
def test_a_limit_every_draft_of_which_died_is_said_from_the_decision(asked: str, language: str, final: str) -> None:
    situation = json.loads(LIMIT)
    assert llm._deterministic_final(situation, {}, asked, language) == final
    assert llm.compose_visible_defect(final, "error", asked, {"situation": LIMIT}) == ""


def test_the_composed_limit_never_ends_empty() -> None:
    # D-s042: the three drafts died (limit_changed_act, limit_asks_the_person, invented) and the turn ended in "".
    asked = "quiero empanadas de una panadería del barrio"
    drafts = [
        "No hago empanadas porque eso está fuera de mis capacidades.",
        "No te pido encargar empanadas en una panadería del barrio.",
        "No preparo empanadas de panadería.",
    ]
    assert _final(asked, LIMIT, drafts) == "Eso no lo hago: lo de empanadas de una panadería del barrio."
    # A writer that never answered still leaves the decided limit.
    assert _final(asked, LIMIT, []) == "Eso no lo hago: lo de empanadas de una panadería del barrio."


@pytest.mark.parametrize(
    ("asked", "language", "final"),
    [
        ("ponme cumbia villera en YouTube mientras cocino", "es",
         "La página de YouTube se abrió, pero no pude confirmar que «cumbia villera» esté sonando."),
        ("put some cumbia on YouTube while I cook", "en",
         "The YouTube page opened, but I couldn't confirm that «cumbia villera» is playing."),
    ],
)
def test_an_unconfirmed_youtube_playback_is_reported_naming_its_target(asked: str, language: str, final: str) -> None:
    situation = _youtube_unverified("cumbia villera")
    assert llm._deterministic_final(json.loads(situation), {}, asked, language) == final
    assert _final(asked, situation, ["Listo, ya suena."] * 3) == final


def test_an_effect_left_uncertain_names_its_target() -> None:
    reason = {"kind": "operation", "operation": "media.play.query", "polarity": "failure", "verified": False,
              "succeeded": False, "error": "spotify_playback_unconfirmed", "effectUncertain": True,
              "target": "Los Prisioneros"}
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "reason": reason}
    final = llm._deterministic_final(situation, {}, "pon a Los Prisioneros en Spotify", "es")
    assert final == "No pude confirmar el resultado con «Los Prisioneros»."
    assert "No pude" in final and "Los Prisioneros" in final


def test_a_turn_failure_keeps_no_fixed_final() -> None:
    # Owner's review of M75: «No pude entender…» fixed would be a false failure. D59 §7 (owner, 2026-10-02): when no
    # draft can be said, the turn is asked about with the person's own words, never a fixed sentence.
    asked = "¿y estás completamente seguro de eso?"
    assert _final(asked, TURN_FAILURE, ["Tengo dudas."] * 3) == (
        '¿Qué quieres que haga con "estás completamente seguro de eso"?'
    )


class _Composer:
    """The recovery's composer: what it is asked, and its answer for each intent."""

    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies
        self.asked: list[str] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("an understood turn is not asked what the person wants")

    def compose_user_message(self, _text: str, intent: str, _facts: dict) -> str:
        self.asked.append(intent)
        return self.replies.get(intent, "")


def test_talk_whose_recovered_reply_tells_a_failure_asks_back() -> None:
    # D-p31-t2: the recovered talk reply told a failure, the App refused it, and its turn failure had no final.
    composer = _Composer({
        "conversation": "No puedo garantizar que todo sea exacto ni saber cómo reaccionará cada cual.",
        "clarification": "¿Qué dato quieres que revise?",
    })
    result = sidecar._recover_failed_turn(
        {"id": "m101", "text": "¿y estás completamente seguro de eso?", "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
    )
    assert composer.asked == ["conversation", "clarification"]
    assert result["kind"] == "clarify" and result["question"] == "¿Qué dato quieres que revise?"


@pytest.mark.parametrize(
    ("reply", "asked", "told"),
    [
        ("No puedo garantizar que todo sea exacto.", "¿y estás completamente seguro de eso?", True),
        ("No pude comprobarlo.", "¿seguro que es así?", True),
        ("¡Qué bien! Que te vaya genial en la reunión.", "hoy almuerzo con mi jefa", False),
        ("No puedo hacer fotos.", "¿serías capaz de hacer una foto ahora?", False),
        ("No sé qué te gusta, así que no puedo recomendarte nada concreto. ¿Qué tipo de películas te gustan?",
         "¿alguna película buena para mí?", False),
    ],
)
def test_a_talk_reply_that_tells_a_failure(reply: str, asked: str, told: bool) -> None:
    assert llm.talk_reply_tells_a_failure(reply, asked) is told


# ------------------------------------------------------------------ 3. an asked state that already held


def _microphone(error: str | None, muted: bool | None = None) -> str:
    if error is not None:
        return json.dumps({"kind": "operation", "operation": "audio.microphone.mute", "polarity": "failure",
                           "verified": False, "succeeded": False, "error": error})
    return json.dumps({"kind": "operation", "operation": "audio.microphone.mute", "polarity": "success",
                       "verified": True, "succeeded": True,
                       "observed": {"version": 1, "baselineMuted": not muted, "muted": muted}})


@pytest.mark.parametrize(
    "draft",
    [
        "El micrófono estaba ya silenciado, por lo que no hubo ningún cambio.",
        "El micrófono ya estaba silenciado, así que no hubo ningún cambio.",
    ],
)
def test_the_state_that_already_held_is_told(draft: str) -> None:
    facts = {"situation": _microphone("microphone_already_muted")}
    assert llm.compose_visible_defect(draft, "status", "mutea el micro porfa", facts) == ""


@pytest.mark.parametrize(
    ("error", "language", "final"),
    [
        ("microphone_already_muted", "es", "El micrófono ya estaba silenciado."),
        ("microphone_already_unmuted", "es", "El micrófono ya estaba activo."),
        ("microphone_already_muted", "en", "The microphone was already muted."),
    ],
)
def test_an_asked_state_that_held_has_a_final_from_its_facts(error: str, language: str, final: str) -> None:
    situation = _microphone(error)
    asked = "mute my mic please" if language == "en" else "mutea el micro porfa"
    assert llm._deterministic_final(json.loads(situation), {}, asked, language) == final
    assert _final(asked, situation, ["Silencié el micrófono."] * 3, intent="status") == final


@pytest.mark.parametrize(("muted", "final"), [(True, "El micrófono está silenciado."), (False, "El micrófono está activo.")])
def test_a_verified_microphone_change_has_a_final_from_its_facts(muted: bool, final: str) -> None:
    situation = _microphone(None, muted)
    asked = "mutea el micro porfa" if muted else "prende el micro porfa"
    assert llm._deterministic_final(json.loads(situation), {}, asked, "es") == final
    assert _final(asked, situation, ["Listo."] * 3, intent="status") == final
