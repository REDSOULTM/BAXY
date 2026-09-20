"""REOPEN1957 H0542 «Crea una carpeta en el escritorio, mete un txt dentro,
comprímela y luego abre el zip», H0459 «cambiá el fondo de pantalla a azul» y
H0077 «descarga la imagen de portada de wikipedia.org y guardala en el
escritorio» (D11): misiones y lecturas sobre las herramientas tipadas
file.compress, file.open, desktop.wallpaper.set y web.download."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({
    "filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open", "desktop.wallpaper.set",
    "web.download", "app.open", "web.search", "browser.navigate", "backup.known.create", "filesystem.known.list",
})
MISSION = "Crea una carpeta en el escritorio, mete un txt dentro, comprímela y luego abre el zip"
FOLDER_NAME = {"type": "object", "properties": {"folder": {"type": "string"}, "name": {"type": "string"}}, "required": ["folder", "name"], "additionalProperties": False}


def test_the_zip_mission_is_four_typed_steps_with_windows_default_names() -> None:
    intent = effect_intent.resolve_explicit_effects(MISSION, AVAILABLE, ("Steam",), ())
    assert intent is not None and intent.operations == ("filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open")
    assert effect_intent.folder_txt_zip_open_mission(MISSION) == "desktop"
    directory = {"type": "object", "properties": {"folder": {"type": "string"}, "relativePath": {"type": "string"}}, "required": ["relativePath"], "additionalProperties": False}
    write = {"type": "object", "properties": {"folder": {"type": "string"}, "relativePath": {"type": "string"}, "text": {"type": "string"}, "expectedSha256": {"type": ["string", "null"]}}, "required": ["relativePath", "text"], "additionalProperties": False}
    assert mind._ground_explicit_arguments("filesystem.create.directory", MISSION, directory) == {"folder": "desktop", "relativePath": "Nueva carpeta"}
    assert mind._ground_explicit_arguments("filesystem.write.text", MISSION, write) == {"folder": "desktop", "relativePath": "Nueva carpeta/Nuevo documento de texto.txt", "text": "", "expectedSha256": None}
    assert mind._ground_explicit_arguments("file.compress", MISSION, FOLDER_NAME) == {"folder": "desktop", "name": "Nueva carpeta"}
    assert mind._ground_explicit_arguments("file.open", MISSION, FOLDER_NAME) == {"folder": "desktop", "name": "Nueva carpeta.zip"}
    assert effect_intent.known_unsupported_effect_request(MISSION, {"app.open"}) is True
    assert effect_intent.known_unsupported_effect_request(MISSION, AVAILABLE) is False


@pytest.mark.parametrize(
    ("text", "operation", "arguments"),
    [
        ("comprimí la carpeta Fotos del escritorio", "file.compress", {"folder": "desktop", "name": "Fotos"}),
        ("abre el zip Nueva carpeta.zip del escritorio", "file.open", {"folder": "desktop", "name": "Nueva carpeta.zip"}),
        ("abrí informe.pdf de documentos", "file.open", {"folder": "documents", "name": "informe.pdf"}),
    ],
)
def test_named_compress_and_open(text: str, operation: str, arguments: dict) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
    assert intent is not None and intent.operations == (operation,)
    assert mind._ground_explicit_arguments(operation, text, FOLDER_NAME) == arguments


def test_wallpaper_colour_and_picture() -> None:
    schema = {"type": "object", "properties": {"color": {"type": ["string", "null"]}, "folder": {"type": ["string", "null"]}, "name": {"type": ["string", "null"]}}, "required": [], "additionalProperties": False}
    colour = "cambiá el fondo de pantalla a azul"
    picture = "poné de fondo de pantalla la foto playa.jpg de imágenes"
    for text in (colour, picture):
        intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
        assert intent is not None and intent.operations == ("desktop.wallpaper.set",)
    assert mind._ground_explicit_arguments("desktop.wallpaper.set", colour, schema) == {"color": "azul", "folder": None, "name": None}
    assert mind._ground_explicit_arguments("desktop.wallpaper.set", picture, schema) == {"color": None, "folder": "pictures", "name": "playa.jpg"}
    assert effect_intent.resolve_explicit_effects("no cambies el fondo de pantalla", AVAILABLE, ("Steam",), ()) is None
    assert effect_intent.known_unsupported_effect_request(colour, {"app.open"}) is True


def test_web_download_of_a_page_cover_and_of_a_file() -> None:
    schema = {"type": "object", "properties": {"url": {"type": "string"}, "folder": {"type": ["string", "null"]}, "name": {"type": ["string", "null"]}}, "required": ["url"], "additionalProperties": False}
    cover = "descarga la imagen de portada de wikipedia.org y guardala en el escritorio"
    file = "descarga https://example.com/a.pdf en descargas"
    for text in (cover, file):
        intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
        assert intent is not None and intent.operations == ("web.download",)
    assert mind._ground_explicit_arguments("web.download", cover, schema) == {"url": "wikipedia.org", "folder": "desktop", "name": None}
    assert mind._ground_explicit_arguments("web.download", file, schema) == {"url": "https://example.com/a.pdf", "folder": "downloads", "name": None}
    assert effect_intent.known_unsupported_effect_request(cover, {"browser.navigate"}) is True


@pytest.mark.parametrize(
    ("text", "payload", "defect"),
    [
        ("Comprimí Nueva carpeta en el escritorio como Nueva carpeta.zip.", {"operation": "file.compress", "seen": {"zipName": "Nueva carpeta.zip", "entryCount": 1, "bytes": 180, "folder": "desktop"}}, ""),
        ("Listo, comprimido.", {"operation": "file.compress", "seen": {"zipName": "Nueva carpeta.zip", "entryCount": 1, "bytes": 180, "folder": "desktop"}}, "missing_state"),
        ("Comprimí Nueva carpeta.zip con 25 archivos.", {"operation": "file.compress", "seen": {"zipName": "Nueva carpeta.zip", "entryCount": 1, "bytes": 180, "folder": "desktop"}}, "invented_number"),
        ("Puse el fondo de pantalla en azul.", {"operation": "desktop.wallpaper.set", "seen": {"mode": "solid_color", "color": "azul"}}, ""),
        ("Descargué portada.png en el escritorio.", {"operation": "web.download", "seen": {"name": "portada.png", "bytes": 5120, "folder": "desktop", "sourceUrl": "https://x/portada.png"}}, ""),
    ],
)
def test_the_reply_names_what_the_postread_saw(text: str, payload: dict, defect: str) -> None:
    assert llm._payload_fact_defect(text, payload, "") == defect


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("zip_already_exists", "file_not_found", "file_open_not_verified", "wallpaper_color_unknown", "download_page_without_image", "download_source_unavailable"):
        assert code in llm._CAUSE_FACT
