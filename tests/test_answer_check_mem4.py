"""MEM4 (REM7 D-1): with BAXY's memory switched off and 4 records kept, «¿qué tienes guardado de mí?» → «No tengo nada
guardado de ti porque la memoria está apagada» (23 of 30 on the bench, Esencial and Completo). Off, the store keeps its
records and nothing reads them: a claim that nothing is kept of the person has no read behind it, as «recuerdo que…» has
none in ``unread_memory``. The check compares shapes: the claim's form and that no memory read completed; the model writes
its answer again (nothing is cut out of it)."""
import json

from baxy_mind.answer_check import check

ASKED = "¿Qué tienes guardado de mí?"


def _rules(answer: str, *, off: bool = True, session: list | None = None, receipts: list | None = None) -> list[str]:
    return [f["rule"] for f in check(answer, ASKED, receipts or [], [] if session is None else session, memory_off=off)
            if f["rule"] == "memory_off_empty"]


def test_saying_nothing_is_kept_with_the_memory_off_is_a_finding() -> None:
    for answer in ("No tengo nada guardado de ti porque la memoria está apagada.",
                   "Como la memoria está apagada, no recuerdo nada de ti.",
                   "No tengo información guardada sobre ti, ya que mi memoria está desactivada.",
                   "No, nada está guardado sobre ti.",
                   "No sé nada de vos.",
                   "I don't have anything saved about you because my memory is off."):
        assert _rules(answer) == ["memory_off_empty"], answer
    found = check("No tengo nada guardado de ti.", ASKED, [], [], memory_off=True)
    assert "apagada" in found[0]["fact"] and "no sabes" in found[0]["fact"], found


def test_saying_it_cannot_be_read_now_is_not() -> None:
    for answer in ("Con la memoria apagada no puedo leer lo que tengo guardado. ¿Quieres que la encienda?",
                   "Mi memoria está apagada, así que ahora no puedo ver qué hay guardado de ti.",
                   "La memoria está apagada, ¿te gustaría que la encienda?"):
        assert _rules(answer) == [], answer


def test_with_the_memory_on_or_after_a_read_it_is_not() -> None:
    # On, a «no lo tengo guardado» is the other rules' (empty_lookup, unread_memory): not this one.
    assert _rules("No tengo nada guardado de ti.", off=False) == []
    # A read that completed and brought nothing backs it (the memory was on by then).
    read = {"op": "memory.recall", "tool": "memory_recall", "arguments": {"query": "persona"},
            "observation": json.dumps({"status": "failed", "error": "memory_none"}), "outcome": "failed"}
    assert _rules("No tengo nada guardado de ti.", session=[("memory.recall", True, True)], receipts=[read]) == []


def test_a_turn_with_the_memory_off_says_nothing_kept_is_written_again(tmp_path) -> None:
    from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, REST, SETTINGS
    from test_mind_final import _mind, _say

    mind, server = _mind(tmp_path, [
        _say("No tengo nada guardado de ti porque la memoria está apagada."),
        _say("Con la memoria apagada no puedo leer lo que tengo guardado de ti. ¿Quieres que la encienda?"),
    ])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST],
                    "memoryOff": True})
    reply = mind.decide(1, ASKED)
    assert reply.get("reply") == ("Con la memoria apagada no puedo leer lo que tengo guardado de ti. "
                                  "¿Quieres que la encienda?"), reply
    assert "memory_off_empty" in (tmp_path / "turns.jsonl").read_text(encoding="utf-8")


def test_a_later_turn_is_read_too(tmp_path) -> None:
    # REM7 D1-D5: «Desactiva la memoria.» first, the question second; ``unread_memory`` reads only the first turn.
    from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, REST, SETTINGS
    from test_mind_final import _mind, _say

    mind, server = _mind(tmp_path, [
        _say("La memoria ya está apagada."),
        _say("Como la memoria está apagada, no tengo nada guardado de ti."),
        _say("Con la memoria apagada no puedo leerla. ¿La enciendo?"),
    ])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST],
                    "memoryOff": True})
    mind.decide(1, "Desactiva la memoria.")
    reply = mind.decide(2, "¿Y qué tienes guardado de mí?")
    assert reply.get("reply") == "Con la memoria apagada no puedo leerla. ¿La enciendo?", reply


