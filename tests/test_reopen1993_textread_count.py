"""REOPEN1957 H0299 (ruta pegada de un ROADMAP.md) y H0701 «Dime cuantos
archivos .py hay en el directorio actual» (D24): una ruta bajo una carpeta
conocida se lee para decir de qué trata (un PDF va al lector de PDF); una ruta
fuera de esas carpetas sigue preguntando; el directorio actual es la carpeta
del Explorador en primer plano y se cuenta por extensión."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"document.text.read", "document.pdf.read", "filesystem.explorer.count", "filesystem.known.search", "app.open"})
TEXT_SCHEMA = {
    "type": "object",
    "properties": {"fileName": {"type": "string"}, "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]}, "maximumCharacters": {"type": "integer"}, "subdirectory": {"type": "string"}},
    "required": ["fileName", "folder"],
    "additionalProperties": False,
}
COUNT_SCHEMA = {"type": "object", "properties": {"extension": {"type": "string"}}, "required": ["extension"], "additionalProperties": False}
ROADMAP = r"%USERPROFILE%\Desktop\ETC\Programacion\Probando Gemma 4\gemma4_agent\ROADMAP.md"


@pytest.mark.parametrize(
    ("text", "operation", "arguments"),
    [
        (ROADMAP, "document.text.read", {"fileName": "ROADMAP.md", "folder": "desktop", "subdirectory": r"ETC\Programacion\Probando Gemma 4\gemma4_agent"}),
        (r"C:\Users\usuario\Desktop\notas.txt", "document.text.read", {"fileName": "notas.txt", "folder": "desktop"}),
        ("~/Documents/proyecto/main.py", "document.text.read", {"fileName": "main.py", "folder": "documents", "subdirectory": "proyecto"}),
        (r"C:\Users\usuario\Documents\informe.pdf", "document.pdf.read", {"fileName": "informe.pdf", "folder": "documents"}),
    ],
)
def test_a_pasted_path_under_a_known_folder_is_read(text: str, operation: str, arguments: dict) -> None:
    assert effect_intent.known_folder_file_path(text) == (operation, arguments)
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == (operation,)
    assert mind._ground_explicit_arguments(operation, text, TEXT_SCHEMA) == arguments
    assert effect_intent.operation_domain_is_grounded(text, operation) is True
    # A Windows-shaped path is still the «bare_path» shape; the decide flow lifts it when the reader serves it.
    assert mind._unresolved_input_kind(text) == ("bare_path" if "\\" in text else None)


@pytest.mark.parametrize("text", [r"D:\Perfil\Escritorio\ETC\x.md", r"C:\Users\usuario\Downloads\setup.exe", r"C:\Windows\System32\drivers\etc\hosts"])
def test_paths_outside_the_known_folders_or_not_text_keep_the_honest_question(text: str) -> None:
    assert effect_intent.known_folder_file_path(text) is None
    assert effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ()) is None
    assert mind._unresolved_input_kind(text) in {"bare_path", None}


@pytest.mark.parametrize(
    ("text", "extension"),
    [
        ("Dime cuantos archivos .py hay en el directorio actual", ".py"),
        ("cuántos archivos .txt hay en esta carpeta?", ".txt"),
        ("how many .py files are in the current directory", ".py"),
        ("contá los .py del directorio actual", ".py"),
    ],
)
def test_the_current_directory_is_the_explorer_folder_in_front(text: str, extension: str) -> None:
    assert effect_intent.explorer_count_request(text) == extension
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("filesystem.explorer.count",)
    assert mind._ground_explicit_arguments("filesystem.explorer.count", text, COUNT_SCHEMA) == {"extension": extension}
    assert effect_intent.resolve_explicit_clarification_intent(text, AVAILABLE) is None
    assert effect_intent.operation_domain_is_grounded(text, "filesystem.explorer.count") is True


def test_without_the_counting_tool_the_folder_is_still_asked_and_negations_do_nothing() -> None:
    text = "Dime cuantos archivos .py hay en el directorio actual"
    without = frozenset({"filesystem.known.search", "app.open"})
    clarification = effect_intent.resolve_explicit_clarification_intent(text, without)
    assert clarification is not None and clarification.operations == ("filesystem.known.search",)
    assert effect_intent.explorer_count_request("no cuentes los .py del directorio actual") is None
    assert effect_intent.explorer_count_request("cuántos .py hay en el escritorio") is None


@pytest.mark.parametrize(
    ("text", "defect"),
    [
        ("En la carpeta gemma4_agent hay 3 archivos .py.", ""),
        ("Hay 3 archivos .py en gemma4_agent, de 7 archivos en total.", ""),
        ("Hay 5 archivos .py en gemma4_agent.", "invented_number"),
        ("Hay tres archivos .py en esa carpeta.", "missing_state"),
    ],
)
def test_the_count_reply_gives_the_figure_and_names_the_folder(text: str, defect: str) -> None:
    payload = {"operation": "filesystem.explorer.count", "seen": {"folderName": "gemma4_agent", "source": "explorer_foreground", "extension": ".py", "count": 3, "filesInFolder": 7}}
    assert llm._payload_fact_defect(text, payload, "Dime cuantos archivos .py hay en el directorio actual") == defect


def test_the_text_read_is_presented_like_a_pdf_with_its_line_count() -> None:
    projected = llm._project_pdf_read({"reviewLabel": "ROADMAP.md", "lines": 12, "text": "# ROADMAP\n\nFase 1: agente local. Fase 2: memoria.\n", "truncated": False}, "es")
    assert projected["document"] == "ROADMAP.md" and projected["lines"] == 12 and projected["pages"] is None
    assert projected["lead"].startswith("# ROADMAP")
    payload = {"operation": "document.text.read", "seen": projected}
    assert llm._pdf_read_in_payload(payload) is not None
    assert llm._payload_fact_defect("Leí ROADMAP.md, 12 líneas; dice «# ROADMAP Fase 1: agente local.»", payload, ROADMAP) == ""
    assert llm._payload_fact_defect("Leí ROADMAP.md; dice «Fase 9: nada».", payload, ROADMAP) == "pdf_unquoted_passage"
    for code in ("known_file_not_text", "known_text_too_large", "explorer_folder_unavailable", "extension_invalid"):
        assert code in llm._CAUSE_FACT
