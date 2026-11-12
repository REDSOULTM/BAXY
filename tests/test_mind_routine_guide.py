"""RUT7 (leader's order 2026-11-11, ENCARGO_RUT7; documentacion/RUTINAS.md §5 d): the person's routines are made,
listed, turned on or off and deleted by BAXY itself with fixed questions and fixed orders, by voice, without the model
writing a call. The order of a routine is the person's words, whole; nothing is done while it is made and only the last
«sí» saves."""
import datetime
import json
from pathlib import Path

import pytest

from baxy_mind import routine_guide
from baxy_mind.routine_guide import Guide, When, heard, spoken
from test_mind_final import _call, _mind, _say

HEADSET = {"id": "r-000001", "name": "audifonos", "trigger": {"phrase": "audífonos"}, "active": True, "steps": [],
           "order": "cambia a los audífonos Kessler"}
MORNING = {"id": "r-000002", "name": "buen dia", "trigger": {"at": "10:00", "repeat": "daily", "days": []},
           "active": True, "steps": [{"say": "buen día, hoy es otro día"}]}
STEPS = {"id": "r-000003", "name": "siguiente", "trigger": {"phrase": "siguiente"}, "active": False,
         "steps": [{"op": "media.control", "arguments": {"action": "next"}}]}


def _guide_mind(tmp_path: Path, replies: list, routines: list | None = None):
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op = {"baxy_routines": "baxy.routines", "media_control": "media.control",
                       "schedule_alarms": "schedule.alarms"}
    mind.routines = routines or []
    return mind, server


def _receipt(observed: dict) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": observed})


def _failed(error: str, **observed) -> str:
    return json.dumps({"status": "failed", "error": error, "observed": observed})


def _talk(mind, words: list[str], first: int = 1) -> list[dict]:
    return [mind.decide(first + index, said) for index, said in enumerate(words)]


# ---------------------------------------------------------------------------------------------------------------------
# The time as people say it
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("said", "clock", "repeat", "days", "offset"), [
    ("a las diez y media de la mañana", "10:30", None, (), None),
    ("10 pm", "22:00", None, (), None),
    ("10pm", "22:00", None, (), None),
    ("a las 10 p. m.", "22:00", None, (), None),
    ("a las 20:30", "20:30", None, (), None),
    ("a las 7:05 am", "07:05", None, (), None),
    ("a las ocho menos cuarto de la tarde", "19:45", None, (), None),
    ("a las once de la noche", "23:00", None, (), None),
    ("a las 12 de la noche", "00:00", None, (), None),
    ("a las 12 del día", "12:00", None, (), None),
    ("al mediodía", "12:00", None, (), None),
    ("a medianoche", "00:00", None, (), None),
    ("a las 15 horas", "15:00", None, (), None),
    ("todos los días a las 8 de la mañana", "08:00", "daily", (), None),
    ("de lunes a viernes a las siete y cuarto de la mañana", "07:15", "days", (0, 1, 2, 3, 4), None),
    ("los fines de semana a las 9 y veinte de la mañana", "09:20", "days", (5, 6), None),
    ("los lunes y miércoles a las 6 de la tarde", "18:00", "days", (0, 2), None),
    ("mañana a las 7 de la mañana", "07:00", "once", (), 1),
    ("mañana por la mañana a las 7", "07:00", "once", (), 1),
    ("esta noche a las 9", "21:00", "once", (), 0),
    ("solo una vez, a las 5 de la tarde", "17:00", "once", (), None),
    ("every day at 9 am", "09:00", "daily", (), None),
    ("at half past seven in the morning, on weekdays", "07:30", "days", (0, 1, 2, 3, 4), None),
    ("quarter to nine at night", "20:45", None, (), None),
    ("Monday to Thursday at 6:30 pm", "18:30", "days", (0, 1, 2, 3), None),
    ("tomorrow at noon", "12:00", "once", (), 1),
])
def test_a_time_and_its_days_as_people_say_them(said: str, clock: str, repeat, days: tuple, offset) -> None:
    found = spoken(said)
    assert found is not None
    assert (found.clock(), found.repeat, found.days, found.offset) == (clock, repeat, days, offset)


