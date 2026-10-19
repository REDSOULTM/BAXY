"""bench_e2e.utterances: the final answer after a confirmation carries its own first sound (E027 s1, 2026-10-19: an
answer heard for 4.3 s had first_audio_ms null and Test-Spoken read it as not spoken), and the turn's response speed
still reads the confirmation question."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402

QUESTION = "¿Borro viejo.txt de tu carpeta de trabajo y lo dejo en la Papelera de reciclaje?"
ANSWER = "Vale, viejo.txt queda en la carpeta de trabajo."


def confirmation_turn() -> list:
    # The order the conductor wrote in nb-e027-l3-e0a7d9923-s1 (t_ms relative): the question sounds, the person's «no»
    # cuts it, the final answer sounds to its end.
    return [
        {"type": "turn.start", "t_ms": 27450, "input": {"text": "borra el archivo viejo.txt"}},
        {"type": "message", "speaker": "person", "t_ms": 27450},
        {"type": "speech.start", "t_ms": 31531, "text": QUESTION, "notice": False},
        {"type": "turn.end", "t_ms": 31540},
        {"type": "turn.start", "t_ms": 31608, "input": {"text": "no"}},
        {"type": "message", "speaker": "person", "t_ms": 31608},
        {"type": "speech.end", "t_ms": 31667, "text": QUESTION},
        {"type": "speech.start", "t_ms": 34763, "text": ANSWER, "notice": False},
        {"type": "turn.end", "t_ms": 34763},
        {"type": "speech.end", "t_ms": 39078, "text": ANSWER},
    ]


def replies() -> list:
    return [{"turn": 1, "text": ANSWER, "asked_confirmation": True, "confirmation_text": QUESTION, "answered": "no"}]


def test_the_answer_after_a_confirmation_has_its_own_first_sound():
    speech = bench_e2e.utterances(confirmation_turn(), [0], replies())
    final = next(s for s in speech if s["kind"] == "final")
    assert final["spoken_text"] == ANSWER
    assert final["first_audio_ms"] == 34763 - 27450
    assert final["completed"] and not final["cancelled"]


def test_the_question_cut_by_the_answer_is_cancelled_and_still_first():
    speech = bench_e2e.utterances(confirmation_turn(), [0], replies())
    question = speech[0]
    assert question["kind"] == "confirmation"
    assert question["first_audio_ms"] == 31531 - 27450
    assert question["cancelled"] and question["stop_latency_ms"] == 31667 - 31608
    # The turn's response speed (judge_case: the first non-notice sound) is still the question's.
    response = [s["first_audio_ms"] for s in speech if s["first_audio_ms"] is not None and s["kind"] != "progress"]
    assert response[0] == 31531 - 27450


def test_a_second_final_utterance_has_no_first_sound_of_its_own():
    events = [
        {"type": "turn.start", "t_ms": 0, "input": {"text": "hola"}},
        {"type": "speech.start", "t_ms": 900, "text": "Un momento.", "notice": True},
        {"type": "speech.end", "t_ms": 1500, "text": "Un momento."},
        {"type": "speech.start", "t_ms": 3000, "text": "Primera frase.", "notice": False},
        {"type": "speech.end", "t_ms": 4000, "text": "Primera frase."},
        {"type": "speech.start", "t_ms": 4100, "text": "Segunda frase.", "notice": False},
        {"type": "speech.end", "t_ms": 5000, "text": "Segunda frase."},
    ]
    speech = bench_e2e.utterances(events, [0], [{"turn": 1, "text": "x", "confirmation_text": "", "answered": None}])
    assert [s["kind"] for s in speech] == ["progress", "final", "final"]
    assert [s["first_audio_ms"] for s in speech] == [900, 3000, None]
