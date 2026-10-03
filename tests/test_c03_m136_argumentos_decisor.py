"""M136 (2026-10-03, DEV-G v4n, D58): the decider's arguments reach the operation's fields instead of being asked again.

DEV-G (iterable, sealed 2026-10-03) first turns where the decider of the App wrote the data and the turn asked for it:
- G-s040 «open Notepad and put it on the left half of the screen please» → {"app": "Notepad", "side": "left"}: «app» is
  app.open's «appId»;
- G-s116 «abrí spotify y ponime algo de jazz tranqui…» → {"app.open": "Spotify", "media.play.query": "jazz tranquilo"}:
  a value keyed by the operation is its one free required text;
- G-s097 «baxy abreme el obs que voy a grabar un tutorial» → «OBS Studio»: the said «OBS» is kept;
- G-s123 «resúmeme el pdf ese que se llama contrato_arriendo_2026…» and G-w40-t1 «busca un archivo que se llama
  cotizacion_mudanza» → a folder nobody said: a read looks in every known folder.
"""

from __future__ import annotations

import importlib

main = importlib.import_module("baxy_mind.__main__")

APP_OPEN = {"type": "object", "properties": {"appId": {"type": "string"}}, "required": ["appId"],
            "additionalProperties": False}
PLAY_QUERY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                               "query": {"type": "string"}},
              "required": ["provider", "query"], "additionalProperties": False}
FOLDERS = ["all_known", "desktop", "documents", "downloads"]
PDF_READ = {"type": "object", "properties": {"fileName": {"type": "string"}, "folder": {"type": "string", "enum": FOLDERS},
                                             "maximumCharacters": {"type": "integer"}},
            "required": ["fileName", "folder"], "additionalProperties": False}
KNOWN_SEARCH = {"type": "object", "properties": {"folder": {"type": "string", "enum": FOLDERS}, "query": {"type": "string"},
                                                 "limit": {"type": "integer"}, "subdirectory": {"type": "string"}},
                "required": ["folder", "query"], "additionalProperties": False}
TRASH = {"type": "object", "properties": {"fileName": {"type": "string"}, "folder": {"type": "string", "enum": FOLDERS}},
         "required": ["fileName", "folder"], "additionalProperties": False}


def _decided(text, operations, arguments, operation, schema, said=None):
    main._remember_decided_arguments(text, tuple(operations), tuple(arguments.items()))
    source = main._with_every_known_folder_unsaid(operation, schema, said or text)
    return main._with_decided_arguments(operation, text, {}, schema, source)


def test_g_s040_the_decider_s_app_is_app_open_s_app_id() -> None:
    text = "open Notepad and put it on the left half of the screen please"
    got = _decided(text, ["app.open", "window.snap"], {"app": "Notepad", "side": "left"}, "app.open", APP_OPEN)
    assert got == {"appId": "Notepad"}


def test_g_s116_values_keyed_by_the_operation() -> None:
    text = "abrí spotify y ponime algo de jazz tranqui, que estoy laburando y necesito algo de fondo"
    args = {"app.open": "Spotify", "media.play.query": "jazz"}
    assert _decided(text, ["app.open", "media.play.query"], args, "app.open", APP_OPEN) == {"appId": "Spotify"}
    assert _decided(text, ["app.open", "media.play.query"], args, "media.play.query", PLAY_QUERY) == {"query": "jazz"}


def test_g_s097_the_said_part_of_an_application_name() -> None:
    text = "baxy abreme el obs que voy a grabar un tutorial"
    assert _decided(text, ["app.open"], {"appId": "OBS Studio"}, "app.open", APP_OPEN) == {"appId": "OBS"}


def test_g_s123_and_g_w40_t1_an_unsaid_folder_of_a_read_is_every_known_folder() -> None:
    text = "o sea, resúmeme el pdf ese que se llama contrato_arriendo_2026, like en tres puntos"
    got = _decided(text, ["document.pdf.read"], {"fileName": "contrato_arriendo_2026", "folder": "Documentos"},
                   "document.pdf.read", PDF_READ)
    assert got["fileName"] == "contrato_arriendo_2026" and got["folder"] == "all_known"
    text = "busca un archivo que se llama cotizacion_mudanza"
    got = _decided(text, ["filesystem.known.search"], {"folder": "Descargas", "query": "cotizacion_mudanza"},
                   "filesystem.known.search", KNOWN_SEARCH)
    assert got == {"folder": "all_known", "query": "cotizacion_mudanza"}


def test_a_said_folder_is_kept_and_a_deletion_never_widens() -> None:
    text = "resúmeme el pdf contrato_arriendo_2026 de descargas"
    got = _decided(text, ["document.pdf.read"], {"fileName": "contrato_arriendo_2026", "folder": "Descargas"},
                   "document.pdf.read", PDF_READ)
    assert got["folder"] == "downloads"
    text = "borra el archivo viejo.txt"
    got = _decided(text, ["filesystem.known.trash.named"], {"fileName": "viejo.txt", "folder": "Documentos"},
                   "filesystem.known.trash.named", TRASH)
    assert got == {"fileName": "viejo.txt"}


def test_nothing_unsaid_is_added() -> None:
    text = "open the app please"
    assert _decided(text, ["app.open"], {"app": "Notepad"}, "app.open", APP_OPEN) is None
    text = "abre spotify"
    assert _decided(text, ["app.open"], {"ap": "Spotify"}, "app.open", APP_OPEN) is None
