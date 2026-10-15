"""Goal v3 destino (r5a lectura M4 y M5, diseño 1 y 2): one resolver of the application a request names and the
precedence of the mission's destination — the framed application, then the conversation's, then a mention; never a
name inside quotes or a path, never the person's window by default."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.semantic import missions
from baxy_mind import turn_history

APPS = tuple(
    json.loads((Path(__file__).parent / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
)


def _destination(text: str, *before: str) -> str | None:
    arguments = missions.free_form_arguments(text, APPS, before)
    assert arguments is not None
    return arguments.get("application")  # type: ignore[return-value]


# --------------------------------------------------------------------------------------------- the one resolver

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # t-long-4: the first framed application wins over a later one («con el Bloc de notas»).
        (
            "abre el explorador en Documentos\\baxy-prueba-v3, crea una carpeta nueva que se llame baxy-respaldo, mueve "
            "notas.txt adentro, luego ábrelo desde ahí con el Bloc de notas y súbele el zoom",
            "Explorador de archivos",
        ),
        # v3-47: what «abre» opens, said in another language, never the OneNote mentioned later.
        ("abre system information, copia el nombre del procesador y pégalo en una página nueva de onenote",
         "Información del sistema"),
        # v3-06: one distinctive word of a single catalog name inside the frame.
        ("búscame en el correo de outlook los mensajes que pongan factura", "Outlook (classic)"),
        # A typing slip in an open verb's slot.
        ("abre el adminsitrador de tareas y ordena por memoria", "Administrador de tareas"),
        # v3-35 T1: a name mentioned by two of its words.
        ("crea una nota rapida nueva", "Notas rápidas"),
        # v3-17: a frame inside another frame's slot is still found.
        ("abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos", "Fotos"),
        ("en obs silencia el audio del escritorio", "OBS Studio (64bit)"),
    ],
)
def test_the_application_said(text: str, expected: str) -> None:
    assert missions.resolve_application(text, APPS) == expected
    assert _destination(text) == expected


def test_a_name_inside_quotes_is_never_the_application() -> None:
    """Contracaso: «dice «baxy prueba»» never resolves BAXY (t-drag-3)."""

    assert missions.resolve_application("escribí una nota que dice «baxy prueba»", APPS) is None
    assert missions.resolve_application('poné un título que diga "paint"', APPS) is None
    # Estabilización L4: t-drag-3 itself («… llevala arrastrando a …») is now the drag limit and never reaches a
    # destination (test_cu_v3_arrastre); the same note carried without the gesture still does.
    text = "agarrá la nota adhesiva que dice «baxy prueba» y llevala a la esquina de arriba a la derecha de la pantalla"
    assert _destination(text) != "BAXY"


def test_an_ordinary_word_is_no_application_that_ends_with_it() -> None:
    """Contracaso: «de la pantalla» never resolves «Teclado en pantalla» (t-drag-3, without the gesture: L4)."""

    text = "agarrá la nota adhesiva que dice «baxy prueba» y llevala a la esquina de arriba a la derecha de la pantalla"
    mission = missions.mission_request(text, APPS)
    assert getattr(mission, "application", None) != "Teclado en pantalla"
    assert missions.place_application(text, APPS) != "Teclado en pantalla"
    assert _destination(text) != "Teclado en pantalla"
    assert missions.catalog_application("pantalla", APPS) is None
    # The whole name said still is the application.
    assert missions.catalog_application("teclado en pantalla", APPS) == "Teclado en pantalla"


def test_an_unknown_name_opened_does_not_fall_to_a_mention() -> None:
    """What an open verb opens is the application; a name the catalog does not know there is no license to take the
    one mentioned later."""

    assert missions.resolve_application("abre el zorblax y copiá el título de onenote", APPS) is None
    # A later frame still says its own place («abre la imagen prueba.png … en fotos» above).
    assert missions.resolve_application("abre el zorblax y pegalo en onenote", APPS) == "OneNote"
    # A place frame that names no application leaves the mention in play.
    assert missions.resolve_application("en la lista de pendientes de onenote marcá la primera", APPS) == "OneNote"


def test_a_typing_slip_after_en_needs_more_than_one_word() -> None:
    """After «en» an ordinary word a letter from a one-word name stays that word («en stream escribí hola»)."""

    assert missions.resolve_application("en stream escribí hola", APPS) is None


def test_with_nothing_named_there_is_no_application() -> None:
    """t-form-4, t-menu-1: no application said and no conversation — none (the engine never takes the person's
    window in front for it)."""

    assert _destination("Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de "
                        "Fuente") is None
    assert _destination("en la carpeta baxy-prueba-v3 de Documentos haceme clic derecho en notas.txt y abrime las "
                        "propiedades, quiero ver cuánto pesa") is None


def test_another_language_through_the_encoder() -> None:
    """The fourth stage: the mind's encoder (or a translation) gives a name, always validated against the catalog."""

    def similar(phrase: str) -> str | None:
        return {"sticky notes app": "Notas rápidas", "spaceship": "Not Installed"}.get(phrase)

    assert missions.resolve_application("open the sticky notes app and add a note", APPS, similar=similar) == "Notas rápidas"
    assert missions.resolve_application("open the spaceship", APPS, similar=similar) is None


