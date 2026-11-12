"""GUA1 (VIVO13, 11-11-2026): with the memory off in Completo, «Recuerda que mi perro se llama Chispo.» → «¡Claro! Acabo
de guardar en mi memoria…» and, after «Sí, dale.», «Ya tengo guardado…», with no call. The check read only «guardé» /
«he guardado»: «acabar de + infinitivo» and «tener + participio» told the same act and went out unread."""
from __future__ import annotations

import pytest

from baxy_mind.answer_check import check

ASKED = "Recuerda que mi perro se llama Chispo."
RECALL = {"op": "memory.recall", "tool": "memory_recall", "arguments": {}, "completed": True, "read": True,
          "outcome": "completado", "observation": '{"facts": [{"text": "mi perro se llama Chispo"}]}'}
SAVE_OFF = {"op": "memory.save", "tool": "memory_save", "arguments": {"text": "perro Chispo"}, "completed": False,
            "read": False, "outcome": "falló (memory_disabled)", "observation": '{"error": "memory_disabled"}'}


def rules(answer: str, receipts: list | None = None, session: list | None = None) -> list[str]:
    return [f["rule"] for f in check(answer, ASKED, receipts or [], [] if session is None else session)]


@pytest.mark.parametrize("answer", [
    # VIVO13 fila 3a and the base's K01 (INT31), word for word.
    "¡Claro! Acabo de guardar en mi memoria que tu perro se llama Chispo.",
    "¡Perfecto! Ya tengo guardado que tu perro se llama Chispo.",
    "¡Claro que sí, Chispo! Ahora lo tengo guardado en mi memoria. ¿Hay algo más que quieras que recuerde?",
    "¡Perfecto, Chispo! Ahora tengo guardado que tu perro se llama así.",
    "¡Claro! Acabo de guardar que tu perro se llama Chispo. ¿Hay algo más que quieras que recuerde?",
    # The same form with other words.
    "Listo, ya lo anoté.",
    "Acabo de guardarlo.",
    "Te lo dejé guardado.",
    "Ya tenemos anotado tu cumpleaños.",
    "Sure! I've just saved that your dog is called Chispo.",
    "I saved it.",
    "I have stored that for you.",
])
def test_a_save_told_done_with_no_call_is_read(answer: str) -> None:
    assert rules(answer) == ["no_call"]


def test_after_the_memory_failed_off_it_is_not_completed() -> None:
    assert rules("Acabo de guardar que tu perro se llama Chispo.", [SAVE_OFF], [("memory.save", False, False)]) == [
        "not_completed"]


@pytest.mark.parametrize("answer", [
    "¿Quieres que lo guarde?",
    "Puedo guardarlo si enciendes la memoria.",
    "No lo he guardado: la memoria está apagada.",
    "Todavía no lo tengo guardado.",
    "Si quieres, lo dejo guardado.",
    "Que lo deje guardado en tu agenda.",
    "I haven't saved it: memory is off.",
    "Do you want me to save it?",
    "La memoria está apagada. ¿Quieres que la encienda para recordarlo?",
])
def test_an_offer_a_denial_or_a_condition_claims_nothing(answer: str) -> None:
    assert rules(answer) == []


def test_what_the_memory_showed_backs_having_it_saved() -> None:
    assert rules("Tengo guardado que tu perro se llama Chispo.", [RECALL], [("memory.recall", True, True)]) == []
    # An earlier recall of the session backs it too.
    assert rules("Sí, lo tengo guardado.", [], [("memory.recall", True, True)]) == []
    # The recent past is an act, not a state: a recall does not back it.
    assert rules("Acabo de guardar que tu perro se llama Chispo.", [RECALL], [("memory.recall", True, True)]) == [
        "no_call"]


def test_a_save_that_ran_backs_every_form() -> None:
    saved = {"op": "memory.save", "tool": "memory_save", "arguments": {"text": "perro Chispo"}, "completed": True,
             "read": False, "outcome": "completado", "observation": '{"saved": true}'}
    for answer in ("Acabo de guardar que tu perro se llama Chispo.", "Ya lo tengo guardado.", "I've just saved it."):
        assert rules(answer, [saved], [("memory.save", True, False)]) == []


def test_an_unknown_session_is_not_read() -> None:
    assert [f["rule"] for f in check("Acabo de guardarlo.", ASKED, [], None)] == []


# ---- the mind: a save told done in a turn that called nothing keeps the tools ------------------------------------------
# Banco GUA1 (K01, 1.4.2): words only, after the note the model wrote «Acabo de guardar que tu perro se llama Chispo.»
# three times: no result told it the memory was off. With its tools it calls memory_save and reads memory_disabled.
def _remembering(tmp_path, replies):
    from test_mind_final import _mind
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [
        {"name": "memory.save", "description": "Guarda un dato de la persona.", "risk": "low_reversible",
         "argumentsSchema": {"type": "object", "properties": {"value": {"type": "string"}}}}]})
    return mind, server