@pytest.mark.parametrize(("said", "hour", "repeat", "days", "offset"), [
    ("a las 10", 10, None, (), None),            # which half of the day is asked, never assumed
    ("a las once", 11, None, (), None),
    ("todos los días a las 10", 10, "daily", (), None),
    ("los lunes y miércoles", None, "days", (0, 2), None),
    ("de lunes a viernes", None, "days", (0, 1, 2, 3, 4), None),
    ("mañana", None, "once", (), 1),
    ("todos los días", None, "daily", (), None),
    ("una vez", None, "once", (), None),
    ("once", None, "once", (), None),
])
def test_a_part_said_is_kept_and_the_part_missing_stays_unknown(said: str, hour, repeat, days: tuple, offset) -> None:
    found = spoken(said)
    assert found is not None and found.clock() is None
    assert (found.hour, found.repeat, found.days, found.offset) == (hour, repeat, days, offset)


@pytest.mark.parametrize("said", ["en 10 minutos", "cada 2 horas", "a las 10 y a las 11", "cuando llegue a casa",
                                  "a las 15 de la mañana", "mañana todos los días a las 8 de la mañana", "a las 25", "",
                                  "tres veces", "a las 10:75", "después de almorzar", "in a while", "every 2 hours",
                                  "a las ocho de la mañana y de la tarde"])
def test_what_is_not_understood_whole_is_not_guessed(said: str) -> None:
    assert spoken(said) is None


# ---------------------------------------------------------------------------------------------------------------------
# The guide, question by question
# ---------------------------------------------------------------------------------------------------------------------

def test_a_word_routine_is_made_by_voice_without_the_model(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["Baxy, crea una rutina", "con una palabra", "audífonos", "cambia a los audífonos Kessler"])
    assert [r["kind"] for r in said] == ["conversation"] * 4
    assert [r["reply"] for r in said] == [
        "¿Con una palabra tuya o a una hora?", "¿Qué palabra vas a decir?", "¿Qué quieres que haga cuando la digas?",
        "Cuando digas «audífonos»: «cambia a los audífonos Kessler». ¿La guardo?"]
    saved = mind.decide(5, "sí")
    assert saved["kind"] == "action" and saved["operation"] == "baxy.routines"
    assert saved["arguments"] == {"action": "create", "phrase": "audífonos", "order": "cambia a los audífonos Kessler"}
    done = mind.continue_turn(6, _receipt({"routine": HEADSET, "saved": True, "runsWhen": "the person says it"}))
    assert done["kind"] == "conversation"
    assert done["reply"] == "Guardada. Cuando digas «audífonos», hago lo que pediste. Ahora no hice nada de eso."
    assert server.bodies == []  # the model was never asked
    assert mind._guide is None


@pytest.mark.parametrize(("word", "order"), [
    ("tiempo", "reproduce o pausa la música"),
    ("pantalla", "desactiva la pantalla de la izquierda"),
    ("audífonos", "cambia a los audífonos"),
    ("altavoces", "cambia a los altavoces"),
])
def test_the_owners_word_examples_by_the_guide(tmp_path: Path, word: str, order: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["Baxy, nueva rutina", "con una palabra", word, order])
    assert said[-1]["reply"] == f"Cuando digas «{word}»: «{order}». ¿La guardo?"
    saved = mind.decide(5, "sí")
    assert saved["operation"] == "baxy.routines"
    assert saved["arguments"] == {"action": "create", "phrase": word, "order": order}
    assert server.bodies == []  # the model was never asked


def test_a_timed_routine_is_made_by_voice_and_the_half_of_the_day_is_asked(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["nueva rutina", "a una hora", "todos los días a las 10", "de la mañana",
                        "buen día, hoy es otro día"])
    assert [r["reply"] for r in said] == [
        "¿Con una palabra tuya o a una hora?", "¿A qué hora, y qué días?", "¿A las 10:00 de la mañana o de la tarde?",
        "¿Qué quieres que te diga?",
        "Todos los días a las 10:00 de la mañana, te digo: «buen día, hoy es otro día». ¿La guardo?"]
    saved = mind.decide(6, "sí, guárdala")
    assert saved["arguments"] == {"action": "create", "at": "10:00", "repeat": "daily",
                                  "steps": ["say: buen día, hoy es otro día"]}
    done = mind.continue_turn(7, _receipt({"routine": MORNING, "saved": True, "nextRunLocal": "2026-11-12 10:00",
                                           "scheduledFor": "tomorrow"}))
    assert done["reply"] == ("Guardada. Todos los días a las 10:00 de la mañana te lo digo, sin alarma; si BAXY está "
                             "cerrada, te sale un aviso de Windows. La primera vez, mañana a las 10:00 de la mañana.")
    assert server.bodies == []