# ------------------------------------------------------------------------------------ the conversation's application

@pytest.mark.parametrize(
    ("turns", "expected"),
    [
        (("en el powerpoint que tengo abierto andá a la pestaña Transiciones",
          "ahora ponele la transición Desvanecer a esta diapo"), "PowerPoint"),
        (("en onenote crea una pagina nueva", "escribe ahi: comprar pan, leche y huevos", "ahora subele el zoom a 150"),
         "OneNote"),
        (("abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos", "recórtala en proporción cuadrada",
          "guárdala como copia en esa misma carpeta"), "Fotos"),
        (("crea una nota rapida nueva", "ponle: pagar la luz", "ahora ponla de color morado"), "Notas rápidas"),
        (("abre terminal", "split the pane vertical", "y renombra la tab a pruebas"), "Terminal"),
        (("en obs silencia el audio del escritorio", "vale, vuelve a activarlo"), "OBS Studio (64bit)"),
        (("en obs silencia el audio del escritorio", "sí"), None),
    ],
)
def test_a_follow_up_happens_in_the_conversations_application(turns: tuple[str, ...], expected: str | None) -> None:
    *before, text = turns
    if expected is None:
        # A bare answer is no order of its own: nothing to try.
        return
    assert _destination(text, *before) == expected


def test_a_turn_in_between_ends_the_conversations_application() -> None:
    """Contracaso: another message in between cuts the inheritance."""

    assert _destination("vale, vuelve a activarlo", "en obs silencia el audio del escritorio",
                        "cuál es la capital de Francia") is None
    # A bare yes in between does not.
    assert _destination("vale, vuelve a activarlo", "en obs silencia el audio del escritorio", "sí") == "OBS Studio (64bit)"


def test_a_place_of_the_previous_order_is_that_place() -> None:
    """v3-58 T2: «configuración» was a place inside Edge; it is not the Settings application."""

    assert _destination("busca cookies ahi en la configuracion", "abre edge y anda a la configuracion") == "Microsoft Edge"
    # Said alone, it is the Settings application.
    assert _destination("busca cookies ahi en la configuracion") == "Configuración"
    # A name searched or typed in the previous order is no place of it: the new frame wins.
    assert _destination("en discord escribí hola", "abre edge y busca discord") == "Discord"


def test_the_framed_application_wins_over_the_conversation() -> None:
    assert _destination("en paint girá la imagen a la derecha", "en onenote crea una pagina nueva") == "Paint"


# ------------------------------------------------------------------------- corrección: el texto dictado (revisión)

@pytest.mark.parametrize(
    ("before", "text", "expected"),
    [
        # A frame inside what «ponle:» dictates is the person's text, never the destination (nor a lifted guard).
        ("crea una nota rapida nueva", "ponle: abrir visual studio code mañana temprano", "Notas rápidas"),
        ("en onenote crea una pagina nueva", "escribe ahí: recordar abrir la terminal y correr npm install", "OneNote"),
        ("crea una nota rapida nueva", "ponle: llamar con whatsapp a mamá", "Notas rápidas"),
        ("crea una nota rapida nueva", "escribe esto en el documento: llamar con whatsapp a mamá", "Notas rápidas"),
    ],
)
def test_a_name_inside_a_dictated_text_is_never_the_destination(before: str, text: str, expected: str) -> None:
    assert _destination(text, before) == expected
    assert missions.resolve_application(text, APPS) is None


def test_a_frame_before_the_dictated_text_still_says_the_place() -> None:
    """Contracaso: the frame said before the colon is the destination; a time's colon opens no text."""

    assert missions.resolve_application("escribe en el bloc de notas: hola", APPS) == "Bloc de notas"
    assert missions.resolve_application("ponle a las 10:30 la reunión en onenote", APPS) == "OneNote"


