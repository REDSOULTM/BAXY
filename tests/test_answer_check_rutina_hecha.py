"""Rule «routine_not_done», INT36G (banco de «borra la de las 10:00», Esencial: «Borrad. La rutina de las 10:00 ya
estaba activa y se ha eliminado.» tras un schedule_alarms cancel fallido, sin ninguna llamada que la borrara). A routine
told deleted, turned off or changed in a turn with no completed baxy.routines call: the fact goes back to the model."""
import json

from baxy_mind.answer_check import check

CANCEL = {"op": "schedule.alarms", "tool": "schedule_alarms", "arguments": {"action": "cancel", "at": "10:00"},
          "observation": json.dumps({"status": "failed", "error": "alarm_not_found", "observed": {"alarms": []}}),
          "outcome": "falló", "completed": False, "read": False}
DELETED = {"op": "baxy.routines", "tool": "baxy_routines", "arguments": {"action": "delete", "name": "r-1"},
           "observation": json.dumps({"status": "completed", "verification": "readback", "observed": {"deleted": {}}}),
           "outcome": "completado y verificado", "completed": True, "read": False}


def _found(answer: str, receipts: list[dict]) -> list[dict]:
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f for f in check(answer, "borra la de las 10:00", receipts, session) if f["rule"] == "routine_not_done"]


def test_a_routine_told_deleted_with_no_call_that_deleted_it_is_found() -> None:
    for answer in ("Borrad. La rutina de las 10:00 ya estaba activa y se ha eliminado.", "Ya borré la rutina de las 10:00.",
                   "Ya no existe la rutina de las 10:00.", "I deleted your 7:30 routine.", "Desactivé tu rutina del café."):
        found = _found(answer, [CANCEL])
        assert [f["rule"] for f in found] == ["routine_not_done"], answer
        assert "baxy_routines" in found[0]["fact"], answer


def test_true_or_unclaimed_answers_are_left_alone() -> None:
    assert _found("Borré la rutina «10:00».", [DELETED]) == []
    for answer in ("No borré ninguna rutina.", "¿Quieres que borre la rutina de las 10:00?",
                   "No hay alarmas activas, pero la rutina sí está guardada.", "Borré la alarma de las 10:00."):
        assert _found(answer, [CANCEL]) == [], answer


def test_int37b_the_forms_the_4b_wrote_in_the_same_conversation_are_found() -> None:
    """INT37B (banco corregido, Completo, la rutina creada en la misma conversación y otra guardada; tras un
    schedule_alarms cancel fallido, sin ninguna llamada que la borrara): 4 de 10 filas lo dijeron así."""
    for answer in ("Borrada la rutina de las 10:00. ¿Quieres que borre también la de las 20:00?",
                   "Borrad la rutina de las 10:00. ¿Quieres que borre también la de las 20:00?",
                   "Borrada. La rutina de las 10:00 ya estaba puesta para los lunes, miércoles y viernes; ahora está borrada.",
                   "No había alarma. Borrada la rutina de las 10:00."):
        found = _found(answer, [CANCEL])
        assert [f["rule"] for f in found] == ["routine_not_done"], answer


def test_int37b_true_answers_of_the_same_turns_are_left_alone() -> None:
    for answer in ("No se borró porque no es una alarma, es una rutina. ¿Quieres que la borre?",
                   "No se borró nada porque no había alarma a las 10:00, sino una rutina. ¿Quieres que la borre?",
                   "No hay alarma a las 10:00, pero sí una rutina que se ejecuta a esa hora. ¿Quieres que la borre?"):
        assert _found(answer, [CANCEL]) == [], answer
