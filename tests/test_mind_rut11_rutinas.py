"""RUT11 (REV11 B-3, B-4, B-5, B-S1): what the second blind review left open in the routines, by voice."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_final import _say
from test_mind_routine_guide import HEADSET, MORNING, STEPS, _failed, _guide_mind, _receipt, _talk

ORDER = {"id": "r-000004", "name": "buenas noches", "trigger": {"phrase": "buenas noches"}, "active": True, "steps": [],
         "order": "apaga el PC"}


# ---------------------------------------------------------------------------------------------------------------------
# B-3: a question with the whole phrase is not the phrase said
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["¿Buenas noches?", "buenas noches?", "Baxy, ¿buenas noches?", "BUENAS NOCHES???"])
def test_a_question_with_the_whole_phrase_does_not_fire_the_routine(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Buenas noches.")], [ORDER])
    assert mind.decide(1, said)["reply"] == "Buenas noches."
    assert server.bodies[0]["messages"][-1]["content"] == said   # the person's words, not the order


@pytest.mark.parametrize("said", ["buenas noches", "Baxy, buenas noches.", "¡Buenas noches!"])
def test_the_phrase_said_without_a_question_still_fires_it(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Apago el PC.")], [ORDER])
    mind.decide(1, said)
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": "apaga el PC"}


def test_a_question_does_not_run_a_routine_of_steps_either(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("¿Qué quieres que pase?")], [{**STEPS, "active": True}])
    assert mind.decide(1, "¿siguiente?")["kind"] == "conversation" and len(server.bodies) == 1


# ---------------------------------------------------------------------------------------------------------------------
# B-4: delete, turn off and change a routine by voice
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["ya no quiero la rutina audífonos", "Baxy, ya no quiero la rutina de audífonos",
                                  "no quiero la rutina audífonos", "I don't want the routine audífonos anymore"])
def test_ya_no_quiero_la_rutina_x_deletes_it(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    asked = mind.decide(1, said)
    assert asked["kind"] == "action" and asked["arguments"] == {"action": "delete", "name": "audífonos"}
    assert server.bodies == []


def test_a_name_said_as_a_time_in_words_is_no_routine_name(tmp_path: Path) -> None:
    # REM2 (REV13 B-1), INT33F: without rut11's model path a time said in words names no routine: the name goes to
    # RoutinesHandler as said, which finds none (routine_not_found): «buen dia» is not deleted.
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    asked = mind.decide(1, "borra la rutina de las diez de la mañana")
    assert (asked.get("arguments") or {}).get("name") != "buen dia"


@pytest.mark.parametrize("said", ["borra todas mis rutinas", "Baxy, elimina todas las rutinas, por favor",
                                  "delete all my routines"])
def test_deleting_every_routine_asks_its_yes_and_deletes_them_one_by_one(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    asked = mind.decide(1, said)
    assert asked["kind"] == "conversation" and "?" in asked["reply"]
    assert "«audifonos»" in asked["reply"] and "«buen dia»" in asked["reply"]
    first = mind.decide(2, "yes" if said.startswith("delete") else "sí")
    assert first["kind"] == "action" and first["arguments"] == {"action": "delete", "name": HEADSET["id"]}
    second = mind.continue_turn(3, _receipt({"deleted": HEADSET}))
    assert second["kind"] == "action" and second["arguments"] == {"action": "delete", "name": MORNING["id"]}
    done = mind.continue_turn(4, _receipt({"deleted": MORNING}))
    assert done["kind"] == "conversation"
    assert done["reply"] in ("Borré tus 2 rutinas: «audifonos» y «buen dia».",
                             "I deleted your 2 routines: «audifonos» and «buen dia».")
    assert server.bodies == []


def test_a_no_to_deleting_every_routine_deletes_nothing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "borra todas mis rutinas")
    left = mind.decide(2, "no")
    assert left["kind"] == "conversation" and left["reply"] == "No borré nada."
    assert server.bodies == []


def test_deleting_every_routine_with_none_says_so(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [])
    told = mind.decide(1, "borra todas las rutinas")
    assert told["kind"] == "conversation" and told["reply"].startswith("No tienes ninguna rutina")
    assert server.bodies == []


def test_turning_every_routine_off_turns_off_the_active_ones(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING, STEPS])
    first = mind.decide(1, "desactiva todas las rutinas")
    assert first["kind"] == "action" and first["arguments"] == {"action": "disable", "name": "audifonos"}
    second = mind.continue_turn(2, _receipt({"routine": {**HEADSET, "active": False}, "saved": True}))
    assert second["arguments"] == {"action": "disable", "name": "buen dia"}
    done = mind.continue_turn(3, _receipt({"routine": {**MORNING, "active": False}, "saved": True}))
    assert done["reply"] == "Desactivé tus 2 rutinas: «audifonos» y «buen dia»."
    assert server.bodies == []


def test_a_failure_halfway_goes_to_the_model_with_what_was_done(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("«audifonos» quedó desactivada; «buen dia» no se pudo desactivar.")] * 2,
                               [HEADSET, MORNING])
    mind.decide(1, "desactiva todas mis rutinas")
    mind.continue_turn(2, _receipt({"routine": {**HEADSET, "active": False}, "saved": True}))
    told = mind.continue_turn(3, _failed("routine_scheduler_unavailable"))
    assert told["kind"] == "conversation" and len(server.bodies) >= 1


@pytest.mark.parametrize(("first", "observed"), [
    ("activa la rutina audífonos", {"routine": HEADSET, "saved": True}),
    ("qué rutinas tengo", {"routines": [HEADSET], "count": 1}),
])
def test_borrala_after_naming_one_routine_deletes_that_one(tmp_path: Path, first: str, observed: dict) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET])
    mind.decide(1, first)
    mind.continue_turn(2, _receipt(observed))
    asked = mind.decide(3, "bórrala")
    assert asked["kind"] == "action" and asked["arguments"] == {"action": "delete", "name": "audifonos"}
    assert server.bodies == []


def test_borrala_after_the_person_named_the_routine_deletes_it(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("La rutina «buenas noches» apaga el PC.")], [ORDER, HEADSET])
    mind.decide(1, "¿qué hace la rutina buenas noches?")
    asked = mind.decide(2, "bórrala")
    assert asked["kind"] == "action" and asked["arguments"] == {"action": "delete", "name": "buenas noches"}
    assert len(server.bodies) == 1


def test_borrala_with_no_routine_named_is_the_models(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Tienes una alarma a las 7."), _say("¿Quieres que la borre?")],
                               [HEADSET, MORNING])
    mind.decide(1, "¿qué alarmas tengo?")
    assert mind.decide(2, "bórrala")["kind"] == "conversation" and len(server.bodies) == 2


def test_borrala_with_several_routines_named_asks_which(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "qué rutinas tengo")
    mind.continue_turn(2, _receipt({"routines": [HEADSET, MORNING], "count": 2}))
    told = mind.decide(3, "bórrala")
    assert told["kind"] == "conversation" and "?" in told["reply"] and "«audifonos»" in told["reply"]
    assert server.bodies == []


def test_a_word_routine_is_changed_by_voice_with_its_yes(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    said = _talk(mind, ["cambia la rutina audífonos", "lo que hace", "cambia a los altavoces"])
    assert said[0]["reply"] == "¿Qué cambio de «audifonos»: la palabra o lo que hace?"
    assert said[1]["reply"] == "¿Qué quieres que haga cuando digas «audífonos»?"
    assert said[2]["reply"] == "«audifonos» quedará así: cuando digas «audífonos»: «cambia a los altavoces». ¿La cambio?"
    changed = mind.decide(4, "sí")
    assert changed["kind"] == "action"
    assert changed["arguments"] == {"action": "change", "name": HEADSET["id"], "order": "cambia a los altavoces"}
    done = mind.continue_turn(5, _receipt({"routine": {**HEADSET, "order": "cambia a los altavoces"}, "saved": True}))
    assert done["reply"] == "Cambié la rutina «audifonos»: «audífonos» hace «cambia a los altavoces»."
    assert server.bodies == []


def test_the_word_of_a_routine_is_changed_and_another_routines_word_is_not_taken(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, ORDER])
    said = _talk(mind, ["cambia la palabra de la rutina audífonos", "buenas noches", "cascos"])
    assert said[0]["reply"] == "¿Qué palabra vas a decir?"
    assert said[1]["reply"].startswith("Ya tienes una rutina con «buenas noches»")
    assert said[2]["reply"] == "«audifonos» quedará así: cuando digas «cascos»: «cambia a los audífonos Kessler». ¿La cambio?"
    assert mind.decide(4, "sí")["arguments"] == {"action": "change", "name": HEADSET["id"], "phrase": "cascos"}
    assert server.bodies == []


def test_the_time_of_a_timed_routine_is_changed_by_voice(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    said = _talk(mind, ["cambia la hora de la rutina buen dia", "a las 9 de la mañana"])
    assert said[0]["reply"] == "¿A qué hora?"
    assert said[1]["reply"] == ("«buen dia» quedará así: Todos los días a las 9:00 de la mañana, te digo: «buen día, hoy "
                                "es otro día». ¿La cambio?")
    changed = mind.decide(3, "sí")
    assert changed["arguments"] == {"action": "change", "name": MORNING["id"], "at": "09:00", "repeat": "daily"}
    assert server.bodies == []


def test_changing_a_routine_that_is_not_there_says_the_ones_there_are(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    told = mind.decide(1, "modifica la rutina de la tele")
    assert told["kind"] == "conversation"
    assert told["reply"] == "No tengo ninguna rutina «tele». Tienes: «audifonos» y «buen dia»."
    assert mind._guide is None and server.bodies == []


def test_cancela_leaves_a_change_with_nothing_changed(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET])
    said = _talk(mind, ["edita la rutina audífonos", "la palabra", "cancela"])
    assert said[-1]["reply"] == "Listo, lo dejo: no cambié ninguna rutina."
    assert mind._guide is None and server.bodies == []


def test_a_change_in_english(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET])
    said = _talk(mind, ["change the routine audífonos", "what it does", "switch to the speakers"])
    assert said[0]["reply"] == "What do I change of «audifonos»: the word or what it does?"
    assert said[2]["reply"] == "«audifonos» will be: when you say «audífonos»: «switch to the speakers». Shall I change it?"
    assert mind.decide(4, "yes")["arguments"] == {"action": "change", "name": HEADSET["id"],
                                                  "order": "switch to the speakers"}
    assert server.bodies == []


# ---------------------------------------------------------------------------------------------------------------------
# B-5: an order about BAXY's own routines is not what a routine does
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("order", ["borra la rutina despertar", "crea una rutina", "qué rutinas tengo"])
def test_an_order_about_the_routines_is_not_saved_as_a_routine(tmp_path: Path, order: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET])
    said = _talk(mind, ["nueva rutina", "con una palabra", "despierta", order])
    assert said[-1]["reply"].startswith("Eso es una orden sobre las rutinas")
    assert mind._guide is not None and mind._guide.step == "order"
    other, _ = _guide_mind(tmp_path, [], [HEADSET])
    breath = other.decide(1, f"cuando te diga hola, {order}")
    assert breath["reply"].startswith("Eso es una orden sobre las rutinas") and "«hola»" in breath["reply"]
    assert other.decide(2, "pon música")["reply"] == "Cuando digas «hola»: «pon música». ¿La guardo?"
    assert server.bodies == []


def test_a_phrase_that_is_an_order_of_baxy_is_said_and_only_the_phrase_is_asked_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [])
    said = mind.decide(1, "cuando te diga qué rutinas tengo, apaga todo")
    assert said["reply"] == ("«qué rutinas tengo» ya es una orden mía y no puede ser el nombre de una rutina. Dime otra "
                             "palabra.")
    assert mind.decide(2, "apagón")["reply"] == "Cuando digas «apagón»: «apaga todo». ¿La guardo?"
    assert server.bodies == []


# ---------------------------------------------------------------------------------------------------------------------
# B-S1: a word of everyday conversation is not a routine's phrase
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("phrase", ["sí", "no", "para", "por supuesto", "sí hazlo", "dale", "de acuerdo"])
def test_a_reply_or_a_stop_order_is_not_taken_as_a_phrase(phrase: str) -> None:
    assert routine_guide.mine(phrase) or routine_guide.everyday(phrase)


def test_a_one_breath_routine_with_an_everyday_phrase_says_so_and_asks_another(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [])
    said = mind.decide(1, "cuando te diga por supuesto, apaga el PC")
    assert "«por supuesto»" in said["reply"] and said["reply"].endswith("Dime otra palabra.")
    nxt = mind.decide(2, "apagón")
    assert nxt["reply"] == "Cuando digas «apagón»: «apaga el PC». ¿La guardo?"
    assert server.bodies == []


@pytest.mark.parametrize("phrase", ["buenas noches", "audífonos", "modo cine"])
def test_ordinary_phrases_stay_phrases(phrase: str) -> None:
    assert not routine_guide.mine(phrase) and not routine_guide.everyday(phrase)
