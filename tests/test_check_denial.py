"""Aid «check_denial» (2026-10-25): a reply of a turn with no call that says BAXY cannot do an act on the person's PC that a
tool of the catalog does («No puedo borrar carpetas de BAXY-bench», «No tengo acceso a tu carpeta», «No puedo leer el
texto del bloc de notas»), with no result behind it. The model is asked once more with a note that names the tool and
what its description says it does; never a reply. Real limits (a coffee, the lights, an app not installed, a window
BAXY may not act on, a confirmation pending) are not denials of a tool."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import DENIAL_NOTE, Mind
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say

CATALOG = {
    "filesystem.known.trash.named": "Delete a file, or a folder with everything in it (isFolder and entries say so), by "
                                    "its name from a known folder (or a subdirectory of it; the user's home folder too) "
                                    "by sending it to the Windows Recycle Bin, where the person can restore it. Use when: "
                                    "borra or elimina the file or the folder X.",
    "filesystem.create.directory": "Create a new folder in Desktop, Documents, Downloads, the user's home folder or BAXY's "
                                   "private work folder. Use when: crea una carpeta.",
    "filesystem.sandbox.move.named": "Move, or copy (copy true), a file given by its exact file name. Use when: moving "
                                     "or copying a file the person names.",
    "file.find": "List the top level of a known folder, or find files under it by name. Use when: busca un archivo.",
    "file.read": "Read the text of a file by its name from a known folder. Use when: lee el archivo X.",
    "file.open": "Open a specific file by its name from a known folder with its default app.",
    "file.write": "Write text to a file in Desktop, Documents, Downloads, the user's home folder.",
    "filesystem.explorer.count": "Count the files with an extension directly in a folder.",
    "input.visible.controls": "Look at an application window: its visible controls, and the text on screen with "
                              "includeText. Use when: read what it shows.",
    "app.open": "Open an installed application.",
    "note.read": "Read one note by its title.",
}


def _denials(answer: str, receipts: list | None = None, tries: list | None = None,
             catalog: dict | None = None) -> list[dict]:
    return [f for f in check(answer, "", receipts or [], [], catalog=CATALOG if catalog is None else catalog,
                             tries=tries or []) if f["rule"] == "denial"]


@pytest.mark.parametrize("answer, tool", [
    ("No puedo borrar carpetas de BAXY-bench, solo archivos. ¿Quieres que borre el archivo old-drafts?",
     "filesystem_known_trash_named"),
    ("No puedo eliminar carpetas de BAXY-bench directamente. Lo que sí puedo hacer es buscar archivos.",
     "filesystem_known_trash_named"),
    ("No puedo borrar archivos de la carpeta BAXY-bench, porque eso es mi carpeta de trabajo privada.",
     "filesystem_known_trash_named"),
    ("No puedo hacer eso directamente. No tengo acceso a tu carpeta BAXY-bench ni a sus archivos.", "file_find"),
    ("No puedo leer directamente el texto de un archivo de notas, pero puedo ayudarte a abrirlo.", "file_read"),
    ("No puedo leer notas del bloc de notas en voz alta directamente.", "input_visible_controls"),
    ("No, no la creé: BAXY-bench es mi carpeta de trabajo y no puedo crear carpetas ahí.",
     "filesystem_create_directory"),
    ("No, no la creé: BAXY-bench es mi carpeta de trabajo, no la tuya, y ahí no se pueden crear carpetas.",
     "filesystem_create_directory"),
    ("No puedo contar los archivos de esa carpeta.", "filesystem_explorer_count"),
    ("I can't delete folders inside BAXY-bench, only files.", "filesystem_known_trash_named"),
    ("I don't have access to your files.", "file_find"),
])
def test_a_denied_act_that_a_tool_of_the_catalog_does_is_flagged_with_that_tool(answer: str, tool: str) -> None:
    found = _denials(answer)
    assert len(found) == 1
    assert tool in found[0]["fact"]
    # What the tool does is its own description, never words to say.
    op = tool.replace("_", ".")
    assert CATALOG[op].split(". ")[0] in found[0]["fact"]


@pytest.mark.parametrize("answer", [
    "No puedo preparar café ni usar la cafetera.",
    "Lo siento, no puedo preparar café: eso es una acción física que no puedo hacer desde el PC.",
    "No puedo controlar las luces del techo.",
    "I can't control your ceiling lamp.",
    "No puedo pedir comida por ti.",
    "No puedo abrirlo: DaVinci Resolve no aparece en el catálogo de programas de Windows.",
    "No, no lo escribí: el foco estaba en Code, donde no puedo escribir.",
    "No, no lo escribí: el Bloc de notas es de Code, y no puedo escribir en sus ventanas.",
    "¿No puedo borrar archivos de esa carpeta?",
    "No puedo borrar el archivo sin que lo confirmes.",
    "Si no me dices en qué carpeta está, no puedo buscar el archivo.",
    "No puedo borrar archivos de tu USB.",
    "No puedo abrir archivos .exe.",
    "No borré el archivo.",
    "Puedo borrar la carpeta si quieres.",
    # Revisión w11-rev4: a condition after the denial, a place outside the person's folders, what the person asked.
    "No puedo abrir el archivo si no me dices cuál es.",
    "No puedo crear el archivo sin un nombre.",
    "I can't open the file unless you tell me which one.",
    "No puedo borrar archivos fuera de tus carpetas.",
    "I can't delete files outside your folders.",
    "No puedo borrar ese archivo: me pediste que no lo tocara.",
    "No puedo borrar archivos de esa carpeta, me dijiste que no borrara nada ahí.",
    "I can't delete that file, you asked me not to touch it.",
])
def test_real_limits_policy_questions_and_conditions_are_not_flagged(answer: str) -> None:
    assert _denials(answer) == []


def test_only_a_turn_with_no_call_is_read() -> None:
    receipt = {"op": "file.find", "tool": "file_find", "arguments": {}, "observation": "{}", "outcome": "falló",
               "completed": False, "read": True}
    assert _denials("No puedo borrar carpetas de BAXY-bench.", receipts=[receipt]) == []


def test_a_tool_the_catalog_does_not_have_is_no_denial() -> None:
    catalog = {k: v for k, v in CATALOG.items() if k != "filesystem.known.trash.named"}
    assert _denials("No puedo borrar carpetas de BAXY-bench.", catalog=catalog) == []
    assert [f for f in check("No puedo borrar carpetas de BAXY-bench.", "", [], []) if f["rule"] == "denial"] == []


@pytest.mark.parametrize("status", ["failed", "needs_confirmation", "cancelled", "unknown"])
def test_an_earlier_try_of_that_act_that_did_not_complete_may_be_what_it_tells(status: str) -> None:
    tries = [("filesystem.known.trash.named", status)]
    assert _denials("No puedo borrar archivos de la carpeta BAXY-bench.", tries=tries) == []


def test_an_earlier_try_refused_for_its_arguments_or_completed_still_leaves_the_denial() -> None:
    for status in ("rejected", "completed"):
        tries = [("filesystem.create.directory", status)]
        assert _denials("No, no la creé: no puedo crear carpetas ahí.", tries=tries)


# ---- the mind --------------------------------------------------------------------------------------------------------
def _configured(tmp_path: Path, replies: list) -> tuple[Mind, object]:
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [
        {"name": "filesystem.known.trash.named", "description": "Envía a la papelera.", "risk": "recoverable_delete",
         "argumentsSchema": {"type": "object", "properties": {"name": {"type": "string"}}}},
        {"name": "app.open", "description": "Abre una aplicación.", "risk": "low_reversible",
         "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"}}}}]})
    return mind, server


DENIED = "No puedo borrar carpetas de BAXY-bench, solo archivos."


def test_a_denial_is_asked_again_once_with_the_tool_and_may_act(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _configured(tmp_path, [_say(DENIED), _call("filesystem_known_trash_named",
                                                              {"folder": "home", "name": "BAXY-bench\\old-drafts"})])
    result = mind.decide(1, "delete the old-drafts folder inside BAXY-bench")
    assert result["kind"] == "action" and result["operation"] == "filesystem.known.trash.named"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(DENIAL_NOTE[:40])
    assert f"«{DENIED}»" in note["content"] and "filesystem_known_trash_named" in note["content"]
    assert "tool_choice" not in server.bodies[-1]  # it may use the tool it was told of
    # The conversation keeps neither the note nor the denial.
    assert not any(DENIED in str(m.get("content")) or str(m.get("content")).startswith(DENIAL_NOTE[:20])
                   for m in mind.conversation)
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert checks[0]["round"] == 1 and checks[0]["findings"][0]["rule"] == "denial"


def test_the_second_reply_is_final(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _configured(tmp_path, [_say(DENIED), _say("No puedo borrar carpetas, sólo archivos.")])
    result = mind.decide(1, "delete the old-drafts folder inside BAXY-bench")
    assert result["reply"] == "No puedo borrar carpetas, sólo archivos." and len(server.bodies) == 2


@pytest.mark.parametrize("setting, checked", [(None, True), ("answer_check", False), ("answer_check,check_denial", True),
                                              ("check_denial", False)])
def test_the_denial_rule_is_an_aid_of_its_own(tmp_path: Path, monkeypatch, setting, checked) -> None:
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _configured(tmp_path, [_say(DENIED), _say("Sí puedo: ¿la borro?")])
    result = mind.decide(1, "delete the old-drafts folder inside BAXY-bench")
    assert (result["reply"] != DENIED) is checked
    assert len(server.bodies) == (2 if checked else 1)


def test_an_earlier_failed_try_in_the_conversation_holds_the_denial(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _configured(tmp_path, [
        _call("filesystem_known_trash_named", {"name": "old-drafts"}), _say("No pude borrarla."),
        _say("No puedo borrar archivos de esa carpeta.")])
    mind.decide(1, "borra old-drafts")
    mind.continue_turn(2, json.dumps({"status": "failed", "error": "known_file_not_found"}))
    result = mind.decide(3, "¿por qué?")
    assert result["reply"] == "No puedo borrar archivos de esa carpeta." and len(server.bodies) == 3
