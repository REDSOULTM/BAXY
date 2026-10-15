"""cu-v3 texto-webview (lote en vivo 2026-10-08, wa-1): «en WhatsApp escribí baxyprueba en el buscador de chats» envió
la frase entera («baxyprueba en el buscador de chats», 34 caracteres) por teclado al marco de la app y el subobjetivo se
dio por cumplido por «stepDone» con la lista sin filtrar. El lugar dicho detrás del texto es el campo donde va, nunca
parte del texto, en español, inglés y spanglish; el texto pedido entre comillas se queda entero.

Revisión adversarial r2: la frase sola no distingue un campo de un lugar del mundo («nos vemos en el campo de fútbol»),
así que sólo el cuadro de búsqueda se separa al leer; un campo por su nombre se separa donde la vista tiene ese campo.
Lo escrito se juzga después de un acto (stepDone), nunca por una primera vista que ya lo muestre (la barra de
direcciones con «…/search?q=gatos»), y el borrador de la persona nunca se reemplaza."""

from __future__ import annotations

import pytest

from baxy_mind import cu_rules
from baxy_mind.semantic import missions

TYPED = "stepDone:input.text.type"


@pytest.mark.parametrize(
    ("clause", "value"),
    [
        ("escribi baxyprueba en el buscador de chats", "baxyprueba"),
        ("escribe hola mundo en la barra de busqueda", "hola mundo"),
        ("type hello in the search box", "hello"),
        ("type hello world into the search bar", "hello world"),
        ("type hi in the chat search box", "hi"),
        # Spanglish: la orden en un idioma y el lugar en el otro.
        ("type hola en el search box", "hola"),
        ("escribi hello in the buscador", "hello"),
        # El texto entre comillas antes del lugar.
        ("escribi «hola mundo» en el buscador", "hola mundo"),
    ],
)
def test_the_search_place_after_the_text_is_the_field_it_goes_to(clause: str, value: str) -> None:
    # Written is the act that typed it, shown by the view after it (TypedTextShows): never a first look.
    assert missions.read_clause(clause) == (f"poner busqueda en {value}", TYPED)


@pytest.mark.parametrize(
    ("clause", "typed"),
    [
        # Contracasos: «en …» dentro del texto pedido entre comillas es del texto.
        ('escribi "nos vemos en el campo"', "nos vemos en el campo"),
        ('escribi "hola en el buscador"', "hola en el buscador"),
        ("type «meet me in the search box»", "meet me in the search box"),
        # Un «en …» que no nombra el buscador es del texto al leer (el campo con nombre lo decide la vista).
        ("escribi nos vemos en el bar", "nos vemos en el bar"),
        ("escribi nos vemos en el campo de mi tio", "nos vemos en el campo de mi tio"),
        ("escribi vamos en el campo", "vamos en el campo"),
        ("escribi la reunion es en la sala de juntas", "la reunion es en la sala de juntas"),
        ("write meet me in the box", "meet me in the box"),
        # Revisión r2, hallazgo 1: lugares del mundo que se parecen a un campo.
        ("escribi nos vemos en el campo de futbol", "nos vemos en el campo de futbol"),
        ("escribi te espero en la barra del hotel", "te espero en la barra del hotel"),
        ("escribi estoy en la caja del super", "estoy en la caja del super"),
        ("escribi llego en la caja 3", "llego en la caja 3"),
        ("escribi te veo en el cuadro de honor", "te veo en el cuadro de honor"),
        ("escribi esta en la barra de herramientas", "esta en la barra de herramientas"),
        ("escribi nos vemos en el campo deportivo", "nos vemos en el campo deportivo"),
        ("write see you on the soccer field", "see you on the soccer field"),
        ("write i left it in the mail box", "i left it in the mail box"),
        ("type stay on the search", "stay on the search"),
        # Un campo con nombre se lee entero: la vista dice si existe.
        ("escribi hola en el campo nombre", "hola en el campo nombre"),
        ("type hello in the chat box", "hello in the chat box"),
    ],
)
def test_contracase_en_inside_the_requested_text_stays_typed(clause: str, typed: str) -> None:
    assert missions.read_clause(clause) == (f"escribir {typed}", missions.WRITTEN_CHECK)


def test_wa_1_the_whole_request_types_only_the_text_as_said() -> None:
    request = missions.mission_request("en WhatsApp escribí BaxyPrueba en el buscador de chats", ("WhatsApp",))
    assert request is not None
    assert (request.application, request.goal, request.success_check) == ("WhatsApp", "poner busqueda en BaxyPrueba", TYPED)
    chained = missions.mission_request("abrí WhatsApp y escribí BaxyPrueba en el buscador de chats", ("WhatsApp",))
    assert chained is not None and chained.goal == "poner busqueda en BaxyPrueba"