def test_a_save_told_with_no_call_is_asked_again_with_the_tools(tmp_path, monkeypatch) -> None:
    from baxy_mind.mind import CHECK_NOTE, UNDONE_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "¡Claro! Acabo de guardar que tu perro se llama Chispo."
    mind, server = _remembering(tmp_path, [_say(said), _call("memory_save", {"value": "perro Chispo"})])
    result = mind.decide(1, ASKED)
    assert result["kind"] == "action" and result["operation"] == "memory.save"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(UNDONE_NOTE[:60])
    assert not note["content"].startswith(CHECK_NOTE[:90]) and "Acabo de guardar" in note["content"]
    assert "tool_choice" not in server.bodies[-1]  # it may do what the person asked


def test_after_a_call_of_the_turn_the_note_stays_words_only(tmp_path, monkeypatch) -> None:
    from baxy_mind.mind import CHECK_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _remembering(tmp_path, [_call("memory_save", {"value": "perro Chispo"}),
                                           _say("Acabo de guardar que tu perro se llama Chispo."),
                                           _say("No pude guardarlo: la memoria está apagada.")])
    mind.decide(1, ASKED)
    mind.continue_turn(1, '{"status": "failed", "error": "memory_disabled"}')
    assert server.bodies[-1]["messages"][-1]["content"].startswith(CHECK_NOTE[:90])


def test_the_note_after_an_undone_act_comes_after_the_answer_it_read(tmp_path, monkeypatch) -> None:
    # GUA2 (banco GUA1, semilla 1: «Ahora lo tengo guardado en mi memoria.» three times): the request after UNDONE_NOTE
    # was the turn's own first request plus the note, so the same seed wrote the same words again. The answer the note
    # reads goes before it, as the model's (Self-Refine, arXiv 2303.17651; CRITIC, arXiv 2305.11738), and both leave
    # the conversation after that request.
    from baxy_mind.mind import UNDONE_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "Ahora lo tengo guardado en mi memoria."
    mind, server = _remembering(tmp_path, [_say(said), _call("memory_save", {"value": "perro Chispo"}),
                                           _say("La memoria está apagada. ¿Quieres que la encienda?")])
    mind.decide(1, ASKED)
    draft, note = server.bodies[-1]["messages"][-2:]
    assert note["content"].startswith(UNDONE_NOTE[:60])
    assert draft == {"role": "assistant", "content": said}
    mind.continue_turn(1, '{"status": "failed", "error": "memory_disabled"}')
    later = [m for m in mind.conversation if m.get("role") == "assistant" and m.get("content") == said]
    assert not later


def test_a_words_only_check_note_has_no_draft_before_it(tmp_path, monkeypatch) -> None:
    from baxy_mind.mind import CHECK_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "Acabo de guardar que tu perro se llama Chispo."
    mind, server = _remembering(tmp_path, [_call("memory_save", {"value": "perro Chispo"}), _say(said),
                                           _say("No pude guardarlo: la memoria está apagada.")])
    mind.decide(1, ASKED)
    mind.continue_turn(1, '{"status": "failed", "error": "memory_disabled"}')
    assert server.bodies[-1]["messages"][-1]["content"].startswith(CHECK_NOTE[:90])
    assert server.bodies[-1]["messages"][-2].get("content") != said


def test_the_draft_before_the_note_is_not_counted_as_said(tmp_path, monkeypatch) -> None:
    # REM3 (REV13 E-1, open since REV12 C-4): GUA2 puts the answer the note reads before it as the model's, and say_once
    # took that draft for BAXY's last words: the same words again after UNDONE_NOTE were asked once more with no tools
    # (tool_choice none), just when the note had kept them. The person never heard the draft: only what they heard counts.
    from baxy_mind.mind import SAID_AGAIN_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "¡Claro! Acabo de guardar que tu perro se llama Chispo."
    mind, server = _remembering(tmp_path, [_say(said), _say(said), _call("memory_save", {"value": "perro Chispo"})])
    result = mind.decide(1, ASKED)
    after = server.bodies[2]
    assert after.get("tool_choice") != "none"
    assert not str(after["messages"][-1].get("content") or "").startswith(SAID_AGAIN_NOTE[:60])
    assert result["kind"] == "action" and result["operation"] == "memory.save"


def test_words_heard_before_are_still_said_again(tmp_path, monkeypatch) -> None:
    # The control: BAXY's last words the person heard (an earlier turn's answer), written again, are still asked once more.
    from baxy_mind.mind import SAID_AGAIN_NOTE
    from test_mind_final import _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "Tu perro se llama Chispo."
    mind, server = _remembering(tmp_path, [_say(said), _say(said), _say("Se llama Chispo, como me contaste.")])
    mind.decide(1, "¿Cómo se llama mi perro?")
    mind.decide(2, "¿Y cómo se llamaba?")
    assert str(server.bodies[2]["messages"][-1].get("content") or "").startswith(SAID_AGAIN_NOTE[:60])