def test_the_hour_and_the_days_are_asked_apart_when_one_is_missing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["quiero una rutina", "a una hora", "los lunes y miércoles", "a las 7", "mañana",
                        "saca la basura"])
    assert [r["reply"] for r in said[2:]] == [
        "¿A qué hora?", "¿A las 7:00 de la mañana o de la tarde?", "¿Qué quieres que te diga?",
        "Los lunes y miércoles a las 7:00 de la mañana, te digo: «saca la basura». ¿La guardo?"]
    assert mind.decide(7, "dale")["arguments"] == {"action": "create", "at": "07:00", "repeat": "days",
                                                   "days": ["mon", "wed"], "steps": ["say: saca la basura"]}
    mind2, _ = _guide_mind(tmp_path, [])
    said = _talk(mind2, ["crea una rutina", "a las 8 de la noche", "todos"])
    assert [r["reply"] for r in said[1:]] == [
        "¿Qué días? Puedes decir «todos los días», «de lunes a viernes» o «solo mañana».", "¿Qué quieres que te diga?"]
    assert server.bodies == []


def test_a_day_said_is_saved_as_its_date(tmp_path: Path) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    mind._today = lambda: datetime.date(2026, 11, 11)  # type: ignore[method-assign]
    said = _talk(mind, ["nueva rutina", "mañana a las 7 de la mañana", "llama al dentista"])
    assert said[-1]["reply"] == "Mañana a las 7:00 de la mañana, te digo: «llama al dentista». ¿La guardo?"
    saved = mind.decide(4, "sí")
    assert saved["arguments"] == {"action": "create", "at": "2026-11-12T07:00", "repeat": "once",
                                  "steps": ["say: llama al dentista"]}
    once = {"id": "r-9", "name": "dentista", "trigger": {"at": "07:00", "repeat": "once", "date": "2026-11-12"},
            "active": True, "steps": [{"say": "llama al dentista"}]}
    done = mind.continue_turn(5, _receipt({"routine": once, "saved": True, "nextRunLocal": "2026-11-12 07:00",
                                           "scheduledFor": "tomorrow"}))
    assert done["reply"] == ("Guardada. Te lo digo mañana a las 7:00 de la mañana, una sola vez y sin alarma; si BAXY "
                             "está cerrada, te sale un aviso de Windows.")


@pytest.mark.parametrize("upto", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("word", ["cancela", "Baxy, cancela", "olvídalo", "cancela, por favor"])
def test_cancela_leaves_at_any_step_with_nothing_saved(tmp_path: Path, upto: int, word: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    steps = ["crea una rutina", "con una palabra", "pantalla", "desactiva la pantalla de la izquierda"]
    _talk(mind, steps[:upto + 1] if upto < 4 else steps)
    if upto < 4:
        assert mind._guide is not None
    left = mind.decide(9, word)
    assert left["kind"] == "conversation" and left["reply"] == "Listo, lo dejo: no guardé ninguna rutina."
    assert mind._guide is None and server.bodies == []


def test_cancel_in_a_timed_guide_and_no_at_the_end_save_nothing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "a una hora", "a las 8 de la mañana"])
    assert mind.decide(4, "cancelar")["reply"] == "Listo, lo dejo: no guardé ninguna rutina."
    said = _talk(mind, ["crea una rutina", "con una palabra", "tiempo", "pausa la música"], first=5)
    assert said[-1]["reply"] == "Cuando digas «tiempo»: «pausa la música». ¿La guardo?"
    no = mind.decide(9, "no")
    assert no["kind"] == "conversation" and no["reply"] == "No la guardé." and mind._guide is None
    assert server.bodies == []


def test_an_answer_that_is_not_understood_asks_that_part_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "no sé, lo que tú digas", "a una hora", "cuando llegue del trabajo",
                        "a las 10", "quién sabe", "de la noche", "en 10 minutos", "todos los días", "...",
                        "buenas noches", "puede ser"])
    assert [r["reply"] for r in said[1:]] == [
        "No te entendí. Di «con una palabra» o «a una hora»; o «cancela» para dejarlo.",
        "¿A qué hora, y qué días?",
        "No entendí la hora. Dímela así: «a las ocho de la mañana, todos los días».",
        "¿A las 10:00 de la mañana o de la tarde?",
        "¿A las 10:00 de la mañana o de la tarde?",
        "¿Qué días? Puedes decir «todos los días», «de lunes a viernes» o «solo mañana».",
        "¿Qué días? Puedes decir «todos los días», «de lunes a viernes» o «solo mañana».",
        "¿Qué quieres que te diga?",
        "No te entendí. ¿Qué quieres que te diga a esa hora?",
        "Todos los días a las 10:00 de la noche, te digo: «buenas noches». ¿La guardo?",
        "Di «sí» para guardarla o «no» para dejarla. Todos los días a las 10:00 de la noche, te digo: «buenas noches». "
        "¿La guardo?"]
    assert mind._guide is not None and server.bodies == []
    assert mind.decide(20, "sí")["arguments"]["at"] == "22:00"


