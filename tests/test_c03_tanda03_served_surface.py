"""Tanda 3 (2026-09-24, official window): «no hago eso» about things the served catalog does.

«Pausa el speaker.», «Inactivar el microphone and the camera.», «me apetece que hagas sonar algo alegre»,
«Muéstrame mi Gallery.», «añadir una nueva lista para material escolar» were refused; «para la música, me va a
explotar la cabeza» was answered with chat; «¿puedes crear un programa en java…?» with «no creo programas»;
«reanudar la lectura de la lección de francés» ran note.restore and showed «argumentos inválidos».

- Before a limit is published the request is re-read in its canonical surface (``semantic.surface``): the
  words the readers know stand where the person said another one. What the readers prove is done, what lacks
  a value is asked, and a served operation only the rewrite grounds is re-decided and, if still refused, asked
  about. A limit of something BAXY does not have keeps its words and stays a limit.
- An order said before talk about it is the order.
- Code is written in the conversation like any other text.
- Restoring or trashing a note must name a note.

The phrasings below are not the tanda's: they are paraphrases the fix does not name.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import surface
from baxy_mind.semantic.patterns import conversation_only_content_request, operation_domain_is_grounded
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence

OPERATIONS = (
    "media.control", "media.play.query", "media.play.youtube", "media.play.exact", "audio.microphone.mute",
    "audio.mute", "audio.volume.adjust", "filesystem.folder.open", "task.create", "note.create", "note.restore",
    "web.search", "system.time",
)
_DESCRIPTIONS = {
    "filesystem.folder.open": "Abre una carpeta conocida de Windows: escritorio, documentos, descargas o imagenes.",
    "media.control": "Pausa, reanuda o salta lo que suena.",
    "media.play.query": "Reproduce musica pedida por genero o descripcion.",
    "task.create": "Crea una tarea o una lista de tareas.",
}


# ------------------------------------------------------------------ the canonical surface


@pytest.mark.parametrize(
    ("said", "canonical"),
    [
        ("Pausa el speaker.", "Pausa el audio."),
        ("detén los parlantes un rato", "detén el audio un rato"),
        ("stop my speakers", "stop the audio"),
        ("baja el volumen del altavoz", "baja el volumen del audio"),
        ("Inactivar el microphone and the camera.", "desactivar el microphone and the camera."),
        ("inactívame el micro", "desactivame el micro"),
        ("me apetece que hagas sonar algo alegre", "pon algo alegre"),
        ("Baxy, quiero que me pongas algo de Queen", "Baxy, ponme algo de Queen"),
        ("me gustaría que pauses la música", "pausa la música"),
        ("necesito que busques recetas de pan", "busca recetas de pan"),
        ("haz sonar música de Chopin", "pon música de Chopin"),
        ("Muéstrame mi Gallery.", "Muéstrame mi carpeta de imagenes."),
        ("open my gallery", "open my pictures folder"),
        ("añadir una nueva lista para material escolar", "crea una lista para material escolar"),
        ("add a new list for groceries", "create a list for groceries"),
    ],
)
def test_the_canonical_surface_replaces_only_the_words_said_another_way(said: str, canonical: str) -> None:
    assert surface.canonical(said) == canonical


@pytest.mark.parametrize(
    "said",
    ["Prende la smart camera", "abre Spotify", "qué hora es", "pausa la música", "inactivo", "quiero que sea así"],
)
def test_a_message_said_with_the_readers_words_has_no_other_surface(said: str) -> None:
    assert surface.canonical(said) is None


@pytest.mark.parametrize(
    ("said", "operations"),
    [
        ("pon en pausa la bocina", ("media.control",)),
        ("ponle pausa al speaker", ("media.control",)),
        ("para el parlante", ("media.control",)),
        ("resume the speakers", ("media.control",)),
        ("inactiva el micrófono por favor", ("audio.microphone.mute",)),
        ("quiero que silencies el micro", ("audio.microphone.mute",)),
        ("me gustaría que reproduzcas algo de Bad Bunny", ("media.play.query",)),
        ("hazme sonar una canción de Shakira", ("media.play.query",)),
    ],
)
def test_what_is_said_another_way_reads_as_the_served_request(said: str, operations: tuple[str, ...]) -> None:
    assert read(said, available_operations=OPERATIONS).effects is None
    canonical = surface.canonical(said)
    assert canonical is not None
    reading = read(canonical, available_operations=OPERATIONS)
    found = reading.effects or reading.clarification
    assert found is not None and set(found.operations) <= set(operations) | {"media.play.youtube"}
    assert found.operations[0] in operations or found.operations == ("media.play.youtube",)


@pytest.mark.parametrize(
    ("said", "operation"),
    [
        ("agrega una nueva lista de pendientes", "task.create"),
        ("add a list for my trip", "task.create"),
        ("haz sonar algo movido", "media.play.query"),
    ],
)
def test_what_is_said_another_way_asks_its_missing_value(said: str, operation: str) -> None:
    canonical = surface.canonical(said)
    assert canonical is not None
    reading = read(canonical, available_operations=OPERATIONS)
    assert reading.clarification is not None and reading.clarification.operations == (operation,)


# ------------------------------------------------------------------ the turn


class _RefusingLlm:
    """The model of the real run: it refuses, or proposes the operation the domain gate then vetoed."""

    def __init__(self, *, proposal: str | None = None, accepts_canonical: str | None = None) -> None:
        self.proposal = proposal
        self.accepts_canonical = accepts_canonical
        self.decided: list[str] = []
        self.chats = 0
        self.confirmations: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def decide_turn(self, text: str, *_args: object, **_kwargs: object) -> dict[str, object]:
        self.decided.append(text)
        operation = self.accepts_canonical if len(self.decided) > 1 else self.proposal
        if operation is not None:
            return {
                "mode": "action", "operation": operation, "question": "", "conversation_kind": "",
                "effect_count": "one", "effect_operations": [operation], "effect_verification": "agreed",
                "response_language": "es",
            }
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "unsupported",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "es",
        }

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Eso no lo hago.", []

    def confirm_operation_before_acting(
        self, text: str, effects: tuple[tuple[str, str], ...], **_kwargs: object,
    ) -> str:
        self.confirmations.append((text, effects))
        return "¿Quieres que abra tu carpeta de Imágenes?"

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que ponga?"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": _DESCRIPTIONS.get(operation, f"Authenticated catalog leaf {operation}."),
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _turn(text: str, llm: _RefusingLlm) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "turn-served-surface", "text": text, "history": [{"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation", "objective"),
    [
        ("Pon en pausa los parlantes.", "media.control", "pausa el audio."),
        ("inactivar el micro, porfa", "audio.microphone.mute", "desactivar el micro, porfa"),
        ("quiero que silencies el microphone", "audio.microphone.mute", "silencia el microphone"),
    ],
)
def test_a_refusal_of_a_served_request_said_another_way_acts(text: str, operation: str, objective: str) -> None:
    llm = _RefusingLlm()

    result = _turn(text, llm)

    assert result["kind"] == "action"
    assert result["operation"] == operation
    # The shell plans and confirms the words that were read.
    assert result["objective"] == objective
    assert llm.chats == 0


def test_a_vetoed_proposal_said_another_way_asks_its_missing_value() -> None:
    # The real run: the model proposed media.play.exact and the domain gate vetoed it into a limit.
    llm = _RefusingLlm(proposal="media.play.exact")

    result = _turn("me provoca que hagas sonar algo bailable", llm)

    assert result["kind"] == "clarify"
    assert result["intentOperations"] == ["media.play.query"]
    assert result["objective"] == "pon algo bailable"
    assert llm.chats == 0


def test_a_list_added_is_a_list_created_and_its_items_are_asked() -> None:
    llm = _RefusingLlm()

    result = _turn("agrega una nueva lista para el viaje", llm)

    assert result["kind"] == "clarify"
    assert result["intentOperations"] == ["task.create"]
    assert llm.chats == 0


def test_a_served_operation_only_the_rewrite_names_is_decided_again_on_the_rewrite() -> None:
    llm = _RefusingLlm(accepts_canonical="filesystem.folder.open")

    result = _turn("enséñame la galería", llm)

    assert llm.decided == ["enséñame la galería", "enséñame la carpeta de imagenes"]
    assert result["kind"] == "action"
    assert result["operation"] == "filesystem.folder.open"
    assert result["objective"] == "enséñame la carpeta de imagenes"


@pytest.mark.parametrize(
    "text", ["muéstrame la carpeta de imágenes", "muestra mis fotos", "dame la galería", "show me my pictures"],
)
def test_the_pictures_of_this_pc_are_never_an_image_downloaded_from_the_web(text: str) -> None:
    operations = ("web.download", "file.open", *OPERATIONS)
    for said in (text, surface.canonical(text) or text):
        reading = read(said, available_operations=operations)
        assert reading.effects is None or "web.download" not in reading.effects.operations


def test_an_image_from_the_web_is_still_downloaded() -> None:
    reading = read("muéstrame una foto de un gato", available_operations=("web.download", "file.open"))

    assert reading.effects is not None and reading.effects.operations == ("web.download", "file.open")


def test_a_served_operation_refused_again_on_the_rewrite_is_asked_never_denied() -> None:
    llm = _RefusingLlm()

    result = _turn("open my gallery", llm)

    assert result["kind"] == "clarify"
    assert result["intentOperations"] == ["filesystem.folder.open"]
    assert result["question"] == "¿Quieres que abra tu carpeta de Imágenes?"
    assert [effects[0][0] for _text, effects in llm.confirmations] == ["filesystem.folder.open"]
    assert result["objective"] == "open my pictures folder"
    assert llm.chats == 0


class _BrokenRereadLlm(_RefusingLlm):
    def decide_turn(self, text: str, *args: object, **kwargs: object) -> dict[str, object]:
        if self.decided:
            self.decided.append(text)
            raise sidecar.PlannerContractError("decisión de turno con forma inválida")
        return super().decide_turn(text, *args, **kwargs)


def test_a_reread_that_breaks_its_contract_keeps_the_limit_already_decided() -> None:
    llm = _BrokenRereadLlm()

    result = _turn("enséñame la galería", llm)

    assert llm.decided == ["enséñame la galería", "enséñame la carpeta de imagenes"]
    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert llm.chats == 1


@pytest.mark.parametrize(
    "text",
    [
        "Prende la smart camera",
        "enciende las luces del cuarto",
        "inactiva la alarma de la casa",
        "quiero que me hagas un café",
        "me gustaría que pidas un taxi",
        "publica en instagram que estoy de vacaciones",
    ],
)
def test_a_limit_of_what_baxy_does_not_have_stays_a_limit(text: str) -> None:
    llm = _RefusingLlm()

    result = _turn(text, llm)

    assert result["kind"] == "conversation"
    assert llm.chats == 1
    # Never decided again on another surface, never asked about a stranger operation.
    assert len(llm.decided) <= 1
    assert not llm.confirmations
    assert "objective" not in result


# ------------------------------------------------------------------ an order said before talk


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("para la música, me duele la cabeza", "media.control"),
        ("para la música, no aguanto más", "media.control"),
        ("apaga la música, me tiene harto", "media.control"),
        ("para la música, que me va a dar algo", "media.control"),
    ],
)
def test_an_order_said_before_talk_about_it_is_the_order(text: str, operation: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is not None and reading.effects.operations == (operation,)
    assert reading.source == "order_with_talk"


@pytest.mark.parametrize(
    "text",
    [
        "apaga el micro, digo el sonido",  # a correction
        "pausa la música, no, mejor no",  # a correction
        "pon música, algo tranquilo",  # more of the order
        "para la música, si puedes",  # a condition
        "silencia el micrófono, pon música",  # another order
    ],
)
def test_what_follows_an_order_and_is_not_talk_is_not_dropped(text: str) -> None:
    assert read(text, available_operations=OPERATIONS).source != "order_with_talk"


# ------------------------------------------------------------------ code in the conversation


@pytest.mark.parametrize(
    "text",
    [
        "¿me escribes una función en java que invierta un arreglo?",
        "crea un programa en c++ para calcular el factorial",
        "write a python function to reverse a string",
        "hazme un script que renombre archivos",
        "genera un algoritmo para ordenar números",
        "can you write a java program that prints hello world",
    ],
)
def test_code_is_written_in_the_conversation(text: str) -> None:
    assert conversation_only_content_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "abre el programa de fotos",
        "ejecuta el script de backup",
        "programa una alarma a las 7",
        "crea un programa de radio",
        "dame el código del wifi",
        "guarda un script en python en el escritorio",
    ],
)
def test_a_program_that_is_not_code_to_write_is_not_a_draft(text: str) -> None:
    assert not conversation_only_content_request(text)


# ------------------------------------------------------------------ a note selector names a note


@pytest.mark.parametrize("operation", ["note.restore", "note.trash"])
def test_restoring_or_trashing_needs_a_note_named(operation: str) -> None:
    assert operation_domain_is_grounded("retoma la lectura del capítulo de historia", operation) is False
    assert operation_domain_is_grounded("recupera la nota de la compra", operation) is True


def test_a_note_never_named_is_not_restored() -> None:
    # The real run executed note.restore with nothing to select and showed «argumentos inválidos».
    llm = _RefusingLlm(proposal="note.restore")

    result = _turn("retoma la lectura del capítulo de historia", llm)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result["conversationKind"] == "unsupported"