def _receipt(op: str, observed: dict, *, read: bool = True) -> dict:
    # The mind's receipt: «outcome» is its words («completado y verificado»), «completed» the flag (mind._outcome).
    return {"op": op, "tool": op.replace(".", "_"), "arguments": {},
            "observation": json.dumps({"status": "completed", "observed": observed}),
            "outcome": "completado y verificado", "completed": True, "read": read}


def test_rem8_m3_a_memory_read_that_completed_in_the_turn_counts() -> None:
    # REV16 M-3: the turn's read was looked for as outcome == "completed", which the mind never writes: a recall that
    # completed in this turn was not seen when the session is not known whole.
    recall = _receipt("memory.recall", {"records": []})
    assert [f["rule"] for f in check("No tengo nada guardado de ti.", ASKED, [recall], None, memory_off=True)
            if f["rule"] == "memory_off_empty"] == []
    assert _rules("No tengo nada guardado de ti.", receipts=[recall], session=[("memory.recall", True, True)]) == []


def test_rem8_m3_a_session_not_known_whole_says_nothing_of_reads_that_may_have_been() -> None:
    # As every other memory rule (check's contract): with session None, a read may have been earlier; nothing is said.
    assert [f["rule"] for f in check("No tengo nada guardado de ti.", ASKED, [], None, memory_off=True)
            if f["rule"] == "memory_off_empty"] == []


def test_rem8_m1_the_honest_doubt_its_own_fact_asks_for_is_not_a_finding() -> None:
    # REV16 M-1: MEMORY_OFF_FACT asks «no sabes si los hay ni cuáles; dilo así», and the rule struck exactly that.
    for answer in ("La memoria está apagada, así que no sé si tengo algo guardado de ti.",
                   "Con la memoria apagada no sé qué tengo guardado de ti.",
                   "No hay forma de saber si tengo recuerdos tuyos mientras la memoria esté apagada.",
                   "My memory is off, so I don't know whether I have anything saved about you.",
                   "I don't know if I have anything stored about you while my memory is off."):
        assert _rules(answer) == [], answer


def test_rem8_m2_a_true_no_of_another_tool_is_not_a_finding() -> None:
    # REV16 M-2 (sondas de REV16 y su subagente M; puerta INT33K u121-B10): with the memory off, as it is born, a «no hay»
    # that another tool's completed read backs, or that is not of what the memory keeps, was struck.
    cases = [
        ("¿Tengo correos nuevos?", "No tengo ningún correo nuevo tuyo en la bandeja.",
         [_receipt("email.read", {"messages": []})]),
        ("¿Dónde dejé mi currículum?", "No hay ningún archivo con tu currículum en Documentos.",
         [_receipt("files.search", {"files": []})]),
        ("¿Me escribió alguien por WhatsApp?", "No tengo ningún mensaje nuevo tuyo en WhatsApp.",
         [_receipt("app.read", {"text": ""})]),
        ("¿Tengo alguna alarma puesta?", "No tengo ninguna alarma tuya guardada.",
         [_receipt("alarm.list", {"alarms": []})]),
        ("¿Tengo citas mañana?", "Tu agenda no la veo desde aquí; no hay información de tus citas para mañana.", []),
        ("¿Qué tengo en mi calendario el viernes?", "No tengo ninguna cita tuya para el viernes.",
         [_receipt("calendar.list", {"events": []})]),
    ]
    for request, answer, receipts in cases:
        session = [(r["op"], True, True) for r in receipts]
        assert [f["rule"] for f in check(answer, request, receipts, session, memory_off=True)
                if f["rule"] == "memory_off_empty"] == [], answer


def test_rem8_what_the_memory_keeps_is_still_a_finding() -> None:
    # The controls: a denial of what is kept of the person, with no memory read, still is, also after another tool's read.
    for answer in ("No tengo nada guardado de ti.",
                   "No recuerdo nada de lo que me dijiste ayer.",
                   "No tengo ningún dato tuyo.",
                   "No tengo información sobre ti.",
                   "I have nothing saved about you."):
        assert _rules(answer) == ["memory_off_empty"], answer
    # An act of another tool (not a read) backs no «no hay».
    note = _receipt("note.create", {"created": True}, read=False)
    assert [f["rule"] for f in check("No tengo nada guardado de ti en mi memoria.", ASKED, [note],
                                     [("note.create", True, False)], memory_off=True)
            if f["rule"] == "memory_off_empty"] == ["memory_off_empty"]