def test_a_word_too_long_or_empty_is_asked_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "palabra", "¡...!", "cuando yo te diga que ya me quiero ir a dormir de una vez",
                        "la palabra es buenas noches"])
    assert [r["reply"] for r in said[2:]] == [
        "No entendí la palabra. ¿Qué palabra vas a decir?",
        "Eso es muy largo para decirlo cada vez. Dime una palabra o una frase corta.",
        "¿Qué quieres que haga cuando la digas?"]
    assert mind._guide.phrase == "buenas noches" and server.bodies == []


def test_a_word_that_already_fires_a_routine_is_not_taken(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, STEPS])
    said = _talk(mind, ["crea una rutina", "con una palabra", "Audífonos", "altavoces"])
    assert said[2]["reply"] == "Ya tienes una rutina con «Audífonos». Dime otra palabra, o «cancela»."
    assert said[3]["reply"] == "¿Qué quieres que haga cuando la digas?"
    assert server.bodies == []


@pytest.mark.parametrize("word", ["nueva rutina", "qué rutinas tengo", "borra la rutina", "gracias", "sí", "no",
                                  "desactiva la rutina tiempo"])
def test_a_word_that_is_already_an_order_to_baxy_is_not_taken(tmp_path: Path, word: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "con una palabra", word])
    assert said[2]["reply"] == (f"«{word}» ya es una orden mía y no puede ser el nombre de una rutina. "
                                "Dime otra palabra.")
    assert mind._guide.step == "phrase" and server.bodies == []


def test_while_the_guide_asks_the_words_are_its_answer_and_nothing_else(tmp_path: Path) -> None:
    # The order is kept whole, as said; a routine's own phrase, a fixed order or a one-breath form said as an answer
    # fire nothing and open nothing.
    mind, server = _guide_mind(tmp_path, [], [HEADSET])
    said = _talk(mind, ["crea una rutina", "con una palabra", "cine", "audífonos"])
    assert said[3]["reply"] == "Cuando digas «cine»: «audífonos». ¿La guardo?"
    assert mind.decide(5, "no")["reply"] == "No la guardé."
    said = _talk(mind, ["crea una rutina", "con una palabra", "cine",
                        "Pon el volumen en 30, abre el navegador y dime «listo»."], first=6)
    assert said[3]["reply"] == ("Cuando digas «cine»: «Pon el volumen en 30, abre el navegador y dime «listo».». "
                                "¿La guardo?")
    assert mind.decide(10, "sí")["arguments"]["order"] == "Pon el volumen en 30, abre el navegador y dime «listo»."
    assert server.bodies == []


def test_words_the_ear_was_unsure_of_ask_the_same_question_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "con una palabra"])
    again = mind.decide(3, "pantaya", None, [("pantaya", 0.3)])
    assert again["reply"] == "No te oí bien. ¿Qué palabra vas a decir?"
    assert mind._guide.step == "phrase" and mind._guide.phrase == "" and server.bodies == []


