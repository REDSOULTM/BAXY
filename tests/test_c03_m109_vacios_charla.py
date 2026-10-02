"""M109 (2026-10-01): talk turns whose every draft died, and a headlines report the App read as reversed.

DEV-D v4d (code 194e12f6, up to M107) still ended two talk turns with an empty visible final and one news read
filtered; the evidence of the three is in tests/data/c03_m109_evidence.json. Every phrasing below is our own, of the
same shape as the rows it stands for.

1. D-p23-t5 / D-p24-t5: the mind's talk reply told a failure («I cannot …») and the App refused it (looks_like_failure);
   its conversation fallback composed with no conversation and every draft died. The talk reply is now judged by the
   App's twin in the mind and written again with what to say instead; a repair that still tells it goes to the turn's
   recovery, which composes with the conversation (BAXY's last message, the person's earlier ones).
2. The vetoes leave a valid answer: the claimed-ability hint carries BAXY's last message and asks for the limit again or
   the act not done with its reason after a colon — which own_write_denied accepts —; the own-write hint says what to
   write when the act was asked; a go-ahead after a question of BAXY's is told that its yes answers nothing asked.
3. When every draft of talk that ran nothing dies anyway, the composer asks the one thing missing (composed by the
   model from the same conversation, never a fixed sentence), and nothing when that cannot be written either.
4. D-p24-t4: «do it» answered with the act not done and why is not an unasked question (mind and App twin).
5. D-w17-t4: the words of the headlines read are observed data, not a failure (App twin of the mind's mask; .NET test).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import ConversationReplyContractError
from baxy_mind.semantic import dialogue

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m109_evidence.json").read_text(encoding="utf-8"))
TALK = json.dumps({"kind": "conversation", "polarity": "success"})


def test_the_evidence_is_the_two_empty_talk_turns_and_the_filtered_headlines() -> None:
    turns = {turn["id"]: turn for turn in EVIDENCE["turns"]}
    assert set(turns) == {"D-p23-t5", "D-p24-t5", "D-w17-t4"}
    for name in ("D-p23-t5", "D-p24-t5"):
        assert turns[name]["reply"] == "" and turns[name]["error"] == "composition_failed: no_response;retry_exhausted"
        assert turns[name]["app_refusal"] == "looks_like_failure"
    assert turns["D-w17-t4"]["error"] == "filtered: reversed_result"


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order; every payload sent is kept. Out of drafts, it runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        if not self._drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self._drafts.pop(0)}, "finish_reason": "stop"}]}


def _system_text(payload: dict) -> str:
    return "\n".join(str(item.get("content") or "") for item in payload["messages"] if item.get("role") == "system")


# ------------------------------------------------------------------ 1. the talk reply the App would refuse


_SUBTITLES_HISTORY = [
    {"role": "user", "content": "Put Portuguese captions on the documentary."},
    {"role": "assistant", "content": "I don't change the captions of films."},
]


def _talk(writer: _Writer, text: str, history: list[dict] | None = None) -> str:
    reply, _ = writer.chat(
        text, history=list(history or []), conversation_kind="knowledge", response_language="en", temperature=0.0,
    )
    return reply


def test_talk_that_tells_a_failure_is_written_again_with_what_to_say() -> None:
    writer = _Writer([
        "I cannot put French captions on the documentary.",
        json.dumps({"answer": "I don't change the captions of films, French ones included."}),
    ])
    reply = _talk(writer, "Then switch them to French.", _SUBTITLES_HISTORY)
    assert reply == "I don't change the captions of films, French ones included."
    assert len(writer.sent) == 2
    hint = _system_text(writer.sent[1])
    assert "Do not tell it as something you could not or cannot do" in hint
    assert "(«I have not done that: …»)" in hint


def test_a_repair_that_still_tells_a_failure_goes_to_the_recovery() -> None:
    writer = _Writer([
        "I cannot reach your streaming account.",
        json.dumps({"answer": "I couldn't reach your streaming account."}),
    ])
    with pytest.raises(ConversationReplyContractError) as refused:
        _talk(writer, "Sounds good, carry on with that.")
    assert refused.value.audit_reason == "told_failure"
    assert refused.value.conversation_kind == "knowledge"


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("I can't tell which captions that film ships with.", "which captions does that film ship with?"),
        ("I can't say for sure, but it premiered in Cannes.", "where did it premiere?"),
    ],
)
def test_a_question_keeps_its_answer_however_it_is_told(reply: str, asked: str) -> None:
    writer = _Writer([reply])
    assert _talk(writer, asked) == reply
    assert len(writer.sent) == 1


# ------------------------------------------------------------------ 2. vetoes that leave a valid answer


def test_the_claimed_ability_hint_carries_the_last_message_and_a_reasoned_denial() -> None:
    last = "I don't change the captions of films."
    english = llm._claimed_ability_instruction(last, "en")
    assert f"«{last}»" in english and "after a colon («I have not done that: …»)" in english
    spanish = llm._claimed_ability_instruction("No cambio los subtítulos de las películas.", "es")
    assert "«No cambio los subtítulos de las películas.»" in spanish and "tras dos puntos («No lo he hecho: …»)" in spanish


@pytest.mark.parametrize(
    ("reply", "asked", "denied"),
    [
        ("I have not added French captions.", "Then switch them to French.", True),
        ("I have not added French captions: I don't change the captions of films.", "Then switch them to French.", False),
        ("No he añadido subtítulos en francés: no cambio los subtítulos.", "Entonces ponlos en francés.", False),
    ],
)
def test_a_denial_that_says_why_is_the_answer_the_hint_asks_for(reply: str, asked: str, denied: bool) -> None:
    assert llm.visible_reply_denies_an_own_write(reply, asked) is denied


def test_the_fallback_composer_follows_the_hint_to_an_answer() -> None:
    # The App's conversation fallback: an «I can» draft, then the reasoned denial the hint asks for.
    writer = _Writer([
        "I can put French captions on your documentary.",
        "I have not done that: I don't change the captions of films.",
    ])
    final = writer.compose_user_message(
        "Then switch them to French.", "conversation",
        {"situation": TALK, "context": "I don't change the captions of films."},
    )
    assert final == "I have not done that: I don't change the captions of films."
    assert "«I don't change the captions of films.»" in _system_text(writer.sent[1])


def test_the_own_write_hint_says_what_to_write_when_the_act_was_asked() -> None:
    for language, words in (("en", "say that you do not do it"), ("es", "di que eso no lo haces")):
        assert words in llm._own_write_denied_instruction(language)


def test_a_go_ahead_after_a_question_is_told_its_yes_answers_nothing_asked() -> None:
    asked = "Which playlist should I start?"
    assert "their yes does not answer what you asked" in llm._go_ahead_instruction(asked, "en")
    assert "su sí no contesta lo que preguntaste" in llm._go_ahead_instruction("¿Qué lista pongo?", "es")
    assert "nothing of yours was waiting for a yes" in llm._go_ahead_instruction("I paused the music.", "en")
    writer = _Writer(["The request is confirmed and under way.", "I have not started anything yet: which playlist?"])
    final = writer.compose_user_message(
        "Yes, that is confirmed, please go ahead.", "conversation", {"situation": TALK, "context": asked},
    )
    assert final == "I have not started anything yet: which playlist?"
    assert "their yes does not answer what you asked" in _system_text(writer.sent[1])


# ------------------------------------------------------------------ 3. the talk floor


def test_talk_whose_every_draft_dies_asks_the_one_thing_missing() -> None:
    claimed = "I can put French captions on your documentary."
    writer = _Writer([claimed, claimed, claimed, "Which documentary do you mean?"])
    final = writer.compose_user_message(
        "Then switch them to French.", "conversation",
        {"situation": TALK, "context": "I don't change the captions of films.", "priorRequests": ["Put captions on."]},
    )
    assert final == "Which documentary do you mean?"
    asked = writer.sent[3]["messages"][-1]["content"]
    assert "clarification" in asked


def test_the_floor_is_never_a_fixed_sentence() -> None:
    claimed = "I can put French captions on your documentary."
    writer = _Writer([claimed, claimed, claimed])
    assert writer.compose_user_message("Then switch them to French.", "conversation", {"situation": TALK}) == ""


def test_an_operation_report_gets_no_talk_floor() -> None:
    failed = json.dumps({"kind": "failure", "polarity": "failure", "cause": "turn_runtime_failure",
                         "operationAttempted": False, "retryable": True})
    writer = _Writer(["Tengo dudas."] * 3 + ["¿Qué quieres que haga?"])
    # D59 §7 (owner, 2026-10-02): no talk floor is composed; the turn not understood is asked with the person's words.
    assert writer.compose_user_message("¿y eso es seguro?", "error", {"situation": failed}) == (
        '¿Qué quieres que haga con "eso es seguro"?'
    )
    assert len(writer.sent) == 3


class _Composer:
    """The recovery's composer: what it is given, and its answer for each intent."""

    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies
        self.facts: list[dict] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("an understood turn is not asked what the person wants")

    def compose_user_message(self, _text: str, intent: str, facts: dict) -> str:
        self.facts.append({"intent": intent, **facts})
        return self.replies.get(intent, "")


