"""cu-v3-documento-nuevo: a new document asked for is made by the opening, never the person's open one.

Uso real t4-r6 c14 «pegame lo que copie en un bloc de notas nuevo» reused the open Notepad and pasted into the
person's «*lista pan» (the decider's rewrite «Abre el Bloc de notas y pega…» lost «nuevo»); c06 «bro abre excel y crea
un blank workbook» with Excel open made nothing. The reading (``semantic.apps.asks_new_document``, words in
``semantic.lexicon``) marks app.open with ``newDocument``; the provider makes the document and sees it made
(tests/Baxy.Providers.Windows.Tests, WindowsInstalledApplicationOpenProviderTests).
"""

from __future__ import annotations

import pytest

from baxy_mind import computer_use, operation_floor
from baxy_mind import cu_history
from baxy_mind import cu_model_calls
from baxy_mind import compose_situation
from baxy_mind import computer_use_finals
from baxy_mind.semantic import apps, claims
from baxy_mind.semantic.arguments import with_new_document
from baxy_mind.semantic.patterns import resolve_application_catalog_app_id

NAMES = ("Bloc de notas", "Excel", "Word", "Spotify")


def _names_an_application(span: str) -> bool:
    return resolve_application_catalog_app_id(f"abre {span}", NAMES) is not None


@pytest.mark.parametrize(
    "text",
    [
        "pegame lo que copie en un bloc de notas nuevo",  # t4-c14
        "bro abre excel y crea un blank workbook",  # t4-c06
        "abre un documento nuevo de word",
        "pega el texto en un archivo nuevo de bloc de notas",
        "abre un excel en blanco",
        "abrí un word nuevo",
        "open a new notepad and paste what I copied",
        "open a new blank document in word",
        "abre otro documento de word",
        "abre excel en blanco",
    ],
)
def test_a_new_document_is_read_next_to_what_is_opened(text: str) -> None:
    assert apps.asks_new_document(text, _names_an_application)


@pytest.mark.parametrize(
    "text",
    [
        "abrí el bloc de notas",
        "abrí el bloc de notas y pegá lo que copié",
        "pegá en mi nota de compras",
        "abre de nuevo el bloc de notas",
        "abre excel otra vez",
        "what's new in notepad",
        "abre spotify y pon lo nuevo de bad bunny",
        "pon lo nuevo de spotify",
        # Review of cu-v3-documento-nuevo, finding 3: the product's name, a document of the person's (an article or a
        # possessive leads it), the text to write, and a window (no document: «otra ventana» was read as one, and in a
        # player the New command makes a playlist in the person's account).
        "abre el nuevo outlook",
        "abre el nuevo teams",
        "abre teams nuevo",
        "abre el documento nuevo que hice ayer en word",
        "abre el excel nuevo que me mandaron",
        "abre la hoja nueva de mi excel de gastos",
        "abre mi nota nueva",
        "abre el archivo nuevo.txt",
        "abre spotify en otra ventana",
        "abre word en otra ventana",
        "abre word y escribe nota nueva de compras",
        "open my new document",
        "pon lo nuevo de bad bunny y el tema nuevo de karol g",
    ],
)
def test_no_new_document_without_it_said_next_to_the_document(text: str) -> None:
    assert not apps.asks_new_document(text, _names_an_application)


def test_the_person_words_mark_the_opening_when_the_rewrite_lost_nuevo() -> None:
    # Twin of t4-r6 req 152: the plan's objective is the decider's rewrite, the person's message still says «nuevo».
    marked = with_new_document(
        {"appId": "windows.notepad"},
        ("pegame lo que copie en un bloc de notas nuevo", "Abre el Bloc de notas y pega lo que hay en el portapapeles."),
        NAMES,
    )
    assert marked == {"appId": "windows.notepad", "newDocument": True}


@pytest.mark.parametrize(
    "said",
    [
        ("abrí el bloc de notas y pegá lo que copié",),
        ("pegá en mi nota de compras", "abre el bloc de notas"),
    ],
)
def test_an_opening_not_asked_new_reuses_the_window(said: tuple[str, ...]) -> None:
    assert with_new_document({"appId": "windows.notepad"}, said, NAMES) == {"appId": "windows.notepad"}


def test_only_an_opening_is_marked() -> None:
    assert with_new_document({}, ("pegame lo que copie en un bloc de notas nuevo",), NAMES) == {}


