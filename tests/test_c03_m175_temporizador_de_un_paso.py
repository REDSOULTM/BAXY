"""M175 (2026-10-05, runs window/v5c-dev{F,D}): a timer asked for a step BAXY's answer timed.

1. «Venga, ponme el temporizador para lo de pochar» after a recipe that says «Pocha patata y cebolla a fuego lento unos
   20 minutos» (DEV-F F-w34-t4) and «¿Me pones un temporizador para voltearlas?» after «ásalas 5 minutos por lado»
   (DEV-D D-w10-t3) were asked «¿Cuántos minutos le pongo al temporizador?»: the step's one length is the timer's.
2. «and one for the garlic knots» after the pizza's 25-minute countdown (DEV-F F-w45-t2) was set to 25 minutes: a
   length said for another thing is never borrowed; how long it runs is asked.

The row texts and histories are the sets' (written) and the run's (lived); the variants are our own. The clock is
fixed (M108): no test reads the machine's date or hour.
"""

from __future__ import annotations

from datetime import datetime as real_datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments, decider
from baxy_mind.semantic.temporal import length_borrowed_for_another, step_timer_request

# Monday 5 October 2026, 17:58 in Chile (UTC-3).
LOCAL = timezone(timedelta(hours=-3))
NOW = real_datetime(2026, 10, 5, 17, 58, tzinfo=LOCAL)

TORTILLA_WRITTEN = [
    ("user", "Oye, ¿cómo se hace una tortilla de patatas para cuatro personas? Con cebolla, eh, que en casa somos de "
             "cebolla"),
    ("assistant", "Para 4: 5 patatas, 6 huevos, 1 cebolla, aceite de oliva y sal. Pocha patata y cebolla a fuego lento "
                  "unos 20 minutos, escurre, mezcla con el huevo batido y cuaja 2-3 minutos por cada lado."),
    ("user", "¿Y si al final somos ocho?"),
    ("assistant", "Para 8, mejor dos tortillas: 10 patatas, 12 huevos y 2 cebollas en total."),
    ("user", "Guárdamela en una nota que se llame tortilla"),
    ("assistant", "Listo, nota «tortilla» guardada con la receta para 8."),
]
# The run's own recipe says how to soften the onion but gives no minutes for it.
TORTILLA_LIVED = [
    ("user", TORTILLA_WRITTEN[0][1]),
    ("assistant", "Tortilla de patatas con cebolla:\n- 8 huevos grandes\n- 1 kg de patatas\n- 1 cebolla mediana o grande\n"
                  "- 1/2 litro de aceite de oliva\n- Sal\n\nPreparación:\n1. Pelar, lavar y secar las patatas, cortarlas "
                  "en taquitos, volver a lavarlas, añadir sal y freirlas en aceite caliente hasta que estén fritas pero no "
                  "doradas, luego escurrirlas.\n2. Cortar la cebolla en cuadraditos pequeños y dorarla en la sartén hasta "
                  "que esté transparente, retirándola junto con las patatas y eliminando el exceso de aceite.\n3. Batir los "
                  "8 huevos con una pizca de sal por cada yema hasta obtener un batido homogéneo con espumita."),
    ("user", "Guárdamela en una nota que se llame tortilla"),
    ("assistant", "He guardado la nota \"tortilla\" con la receta para 8 personas que incluye 16 huevos grandes."),
]
AREPAS_WRITTEN = [
    ("user", "Buenas, qué pena la molestia, ¿me regalas una receta sencilla de arepas de queso?"),
    ("assistant", "Claro: 2 tazas de harina de maíz precocida, 2 tazas de agua tibia, 1 taza de queso costeño rallado y "
                  "una pizca de sal. Amasa 3 minutos, forma 6 arepas y ásalas 5 minutos por lado a fuego medio."),
    ("user", "¿Y cuánto sería eso de harina en gramos, por favor?"),
    ("assistant", "Dos tazas de harina de maíz precocida son unos 260 g."),
]
AREPAS_LIVED = [
    ("user", AREPAS_WRITTEN[0][1]),
    ("assistant", "Arepas colombianas de queso con relleno de mozzarella:\n- 375 ml de agua templada\n- 10 g de sal\n"
                  "1. Mezclamos en un bol el agua, la sal y la mantequilla.\n2. Incorporamos poco a poco la harina de maíz "
                  "blanca precocida.\n4. Dejamos reposar la masa.\n5. Formamos las arepas.\n7. Las cocinamos 5 minutos por "
                  "cada lado.\n8. Las dejamos reposar para que se enfríen."),
    ("user", AREPAS_WRITTEN[2][1]),
    ("assistant", "250 ml de harina son aproximadamente 132,5 gramos."),
]
PIZZA = [
    ("user", "pizza just went in, gimme a 25 minute countdown"),
    ("assistant", "I have set a 25-minute countdown for the pizza, scheduled to ring at 18:23 today."),
]