def test_the_recovery_composes_with_the_conversation() -> None:
    composer = _Composer({"conversation": "I don't change the captions of films, French ones included."})
    history = [*_SUBTITLES_HISTORY, {"role": "user", "content": "Then switch them to French."}]
    result = sidecar._recover_failed_turn(
        {"id": "m109", "text": "Then switch them to French.", "history": history},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
        conversation_kinds=("knowledge", "knowledge"),
    )
    assert result["reply"] == "I don't change the captions of films, French ones included."
    given = composer.facts[0]
    assert given["context"] == "I don't change the captions of films."
    assert given["priorRequests"] == ["Put Portuguese captions on the documentary."]


def test_the_recovery_question_is_asked_with_the_conversation_too() -> None:
    composer = _Composer({"clarification": "Which documentary do you mean?"})
    history = [*_SUBTITLES_HISTORY]
    result = sidecar._recover_failed_turn(
        {"id": "m109", "text": "Then switch them to French.", "history": history},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
        conversation_kinds=("knowledge", "knowledge"),
    )
    assert result["kind"] == "clarify" and result["question"] == "Which documentary do you mean?"
    assert [facts["intent"] for facts in composer.facts] == ["conversation", "clarification"]
    assert composer.facts[1]["context"] == "I don't change the captions of films."