# ------------------------------------------------------- corrección: la app en que terminó el pedido anterior (revisión)

@pytest.mark.parametrize(
    ("before", "text", "expected"),
    [
        # The conversation is in the application the earlier request ended in, as a chain ends in its last step.
        ("abre la calculadora y en el bloc de notas escribí el resultado", "en el bloc de notas guardalo como total.txt",
         "Bloc de notas"),
        ("abre paint y pegá la imagen en fotos", "en fotos recortala", "Fotos"),
        ("en paint dibujá un círculo y después en el bloc de notas escribí hola", "guardalo como prueba.txt",
         "Bloc de notas"),
    ],
)
def test_the_conversation_is_in_the_application_the_last_request_ended_in(before: str, text: str, expected: str) -> None:
    assert _destination(text, before) == expected


def test_an_application_framed_before_is_no_place_of_another() -> None:
    """Only a name after a verb of going, and not read as an application's frame, was a place: «pegá la imagen en
    fotos» framed Fotos itself; «andá a la configuración» went to a place of Edge."""

    assert _destination("en fotos recortala", "abre paint y pegá la imagen en fotos") == "Fotos"
    assert _destination("busca cookies ahi en la configuracion", "abre edge y anda a la configuracion") == "Microsoft Edge"
    # «buscá cookies en la configuración» framed the Settings application: no place of Edge to keep.
    assert _destination("en la configuracion activa el modo oscuro", "abre edge y busca cookies en la configuracion") == (
        "Configuración"
    )


# ------------------------------------------- corrección: el mensaje actual nunca es un pedido anterior (revisión)

def test_a_plan_steps_purpose_never_inherits_from_the_current_message() -> None:
    """A plan step is grounded on its purpose, in the model's words: the person's current message, last in the
    history, is no earlier request of the conversation (it named Spotify first; the step is no Spotify one)."""


    history = [{"role": "user", "content": "abre spotify y después agregá comprar pan a mis notas rapidas"}]
    assert turn_history._prior_user_requests(history) == ()
    assert _destination("escribir comprar pan", *turn_history._prior_user_requests(history)) is None


def test_the_earlier_messages_are_still_the_conversation() -> None:
    """Contracaso: the person's earlier messages stay, oldest first; an assistant turn last means the current
    message is not in the history."""


    history = [
        {"role": "user", "content": "en onenote crea una pagina nueva"},
        {"role": "assistant", "content": "Listo."},
        {"role": "user", "content": "escribe ahi: comprar pan"},
    ]
    assert turn_history._prior_user_requests(history) == ("en onenote crea una pagina nueva",)
    assert _destination("escribir comprar pan", *turn_history._prior_user_requests(history)) == "OneNote"
    assert turn_history._prior_user_requests(history[:2]) == ("en onenote crea una pagina nueva",)


# ------------------------------------------------- corrección: la palabra distintiva y los marcos (revisión)

@pytest.mark.parametrize(
    "text",
    [
        # After «on», «con», «with» or «using» one word of a name is no destination (an EPSON utility, the on-screen
        # keyboard whose clicks would type into the person's window).
        "turn on bluetooth",
        "con el teclado escribí hola",
        # After «en», a word alone is no complement: and a manual is never what a word of it names.
        "en la consola escribí dir",
    ],
)
def test_one_word_after_a_means_or_place_frame_is_no_application(text: str) -> None:
    assert missions.resolve_application(text, APPS) is None
    assert _destination(text) is None


def test_a_distinctive_word_still_names_its_application() -> None:
    """Contracaso: as the complement of a thing after a place frame, in an open verb's slot, or the whole name after a
    means frame."""

    assert missions.resolve_application("en el correo de outlook busca facturas", APPS) == "Outlook (classic)"
    assert missions.resolve_application("abre el teclado en pantalla", APPS) == "Teclado en pantalla"
    assert missions.resolve_application("con el bloc de notas abrilo", APPS) == "Bloc de notas"
    assert missions.resolve_application("using paint draw a line", APPS) == "Paint"


def test_the_no_application_stop_claims_only_what_the_twin_holds() -> None:
    """The twin (extended by the round-5 integration) holds keys, text, clicks, scrolls and drags on the person's window:
    its stop says the window in front was not touched, never that nothing at all was done (an app.open may have run)."""

    floor = json.loads(
        (Path(missions.__file__).parent.parent / "data" / "operation_floor.v1.json").read_text(encoding="utf-8")
    )
    found = [value for key, value in _walk(floor) if key == "computer_use_no_application"]
    assert found, "the stop's prose is in the floor data"
    prose = found[0]
    assert "no toqué la ventana de delante" in prose["es"] and "did not touch the window in front" in prose["en"]
    assert "nada" not in prose["es"] and "nothing" not in prose["en"]


