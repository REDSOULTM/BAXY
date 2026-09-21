"""REOPEN1957 H0188 «Haz un powerpoint hablando de amor de 6 diapositivas»
(D11): la mente lee el tema y la cantidad, el modelo local redacta las
diapositivas, document.presentation.create escribe el paquete y file.open lo
abre; el final nombra el archivo y cuenta las diapositivas del paquete."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"document.presentation.create", "file.open", "office.document.create", "app.open", "web.search"})


@pytest.mark.parametrize(
    ("text", "topic", "count"),
    [
        ("Haz un powerpoint hablando de amor de 6 diapositivas", "amor", 6),
        ("armá una presentación sobre el sistema solar de 4 diapositivas", "el sistema solar", 4),
        ("creá un powerpoint sobre gatos", "gatos", 6),
        ("hacé una presentación de tres slides sobre la fotosíntesis", "la fotosíntesis", 3),
        ("make a presentation about dogs with 5 slides", "dogs", 5),
    ],
)
def test_a_deck_request_is_written_and_opened(text: str, topic: str, count: int) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("document.presentation.create", "file.open")
    assert effect_intent.presentation_request(text) == (topic, count)
    assert effect_intent.operation_domain_is_grounded(text, "document.presentation.create") is True


def test_negations_and_topicless_requests_abstain() -> None:
    assert effect_intent.presentation_request("no hagas un powerpoint") is None
    assert effect_intent.presentation_request("crea un powerpoint") is None
    assert effect_intent.known_unsupported_effect_request("Haz un powerpoint hablando de amor de 6 diapositivas", {"app.open"}) is True
    assert effect_intent.known_unsupported_effect_request("Haz un powerpoint hablando de amor de 6 diapositivas", AVAILABLE) is False


class _FakeModel:
    def __init__(self, slides: list[str]) -> None:
        self.slides = slides
        self.asked: tuple[str, int] | None = None

    def compose_presentation_slides(self, topic: str, count: int) -> list[str]:
        self.asked = (topic, count)
        return self.slides


def test_the_model_writes_the_slides_and_the_request_owns_title_and_count() -> None:
    model = _FakeModel([f"Diapositiva {index}\nUna idea\nOtra idea" for index in range(1, 7)])
    arguments = mind._presentation_arguments(model, "Haz un powerpoint hablando de amor de 6 diapositivas")
    assert model.asked == ("amor", 6)
    assert arguments is not None
    assert arguments["title"] == "Amor" and arguments["folder"] == "documents"
    assert len(arguments["slides"]) == 6 and arguments["slides"][0] == "Diapositiva 1\nUna idea\nOtra idea"
    assert mind._presentation_arguments(_FakeModel(["solo una"]), "Haz un powerpoint hablando de amor de 6 diapositivas") is None
    schema = {"type": "object", "properties": {"folder": {"type": "string"}, "name": {"type": "string"}}, "required": ["folder", "name"], "additionalProperties": False}
    assert mind._ground_explicit_arguments("file.open", "Haz un powerpoint hablando de amor de 6 diapositivas", schema) == {"folder": "documents", "name": "Amor.pptx"}


@pytest.mark.parametrize(
    ("text", "defect"),
    [
        ("Creé Amor.pptx en Documentos con 6 diapositivas.", ""),
        ("Creé la presentación Amor con seis diapositivas.", ""),
        ("Creé Amor.pptx con 12 diapositivas.", "invented_number"),
        ("Listo, la presentación está hecha.", "missing_state"),
    ],
)
def test_the_reply_names_the_file_and_the_slide_count(text: str, defect: str) -> None:
    payload = {"operation": "document.presentation.create", "seen": {"name": "Amor.pptx", "folder": "documents", "slideCount": 6, "slideTitles": []}}
    assert llm._payload_fact_defect(text, payload, "Haz un powerpoint hablando de amor de 6 diapositivas") == defect


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("presentation_slides_invalid", "presentation_write_failed", "presentation_postread_failed"):
        assert code in llm._CAUSE_FACT