def test_the_mission_opening_makes_the_new_workbook() -> None:
    # t4-c06 inside a mission: the application is not in front and the request asks for a blank workbook.
    decision = computer_use._decide_step(
        None, objective="bro abre excel y crea un blank workbook", goal="crear un blank workbook", application="Excel",
        success_check=None, view={}, history=[], budget_left=8, application_names=list(NAMES), subgoal=0,
        subgoal_count=1, translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert decision["operation"] == "app.open"
    assert decision["arguments"].get("newDocument") is True


def test_the_mission_opening_without_new_reuses() -> None:
    decision = computer_use._decide_step(
        None, objective="abre excel y suma la columna a", goal="sumar la columna a", application="Excel",
        success_check=None, view={}, history=[], budget_left=8, application_names=list(NAMES), subgoal=0,
        subgoal_count=1, translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert decision["operation"] == "app.open"
    assert "newDocument" not in decision["arguments"]


def test_the_floor_says_the_new_document_made() -> None:
    entry = operation_floor.floor_data()["operations"]["app.open"]
    assert operation_floor._variant(entry, {"newDocument": True})["es"][1] == "creé un documento nuevo en la aplicación"
    assert operation_floor._variant(entry, {}) is None


# ---------------------------------------------------------------- review of cu-v3-documento-nuevo

WIDE = ("Bloc de notas", "Excel", "Word", "Spotify", "Google Chrome", "Microsoft Teams")


@pytest.mark.parametrize(
    ("app_id", "said"),
    [
        # Finding 2: the marker belongs to the document of another application than the step's.
        ("Spotify", "abre el bloc de notas nuevo y spotify"),
        ("Spotify", "abre un bloc de notas nuevo y spotify"),
        ("Google Chrome", "copia el titulo de la pagina de chrome y pegalo en un bloc de notas nuevo"),
        ("Google Chrome", "copia el titulo de chrome y pegalo en un documento nuevo"),
        ("windows.notepad", "abre un documento nuevo de word"),
    ],
)
def test_the_new_document_is_the_step_applications_only(app_id: str, said: str) -> None:
    assert with_new_document({"appId": app_id}, (said,), WIDE) == {"appId": app_id}


@pytest.mark.parametrize(
    ("app_id", "said"),
    [
        ("windows.notepad", "copia el titulo de la pagina de chrome y pegalo en un bloc de notas nuevo"),
        ("Bloc de notas", "abre un bloc de notas nuevo y spotify"),
        ("Excel", "bro abre excel y crea un blank workbook"),
        ("Word", "abre un documento nuevo de word"),
        ("Excel", "abre un excel en blanco"),
        ("windows.notepad", "open a new notepad"),
    ],
)
def test_the_step_application_named_with_the_marker_is_marked(app_id: str, said: str) -> None:
    assert with_new_document({"appId": app_id}, (said,), WIDE) == {"appId": app_id, "newDocument": True}


def test_the_mission_opening_of_the_source_application_makes_nothing_new() -> None:
    # Finding 2, measured: «copia el titulo de la pagina de chrome y pegalo en un bloc de notas nuevo» opened Chrome
    # with newDocument (an empty window the mission then copied from).
    decision = computer_use._decide_step(
        None, objective="copia el titulo de la pagina de chrome y pegalo en un bloc de notas nuevo",
        goal="copiar el titulo de la pagina", application="Google Chrome", success_check=None, view={}, history=[],
        budget_left=8, application_names=list(WIDE), subgoal=0, subgoal_count=2,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert decision["operation"] == "app.open"
    assert "newDocument" not in decision["arguments"]


def test_the_sub_goal_the_model_wrote_marks_nothing() -> None:
    # Finding 8: only the person's words decide keys sent; the model's sub-goal «crear un libro nuevo» is not theirs.
    decision = computer_use._decide_step(
        None, objective="abre excel y suma la columna a", goal="crear un libro nuevo", application="Excel",
        success_check=None, view={}, history=[], budget_left=8, application_names=list(NAMES), subgoal=0,
        subgoal_count=1, translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert "newDocument" not in decision["arguments"]


def test_a_plain_opening_backs_no_creation() -> None:
    # Finding 1: the variant's verbs back an act only when the opening observed the document made.
    plain = computer_use_finals._act_ledger({"operation": "app.open", "verified": True, "succeeded": True})
    assert plain is not None and not {"crear", "hacer", "agregar"} & plain
    assert claims.unbacked_act("Abrí OBS Studio; la escena Pruebas quedó creada.", plain)
    made = computer_use_finals._act_ledger(
        {"operation": "app.open", "verified": True, "succeeded": True, "observed": {"newDocument": True}}
    )
    assert made is not None and "crear" in made
    assert claims.unbacked_act("Abrí Excel y creé un libro en blanco.", made) == ""


def test_the_opening_that_made_the_document_acted() -> None:
    # Finding 7: twin of ComputerUseMission.MayHaveActed.
    assert cu_history._may_have_acted({"operation": "app.open", "ok": True, "newDocument": True})
    assert not cu_history._may_have_acted({"operation": "app.open", "ok": True})


def test_the_new_document_not_made_is_said_as_a_fact() -> None:
    # Finding 6: never «new document not created» in prose.
    fact = compose_situation._CAUSE_FACT["new_document_not_created"]
    assert "new document not created" not in fact and "nothing was written" in fact
    spanish, english = operation_floor.failure_sentences()["new_document_not_created"]
    assert spanish.startswith("Abrí la aplicación, pero no pude crear un documento nuevo")
    assert english.startswith("I opened the app, but I couldn't make a new document")
