"""Ruta tipada en app (auditoría de estabilidad 2026-10-08, riesgos-fusion 2, verificada): the coverage gate handed the
computer-use engine every typed system or BAXY operation of an order of one clause said «en <app>»
(``semantic.decider.order_served_elsewhere``, ``doing_in_place``): brightness, wifi and bluetooth «en configuración»
went from ~2 s typed to 10-40 s missions (t4-c04 t1 2 071 ms typed; t4-c04 t3 20 858 ms failed), «en word ponme un
recordatorio» created none, «en spotify silencia todo» lost the PC's mute and «en spotify sube el volumen al 80» was
neither the PC's volume nor Spotify's (owner rule: a volume said in an application is that application's).

A typed operation that covers the whole order keeps its route when the application is only where the person believes
it is done (``served_where_said_purpose`` in ``data/operation_surface.v1.json``); the engine keeps what is the
application's own control.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic import decider, missions, patterns
from baxy_mind.semantic.decider import ContextDecision

from test_cu_v3_cobertura import APPS, OPERATIONS, _decided_with
from baxy_mind import engine_handoff
from baxy_mind import argument_grounding

PLACES = APPS + (
    "Configuración", "Settings", "Word", "Visual Studio Code", "Visor de eventos", "Outlook", "Google Calendar",
    "OneNote", "Teams",
)


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        # The PC's own settings window is only where the person believes the system is set.
        ("en configuración sube el brillo al 70", "Sube el brillo al 70.", ("system.settings.set",)),
        ("en configuracion pon el brillo al 50", "Pon el brillo al 50.", ("system.settings.set",)),
        ("en configuración bajá el brillo al 30", "Baja el brillo al 30.", ("system.settings.set",)),
        ("en configuración apaga el bluetooth", "Apaga el Bluetooth.", ("bluetooth.radio.set",)),
        ("in settings turn off bluetooth", "Turn off Bluetooth.", ("bluetooth.radio.set",)),
        ("en configuración desactiva el wifi", "Desactiva el wifi.", ("wifi.radio.set",)),
        # BAXY's own reminders, alarms and memory, said in any application.
        ("en word ponme un recordatorio a las 5 para llamar a ana", "Recuérdame a las 5 llamar a Ana.",
         ("reminder.create",)),
        ("en word ponme una alarma a las 7", "Pon una alarma a las 7.", ("notification.schedule",)),
        # The whole PC named as the object, in any application.
        ("en spotify silencia el pc", "Silencia el PC.", ("audio.mute",)),
        # Revisión ruta-tipada 7: the PC's settings said whole are still the settings window.
        ("en la configuracion del pc baja el brillo al 30", "Baja el brillo al 30.", ("system.settings.set",)),
    ],
)
def test_a_typed_operation_said_where_the_person_believes_it_is_done_keeps_its_route(
    text: str, restated: str, chosen: tuple[str, ...],
) -> None:
    assert missions.doing_said_in_place(text, PLACES)
    result = _decided_with(text, ContextDecision(restated, "action", chosen, ""), PLACES)
    assert result["effectOperations"] == list(chosen)


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        # The application's own control stays the engine's there.
        ("en chrome buscá recetas", "Busca recetas.", ("web.search",)),
        ("in chrome search for pasta recipes", "Search for pasta recipes.", ("web.search",)),
        ("en obs silencia el audio del escritorio", "Silencia el audio.", ("audio.mute",)),
        ("en OBS Studio silenciá el micrófono de la escena", "Silencia el micrófono.", ("audio.mute",)),
        ("en fotos subí el brillo al 70", "Sube el brillo al 70.", ("system.settings.set",)),
        ("en notas rápidas anotá llamar al dentista", "Crea una nota: llamar al dentista.", ("note.create",)),
        # In the settings window, what the typed readers do not read in the clause is no system operation of theirs.
        ("en configuración comprobá si hay actualizaciones", "Comprueba si hay actualizaciones.", ("system.status",)),
        ("en configuracion pon el modo oscuro", "Pon el modo oscuro.", ("system.settings.set",)),
        # Revisión ruta-tipada 1: a bare «todo», «general» or «global» names the application's own things, no PC.
        ("en spotify silencia todo", "Silencia todo.", ("audio.mute",)),
        ("en obs silencia todo el audio del escritorio", "Silencia el audio.", ("audio.mute",)),
        ("en obs silencia el audio global", "Silencia el audio.", ("audio.mute",)),
        ("en discord silencia todo el servidor", "Silencia.", ("audio.mute",)),
        ("en teams silencia todo", "Silencia todo.", ("audio.mute",)),
        ("en discord activá no molestar en todo", "Activa no molestar.", ("system.settings.set",)),
        # Revisión ruta-tipada 2: an application that keeps the person's own reminders or notes keeps them there, and a
        # reminder the readers do not read as the person's own («recordale a Juan») is a message there.
        ("en outlook creá un recordatorio para mañana a las 9", "Crea un recordatorio mañana a las 9.",
         ("reminder.create",)),
        ("en google calendar ponme un recordatorio a las 5", "Recordatorio a las 5.", ("reminder.create",)),
        ("en outlook mostrame mis recordatorios", "Muestra mis recordatorios.", ("reminder.list",)),
        ("en discord recordale a juan que mañana hay reunion", "Recuérdale a Juan que mañana hay reunión.",
         ("reminder.create",)),
        ("en discord mostrame las notificaciones", "Muestra las notificaciones.", ("notification.list",)),
        # Revisión ruta-tipada 7: another application's settings are not the PC's.
        ("en configuración de spotify silencia el audio", "Silencia el audio.", ("audio.mute",)),
    ],
)
def test_contracase_what_is_the_applications_own_control_stays_the_engines(
    text: str, restated: str, chosen: tuple[str, ...],
) -> None:
    result = _decided_with(text, ContextDecision(restated, "action", chosen, ""), PLACES)
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == text


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("en configuración bajá el brillo al 30", "baja el brillo al 30"),
        ("in Settings turn off bluetooth", "turn off bluetooth"),
        # a comma is a link a second clause could hang from (doing_said_in_place)
        ("in Settings, turn off bluetooth", None),
        ("en la Configuración apaga el wifi", "apaga el wifi"),
        ("abrime steam porfa y de paso fijate que hora es", None),
        ("bajá el brillo al 30", None),
    ],
)
def test_said_without_its_place(text: str, said: str | None) -> None:
    # Estabilización R21: said_without_its_place (only this test called it) was said_in_place's clause; the turn
    # reads said_in_place (__main__).
    found = missions.said_in_place(text, PLACES)
    assert (found[1] if found is not None else None) == said


def test_baxys_own_memory_said_in_an_application_is_not_the_engines() -> None:
    text = "en discord recordá que mi color favorito es el azul"
    decided = ContextDecision("Recuerda que mi color favorito es el azul.", "action", ("memory.save",), "")
    assert engine_handoff._order_served_elsewhere(text, decided, OPERATIONS, PLACES, lambda _operation: None) is None


def test_contracase_what_is_said_kept_in_an_application_that_keeps_notes_is_the_engines() -> None:
    # Revisión ruta-tipada 2: «guardá que…» in OneNote is a note there, not BAXY's private memory.
    text = "en onenote guardá que la reunión es el martes"
    decided = ContextDecision("Guarda que la reunión es el martes.", "action", ("memory.save",), "")
    assert engine_handoff._order_served_elsewhere(text, decided, OPERATIONS, PLACES, lambda _operation: None) == (
        "elsewhere", text,
    )


def test_kept_where_said_reads_the_surface_data() -> None:
    reminder = ("reminder.create",)
    assert decider.kept_where_said(reminder, "Word", reminder, "ponme un recordatorio") == {"reminder.create"}
    # a reminder the readers do not read in the clause, or said where reminders are kept, is not BAXY's
    assert decider.kept_where_said(reminder, "Discord", (), "recordale a juan que hay reunion") == frozenset()
    assert decider.kept_where_said(reminder, "Outlook", reminder, "ponme un recordatorio") == frozenset()
    assert decider.kept_where_said(("memory.save",), "Word", (), "acordate de que va en arial") == {"memory.save"}
    assert decider.kept_where_said(("memory.save",), "OneNote", (), "guarda que es el martes") == frozenset()
    assert decider.kept_where_said(("memory.save",), "Microsoft To Do", (), "guarda pan") == frozenset()
    assert decider.kept_where_said(("note.create",), "Word", ("note.create",), "anota pan") == frozenset()
    assert decider.kept_where_said(
        ("system.settings.set",), "Configuración", ("system.settings.set",), "baja el brillo al 30",
    ) == {"system.settings.set"}
    # what the clause is not read as, and a system operation said in another application, are not kept
    assert decider.kept_where_said(("system.status",), "Configuración", (), "comproba actualizaciones") == frozenset()
    assert decider.kept_where_said(
        ("system.settings.set",), "Fotos", ("system.settings.set",), "subi el brillo al 70",
    ) == frozenset()
    assert decider.kept_where_said(("audio.mute",), "Spotify", ("audio.mute",), "silencia el pc") == {"audio.mute"}
    for bare in ("silencia todo", "silencia todo el audio del escritorio", "silencia el audio global"):
        assert decider.kept_where_said(("audio.mute",), "Spotify", ("audio.mute",), bare) == frozenset()
    assert decider.kept_where_said(("audio.mute",), "OBS Studio", ("audio.mute",), "silencia el audio") == frozenset()
    # another application's settings («en configuración de spotify …») are not the PC's; the PC's are
    settings = ("system.settings.set",)
    assert decider.kept_where_said(settings, "Configuración", settings, "de spotify baja el brillo") == frozenset()
    assert decider.kept_where_said(settings, "Configuración", settings, "del pc baja el brillo al 30") == set(settings)

    # the clause is read only when an operation needs it (revisión 6)
    def unread() -> tuple[str, ...]:
        raise AssertionError("read without need")

    assert decider.kept_where_said(("audio.mute",), "OBS Studio", unread, "silencia el audio") == frozenset()
    assert decider.order_served_elsewhere(("audio.mute",), 1, doing_in_place=True, kept_in_place=("audio.mute",)) is None
    assert decider.system_settings_application("Configuración") and decider.system_settings_application("Settings")
    assert not decider.system_settings_application("Spotify")


# ------------------------------------------------------------------ a volume said in an application is its volume


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("en spotify sube el volumen al 80", "audio.app.volume.set"),
        ("en steam pon el volumen al 30", "audio.app.volume.set"),
        ("in spotify set the volume to 40", "audio.app.volume.set"),
        ("in spotify turn the volume down by 20", "audio.app.volume.adjust"),
        ("en spotify bajá el volumen en 10", "audio.app.volume.adjust"),
    ],
)
def test_a_volume_said_in_an_application_is_that_applications(text: str, operation: str) -> None:
    read = patterns.resolve_explicit_effects(text, OPERATIONS, PLACES)
    assert read is not None and read.operations == (operation,)


def test_a_raise_to_a_level_is_that_level_not_an_amount() -> None:
    """«al 80» gives the level, as for the PC's volume (semantic.levels: «a 40» is no «40 less»); «en 20» the amount."""

    assert patterns.app_volume_set_request("en spotify sube el volumen al 80", PLACES) == ("Spotify", 80)
    assert patterns.app_volume_set_request("sube el volumen de spotify al 80", PLACES) == ("Spotify", 80)
    assert patterns.app_volume_set_request("turn spotify volume down to 20", PLACES) == ("Spotify", 20)
    assert patterns.app_volume_request("sube el volumen de spotify al 80", PLACES) is None
    assert patterns.app_volume_request("subí el volumen de spotify en 20", PLACES) == ("Spotify", "up", 20)
    assert patterns.app_volume_request("turn down spotify volume by 10", PLACES) == ("Spotify", "down", 10)
    # Revisión ruta-tipada 5: «a 20 puntos» counts points to move it by.
    assert patterns.app_volume_request("sube el volumen de spotify a 20 puntos", PLACES) == ("Spotify", "up", 20)
    assert patterns.app_volume_set_request("sube el volumen de spotify a 20 puntos", PLACES) is None


