"""Encargo TZ-HOLD: «no po, en spotify te dije, no en youtube» with Spotify verified playing denied what BAXY did.

Tanda z6 on the notebook (fable/estab-fase3 e9266d59b), conversation t4-c01: t3 «y ponme cumbia mientras» played
«Raymix - Ángel Malvado» in Spotify, verified (``spotify_windows_uia_postread``, playing) and told «Estoy reproduciendo
"Raymix - Ángel Malvado" de Spotify.»; t4 the correction (the person is wrong: it already plays in Spotify).
``correction_already_holds`` held it (kind playing) and handed it to the writer:

- the first draft «Ya está reproduciendo "Raymix - Ángel Malvado" en Spotify.» died as ``effect_claim``: a conversation
  turn ran nothing, and «está reproduciendo» reads as an effect claimed (``reply_claims.conversation_world_claim``);
  «Ya está sonando…», the words of z1, z3, z4 and z5, does not;
- the hint of ``effect_claim`` says «En este turno no se ejecutó nada… Si la persona lo pidió, di en una frase que no
  lo hiciste», so the retry denied it — «Eso es incorrecto, no estoy reproduciendo en Spotify.» — and passed every
  check (it names Spotify and says no YouTube): published (1,2 s).

Now a held effect (every kind but a count of items told) is said with its sentence (data «heldFact»), never drafted —
TZ-CAL did it for the held state: «Ya está sonando «Raymix - Ángel Malvado» en Spotify.» Contracaso: with YouTube
playing the correction holds nothing and the turn goes on to the decider; a held count is still the writer's.
"""

from __future__ import annotations

import pytest

from baxy_mind import turn_audit, turn_decide, turn_followups
from baxy_mind.deterministic_finals import _held_fact_final
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue

T3 = "y ponme cumbia mientras"
T4 = "no po, en spotify te dije, no en youtube"
RISKS = {"media.play.query": "low_reversible", "system.settings.set": "low_reversible"}

# t3's play as z6 recorded it (compose_audit.jsonl, stage first, situation) and the final it told.
Z6_T3 = {
    "kind": "operation", "operation": "media.play.query", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "provider": "spotify", "title": "Raymix - Ángel Malvado", "query": "cumbia",
        "matchesQuery": True, "playbackStatus": "playing", "authority": "spotify_windows_uia_postread",
    },
}
Z6_T3_TOLD = 'Estoy reproduciendo "Raymix - Ángel Malvado" de Spotify.'
# The two drafts of z6 t4 (compose_audit.jsonl: first, vetoed effect_claim; retry, published).
Z6_DRAFT = 'Ya está reproduciendo "Raymix - Ángel Malvado" en Spotify.'
Z6_RETRY = "Eso es incorrecto, no estoy reproduciendo en Spotify."
# z5's same turn, the contracaso the judge marked right (final «Ya está sonando «…» en Spotify.»).
Z5_T3 = {
    **Z6_T3,
    "observed": {**Z6_T3["observed"], "title": "Rayito Colombiano - Besar Tu Piel"},
}
Z5_T3_TOLD = "Está sonando «Rayito Colombiano - Besar Tu Piel» en Spotify."


@pytest.fixture(autouse=True)
def _no_turn_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_audit, "_append_turn_audit", lambda row: None)


class _Writer:
    """The writer of z6: every draft it is asked for is the retry that denied the play."""

    def __init__(self, reply: str = Z6_RETRY) -> None:
        self.reply = reply
        self.situations: list[dict] = []

    def compose_user_message(self, text: str, intent: str, facts: dict, *, said: str = "") -> str:
        self.situations.append(facts["situation"])
        return self.reply


def _state(t3: dict, told: str, request: str = T3) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, [str(t3["operation"])])
    state.record(t3)
    state.told(t3, told)
    return state


def _turn(t3: dict, told: str, writer: _Writer, text: str = T4) -> dict | None:
    history = [{"role": "user", "content": T3}, {"role": "assistant", "content": told}]
    return turn_followups._correction_already_held(
        {"id": "t4", "text": text, "history": history}, _state(t3, told), writer, RISKS.get,
    )