# The view of the client's content surface (the worker's view of its WebView2, measured live 2026-10-08): the search
# box, a read-only document holding the address, the chat filters.
_SURFACE = {
    "ok": True,
    "window": {"title": "(5) WhatsApp", "process": "msedgewebview2", "focused": {"kind": "TabItem", "name": "Todos", "i": 17}},
    "controls": [
        {"i": 4, "kind": "Document", "name": "(5) WhatsApp", "state": "readonly", "value": "https://web.whatsapp.com/"},
        {"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "state": "", "value": ""},
        {"i": 17, "kind": "TabItem", "name": "Todos", "state": "selected"},
        {"i": 18, "kind": "TabItem", "name": "Favoritos", "state": ""},
    ],
}
# The same client with a chat open: the message box holds the person's draft.
_CHAT_OPEN = {
    "ok": True,
    "window": {"title": "(5) WhatsApp", "process": "msedgewebview2", "focused": {"kind": "ListItem", "name": "Juanito", "i": 20}},
    "controls": [
        {"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "state": "", "value": ""},
        {"i": 20, "kind": "ListItem", "name": "Juanito", "state": "selected"},
        {"i": 31, "kind": "Edit", "name": "Escribe un mensaje", "state": "", "value": "borrador de la persona"},
    ],
}


def _step(goal: str, view: dict, history: list[dict] | None = None) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history or [], application="WhatsApp")


def test_the_search_field_takes_the_text_by_its_label_replacing_what_it_held() -> None:
    step = _step("poner busqueda en BaxyPrueba", _SURFACE)
    assert step is not None and step["operation"] == "input.text.type"
    assert step["arguments"] == {"text": "BaxyPrueba", "field": "Buscar un chat o iniciar uno nuevo", "replace": True}


def test_contracase_a_view_without_the_field_dictates_no_step() -> None:
    # The frame's view of live wa-1: caption buttons and panes, no field; the text never goes to its focus by rule.
    frame = {
        "ok": True,
        "window": {"title": "WhatsApp", "process": "WhatsApp.Root", "focused": {"kind": "Pane", "name": "Non Client Input Sink Window"}},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Minimize"}, {"i": 1, "kind": "Button", "name": "Maximize"},
            {"i": 2, "kind": "Button", "name": "Close"}, {"i": 4, "kind": "Pane", "name": "Non Client Input Sink Window"},
        ],
    }
    assert _step("poner busqueda en BaxyPrueba", frame) is None


@pytest.mark.parametrize(
    "bar",
    [
        {"i": 3, "kind": "Edit", "name": "Barra de direcciones y de búsqueda", "value": "https://www.google.com/search?q=gatos"},
        {"i": 3, "kind": "Edit", "name": "Address and search bar", "value": "https://www.google.com/search?q=gatos"},
        {"i": 3, "kind": "Edit", "name": "Research notes", "value": ""},
    ],
)
def test_contracase_the_address_bar_or_a_name_holding_search_is_no_search_box(bar: dict) -> None:
    # Revisión r2, hallazgo 3: «en Chrome escribí gatos en la barra de búsqueda» never passes on the address bar that
    # already shows «…/search?q=gatos», and «search» inside «Research» names no search box.
    browser = {"ok": True, "window": {"title": "gatos - Buscar con Google", "focused": {"kind": "Document", "name": "gatos"}}, "controls": [bar]}
    assert _step("poner busqueda en gatos", browser) is None
    assert missions.read_clause("escribi gatos en la barra de busqueda")[1] == TYPED


_FORM = {
    "ok": True,
    "window": {"title": "Nuevo contacto", "focused": {"kind": "Button", "name": "Aceptar"}},
    "controls": [
        {"i": 1, "kind": "Edit", "name": "Nombre:", "value": ""},
        {"i": 2, "kind": "Edit", "name": "Subject", "value": ""},
        {"i": 3, "kind": "Button", "name": "Aceptar"},
    ],
}


