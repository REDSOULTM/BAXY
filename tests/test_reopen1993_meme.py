"""REOPEN1957 H0069 «Tienes algun meme?» (D11): un meme o una imagen de la web
se busca en el buscador de imágenes, se descarga a Imágenes y se abre con el
visor; una foto sin sujeto pregunta de qué; la negación no hace nada."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"web.download", "file.open", "web.search", "app.open"})
DOWNLOAD_SCHEMA = {
    "type": "object",
    "properties": {"url": {"type": ["string", "null"]}, "query": {"type": ["string", "null"]}, "folder": {"type": ["string", "null"]}, "name": {"type": ["string", "null"]}},
    "required": [],
    "additionalProperties": False,
}
OPEN_SCHEMA = {"type": "object", "properties": {"folder": {"type": "string"}, "name": {"type": "string"}}, "required": ["folder", "name"], "additionalProperties": False}


@pytest.mark.parametrize(
    ("text", "query", "name"),
    [
        ("Tienes algun meme?", "meme", "meme"),
        ("mandame un meme", "meme", "meme"),
        ("mostrame un meme de gatos", "meme de gatos", "meme"),
        ("show me a meme", "meme", "meme"),
        ("send me a cat meme", "cat meme", "meme"),
        ("pasame una foto de un gato", "foto de un gato", "foto"),
        ("mandame un gif de risa", "gif de risa", "gif"),
    ],
)
def test_a_meme_or_an_image_is_downloaded_and_opened(text: str, query: str, name: str) -> None:
    assert effect_intent.web_image_request(text) == (query, False)
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("web.download", "file.open")
    assert mind._ground_explicit_arguments("web.download", text, DOWNLOAD_SCHEMA) == {"url": None, "query": query, "folder": "pictures", "name": name}
    assert effect_intent.operation_domain_is_grounded(text, "web.download") is True
    assert effect_intent.operation_domain_is_grounded(text, "file.open") is True
    skeleton = mind._explicit_plan_skeleton(("web.download", "file.open"), (text, text))
    assert skeleton["steps"][1]["argumentsMode"] == "after_dependencies" and skeleton["steps"][1]["dependsOn"] == ["step_1"]


def test_the_viewer_opens_the_file_the_download_wrote() -> None:
    tool = {"function": {"parameters": OPEN_SCHEMA}}
    observations = [{"operation": "web.download", "verified": True, "status": "completed", "result": {"folder": "pictures", "name": "meme.png", "bytes": 10}}]
    assert mind._verified_dependency_identity_arguments("file.open", "Tienes algun meme?", observations, tool) == {"folder": "pictures", "name": "meme.png"}
    assert mind._verified_dependency_identity_arguments("file.open", "Tienes algun meme?", [], tool) is None
    assert mind._ground_explicit_arguments("file.open", "Tienes algun meme?", OPEN_SCHEMA) is None


def test_an_image_of_nothing_in_particular_is_asked_about() -> None:
    assert effect_intent.web_image_request("tienes alguna foto?") == ("foto", True)
    assert effect_intent.resolve_explicit_effects("tienes alguna foto?", AVAILABLE, (), ()) is None
    clarification = effect_intent.resolve_explicit_clarification_intent("tienes alguna foto?", AVAILABLE)
    assert clarification is not None and clarification.operations == ("web.download",) and clarification.missing_fields == ("query",)
    completed = effect_intent.resolve_explicit_effects("de un gato", AVAILABLE, (), (), previous_user_text="tienes alguna foto?")
    assert completed is not None and completed.operations == ("web.download", "file.open")
    assert effect_intent.web_image_request(completed.evidence[0]) == ("foto de un gato", False)


def test_a_negation_and_the_old_limit_without_the_tools() -> None:
    assert effect_intent.web_image_request("no me mandes memes") is None
    assert effect_intent.resolve_explicit_effects("Tienes algun meme?", {"app.open", "web.search"}, (), ()) is None
    assert effect_intent.visual_content_request("Tienes algun meme?") is True


def test_the_other_file_open_plans_keep_their_literal_names() -> None:
    deck = mind._explicit_plan_skeleton(("document.presentation.create", "file.open"), ("Haz un powerpoint hablando de amor de 6 diapositivas",) * 2)
    assert deck["steps"][1]["argumentsMode"] == "literal"
    for code in ("download_source_missing", "download_query_without_image"):
        assert code in llm._CAUSE_FACT