class _Model:
    """The decider and the writer of a whole turn: every call is recorded; the decider's is the turn going on."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> object:
        def call(*_args: object, **_kwargs: object) -> str:
            self.calls.append(name)
            if name == "compose_user_message":
                return Z6_RETRY
            raise _Decided(name)

        return call


class _Decided(Exception):
    pass


def _whole_turn(t3: dict, told: str) -> tuple[dict | None, _Model]:
    model = _Model()
    play = {
        "type": "function",
        "function": {
            "name": "media_play_query", "canonical_name": "media.play.query", "risk": "low_reversible",
            "description": "Authenticated catalog leaf media.play.query.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "provider": {"type": "string"}},
                           "required": [], "additionalProperties": False},
        },
    }
    history = [{"role": "user", "content": T3}, {"role": "assistant", "content": told}, {"role": "user", "content": T4}]
    try:
        result = turn_decide._prepare_turn_result(
            {"id": "t4", "text": T4, "history": history}, llm=model, planner_catalog=PlannerCatalog([play]),
            encoder=lambda _texts: (), tool_by_name={"media.play.query": {}}, application_names=("Spotify", "YouTube"),
            dialogue_state=_state(t3, told),
        )
    except _Decided:
        result = None
    return result, model


def test_the_whole_z6_turn_says_the_play_and_asks_no_model() -> None:
    result, model = _whole_turn(Z6_T3, Z6_T3_TOLD)

    assert result is not None and result["kind"] == "conversation" and result["effectOperations"] == []
    assert result["reply"] == "Ya está sonando «Raymix - Ángel Malvado» en Spotify."
    assert model.calls == []


@pytest.mark.parametrize(("t3", "told", "title"), [
    (Z6_T3, Z6_T3_TOLD, "Raymix - Ángel Malvado"),
    (Z5_T3, Z5_T3_TOLD, "Rayito Colombiano - Besar Tu Piel"),
])
def test_z6_and_z5_say_the_verified_play_without_the_writer(t3: dict, told: str, title: str) -> None:
    writer = _Writer()
    result = _turn(t3, told, writer)

    assert result is not None and result["kind"] == "conversation" and result["effectOperations"] == []
    assert result["reply"] == f"Ya está sonando «{title}» en Spotify."
    assert writer.situations == []


def test_the_denial_z6_published_can_never_be_the_final() -> None:
    for reply in (Z6_RETRY, Z6_DRAFT, "Ya está sonando en YouTube."):
        result = _turn(Z6_T3, Z6_T3_TOLD, _Writer(reply))
        assert result is not None and result["reply"] == "Ya está sonando «Raymix - Ángel Malvado» en Spotify."


def test_the_held_play_carries_the_service_as_written_and_its_title() -> None:
    holds = _state(Z6_T3, Z6_T3_TOLD).already_holds(T4)

    assert holds == dialogue.AlreadyHolds("playing", named="Spotify", title="Raymix - Ángel Malvado")
    assert holds.effect


def test_the_held_play_in_english() -> None:
    result = _turn(Z6_T3, Z6_T3_TOLD, _Writer(), "no, I told you on spotify, not on youtube")

    assert result is not None and result["reply"] == "«Raymix - Ángel Malvado» is already playing on Spotify."


def test_a_play_without_title_is_said_without_it() -> None:
    untitled = {**Z6_T3, "observed": {key: value for key, value in Z6_T3["observed"].items() if key != "title"}}
    result = _turn(untitled, Z6_T3_TOLD, _Writer())

    assert result is not None and result["reply"] == "Ya está sonando en Spotify."
    assert _held_fact_final({"alreadyHolds": {"kind": "playing", "named": "Spotify"}}, "en") == (
        "It is already playing on Spotify."
    )


def test_a_paused_play_is_held_as_the_service_only() -> None:
    paused = {**Z6_T3, "observed": {**Z6_T3["observed"], "playbackStatus": "paused"}}
    writer = _Writer()
    result = _turn(paused, Z6_T3_TOLD, writer)

    assert result is not None and result["reply"] == "Ya está en Spotify."
    assert writer.situations == []


def test_a_held_target_is_said_from_its_facts() -> None:
    """z3–z6 t4-c04 «joder que te he dicho brillo no volumen»: three drafts died every run and the floor said it; now the
    floor's sentence is the answer, with no draft."""

    brightness = {
        "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"version": 1, "setting": "brightness", "value": 40, "baselineValues": [40]},
    }
    writer = _Writer("Brillo y volumen ya están configurados como pediste.")
    result = turn_followups._correction_already_held(
        {"id": "t2", "text": "joder que te he dicho brillo no volumen", "history": []},
        _state(brightness, "He puesto el brillo al 40.", "pon el brillo al 40"), writer, RISKS.get,
    )

    assert result is not None and result["reply"] == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert writer.situations == []


# --------------------------------------------------------------------------- contracasos


def test_the_whole_turn_with_youtube_playing_goes_to_the_decider() -> None:
    """Contracaso: with YouTube truly playing nothing holds, nothing is said as held and the turn goes on to the
    decider, which acts on it (the base behaviour, unchanged)."""

    youtube = {**Z6_T3, "observed": {**Z6_T3["observed"], "provider": "youtube"}}
    result, model = _whole_turn(youtube, "Está sonando «Raymix - Ángel Malvado» en YouTube.")

    assert result is None and model.calls == ["prepare_decision"]


def test_youtube_truly_playing_holds_nothing_and_the_turn_is_decided() -> None:
    """Contracaso: «en spotify, no en youtube» with YouTube playing is no correction that holds: nothing is said here,
    and the turn goes on to be decided (``DialogueState.attempted_again`` or the decider plays it in Spotify)."""

    youtube = {**Z6_T3, "observed": {**Z6_T3["observed"], "provider": "youtube"}}
    writer = _Writer("Ya está sonando en Spotify.")

    assert _state(youtube, "Está sonando «Raymix - Ángel Malvado» en YouTube.").already_holds(T4) is None
    assert _turn(youtube, "Está sonando «Raymix - Ángel Malvado» en YouTube.", writer) is None
    assert writer.situations == []


def test_a_play_that_was_not_verified_holds_nothing() -> None:
    unverified = {**Z6_T3, "verified": False}

    assert _turn(unverified, Z6_T3_TOLD, _Writer()) is None


def test_a_held_count_is_still_the_writers() -> None:
    """Contracaso: a count of items told is no effect: the writer gives the same items again (z1–z6 t4-c02 t2)."""

    told = "Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."
    state = dialogue.DialogueState()
    state.expect("dame 3 libros de cortazar para arrancar", [])
    state.told({"kind": "conversation", "polarity": "success"}, told)
    writer = _Writer("Bestiario, Rayuela y Octaedro.")
    result = turn_followups._correction_already_held(
        {"id": "t2", "text": "no, te pedi 3 nomas y me tiraste una lista enorme", "history": []}, state, writer,
        RISKS.get,
    )

    assert result is not None and result["reply"] == "Bestiario, Rayuela y Octaedro."
    assert [situation["alreadyHolds"]["kind"] for situation in writer.situations] == ["count"]
    assert not dialogue.AlreadyHolds("count", count=3).effect
