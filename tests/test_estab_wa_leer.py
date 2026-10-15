"""Encargo WA-LEER: «en WhatsApp leé lo último que me escribió Abuela» read from the lines of a chat drawn without an
accessible tree (semantic cu_chat_lines), over a real frozen view.

The view is the chat «Abuela» opened on redpc on 2026-10-14 (WhatsApp Desktop, 1938×1098, Windows OCR of the window's
own drawing, one pass, every line where it was read): only the lines from x ≥ 0.2 are kept (the conversation, the header
and the chat list's column of times and dates; the list's names and previews of other chats are left out). In that chat
every bubble is the person's («Holaaa», thirteen «prueba BAXY imp»), on the right; older messages stay on the phone.
The contracases put a bubble of Abuela's on the left with the geometry of a received bubble read on the same window
(x 0.3323, its time right after its text).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_chat_lines, cu_finals  # noqa: E402
from baxy_mind.semantic import app_places  # noqa: E402

_ASKED = "leé lo último que me escribió Abuela"

_ABUELA_VIEW = [
    {"text": "x", "x": 0.9773, "y": 0.0191, "w": 0.0062, "h": 0.0109},
    {"text": "Abuela", "x": 0.3323, "y": 0.0683, "w": 0.032, "h": 0.0137},
    {"text": "haz clic aquí para ver la información de contacto", "x": 0.3328, "y": 0.092, "w": 0.1796, "h": 0.0146},
    {"text": "x", "x": 0.2534, "y": 0.143, "w": 0.0067, "h": 0.0118},
    {"text": "4:51", "x": 0.2487, "y": 0.3087, "w": 0.0134, "h": 0.01},
    {"text": "Ayer", "x": 0.2482, "y": 0.4454, "w": 0.0155, "h": 0.0128},
    {"text": "15/9/2026", "x": 0.2255, "y": 0.582, "w": 0.0361, "h": 0.0109},
    {"text": "15/9/2026", "x": 0.2255, "y": 0.6685, "w": 0.0361, "h": 0.0109},
    {"text": "4/6/2026", "x": 0.2291, "y": 0.755, "w": 0.0325, "h": 0.0109},
    {"text": "17/5/2026", "x": 0.2255, "y": 0.8415, "w": 0.0361, "h": 0.0109},
    {"text": "Haz clic aquí para obtener mensajes anteriores de tu teléfono.", "x": 0.5273, "y": 0.133, "w": 0.2208,
     "h": 0.0146},
    {"text": "5/2/2026", "x": 0.6218, "y": 0.1876, "w": 0.032, "h": 0.0109},
    {"text": "Ayer", "x": 0.6295, "y": 0.2814, "w": 0.016, "h": 0.0128},
    {"text": "Hoy", "x": 0.6311, "y": 0.4973, "w": 0.0134, "h": 0.0128},
    {"text": "Escribe un mensaje", "x": 0.354, "y": 0.9426, "w": 0.0831, "h": 0.0164},
    {"text": "Holaaa", "x": 0.8839, "y": 0.2322, "w": 0.0284, "h": 0.0128},
    {"text": "17:18", "x": 0.9164, "y": 0.2413, "w": 0.0186, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8411, "y": 0.3251, "w": 0.0712, "h": 0.0164},
    {"text": "23:12", "x": 0.9159, "y": 0.3352, "w": 0.0191, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8411, "y": 0.3661, "w": 0.0712, "h": 0.0164},
    {"text": "23:13", "x": 0.9159, "y": 0.3761, "w": 0.0191, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8411, "y": 0.4071, "w": 0.0712, "h": 0.0164},
    {"text": "23:17", "x": 0.9159, "y": 0.4171, "w": 0.0191, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8411, "y": 0.4481, "w": 0.0712, "h": 0.0164},
    {"text": "23:18", "x": 0.9159, "y": 0.4581, "w": 0.0191, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.5419, "w": 0.0712, "h": 0.0164},
    {"text": "0:13", "x": 0.9205, "y": 0.551, "w": 0.0144, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.5829, "w": 0.0712, "h": 0.0164},
    {"text": "0:14", "x": 0.9205, "y": 0.592, "w": 0.0144, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.6239, "w": 0.0712, "h": 0.0164},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.6648, "w": 0.0712, "h": 0.0164},
    {"text": "0:20", "x": 0.9205, "y": 0.674, "w": 0.0144, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.7058, "w": 0.0712, "h": 0.0164},
    {"text": "0:25", "x": 0.9205, "y": 0.7149, "w": 0.0144, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.7468, "w": 0.0712, "h": 0.0164},
    {"text": "0:26", "x": 0.9205, "y": 0.7559, "w": 0.0144, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.7878, "w": 0.0712, "h": 0.0164},
    {"text": "4:43", "x": 0.92, "y": 0.7969, "w": 0.015, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.8288, "w": 0.0712, "h": 0.0164},
    {"text": "4:47", "x": 0.92, "y": 0.8379, "w": 0.015, "h": 0.01},
    {"text": "prueba BAXY imp", "x": 0.8452, "y": 0.8698, "w": 0.0712, "h": 0.0164},
    {"text": "4:51", "x": 0.92, "y": 0.8789, "w": 0.0139, "h": 0.01},
    {"text": "4/4/2026", "x": 0.2291, "y": 0.9281, "w": 0.0325, "h": 0.0109},
]


def _seen(lines: list[dict], question: str = _ASKED) -> dict:
    return {"question": question, "reached": True, "application": "WhatsApp", "chatLines": lines, "messages": []}


def _hers(y: float, text: str = "¿venís el domingo?", time: str = "4:52") -> list[dict]:
    return [
        {"text": text, "x": 0.3323, "y": y, "w": 0.0857, "h": 0.0164},
        {"text": time, "x": 0.4217, "y": y + 0.0091, "w": 0.0144, "h": 0.01},
    ]


def _without_bubble_at(y: float) -> list[dict]:
    return [line for line in _ABUELA_VIEW if not (line["x"] > 0.8 and abs(line["y"] - y) < 0.012)]


def test_the_real_view_every_bubble_is_the_persons_and_none_is_abuelas() -> None:
    region = app_places.conversation("WhatsApp")
    read = cu_chat_lines.bubbles(_ABUELA_VIEW, region)
    # Fourteen bubbles drawn; one time («0:19») was not read, so thirteen close, every one the person's.
    assert len(read) == 13 and {bubble.side for bubble in read} == {"own"}
    assert (read[0].texts, read[0].time) == (("Holaaa",), "17:18")
    assert (read[-1].texts, read[-1].time) == (("prueba BAXY imp",), "4:51")
    assert cu_finals.question_answer(_seen(_ABUELA_VIEW), english=False) == (
        "En lo que muestra el chat no hay mensajes de Abuela.")


def test_her_last_bubble_on_the_left_is_quoted_with_its_time() -> None:
    lines = _without_bubble_at(0.8698) + _hers(0.8698)
    assert cu_finals.question_answer(_seen(lines), english=False) == (
        "Lo último que te escribió Abuela fue «¿venís el domingo?» (4:52).")


def test_contracase_the_persons_bubbles_after_hers_are_not_hers() -> None:
    # Abuela wrote at 0:26; the person wrote three more after it, on the right: hers is still the one quoted.
    lines = _without_bubble_at(0.7468) + _hers(0.7468, "ya llegué", "0:26")
    assert cu_finals.question_answer(_seen(lines), english=False) == (
        "Lo último que te escribió Abuela fue «ya llegué» (0:26).")


def test_contracase_an_empty_panel_says_nothing_could_be_read() -> None:
    # The chat drawn without its bubbles yet (header, list column, separators): nothing is quoted nor denied.
    empty = [line for line in _ABUELA_VIEW if not line["x"] > 0.8]
    assert cu_chat_lines.last_written(empty, app_places.conversation("WhatsApp")) is None
    assert cu_finals.question_answer(_seen(empty), english=False) == (
        "En lo que muestra el chat no pude leer ningún mensaje de Abuela.")


def test_a_list_date_between_a_bubble_and_its_time_neither_joins_nor_parts_them() -> None:
    # A narrow window (the notebook's: the chat list reaches x≈0.35): the list's «Ayer» is read between the text of her
    # bubble and its time. Before, «Ayer» took the time («fue «Ayer» (21:07)») and her bubble lost it.
    region = app_places.conversation("WhatsApp")
    lines = [
        {"text": "llego a las ocho", "x": 0.372, "y": 0.640, "w": 0.090, "h": 0.015},
        {"text": "Ayer", "x": 0.304, "y": 0.648, "w": 0.019, "h": 0.014},
        {"text": "21:07", "x": 0.466, "y": 0.652, "w": 0.020, "h": 0.011},
    ]
    assert [(bubble.texts, bubble.time) for bubble in cu_chat_lines.bubbles(lines, region)] == [
        (("llego a las ocho",), "21:07")]
    # Contracase: the list's date on the row of the person's bubble time, across the window, closes no bubble.
    own = [
        {"text": "prueba BAXY imp", "x": 0.812, "y": 0.457, "w": 0.087, "h": 0.018},
        {"text": "Ayer", "x": 0.304, "y": 0.471, "w": 0.019, "h": 0.014},
        {"text": "23:14", "x": 0.903, "y": 0.478, "w": 0.023, "h": 0.011},
    ]
    assert [(bubble.side, bubble.texts) for bubble in cu_chat_lines.bubbles(own, region)] == [
        ("own", ("prueba BAXY imp",))]
    assert cu_finals.question_answer(_seen(own), english=False) == "En lo que muestra el chat no hay mensajes de Abuela."