@pytest.mark.parametrize(
    ("goal", "arguments"),
    [
        ("escribir Hola en el campo nombre", {"text": "Hola", "field": "Nombre", "replace": True}),
        # Revisión r2, hallazgo 6: the field's name in the other language of the screen.
        ("escribir Reunión en el campo de asunto", {"text": "Reunión", "field": "Subject", "replace": True}),
        ("escribir hi in the name field", {"text": "hi", "field": "Nombre", "replace": True}),
    ],
)
def test_a_named_field_the_view_shows_takes_the_text_before_the_place(goal: str, arguments: dict) -> None:
    step = _step(goal, _FORM)
    assert step is not None and step["operation"] == "input.text.type" and step["arguments"] == arguments


def test_contracase_a_named_place_the_view_lacks_is_typed_whole() -> None:
    # «nos vemos en el campo de futbol» on a form without a field «futbol»: the whole phrase is the person's text.
    focused = {**_FORM, "window": {"title": "Notas", "focused": {"kind": "Document", "name": "Editor", "value": ""}}}
    step = _step("escribir nos vemos en el campo de futbol", focused)
    assert step == {"operation": "input.text.type", "arguments": {"text": "nos vemos en el campo de futbol"}, "reason": step["reason"]}


def _labelled(name: str) -> dict:
    return {"ok": True, "window": {"title": "Registro"}, "controls": [
        {"i": 1, "kind": "Edit", "name": name, "value": ""}, {"i": 3, "kind": "Button", "name": "Aceptar"}]}


@pytest.mark.parametrize(
    ("goal", "label", "text"),
    [
        ("escribir John in your name field", "Your name", "John"),
        ("escribir Ana en el campo tu nombre", "Tu nombre", "Ana"),
        ("escribir great video in the add a comment box", "Add a comment", "great video"),
    ],
)
def test_a_field_whose_label_has_a_possessive_or_an_article_takes_the_text(goal: str, label: str, text: str) -> None:
    # Encargo W: the veto of possessives and indefinite articles in a field's name (_NOT_A_FIELD_NAME) was written with
    # backspaces and never matched; set right, it typed «John in your name field» into «Your name». It is gone: the view
    # decides, and these labels are the field.
    step = _step(goal, _labelled(label))
    assert step is not None and step["arguments"] == {"text": text, "field": label, "replace": True}


def test_contracase_the_field_of_my_uncle_is_typed_whole_on_a_view_without_it() -> None:
    # «el campo de mi tío» is a place of the text: no field of the view carries that name, so the whole phrase is typed.
    focused = {**_FORM, "window": {"title": "Notas", "focused": {"kind": "Document", "name": "Editor", "value": ""}}}
    step = _step("escribir nos vemos en el campo de mi tio", focused)
    assert step == {"operation": "input.text.type", "arguments": {"text": "nos vemos en el campo de mi tio"}, "reason": step["reason"]}


def test_the_message_box_holding_a_draft_is_never_replaced() -> None:
    # Revisión r2, hallazgo 2: «escribí hola en la caja de mensaje» with «borrador de la persona» in the box. The box is
    # clicked so the caret goes there, then the text is typed at the caret: never SetValue with replace.
    first = _step("escribir hola en la caja de mensaje", _CHAT_OPEN)
    assert first is not None and first["operation"] == "input.visible.click"
    assert first["arguments"] == {"label": "Escribe un mensaje", "index": 31}
    typing = {**_CHAT_OPEN, "window": {**_CHAT_OPEN["window"], "focused": {"kind": "Edit", "name": "Escribe un mensaje", "i": 31}}}
    clicked = [{"operation": "input.visible.click", "label": "Escribe un mensaje", "ok": True}]
    second = _step("escribir hola en la caja de mensaje", typing, clicked)
    assert second is not None and second["operation"] == "input.text.type" and second["arguments"] == {"text": "hola"}


def test_a_field_goal_never_replaces_a_message_draft() -> None:
    # Revisión r2, hallazgo 2, por la vía de los formularios: «poner mensaje en hola» sobre el borrador.
    assert _step("poner mensaje en hola", _CHAT_OPEN) is None
    empty = {**_CHAT_OPEN, "controls": [{**control, "value": ""} for control in _CHAT_OPEN["controls"]]}
    step = _step("poner mensaje en hola", empty)
    assert step is not None and step["arguments"]["field"] == "Escribe un mensaje"


def test_contracase_a_chat_box_is_never_the_chat_search() -> None:
    # Revisión r2, hallazgo 2: «type hello in the chat box» never goes to «Buscar un chat o iniciar uno nuevo».
    step = _step("escribir hello in the chat box", _CHAT_OPEN)
    assert step is None or (
        "Buscar" not in str(step["arguments"].get("field") or step["arguments"].get("label") or "")
        and "replace" not in step["arguments"]
    )