class _Decider:
    """A contextual decider that answers one recorded decision."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")
        self.decisions = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decisions += 1
        return self.decided

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def clarify_after_turn_failure(objective: str, *_args: object, **_kwargs: object) -> str:
        return "How long should it run?" if "the" in objective else "¿Cuántos minutos le pongo al temporizador?"


TOOLS = ("notification.schedule", "reminder.create", "notification.list", "notification.cancel.latest",
         "calendar.event.create", "note.create", "web.search")


def _decided(text: str, history: list[tuple[str, str]], model: _Decider) -> dict[str, object]:
    tools = [
        {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                          "description": f"Operación {name}.", "parameters": {
                                              "type": "object", "properties": {}, "required": []}}}
        for name in TOOLS
    ]
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._context_decided_result(
        {"id": "m175", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(tools),
    )


def _rings_in(objective: str) -> timedelta:
    read = arguments._explicit_notification_schedule_arguments(objective)
    assert read is not None and read["kind"] == "alarm", objective
    due = arguments._canonical_due_utc(str(read["dueUtc"]), objective, now_utc=NOW)
    assert due is not None, objective
    return real_datetime.fromisoformat(due.replace("Z", "+00:00")) - NOW


def _asked_minutes() -> _Decider:
    return _Decider("Pon un temporizador para pochar la tortilla.", "clarify")


# ------------------------------------------------------------------ 1. the rows


def test_f_w34_t4_the_softening_step_is_the_timer() -> None:
    model = _asked_minutes()
    result = _decided("Venga, ponme el temporizador para lo de pochar", TORTILLA_WRITTEN, model)
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    assert result["objective"] == "pon un temporizador de 20 minutos para pochar"
    assert _rings_in(str(result["objective"])) == timedelta(minutes=20)


def test_f_w34_t4_lived_recipe_without_minutes_for_the_step_still_asks() -> None:
    result = _decided("Venga, ponme el temporizador para lo de pochar", TORTILLA_LIVED, _asked_minutes())
    assert result["kind"] == "clarify" and result["effectOperations"] == []


@pytest.mark.parametrize("history", [AREPAS_WRITTEN, AREPAS_LIVED], ids=["written", "lived"])
def test_d_w10_t3_flipping_is_the_length_of_one_side(history: list[tuple[str, str]]) -> None:
    model = _Decider("Pon un temporizador para voltear las arepas.", "clarify")
    result = _decided("Listo, parce. ¿Me pones un temporizador para voltearlas?", history, model)
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    assert result["objective"] == "pon un temporizador de 5 minutos para voltearlas"
    assert _rings_in(str(result["objective"])) == timedelta(minutes=5)


def test_f_w45_t2_the_pizza_length_is_not_borrowed_for_the_garlic_knots() -> None:
    model = _Decider("Set a 25-minute countdown for the garlic knots.", "action", ("notification.schedule",))
    result = _decided("and one for the garlic knots", PIZZA, model)
    assert result["kind"] == "clarify" and result["effectOperations"] == []
    # The answer to the question asked is M110's: the length that answers «how long?» is the timer.
    answered = _decided(
        "go with 12, the bag says 10 to 12 but my oven runs cold",
        [*PIZZA, ("user", "and one for the garlic knots"), ("assistant", "How long for the garlic knots?")],
        _Decider("unused", "clarify"),
    )
    assert answered["kind"] == "action" and answered["objective"] == "set a 12 minute timer for the garlic knots"


# ------------------------------------------------------------------ 2. other words, the other language


@pytest.mark.parametrize(
    ("text", "answer", "objective", "minutes"),
    [
        ("oye, ¿me pones un timer para el arroz?",
         "Sofríe el ajo, añade el arroz y el agua, y cuece el arroz a fuego bajo 18 minutos tapado.",
         "pon un temporizador de 18 minutos para el arroz", 18),
        ("can you set a timer to flip them?",
         "Pour a ladle of batter, cook the pancakes 2 to 3 minutes per side and serve warm.",
         "set a 3 minute timer to flip them", 3),
        ("ok set a timer for the pasta please",
         "Boil salted water. Add the pasta and cook it 10 minutes to 12 minutes, then drain.",
         "set a 12 minute timer for the pasta", 12),
        ("avísame para sacar el pan",
         "Forma la hogaza, déjala crecer y hornea el pan a 200 grados durante 1 hora.",
         "pon un temporizador de 1 hora para sacar el pan", 60),
    ],
)
def test_a_timer_for_a_step_takes_the_length_the_answer_gave_it(
    text: str, answer: str, objective: str, minutes: int,
) -> None:
    model = _Decider("Pon un temporizador.", "clarify")
    result = _decided(text, [("user", "¿cómo lo hago?"), ("assistant", answer)], model)
    assert result["kind"] == "action" and result["objective"] == objective
    assert _rings_in(objective) == timedelta(minutes=minutes)


def test_a_wrong_length_of_the_decider_for_the_step_is_the_step_length() -> None:
    model = _Decider("Pon un temporizador de 3 minutos para pochar.", "action", ("notification.schedule",))
    result = _decided("Venga, ponme el temporizador para lo de pochar", TORTILLA_WRITTEN, model)
    assert result["objective"] == "pon un temporizador de 20 minutos para pochar"


# ------------------------------------------------------------------ 3. what does not change


def test_a_length_said_in_the_message_stays_the_decider() -> None:
    model = _Decider("Pon un temporizador de 10 minutos.", "action", ("notification.schedule",))
    result = _decided("pon un temporizador de 10 minutos", TORTILLA_WRITTEN, model)
    assert result["objective"] == "Pon un temporizador de 10 minutos." and model.decisions == 1


def test_a_timer_for_a_thing_with_no_answer_before_is_still_asked() -> None:
    result = _decided("pon un temporizador para la pasta", [], _Decider("Pon un temporizador para la pasta.", "clarify"))
    assert result["kind"] == "clarify"
    english = _decided("set a timer for the pasta", [], _Decider("Set a timer for the pasta.", "clarify"))
    assert english["kind"] == "clarify"


def test_the_decider_that_already_set_the_step_length_keeps_its_decision() -> None:
    model = _Decider("Pon un temporizador de 20 minutos para pochar las patatas.", "action", ("notification.schedule",))
    result = _decided("Venga, ponme el temporizador para lo de pochar", TORTILLA_WRITTEN, model)
    assert result["objective"] == "Pon un temporizador de 20 minutos para pochar las patatas."


def test_the_length_answering_how_long_is_still_m110() -> None:
    model = _Decider("unused", "clarify")
    result = _decided("unos 8", [("user", "ponme un temporizador para los huevos"),
                                 ("assistant", "¿Cuántos minutos le pongo al temporizador para los huevos?")], model)
    assert result["objective"] == "pon un temporizador de 8 minutos para los huevos" and model.decisions == 0


@pytest.mark.parametrize(
    ("text", "restated", "history"),
    [
        # The same length asked again, or a thing the conversation timed with that length.
        ("y otro igual para el arroz", "Pon un temporizador de 10 minutos para el arroz.",
         [("assistant", "Listo, temporizador de 10 minutos para la pasta.")]),
        ("and another one for the pasta", "Set a 10-minute timer for the pasta.",
         [("assistant", "Done, a 10-minute timer for the pasta.")]),
        # A moment, not a thing (DEV-H H-w38-t3).
        ("and set another one for the day after, same time", "Set a reminder for the day after at 15:30.",
         [("assistant", "I have scheduled the Dentist reminder for tomorrow at 15:30.")]),
        # The length was asked in other words (DEV-I I-w08-t3, set right in the run).
        ("joya, poneme un timer por lo que tienen que estar en el horno", "Pon un temporizador de 20 minutos.",
         [("assistant", "Para 3: 250 g de almidón. Mismo horno: 20 minutos a 200 °C.")]),
    ],
)
def test_a_length_that_is_not_borrowed_stays(text: str, restated: str, history: list[tuple[str, str]]) -> None:
    said_before = [content for _, content in reversed(history)]
    assert not length_borrowed_for_another(text, restated, said_before)
    model = _Decider(restated, "action", ("notification.schedule",))
    assert _decided(text, history, model)["kind"] == "action"


@pytest.mark.parametrize(
    ("text", "answers"),
    [
        # Two lengths for the step, or none: asked.
        ("pon un temporizador para la pasta", ["Cuece la pasta 8 minutos si es fina; la gruesa, cuece la pasta 12 minutos."]),
        ("pon un temporizador para la pasta", ["Echa la pasta en agua hirviendo con sal."]),
        # A «para» further on is about something else.
        ("recuérdame comprar tinto para la oficina", ["La oficina queda a 20 minutos de aquí."]),
        # A timer BAXY reports setting is no step.
        ("and one for the pizza", ["I have set a 25-minute countdown for the pizza."]),
        # A moment is no step, and an alarm or a reminder for a thing names a moment.
        ("ponme un temporizador para mañana", ["Mañana sale el tren a las 7, son 40 minutos a Ñuñoa."]),
        ("ponme una alarma para el partido", ["El partido dura 90 minutos más el descanso."]),
        ("remind me to drain the pasta", ["Boil the pasta for 9 minutes, then drain it."]),
        ("pon un temporizador para el partido", ["El partido empieza a las 20:00, dura 90 minutos."]),
    ],
)
def test_no_step_length_no_timer(text: str, answers: list[str]) -> None:
    assert step_timer_request(text, answers) is None