def test_a_guide_left_unanswered_is_dropped_and_the_words_are_a_turn_as_any_other(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Son las tres.")])
    _talk(mind, ["crea una rutina", "con una palabra"])
    mind._guide_at -= 400
    assert mind.decide(3, "qué hora es")["reply"] == "Son las tres."
    assert mind._guide is None and len(server.bodies) == 1


def test_a_new_session_forgets_the_guide(tmp_path: Path) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina"])
    mind.new_session()
    assert mind._guide is None


def test_the_guide_in_english(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["Baxy, new routine", "with a word", "speakers", "switch to the Vantor speakers", "yes"])
    assert [r["reply"] for r in said[:4]] == [
        "With a word of yours or at a time?", "What word will you say?", "What should I do when you say it?",
        "When you say «speakers»: «switch to the Vantor speakers». Shall I save it?"]
    assert said[4]["arguments"] == {"action": "create", "phrase": "speakers", "order": "switch to the Vantor speakers"}
    kept = {"id": "r-7", "name": "speakers", "trigger": {"phrase": "speakers"}, "active": True, "steps": [],
            "order": "switch to the Vantor speakers"}
    done = mind.continue_turn(9, _receipt({"routine": kept, "saved": True}))
    assert done["reply"] == "Saved. When you say «speakers», I'll do what you asked. I haven't done any of it now."
    said = _talk(mind, ["create a routine", "at a time", "every day at half past nine", "at night", "time for bed",
                        "save it"], first=10)
    assert [r["reply"] for r in said[2:5]] == [
        "At 9:30 in the morning or in the afternoon?", "What should I tell you?",
        "Every day at 9:30 PM, I'll tell you: «time for bed». Shall I save it?"]
    assert said[5]["arguments"] == {"action": "create", "at": "21:30", "repeat": "daily", "steps": ["say: time for bed"]}
    assert server.bodies == []


# ---------------------------------------------------------------------------------------------------------------------
# A failed save is said as it is
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("error", "said"), [
    ("routine_duplicate_phrase", "No la guardé: ya tienes una rutina activa con «tiempo»."),
    ("routines_full", "No la guardé: ya tienes el máximo de rutinas. Borra una primero."),
    ("routine_duplicate_name", "No la guardé: ya tienes una rutina con ese nombre."),
])
def test_a_save_the_app_refused_is_said_from_its_receipt(tmp_path: Path, error: str, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "con una palabra", "tiempo", "pausa o reanuda la música", "sí"])
    assert mind.continue_turn(6, _failed(error))["reply"] == said
    assert server.bodies == []


def test_a_receipt_with_no_fixed_sentence_goes_to_the_model(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("No pude guardarla: el disco no dejó escribir.")])
    _talk(mind, ["crea una rutina", "con una palabra", "tiempo", "pausa o reanuda la música", "sí"])
    reply = mind.continue_turn(6, _failed("routines_write_failed"))
    assert reply["reply"] == "No pude guardarla: el disco no dejó escribir." and len(server.bodies) == 1


@pytest.mark.parametrize(("error", "said"), [
    ("routine_time_passed", "No la guardé: esa hora ya pasó."),
    ("routine_scheduler_unavailable", "No la guardé: no pude programarla en Windows."),
    ("routine_task_not_verified", "No la guardé: no pude programarla en Windows."),
    # REV11 B-1: registered, not read back and not taken off: what it may still do is said, and how to stop it.
    ("routine_task_not_removed", ("No la guardé, pero no pude quitar lo que dejé programado en Windows: puede que te lo "
                                  "diga igual. «Olvidar todo», en el panel de memoria, lo quita.")),
])
def test_a_timed_save_that_failed_is_said(tmp_path: Path, error: str, said: str) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "hoy a las 6 de la mañana", "despierta", "sí"])
    assert mind.continue_turn(6, _failed(error))["reply"] == said


# ---------------------------------------------------------------------------------------------------------------------
# The one-breath phrase, split by its form
# ---------------------------------------------------------------------------------------------------------------------

OWNER_WORDS = [
    ("cuando te diga tiempo, reproduce o pausa la música", "tiempo", "reproduce o pausa la música"),
    ("Cuando te diga pantalla, desactiva la pantalla de la izquierda.", "pantalla", "desactiva la pantalla de la izquierda"),
    ("Baxy, cuando te diga audífonos, cambia a los audífonos", "audífonos", "cambia a los audífonos"),
    ("cuando diga «altavoces», cambia a los altavoces", "altavoces", "cambia a los altavoces"),
    ("cada vez que diga modo cine: baja el brillo y pon el volumen en 20", "modo cine", "baja el brillo y pon el volumen en 20"),
    ("cuando yo te diga la palabra descanso, pausa la música", "descanso", "pausa la música"),
    ("Oye Baxy, cuando te diga siesta, pon el volumen en 10", "siesta", "pon el volumen en 10"),
    ("when I say focus, mute the microphone", "focus", "mute the microphone"),
    ("Whenever I say \"lights out\", turn off the left monitor", "lights out", "turn off the left monitor"),
    # a few words may come before it (four at most), and «le diga» is the same said with usted
    ("Baxi, desde hoy, cuando te diga recreo, pon la música en pausa", "recreo", "pon la música en pausa"),
    ("Che Baxy, cuando te diga cueva, apagá el monitor de la izquierda", "cueva", "apagá el monitor de la izquierda"),
    ("Baxy, cuando yo le diga ratico, me pausa la música", "ratico", "me pausa la música"),
    ("Baxy, from today whenever I say hush, pause the music", "hush", "pause the music"),
    # a short question hung at the end («¿vale?», "ok?") asks nothing: it is left out of the order
    ("cuando te diga recreo, pon la música en pausa, ¿vale?", "recreo", "pon la música en pausa"),
    ("when I say hush, pause the music, ok?", "hush", "pause the music"),
]


