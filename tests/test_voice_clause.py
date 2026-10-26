"""The first clause as the first take (src/baxy_mind/voice_output.py; H7 on the notebook): 80 of 82 replies were one
sentence, so the first sound waited for the whole reply. It changes the prosody (a pause at the clause), never the
words; the spoken A/B (2026-10-25: the first answer 378 ms sooner on average, 7 of 10 orders) made it the behaviour."""
import time
from pathlib import Path

import pytest

from baxy_mind import voice_output
from baxy_mind.speech_text import spoken
from baxy_mind.voice_output import GAP_CLAUSE_S, GAP_QUESTION_S, GAP_S, Speech, clause_cut


def _head(sentence: str) -> str | None:
    cut = clause_cut(sentence)
    return None if cut is None else sentence[:cut]


@pytest.mark.parametrize(("sentence", "head"), [
    # a comma, a semicolon or a colon once the clause has 25 characters and 4 words, and 4 words after it
    ("Abrí el informe de ventas del mes, y lo dejé en el escritorio.", "Abrí el informe de ventas del mes,"),
    ("Spotify ya está abierto en tu PC; suena la lista que dejaste ayer.", "Spotify ya está abierto en tu PC;"),
    ("Encontré tres archivos con ese nombre: dos en Descargas y uno en Documentos.",
     "Encontré tres archivos con ese nombre:"),
    # a short first clause is passed over for the next one
    ("Listo, el informe de ventas ya está guardado, y también lo copié a tu escritorio.",
     "Listo, el informe de ventas ya está guardado,"),
    ("Listo, Spotify está abierto y sonando en tu PC.", None),            # no clause long enough
    ("Hola, ¿qué tal?", None),
    # never inside a number or after one: «1,5» has no space after its comma; lists of numbers are not clauses
    ("El disco tiene 1,5 GB libres y 2,5 GB usados en total.", None),
    ("Puedes elegir entre las opciones 1, 2 o 3 del menú principal.", None),
    ("Puedes elegir entre las opciones uno, dos o tres del menú principal.", None),
    # never inside quotes or brackets; the clause after them may end there
    ("Te dejé la nota «compra pan, leche y huevos para mañana» en el escritorio, como pediste ayer por la tarde.",
     "Te dejé la nota «compra pan, leche y huevos para mañana» en el escritorio,"),
    ("Abrí la carpeta (la de fotos, no la de música) que usaste ayer por la tarde.", None),
    ('Busqué "informe final, versión dos" en tus documentos y no aparece en ninguna carpeta.', None),
    # what follows must be four words or more (Supertonic's weak spot, issue #30)
    ("Abrí el informe de ventas del mes, como pediste.", None),
])
def test_where_the_first_take_ends_at_a_clause(sentence: str, head: str | None) -> None:
    assert _head(sentence) == head


def test_a_sentence_still_being_written_has_the_cut_of_the_whole_sentence() -> None:
    whole = "Abrí el informe de ventas del mes, y lo dejé en el escritorio."
    cuts = {clause_cut(whole[:end]) for end in range(len(whole) + 1)}
    assert cuts == {None, clause_cut(whole)}
    # and once the written part has it, every longer one has it too
    first = next(end for end in range(len(whole) + 1) if clause_cut(whole[:end]) is not None)
    assert all(clause_cut(whole[:end]) == clause_cut(whole) for end in range(first, len(whole) + 1))


REPLIES = [
    "Abrí el informe de ventas del mes, y lo dejé en el escritorio.",
    "Tienes 1,5 GB libres en el disco C, y el resto está ocupado por juegos. ¿Quieres que lo revise?",
    "Encontré tres archivos con ese nombre: dos en Descargas y uno en Documentos.",
    "Listo. Spotify está abierto, sonando la lista que dejaste ayer por la tarde.",
    "Listo, Spotify está abierto y sonando en tu PC. ¿Quieres que suba el volumen?",
    "Abrí la carpeta de fotos — la de las vacaciones — que usaste ayer por la tarde.",
    "Te dejé la nota «compra pan, leche y huevos para mañana» en el escritorio, como pediste ayer.",
]


def _takes(text: str) -> list[str]:
    return Speech._takes(Speech._units(text), text)


@pytest.mark.parametrize("reply", REPLIES)
def test_the_takes_say_the_model_s_words_and_marks_in_order(reply: str) -> None:
    assert " ".join(_takes(reply)) == spoken(reply)


def test_the_first_clause_is_its_own_take() -> None:
    assert _takes(REPLIES[0]) == ["Abrí el informe de ventas del mes,", "y lo dejé en el escritorio."]
    assert _takes(REPLIES[1]) == ["Tienes uno coma cinco gigas libres en el disco C,",
                                  "y el resto está ocupado por juegos.", "¿Quieres que lo revise?"]
    # a dash is said as a comma (speech_text.spoken), so it is a clause too
    assert _takes(REPLIES[5]) == ["Abrí la carpeta de fotos,",
                                  "la de las vacaciones, que usaste ayer por la tarde."]
    # a short opener still goes whole with the next sentence (issue #30): no clause is taken out of that take
    assert _takes(REPLIES[3]) == [spoken(REPLIES[3])]
    assert _takes(REPLIES[4]) == Speech._units(REPLIES[4])  # «Listo,» is too short a clause


def test_a_sentence_without_a_clause_to_end_at_is_one_take() -> None:
    for reply in (REPLIES[4], "Abrí el informe de ventas del mes, como pediste.", "Hola, ¿qué tal?"):
        units = Speech._units(reply)
        joined = [f"{units[0]} {units[1]}", *units[2:]] if len(units) > 1 and len(units[0].split()) <= 3 else units
        assert _takes(reply) == joined


def test_a_clause_pauses_less_than_a_sentence() -> None:
    assert voice_output._gap("Abrí el informe de ventas del mes,") == GAP_CLAUSE_S < GAP_S
    assert voice_output._gap("Encontré tres archivos con ese nombre:") == GAP_CLAUSE_S
    assert voice_output._gap("y lo dejé en el escritorio.") == GAP_S
    assert voice_output._gap("¿Quieres que lo revise?") == GAP_QUESTION_S


# --- in the stream: the clause is synthesized once it is closed, and used by the answer --------------------------------

def _voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthesized: list[str], played: list[str]) -> Speech:
    for name in voice_output._MODEL_FILES:
        (tmp_path / name).write_bytes(b"")
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(tmp_path))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(Speech, "_synthesize", lambda self, text, pause=True: synthesized.append(text) or text)
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda *spoken: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    return speech


def _until(condition) -> None:
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)


def test_a_closed_first_clause_is_foreseen_before_its_sentence_ends_and_sounds_with_its_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    assert not speech.foresee("Abrí el informe de ventas del mes,", False)    # its space is not written yet
    assert not speech.foresee("Abrí el informe de ventas del mes, y lo dejé", False)  # three words after it
    assert speech.foresee("Abrí el informe de ventas del mes, y lo dejé en", False)
    _until(lambda: synthesized)
    assert synthesized == ["Abrí el informe de ventas del mes,"] and played == []
    assert speech.speak(REPLIES[0])
    _until(lambda: len(played) == 2)
    assert played == ["Abrí el informe de ventas del mes,", "y lo dejé en el escritorio."]
    assert synthesized == played  # the clause was not synthesized again


def test_without_a_clause_to_end_at_the_stream_waits_for_the_sentence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    whole = "Listo, Spotify está abierto y sonando en tu PC."
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    assert not speech.foresee(whole[:-4], False)
    assert speech.foresee(whole, True)
    _until(lambda: synthesized)
    assert synthesized == [spoken(whole)]