# ----------------------------------------------------- integración ronda 5: the person names the window in front

@pytest.mark.parametrize(
    "text",
    [
        "en esta ventana escribí hola",
        "hacé clic en Aceptar en esta ventana",
        "en la ventana activa bajá hasta el final",
        "en la ventana de delante cerrá la pestaña de ajustes",
        "in this window click OK",
        "in the active window scroll down",
    ],
)
def test_the_person_naming_the_window_in_front_makes_it_the_destination(text: str) -> None:
    arguments = missions.free_form_arguments(text, APPS)
    assert arguments == {"goal": text, "frontWindow": True}
    # Not the conversation's application either: the person pointed at the window in front.
    assert missions.free_form_arguments(text, APPS, ("en onenote crea una pagina nueva",)) == {
        "goal": text, "frontWindow": True,
    }


@pytest.mark.parametrize(
    ("text", "before", "application"),
    [
        # No point at the window in front: no frontWindow, so the shell touches nothing of the person's.
        ("escribí hola", (), None),
        ("hacé clic en Aceptar", (), None),
        # «en la ventana» alone, or the window of a named application, is no point at the window in front.
        ("en la ventana de spotify poné pausa", (), "Spotify"),
        # Inside a dictated text it is the text.
        ("escribí: en esta ventana no", (), None),
        # A framed application wins over «esta ventana».
        ("en esta ventana del bloc de notas escribí hola", (), "Bloc de notas"),
        ("abre paint y en esta ventana dibujá una línea", (), "Paint"),
        # The conversation's application stays when the window in front is not named.
        ("escribir comprar pan", ("en onenote crea una pagina nueva",), "OneNote"),
    ],
)
def test_without_the_window_in_front_named_there_is_no_front_window(
    text: str, before: tuple[str, ...], application: str | None,
) -> None:
    arguments = missions.free_form_arguments(text, APPS, before)
    assert arguments is not None and "frontWindow" not in arguments
    assert arguments.get("application") == application


def _walk(node: object):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


# ------------------------------------------------------------------------- the person's address (tanda t4-r6)

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # t4-r6 c06: «bro» before the order dropped Excel and the chain lost its second step.
        ("bro abre excel y crea un libro en blanco", "Excel"),
        ("oye bro abre excel y crea un libro en blanco", "Excel"),
        ("che porfa abrí el bloc de notas y escribí hola", "Bloc de notas"),
        ("wey, abre word y escribe un título", "Word"),
    ],
)
def test_a_leading_vocative_is_the_address_not_the_order(text: str, expected: str) -> None:
    assert missions.place_application(text, APPS) == expected
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.application == expected


def test_a_vocative_word_inside_the_order_stays_as_said() -> None:
    """Contracaso: «bro» written as text or as part of a file name is content, and a marker before no order is not
    stripped into one."""

    from baxy_mind.semantic.grammar import _strip_request_envelope

    assert _strip_request_envelope("escribe bro en el bloc de notas") == "escribe bro en el bloc de notas"
    assert _strip_request_envelope("bro que hora es") == "bro que hora es"
    assert _strip_request_envelope("bro abre bro.txt") == "abre bro.txt"
    # Spanish «pal» is «para el», never the address: the reading keeps it as «para el lunes …» is kept.
    from baxy_mind.semantic.grammar import _without_address

    assert _without_address("pal lunes recuérdame pagar la luz") is None
    # The order without the address reads the same as the order said with it, «bro» in its text kept.
    with_address = missions.mission_request("wey abre word y escribe bro", APPS)
    without = missions.mission_request("abre word y escribe bro", APPS)
    assert with_address is not None and without is not None
    assert with_address.goal == without.goal and "bro" in with_address.goal


def test_the_order_after_the_address_keeps_the_persons_writing() -> None:
    """t4-r6 regression: «oye pon rosalía» read on the folded envelope lost the accent the order said alone keeps."""

    from baxy_mind.semantic.patterns import resolve_explicit_effects

    operations = ("media.play.youtube", "media.play.query")
    for said in ("oye pon rosalía", "bro pon rosalía", "oye, pon rosalía"):
        found = resolve_explicit_effects(said, operations)
        assert found is not None and found.evidence == ("pon rosalía",)
