"""GUA3 (REV11 C-1, 11-11-2026): the forms GUA1 added read answers that tell nothing done now. The English ones did not look
at a negation, a condition or a time clause before them («If I deleted it by mistake, you can restore it…»), and «anoté»
counted even when what it wrote is the answer itself («Te anoté los pasos aquí abajo: 1. …»). And UNDONE_NOTE kept the
tools for any of them, with «si la persona lo pidió, hazlo ahora»: an invitation to act with no request."""
from __future__ import annotations

import pytest

from baxy_mind.answer_check import asked_for, check

SAVE = "Guarda que mi perro se llama Chispo"


def rules(answer: str, request: str = SAVE) -> list[str]:
    return [f["rule"] for f in check(answer, request, [], [])]


# REV11 tmp\REV11\verif\c_gua1.txt (FP1, FP4) and zonas\C\ingles_salida.txt, word for word, and more of the same form.
@pytest.mark.parametrize("answer, asked", [
    ("If I deleted it by mistake, you can restore it from the Recycle Bin.", "Where did my file go?"),
    ("Unless I closed it, Chrome should still be open.", "Is Chrome still open?"),
    ("When I opened Word yesterday it was slow, so try safe mode.", "Word is slow"),
    ("Te anoté los pasos aquí abajo: 1. Abre Word. 2. Pulsa Guardar.", "¿Cómo guardo en Word?"),
    ("I've just sent you the summary below: the meeting is at 5.", "Summarize the meeting"),
    ("If I've already saved a draft, Word keeps it in Recent.", "Where are my drafts?"),
    ("Whenever I've installed it before, it asked for a restart.", "Will it ask for a restart?"),
    ("I haven't saved anything yet.", "Did you save it?"),
    ("Cuando acabo de guardar un archivo, Word lo muestra en Recientes.", "¿Dónde salen mis archivos?"),
    ("Te dejé anotada la receta a continuación: harina, huevos y leche.", "Dame una receta de panqueques"),
])
def test_a_condition_a_time_clause_or_the_answer_itself_claims_nothing(answer: str, asked: str) -> None:
    assert rules(answer, asked) == []


@pytest.mark.parametrize("answer", [
    # REV11 FN1, FN2, FN10, FN12-FN16: still read.
    "¡Claro! Acabo de guardar en mi memoria que tu perro se llama Chispo.",
    "Ya tengo guardado que tu perro se llama Chispo.",
    "I have saved it.",
    "Recién guardé que tu perro se llama Chispo.",
    "Te lo guardé.",
    "Acabo de apagar el wifi.",
    "Acabo de borrar la carpeta.",
    "Acabo de cerrar Chrome.",
    "I saved it.",
    # A deixis in another clause, or no deixis at all, does not make the act the answer's own.
    "Lo anoté: tu perro se llama Chispo.",
    "Done, I've saved it, here it is: your dog is Chispo.",
    "Listo, lo anoté aquí abajo.",  # nothing follows: nothing of it is in the answer
])
def test_a_claim_of_an_act_is_still_read(answer: str) -> None:
    assert rules(answer) == ["no_call"]


@pytest.mark.parametrize("said, asked, offered, expected", [
    ("Acabo de guardar en mi memoria", "Recuerda que mi perro se llama Chispo.", "", True),
    ("Acabo de guardar", "oye recuerda que mi perro se llama Chispo", "", True),
    ("I've just saved it", "Can you note down that my cat takes his pill?", "", True),
    ("Lo anoté", "Ya po, anota que el cumpleaños de mi tata es el 14.", "", True),
    ("Te lo guardé", "Oye, guárdame que mi gato se llama Tlacuache.", "", True),
    ("Acabo de guardar", "Acuérdate porfa que soy alérgico.", "", True),
    ("Acabo de cerrar Chrome", "¿Chrome gasta mucha RAM?", "", False),
    ("Acabo de cerrar Chrome", "Cierra Chrome.", "", True),
    ("Acabo de guardar", "No lo guardes, era una prueba.", "", False),
    ("Acabo de borrar la carpeta", "If I delete it, can I get it back?", "", False),
    ("I opened the topic", "Write an intro", "", False),
    # The person's words answer BAXY's own question that offered that act.
    ("Listo, lo guardé", "Sí, dale.", "La memoria está apagada. ¿Quieres que la encienda para guardarlo?", True),
    ("Listo, lo guardé", "ya po, hazle nomas", "¿Quieres que lo recuerde para siempre?", True),
    ("Listo, lo guardé", "No, déjalo así.", "¿Quieres que lo guarde?", False),
    ("Listo, lo guardé", "Sí, dale.", "La memoria está apagada; puedes encenderla en Ajustes.", False),
    ("Listo, lo guardé", "Sí, dale.", "¿Quieres que abra el Bloc de notas?", False),
])
def test_the_turn_asked_for_the_act_by_its_own_words(said: str, asked: str, offered: str, expected: bool) -> None:
    assert asked_for(said, asked, offered) is expected


# ---- the mind: the tools stay only when the person asked for that act ------------------------------------------------
def _closing(tmp_path, replies):
    from test_mind_final import _mind
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [
        {"name": "app.close", "description": "Cierra una aplicación.", "risk": "low_reversible",
         "argumentsSchema": {"type": "object", "properties": {"name": {"type": "string"}}}}]})
    return mind, server


def test_an_act_nobody_asked_for_is_asked_again_in_words_only(tmp_path, monkeypatch) -> None:
    # REV11 FN16: «Acabo de cerrar Chrome.» to «¿Chrome gasta mucha RAM?»: false, and nobody asked to close it. The note
    # asks for the answer again telling only what was done; it does not invite the model to close Chrome.
    from baxy_mind.mind import CHECK_NOTE
    from test_mind_final import _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _closing(tmp_path, [_say("Acabo de cerrar Chrome."), _say("Chrome usa bastante RAM con muchas pestañas.")])
    result = mind.decide(1, "¿Chrome gasta mucha RAM?")
    assert result["kind"] == "conversation"
    note = server.bodies[-1]["messages"][-1]
    assert note["content"].startswith(CHECK_NOTE[:90]) and "hazlo ahora" not in note["content"]
    assert server.bodies[-1].get("tool_choice") == "none"


def test_an_act_the_person_ordered_keeps_the_tools(tmp_path, monkeypatch) -> None:
    from baxy_mind.mind import UNDONE_NOTE
    from test_mind_final import _call, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _closing(tmp_path, [_say("Acabo de cerrar Chrome."), _call("app_close", {"name": "Chrome"})])
    result = mind.decide(1, "Cierra Chrome, porfa.")
    assert result["kind"] == "action" and result["operation"] == "app.close"
    assert server.bodies[-1]["messages"][-1]["content"].startswith(UNDONE_NOTE[:60])
    assert "tool_choice" not in server.bodies[-1]
