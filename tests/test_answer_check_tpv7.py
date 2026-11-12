"""TPV7 (VIVO11, 11-11-2026, candidata 1.4.0 en Esencial: «Nota creada: "Hola"» sin llamar note.create; banco, 11-11:
«Ya está, te puse la cumbia» with the music tool only turned on). Why the rule «said done, nothing completed» of
answer_check read neither, and the two forms it now reads."""
import pytest

from test_answer_check import _r, _rules

# VIVO11: «Nota creada: "Hola"» after the «sí» that only turned the tool on. A bare participle was no claim for the rule
# «said done, nothing completed» (answer_check, KINDS «crear»), so the answer went out as it was.
TURNED_ON = {"status": "rejected", "error": "not_run_tool_turned_on", "turnedOn": "the tool «Create a note»",
             "next": "only a setting changed so far"}


@pytest.mark.parametrize("answer,flagged", [
    ('Nota creada: "Hola"', True),
    ("Listo, nota creada.", True),
    ("Recordatorio creado para mañana a las ocho.", True),
    ("Creé la nota «hola».", True),
    ("La herramienta de notas ya está encendida; la nota aún no está creada.", False),
    ("Ya encendí las notas. Lo que pediste todavía no se hizo.", False),
    ("¿Quieres que la cree ahora?", False),
])
def test_a_note_told_as_created_by_a_bare_participle_is_read_against_the_call_that_did_not_run(
        answer: str, flagged: bool) -> None:
    receipts = [_r("confirmation.answer", TURNED_ON, {"answer": "yes"})]
    assert ("not_completed" in _rules(answer, receipts, "sí")) is flagged


def test_a_note_that_was_created_is_told_as_created() -> None:
    receipts = [_r("confirmation.answer", TURNED_ON, {"answer": "yes"}),
                _r("note.create", {"status": "completed", "verification": "readback"}, {"title": "hola"})]
    assert _rules('Nota creada: "Hola"', receipts, "sí") == []
    # With no call of its kind in the turn, the participle may tell what a look saw or what the answer itself made.
    assert _rules("Aquí tienes la lista creada con lo que me dijiste: pan, leche.", [], "hazme una lista") == []


# Banco TPV7 (11-11-2026, Esencial, T09): «Ya está, te puse la cumbia» after the «sí» that only turned the music tool on,
# with no call after it. A strong preterite is written with no accent («puse», «reproduje», «traje») and the rule only
# counted a verb ending in «e» when it carried one, so that claim was never read.
@pytest.mark.parametrize("answer,flagged", [
    ("Ya está, te puse la cumbia del Grupo Candela Chalaca. ¿Te gusta?", True),
    ("Listo, puse la música que pediste.", True),
    ("Reproduje la canción.", True),
    ("La herramienta de música ya está encendida; todavía no puse nada.", False),
    ("¿Quieres que la ponga ahora?", False),
])
def test_a_strong_preterite_is_a_claim_though_it_carries_no_accent(answer: str, flagged: bool) -> None:
    turned_on = {**TURNED_ON, "turnedOn": "the tool «Play music»"}
    assert ("not_completed" in _rules(answer, [_r("media.play.query", turned_on, {})], "sí")) is flagged


def test_a_strong_preterite_of_a_call_that_completed_stands() -> None:
    receipts = [_r("media.play.query", {"status": "completed", "verification": "state"}, {"query": "cumbia"})]
    assert _rules("Ya está, te puse la cumbia.", receipts, "sí") == []