@pytest.mark.parametrize(("said", "phrase", "order"), OWNER_WORDS)
def test_cuando_diga_x_orden_is_split_by_its_form_and_waits_for_the_si(tmp_path: Path, said: str, phrase: str,
                                                                       order: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    asked = mind.decide(1, said)
    english = "i say" in said.lower()
    assert asked["kind"] == "conversation"  # nothing is done: only the question
    assert asked["reply"] == (f"When you say «{phrase}»: «{order}». Shall I save it?" if english
                              else f"Cuando digas «{phrase}»: «{order}». ¿La guardo?")
    saved = mind.decide(2, "yes" if english else "sí")
    assert saved["operation"] == "baxy.routines"
    assert saved["arguments"] == {"action": "create", "phrase": phrase, "order": order}
    assert server.bodies == []


def test_the_owners_timed_example_in_one_breath(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["todos los días a las 10 dime buen día, hoy es otro día", "de la mañana"])
    assert [r["reply"] for r in said] == [
        "¿A las 10:00 de la mañana o de la tarde?",
        "Todos los días a las 10:00 de la mañana, te digo: «buen día, hoy es otro día». ¿La guardo?"]
    assert mind.decide(3, "sí")["arguments"] == {"action": "create", "at": "10:00", "repeat": "daily",
                                                 "steps": ["say: buen día, hoy es otro día"]}
    mind2, _ = _guide_mind(tmp_path, [])
    whole = mind2.decide(1, "Baxy, de lunes a viernes a las 7:30 de la mañana dime que hay que sacar al perro")
    assert whole["reply"] == ("De lunes a viernes a las 7:30 de la mañana, te digo: «que hay que sacar al perro». "
                              "¿La guardo?")
    mind3, _ = _guide_mind(tmp_path, [])
    english = mind3.decide(1, "every day at 8 am tell me good morning")
    assert english["reply"] == "Every day at 8:00 AM, I'll tell you: «good morning». Shall I save it?"
    assert server.bodies == []


# RUT11 (REV11 B-S1): «cuando te diga qué rutinas tengo, apaga todo» splits cleanly: test_mind_rut11_rutinas says why
# its phrase is not taken and asks only that.
@pytest.mark.parametrize("said", ["cuando te diga algo raro haz lo que quieras", "cuando diga, pausa",
                                  "cuando diga uno dos tres cuatro cinco seis siete, pausa la música",
                                  "Baxy, quiero que cuando te diga cueva me apagues el monitor del lado izquierdo",
                                  "necesito que cada vez que yo le diga ratico me pause lo que suena",
                                  "quiero que cuando te diga cueva me apagues el monitor izquierdo, ¿sale?",
                                  "cuando te diga la calle apúntala en una nota, es sólo para ahora",
                                  "whenever I say your name my cat runs away, it is so funny"])
def test_a_one_breath_phrase_that_does_not_split_cleanly_opens_the_guide_at_its_first_question(tmp_path: Path,
                                                                                               said: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    asked = mind.decide(1, said)
    first = "With a word of yours or at a time?" if "i say" in said.lower() else "¿Con una palabra tuya o a una hora?"
    assert asked["kind"] == "conversation" and asked["reply"] == first
    assert mind._guide.step == "kind" and server.bodies == []


@pytest.mark.parametrize("said", [
    "¿qué pasa cuando te diga pantalla?", "oye, y dime tú qué hago yo cuando diga audífonos, cambia",
    "pon la música de ayer en la sala y cuando te diga basta, para", "no me escuchas cuando te digo las cosas dos veces",
    "cada vez que digo tu nombre se prende también la tele, qué lata", "cuando te diga recreo, ¿qué vas a hacer?",
    "cuando te diga recreo, pausa la música, ¿o prefieres que te lo pida de otra forma?",
    "pon una alarma todos los días a las 10", "recuérdame a las 10 tomar agua",
    "dime qué hora es", "todos los días me levanto a las 7, dime si es tarde", "cuando llegue Marta, dime",
    "no crees una rutina", "qué es una rutina", "crea una rutina para las mañanas", "explícame mis rutinas de sueño"])
def test_other_words_are_the_models_as_always(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Vale.")])
    assert mind.decide(1, said)["reply"] == "Vale."
    assert mind._guide is None and len(server.bodies) == 1
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": said}


def test_after_a_question_of_baxy_the_one_breath_form_is_its_answer_and_a_closed_order_still_is_one(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("¿Qué quieres hacer?"), _say("Entendido."), _say("¿Algo más?")])
    mind.decide(1, "hola")
    assert mind.decide(2, "cuando te diga pantalla, apaga la izquierda")["reply"] == "Entendido."
    assert mind._guide is None
    mind.decide(3, "bien")
    assert mind.decide(4, "crea una rutina")["reply"] == "¿Con una palabra tuya o a una hora?"
    assert len(server.bodies) == 3


# ---------------------------------------------------------------------------------------------------------------------
# List, delete, turn on and off
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["qué rutinas tengo", "Baxy, ¿qué rutinas tengo?", "mis rutinas", "lista mis rutinas",
                                  "what routines do I have?", "borra la rutina"])
def test_the_routines_are_listed_from_the_apps_receipt(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING, STEPS])
    asked = mind.decide(1, said)
    assert asked["kind"] == "action" and asked["operation"] == "baxy.routines" and asked["arguments"] == {"action": "list"}
    told = mind.continue_turn(2, _receipt({"routines": [HEADSET, MORNING, STEPS], "count": 3}))["reply"]
    if said.startswith("what"):
        assert told == ("You have 3 routines: «audífonos» does «cambia a los audífonos Kessler»; every day at 10:00 AM "
                        "I tell you «buen día, hoy es otro día»; «siguiente» (by steps) (off).")
    else:
        assert told == ("Tienes 3 rutinas: «audífonos» hace «cambia a los audífonos Kessler»; todos los días a las 10:00 "
                        "de la mañana te digo «buen día, hoy es otro día»; «siguiente» (por pasos) (desactivada).")
    assert server.bodies == []