_ADJUST_SCHEMA = {
    "type": "object",
    "properties": {
        "app": {"type": "string"}, "amount": {"type": "integer"}, "direction": {"type": "string", "enum": ["up", "down"]},
    },
    "required": ["app", "amount", "direction"],
    "additionalProperties": False,
}
_SET_SCHEMA = {
    "type": "object",
    "properties": {"app": {"type": "string"}, "level": {"type": "integer"}},
    "required": ["app", "level"],
    "additionalProperties": False,
}


def test_the_deciders_adjustment_keeps_the_persons_literal() -> None:
    """Revisión ruta-tipada 3 (twin of M177 «¿Le bajo el volumen a Spotify?» → «dale, a 20» → «Baja el volumen de
    Spotify a 20.» with audio.app.volume.adjust): the decider's adjustment is grounded from its literal, as before the
    branch, never one more extraction call to the model."""

    assert argument_grounding._ground_explicit_arguments(
        "audio.app.volume.adjust", "Baja el volumen de Spotify a 20.", _ADJUST_SCHEMA, ("Spotify",),
    ) == {"app": "Spotify", "amount": 20, "direction": "down"}


@pytest.mark.parametrize(
    ("previous", "answer", "operation"),
    [
        # Revisión ruta-tipada 4: «al 20» answers the level, a bare number or «en 20» the amount asked.
        ("en spotify subí el volumen", "al 20", "audio.app.volume.set"),
        ("subí el volumen de spotify", "al 20", "audio.app.volume.set"),
        ("turn spotify volume up", "to 20", "audio.app.volume.set"),
        ("en spotify subí el volumen", "20", "audio.app.volume.adjust"),
        ("en spotify subí el volumen", "en 20", "audio.app.volume.adjust"),
        ("en spotify subí el volumen", "a 20 puntos", "audio.app.volume.adjust"),
        ("turn spotify volume up", "20", "audio.app.volume.adjust"),
    ],
)
def test_the_answer_to_how_much_reads_a_level_as_the_request_does(previous: str, answer: str, operation: str) -> None:
    read = patterns.resolve_explicit_effects(answer, OPERATIONS, PLACES, previous_user_text=previous)
    assert read is not None and read.operations == (operation,)
    resumed = f"{previous} aclaracion confiable del usuario: {answer}"
    if operation == "audio.app.volume.set":
        grounded = argument_grounding._ground_explicit_arguments(operation, resumed, _SET_SCHEMA, PLACES)
        assert grounded == {"app": "Spotify", "level": 20}
    else:
        grounded = argument_grounding._ground_explicit_arguments(operation, resumed, _ADJUST_SCHEMA, PLACES)
        assert grounded == {"app": "Spotify", "amount": 20, "direction": "up"}


@pytest.mark.parametrize(
    "text",
    [
        # the settings window has no volume of its own: the PC's is set there
        "en configuración sube el volumen al 50",
        "in settings set the volume to 30",
        # the application's own control that is no volume
        "en spotify poné el modo aleatorio",
        # the volume said whole is the PC's
        "subí el volumen a 40",
    ],
)
def test_contracase_no_application_volume(text: str) -> None:
    read = patterns.resolve_explicit_effects(text, OPERATIONS, PLACES)
    assert read is None or not set(read.operations) & {"audio.app.volume.set", "audio.app.volume.adjust"}


def test_a_volume_said_in_an_application_without_an_amount_asks_how_much() -> None:
    """Owner rule (relative volume without a quantity asks it), for the application's volume."""

    asked = patterns.resolve_explicit_clarification_intent("en spotify subí el volumen", OPERATIONS, PLACES)
    assert asked is not None and asked.operations == ("audio.app.volume.adjust",) and asked.missing_fields == ("amount",)