# ------------------------------------------------------------------ 4. «do it» answered with the act not done and why


@pytest.mark.parametrize(
    ("reply", "told"),
    [(row["reply"], row["told"]) for row in EVIDENCE["not_done_and_why_twins"]],
)
def test_the_act_not_done_and_why(reply: str, told: bool) -> None:
    # The same rows are read by the App's twin (M109VaciosCharlaTests).
    assert dialogue.says_not_done_and_why(reply) is told


# ------------------------------------------------------------------ 5. the headlines read are data (mind side)


_HEADLINES = json.dumps({
    "kind": "operation", "operation": "web.news.headlines", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {"edition": "es-419/CL", "count": 2, "headlines": [
        {"title": "El ministro responde a la oposición: “No acepto esas críticas”", "source": "Diario Uno"},
        {"title": "Rechazado en el Senado el plan de transporte nocturno", "source": "Radio Dos"},
    ]},
}, ensure_ascii=False)


def test_a_headlines_report_is_no_failure_told_while_an_own_failure_still_is() -> None:
    report = ("Titulares: «El ministro responde a la oposición: “No acepto esas críticas”»; «Rechazado en el Senado "
              "el plan de transporte nocturno».")
    facts = {"situation": _HEADLINES}
    assert llm.compose_visible_defect(report, "status", "qué hay de nuevo en las noticias", facts) != "asserted_failure"
    own = report + " No pude leer el resto."
    assert llm.compose_visible_defect(own, "status", "qué hay de nuevo en las noticias", facts) == "asserted_failure"


def test_do_it_answered_with_the_act_not_done_and_why_is_no_unasked_question() -> None:
    facts = {"situation": TALK, "context": "The download of the album failed because the store asks for a sign-in."}
    reasoned = "I have not done it yet because the store asks me to sign in on this PC first."
    assert llm.compose_visible_defect(reasoned, "conversation", "Yes, do it for me.", facts) != (
        "clarification_not_a_question"
    )
    assert llm.compose_visible_defect("Sure.", "conversation", "do it", {"situation": TALK}) == (
        "clarification_not_a_question"
    )