def test_no_routines_is_said_so(tmp_path: Path) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    mind.decide(1, "qué rutinas tengo")
    assert mind.continue_turn(2, _receipt({"routines": [], "count": 0}))["reply"] == (
        "No tienes ninguna rutina guardada. Di «nueva rutina» para crear una.")


@pytest.mark.parametrize(("said", "action", "name", "observed", "told"), [
    ("borra la rutina audífonos", "delete", "audífonos", {"deleted": HEADSET}, "Borré la rutina «audifonos»."),
    ("Baxy, borra la rutina de audífonos, por favor", "delete", "audífonos", {"deleted": HEADSET},
     "Borré la rutina «audifonos»."),
    ("desactiva la rutina audífonos", "disable", "audífonos", {"routine": {**HEADSET, "active": False}, "saved": True},
     "Desactivé la rutina «audifonos»."),
    ("activa la rutina Siguiente", "enable", "Siguiente", {"routine": {**STEPS, "active": True}, "saved": True},
     "Activé la rutina «siguiente»."),
    ("delete the routine called buen dia", "delete", "buen dia", {"deleted": MORNING},
     "I deleted the routine «buen dia»."),
])
def test_a_routine_is_deleted_or_turned_on_or_off_by_a_fixed_order(tmp_path: Path, said: str, action: str, name: str,
                                                                   observed: dict, told: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING, STEPS])
    asked = mind.decide(1, said)
    assert asked["kind"] == "action" and asked["operation"] == "baxy.routines"
    assert asked["arguments"] == {"action": action, "name": name}
    assert mind.continue_turn(2, _receipt(observed))["reply"] == told
    assert server.bodies == []


def test_a_name_that_is_no_routine_is_said_with_the_ones_there_are(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "borra la rutina de la tele")
    told = mind.continue_turn(2, _failed("routine_not_found"))["reply"]
    assert told == "No tengo ninguna rutina «tele». Tienes: «audifonos» y «buen dia»."
    mind.routines = []
    mind.decide(3, "desactiva la rutina tele")
    assert mind.continue_turn(4, _failed("routine_not_found"))["reply"] == (
        "No tengo ninguna rutina «tele». No tienes rutinas guardadas.")
    assert server.bodies == []


def test_ejecuta_la_rutina_x_is_saying_x(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Cambié a los audífonos.")], [HEADSET, {**STEPS, "active": True}])
    assert mind.decide(1, "ejecuta la rutina audífonos")["reply"] == "Cambié a los audífonos."
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": "cambia a los audífonos Kessler"}
    run = mind.decide(2, "ejecuta la rutina siguiente")
    assert run["kind"] == "action" and run["arguments"] == {"action": "run", "name": "siguiente"}
    step = mind.continue_turn(3, _receipt({"run": {**STEPS, "active": True}}))
    assert step["kind"] == "action" and step["operation"] == "media.control"


# ---------------------------------------------------------------------------------------------------------------------
# The model no longer writes a routine
# ---------------------------------------------------------------------------------------------------------------------

def test_the_models_own_call_only_opens_the_guide(tmp_path: Path) -> None:
    written = {"action": "create", "phrase": "cine", "steps": ['media_control {"action": "pause"}']}
    mind, server = _guide_mind(tmp_path, [_call("baxy_routines", written)])
    opened = mind.decide(1, "me armas algo para cuando vea películas")
    assert opened["kind"] == "conversation" and opened["reply"] == "¿Con una palabra tuya o a una hora?"
    assert mind._guide is not None and mind._guide.step == "kind" and mind._guide.phrase == ""
    assert mind.decide(2, "con una palabra")["reply"] == "¿Qué palabra vas a decir?"
    assert len(server.bodies) == 1  # the guide's answers are not the model's


def test_a_call_beside_the_models_opening_is_not_run(tmp_path: Path) -> None:
    both = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": "baxy_routines", "arguments": "{}"}},
        {"id": "c2", "function": {"name": "media_control", "arguments": json.dumps({"action": "pause"})}}]}}]}
    mind, server = _guide_mind(tmp_path, [both])
    opened = mind.decide(1, "hazme una rutina que pause la música")
    assert opened["kind"] == "conversation" and opened["reply"] == "¿Con una palabra tuya o a una hora?"
    results = [m for m in mind.conversation if m.get("role") == "tool"]
    assert [json.loads(m["content"]).get("status") for m in results] == ["completed", "not_run"]
    assert json.loads(results[0]["content"])["observed"] == {"guide": "opened", "saved": False}


def test_the_model_reads_no_note_with_the_routines(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Hola.")], [HEADSET, MORNING])
    mind.decide(1, "hola")
    assert all("audífonos" not in str(m.get("content")) for m in server.bodies[0]["messages"])


def test_the_tool_text_says_a_routine_is_asked_for_also_without_its_name() -> None:
    # Asked in words that are none of the forms and do not say «rutina» («quiero que cada vez que diga X hagas Y»),
    # the 4B answered «no puedo crear rutinas» or «entendido» with nothing saved: of 10 such held-out phrases × 2
    # seeds, none opened the guide; with this text 7 of 20 (Esencial; frontier and controls the same; INFORME_RUT7.md).
    data = Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"
    text = json.loads(data.read_bytes())["tools"]["baxy.routines"]
    assert "with or without the word «rutina»" in text
    assert "never answer that it cannot" in text and "never answer that it is set up without this call" in text


def test_without_the_tool_in_the_profile_nothing_here_is_heard(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("No tengo rutinas en este perfil.")])
    mind.wire_to_op = {"media_control": "media.control"}
    assert mind.decide(1, "crea una rutina")["reply"] == "No tengo rutinas en este perfil."
    assert mind._guide is None and len(server.bodies) == 1


# ---------------------------------------------------------------------------------------------------------------------
# The forms, alone
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", [*routine_guide.NEW_ES[:6], "Baxy, quiero crear una rutina, por favor", "Oye, nueva rutina."])
def test_the_closed_orders_that_open_the_guide(said: str) -> None:
    order = heard(said)
    assert order is not None and order.action == "new" and order.guide is not None and order.guide.step == "kind"


def test_heard_is_whole_turn_only() -> None:
    assert heard("crea una rutina y pon música") is None
    assert heard("sabes crear una rutina") is None
    assert heard("") is None and heard("Baxy") is None
    assert heard("borra la rutina audífonos, por favor").name == "audífonos"  # type: ignore[union-attr]
    assert heard("cuando te diga pantalla, apaga la izquierda", whole=True) is None


def test_the_guide_view_says_the_step_in_progress() -> None:
    guide = Guide(step="order", kind="word", phrase="cine")
    assert guide.view() == {"step": "order", "kind": "word", "question": "¿Qué quieres que haga cuando la digas?",
                            "phrase": "cine", "order": None, "say": None, "when": None}


def test_twelve_is_asked_noon_or_night() -> None:
    guide = Guide(step="when", kind="time", when=When(hour=12, repeat="daily"))
    assert guide.question() == "¿A las 12:00 del mediodía o de la noche?"
    assert guide.answer("del mediodía")[0] == "¿Qué quieres que te diga?" and guide.when.clock() == "12:00"
