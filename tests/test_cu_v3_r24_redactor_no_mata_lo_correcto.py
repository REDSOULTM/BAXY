"""Ronda 24 de uso real (tandas r23): the writer neither kills a right draft nor leaves a turn without its final.

- t2-c02#3 «dale, la segunda como se hace?»: the recipe's length note went as a system message after the user's one;
  the product's chat template answers HTTP 400 («System message must be at the beginning», confirmed with a request to
  llama-server on the product's Qwen3.5 4B) and the composer raised, leaving no final.
- t3-c09 t1 «vi que los SLEVE EVO están emparejados»: a look told in the first person read as an act on a screen value.
- t3-c16 t4: «De Música Ligera Soda Stereo» dropped as a subject because it shares words with «De Música Ligera».
- t4-c02 t3 «No hay película de Bestiario…, pero sí existe una llamada Bestiario de 2002.»: denied and affirmed.
"""

from __future__ import annotations

import importlib.util
import time
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from baxy_mind import llm
from baxy_mind import payload_fact_checks
from baxy_mind import search_report
from baxy_mind import computer_use_finals
from baxy_mind import llm_compose
from baxy_mind.llm_transport import ChatCompletionCancellation, ChatCompletionCancelled
from baxy_mind.semantic import answer_evidence, claims, listing
from baxy_mind.semantic.web import carried_subjects, names_subject


# --- (a) a system message after the dialogue began -------------------------------------------------------------------

def _sent(messages: list[dict]) -> list[dict]:
    runtime = object.__new__(llm.LlmRuntime)
    payload = {"messages": messages, "max_tokens": 64}
    with patch("baxy_mind.llm.post_chat_completion", return_value={"choices": []}) as transport:
        runtime._post(payload, max_attempts=1, cancellation=ChatCompletionCancellation())
    return transport.call_args.args[0]["messages"]


def test_a_late_system_note_is_served_with_the_prefix_and_the_dialogue_keeps_its_order() -> None:
    user = {"role": "user", "content": '{"request": "la segunda como se hace?"}'}
    sent = _sent([
        {"role": "system", "content": "Escribe la receta."}, user,
        {"role": "system", "content": "Tienes espacio para unas 100 palabras."},
        {"role": "system", "content": "Usa la forma pedida."},
    ])
    assert sent == [
        {"role": "system", "content": "Escribe la receta.\n\nTienes espacio para unas 100 palabras.\n\nUsa la forma pedida."},
        user,
    ]
    dialogue = [
        {"role": "user", "content": "hola"}, {"role": "assistant", "content": "Hola."}, {"role": "user", "content": "y?"},
    ]
    sent = _sent([{"role": "system", "content": "A"}, *dialogue[:2], {"role": "system", "content": "B"}, dialogue[2]])
    assert sent == [{"role": "system", "content": "A\n\nB"}, *dialogue]


def test_contracase_a_payload_with_one_leading_system_is_sent_as_it_is() -> None:
    messages = [{"role": "system", "content": "A"}, {"role": "user", "content": "x"}]
    assert _sent(list(messages)) == messages


class _Failing(llm.LlmRuntime):
    def __init__(self, error: BaseException) -> None:  # noqa: D107
        self._gguf = None
        self._measured_decode_rate = 26.0
        self.error = error
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        raise self.error


def _recipe(client: llm.LlmRuntime, seconds_left: float) -> object:
    reference = {
        "kind": "recipe", "title": "Arroz con pollo", "text": "Ingredientes: 1 taza de arroz…", "servings": None,
        "seen": {},
    }
    with patch.object(llm_compose, "_reference_of", lambda situation: reference):
        return client._compose_consulted_answer(
            "la segunda como se hace? pasame los pasos cortitos", {"priorRequests": ["dame 5 ideas de cena"]},
            {"operation": "web.search"}, "es", client._post, time.monotonic() + seconds_left, "",
        )


def test_a_recipe_draft_the_server_refuses_leaves_the_final_to_the_ordinary_composition() -> None:
    client = _Failing(urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", 400, "bad", {}, None))
    assert _recipe(client, 9.9) is None
    assert client.payloads  # it was asked, and the failure did not end the turn


def test_contracase_a_cancelled_or_dropped_recipe_draft_is_still_the_callers() -> None:
    with pytest.raises(ChatCompletionCancelled):
        _recipe(_Failing(ChatCompletionCancelled("cancelada")), 9.9)
    with pytest.raises(ConnectionError):
        _recipe(_Failing(ConnectionError("el servidor cerró la conexión")), 9.9)


# --- (b) a look told in the first person is no act -------------------------------------------------------------------

SEEN = claims.fold("Bluetooth | Auriculares SLEVE EVO | Emparejado | Calculadora | Decimal | Programador")


def test_c09_a_look_told_in_the_first_person_acts_on_nothing() -> None:
    told = "Vi que los auriculares SLEVE EVO están emparejados."
    assert any("ver" in lemmas for _word, lemmas in claims.claimed_acts(told, third_person=False))
    assert claims.screen_only_object(told, claims.fold("bluetooth"), SEEN) == ""
    assert claims.screen_only_object("Comprobé que los SLEVE EVO están emparejados.", "", SEEN) == ""


def test_contracase_a_screen_value_told_as_an_act_stays_vetoed() -> None:
    assert claims.screen_only_object("Elegí el modo Decimal.", claims.fold("programador"), SEEN) == "decimal"


def _c18() -> dict:
    """The real situation of t3-c18/2 (tests/test_cu_v3_lo_no_hecho.py): Programmer reached, Decimal only on screen."""

    spec = importlib.util.spec_from_file_location("lo_no_hecho", Path(__file__).with_name("test_cu_v3_lo_no_hecho.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.C18_SITUATION


@pytest.mark.parametrize("told", [
    # Revisión 1 de r24 (bloqueante 1): a neutral lemma that is no look acts on what follows.
    "Llegué al Programador de la Calculadora y dejé el modo Decimal.",
    "Llegué al Programador de la Calculadora y usé el modo Decimal.",
    # A look with a direct object keeps it, and «lo elegí» takes up what the look saw.
    "Vi el modo Decimal en el Programador y lo elegí.",
    "Vi que el modo Decimal estaba disponible y lo elegí.",
])
def test_contracase_review_1_a_neutral_act_or_a_look_taken_up_stays_unbacked(told: str) -> None:
    assert computer_use_finals._claims_defect(told, "status", _c18()) == "unbacked_act"


def test_review_1_only_a_look_that_tells_a_state_is_skipped() -> None:
    situation = _c18()
    assert computer_use_finals._screen_value_told_as_act("Llegué al Programador y vi que quedó en Decimal.", situation) == ""
    assert computer_use_finals._screen_value_told_as_act("Llegué al Programador y comprobé que el modo Decimal está marcado.", situation) == ""


# --- (c) a subject written longer is the same subject ----------------------------------------------------------------

def test_c16_a_longer_writing_of_the_subject_adds_its_words() -> None:
    subjects = carried_subjects(
        "¿Quién cantaba De Música Ligera?", "quién cantaba De Música Ligera Soda Stereo", "cómo se llamaba el que cantaba",
        "De Música Ligera - Soda Stereo (Letra) La canción de 1990.\nOtra página",
    )
    assert subjects == ("De Música Ligera Soda Stereo",)
    assert names_subject("El cantante era Gustavo Cerati, de Soda Stereo.", subjects[0])
    assert names_subject("Cantaba Gustavo Cerati, en De Música Ligera.", subjects[0])


def test_contracase_oppenheimer_still_has_to_be_named() -> None:
    subjects = carried_subjects(
        "Buscá qué dijo la crítica sobre Oppenheimer.", "qué dijo la crítica sobre Oppenheimer",
        "averiguá qué dijo la crítica",
    )
    assert subjects == ("Oppenheimer",)
    assert not names_subject("John Carpenter no se subió a los elogios de la película.", subjects[0])


def test_contracase_review_1_two_entities_in_the_query_are_no_alternatives_of_the_subject() -> None:
    # Revisión 1 de r24 (bloqueante 3): no result writes «Chile Copa América Chile Argentina» as a unit.
    pages = "Chile vs Argentina: cuándo juega Chile en la Copa América\nFixture de la Copa América"
    subjects = carried_subjects(
        "¿Cuándo juega Chile?", "cuándo juega Chile Copa América Chile Argentina", "y cuándo juega", pages,
    )
    assert subjects == ("Chile",)
    payload = {"operation": "web.search", "verified": True, "seen": {
        "query": "cuándo juega Chile Copa América Chile Argentina",
        "results": [{"title": "Chile vs Argentina", "snippet": "Cuándo juega Chile en la Copa América.",
                     "url": "https://example.org/a"}],
    }}
    assert search_report._search_report_leaves_out_subject(
        "Argentina juega el martes contra Perú.", payload, "¿Cuándo juega Chile?", "y cuándo juega",
    ) == ["Chile"]
    subjects = carried_subjects(
        "Buscá qué dijo la crítica sobre Oppenheimer.", "crítica Oppenheimer Christopher Nolan",
        "averiguá qué dijo la crítica", "Oppenheimer, la película de Christopher Nolan, divide a la crítica",
    )
    assert subjects == ("Oppenheimer",)
    assert not names_subject("Christopher Nolan habló de su trabajo.", subjects[0])
    # Without results, a longer writing never replaces the subject.
    assert carried_subjects(
        "¿Quién cantaba De Música Ligera?", "quién cantaba De Música Ligera Soda Stereo", "cómo se llamaba el que cantaba",
    ) == ("De Música Ligera",)


# --- (d) one name denied and affirmed --------------------------------------------------------------------------------

def test_t4_c02_a_name_denied_and_affirmed_is_found() -> None:
    told = "No hay película de Bestiario ni de Rayuela, pero sí existe una llamada Bestiario de 2002."
    assert answer_evidence.denied_and_affirmed(told) == ["Bestiario de 2002"]


def test_contracase_different_names_denied_and_affirmed_are_no_contradiction() -> None:
    assert answer_evidence.denied_and_affirmed("Rayuela no tiene película, pero Bestiario sí.") == []
    assert answer_evidence.denied_and_affirmed("Hay una película de Bestiario. No hay de Rayuela.") == []
    assert answer_evidence.denied_and_affirmed("Bestiario tiene película desde 2002.") == []


def _search(*snippets: str) -> dict:
    results = [{"title": snippet.split(".")[0], "snippet": snippet, "url": f"https://example.org/{index}"}
               for index, snippet in enumerate(snippets)]
    return {"operation": "web.search", "verified": True, "seen": {"results": results}}


@pytest.mark.parametrize(("told", "evidence"), [
    # Revisión 1 de r24 (bloqueante 2): a partial report says what it did not find; that denies nothing.
    ("The Last of Us tiene dos temporadas. No encontré cuándo sale la tercera de The Last of Us.",
     "The Last of Us tiene dos temporadas en HBO."),
    ("Dune: Parte Dos se estrenó en 2024. No encontré la fecha de estreno de Dune: Parte Tres.",
     "Dune: Parte Dos se estrenó en 2024."),
    ("Dune: Parte Dos se estrenó en 2024, pero no encontré la fecha de Dune: Parte Tres.",
     "Dune: Parte Dos se estrenó en 2024."),
    # A correction that names its subject again denies no existence.
    ("No, Taylor Swift no está casada; Taylor Swift está comprometida con Travis Kelce.",
     "Taylor Swift está comprometida con Travis Kelce."),
    # The owner of what is lacking is not denied («no tiene hijos» says nothing against «Taylor Swift»).
    ("Taylor Swift no tiene hijos. Taylor Swift está comprometida con Travis Kelce.",
     "Taylor Swift está comprometida con Travis Kelce."),
    # The way out the repair asks for: the other thing told as another.
    ("No hay película de Bestiario de Cortázar; la Bestiario de 2002 es otra obra.",
     "Bestiario (2002) es una película de terror."),
    ("There is no film of Bestiario by Cortázar; the 2002 Bestiario is a different work.",
     "Bestiario (2002) is a horror film."),
])
def test_contracase_review_1_a_report_that_denies_no_existence_is_no_contradiction(told: str, evidence: str) -> None:
    assert answer_evidence.denied_and_affirmed(told, evidence, search_report._SEARCH_NOT_FOUND) == []
    assert payload_fact_checks._payload_fact_defect(told, _search(evidence)) != "search_report_denies_and_affirms"


@pytest.mark.parametrize("told", [
    "No hay película de Bestiario ni de Rayuela, pero sí existe una llamada Bestiario de 2002.",
    "No existe una película de Bestiario. Bestiario de 2002 es una película de terror.",
    "Bestiario no existe como película, aunque Bestiario de 2002 es una película de terror.",
    "There is no film of Bestiario, but there is one called Bestiario from 2002.",
])
def test_review_1_an_existence_denied_then_affirmed_stays_found(told: str) -> None:
    assert answer_evidence.denied_and_affirmed(
        told, "Una película llamada Bestiario (2002) es de terror.", search_report._SEARCH_NOT_FOUND,
    )



# --- revisión 2: naming the name again affirms nothing ---------------------------------------------------------------

@pytest.mark.parametrize(("told", "evidence"), [
    # Bloqueante 1: the name read inside what is denied («película DE Rayuela») and named again in a later clause that
    # says no such thing exists. Each draft says what its result says.
    ("No hay película de Rayuela. Rayuela es una novela de Julio Cortázar publicada en 1963.",
     "Rayuela es una novela de Julio Cortázar publicada en 1963."),
    ("No hay tercera temporada de Arcane. Arcane terminó con su segunda temporada en 2024.",
     "Arcane terminó con su segunda temporada en 2024."),
    ("No hay vuelos directos de Santiago a Tokio; desde Santiago hay que hacer escala en Dallas o Madrid.",
     "No hay vuelos directos de Santiago a Tokio; desde Santiago hay que hacer escala en Dallas o Madrid."),
    ("There is no direct flight from Santiago to Tokyo; from Santiago you connect in Dallas or Madrid.",
     "There is no direct flight from Santiago to Tokyo; from Santiago you connect in Dallas or Madrid."),
    ("No existe una versión de Minecraft para Xbox 360 actualizada; Minecraft para Xbox One recibe actualizaciones.",
     "Minecraft para Xbox 360 dejó de actualizarse; Minecraft para Xbox One recibe actualizaciones."),
])
def test_review_2_a_name_named_again_without_existence_is_no_contradiction(told: str, evidence: str) -> None:
    assert answer_evidence.denied_and_affirmed(told, evidence, search_report._SEARCH_NOT_FOUND) == []
    assert payload_fact_checks._payload_fact_defect(told, _search(evidence)) != "search_report_denies_and_affirms"


@pytest.mark.parametrize("told", [
    # Contracaso: a later clause that says the thing exists or is had, or says the whole thing denied, still affirms it.
    "No hay película de Rayuela, pero sí existe una llamada Rayuela de 2010.",
    "No hay tercera temporada de Arcane, pero sí hay una tercera temporada de Arcane anunciada.",
    "No hay vuelos directos de Santiago a Tokio. Hay vuelos directos de Santiago a Tokio los lunes.",
    "There is no film of Rayuela, but there is one called Rayuela from 2010.",
])
def test_review_2_an_existence_affirmed_after_the_denial_stays_found(told: str) -> None:
    assert answer_evidence.denied_and_affirmed(told, "", search_report._SEARCH_NOT_FOUND)


def test_review_2_si_without_accent_is_a_condition_not_an_affirmation() -> None:
    assert answer_evidence.denied_and_affirmed(
        "No hay película de Rayuela; si hay una adaptación de Rayuela, sería teatral.", "", search_report._SEARCH_NOT_FOUND,
    ) == []


# --- revisión 4: one variant denied and another one of the same name affirmed ----------------------------------------

@pytest.mark.parametrize("told", [
    # Bloqueante 1 de la revisión 4: «no X, pero sí Y» where Y shares a name with X is the true alternative; each result
    # says exactly the same as the report.
    "Netflix no tiene la tercera temporada de Arcane, pero sí tiene las dos primeras temporadas de Arcane.",
    "No hay vuelos directos de Santiago a Tokio, pero sí hay vuelos de Santiago a Tokio con escala en Dallas.",
    "No hay entradas para Coldplay el viernes en Santiago, pero sí hay entradas para Coldplay el sábado en Santiago.",
    "There are no direct flights from Santiago to Tokyo, but there are indeed flights from Santiago to Tokyo via Dallas.",
    "No existe Minecraft nativo para PS5, pero sí existe Minecraft para PS4, que funciona en PS5.",
])
def test_review_4_another_variant_of_the_same_name_affirmed_is_no_contradiction(told: str) -> None:
    assert answer_evidence.denied_and_affirmed(told, told, search_report._SEARCH_NOT_FOUND) == []
    assert payload_fact_checks._payload_fact_defect(told, _search(told)) != "search_report_denies_and_affirms"


@pytest.mark.parametrize("told", [
    # Contracaso: the same thing said to exist after its denial, or a thing told by the denied name, stays found.
    "No hay película de Rayuela, pero sí existe una película de Rayuela.",
    "Netflix no tiene la tercera temporada de Arcane, pero sí tiene la tercera temporada de Arcane.",
    "There are no direct flights from Santiago to Tokyo, but there are indeed direct flights from Santiago to Tokyo.",
    "No hay película de Bestiario ni de Rayuela, pero sí existe una llamada Bestiario de 2002.",
])
def test_contracase_review_4_the_same_thing_affirmed_after_its_denial_stays_found(told: str) -> None:
    assert answer_evidence.denied_and_affirmed(told, "", search_report._SEARCH_NOT_FOUND)


# --- revisión 2: a slip inside an enumeration is no title ------------------------------------------------------------

def test_review_2_an_item_doubled_inside_an_enumeration_is_a_repeat() -> None:
    assert listing.duplicated_run(
        "Necesitas arroz, leche de coco, leche de coco y azúcar.", comma_doubled=False,
    ) == "leche de coco"
    assert listing.duplicated_run(
        "1. Pollo al curry rápido: Corta el pollo, añade leche de coco, leche de coco y un poco de arroz cocido.",
        comma_doubled=False,
    ) == "leche de coco"


@pytest.mark.parametrize("text", [
    # Contracaso (r22): titles written doubled, alone or inside an enumeration, are read once.
    "La canción más famosa de Frank Sinatra es New York, New York, grabada en 1979.",
    "Mis favoritas: Yesterday, New York, New York y Imagine.",
    "En esa película Doris Day canta Que Sera, Sera.",
])
def test_review_2_a_title_written_doubled_is_still_read_once(text: str) -> None:
    assert listing.duplicated_run(text, comma_doubled=False) == ""


def test_review_2_a_lower_case_double_the_pages_write_so_is_read_once() -> None:
    text = "La letra pide comprar pan, volver a casa, volver a casa antes del final."
    evidence = "El estribillo dice volver a casa, volver a casa hasta el final."
    assert listing.duplicated_run(text, comma_doubled=False) == "volver a casa"
    assert listing.duplicated_run(text, comma_doubled=False, evidence=evidence) == ""


# --- revisión 2: markdown emphasis written plain --------------------------------------------------------------------

def test_review_2_emphasis_is_written_plain() -> None:
    assert listing.without_emphasis("1. **Pollo al curry rápido**: Corta el pollo.") == (
        "1. Pollo al curry rápido: Corta el pollo."
    )
    assert listing.without_emphasis("**Ingredientes:**\n- arroz\n- __pollo frito__") == (
        "Ingredientes:\n- arroz\n- pollo frito"
    )


def test_contracase_review_2_code_and_lone_marks_keep_their_asterisks() -> None:
    code = "```python\ndef f(x):\n    return x**2 + y**3\n```"
    assert listing.without_emphasis(code) == code
    assert listing.without_emphasis("Usa `__init__` y `a**b**c`.") == "Usa `__init__` y `a**b**c`."
    assert listing.without_emphasis("Calcula 2**10 y luego 3 * 4.") == "Calcula 2**10 y luego 3 * 4."
    assert listing.without_emphasis("el método __init__ de la clase") == "el método __init__ de la clase"


class _Talk(llm.LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.calls = 0

    def _post(self, payload: dict, **_: object) -> dict:
        self.calls += 1
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


IDEAS = (
    "1. **Pollo al curry rápido**: Corta el pollo en cubos y saltea con ajo.\n\n"
    "2. **Arroz con pollo y frijoles**: Cocina el pollo con cebolla y mezcla con arroz."
)


def test_review_2_c02_the_talk_publishes_its_list_without_emphasis() -> None:
    writer = _Talk([IDEAS])
    final, _ = writer.chat(
        "dame 2 ideas de cena con pollo y arroz que no tarden mas de media hora", history=[],
        conversation_kind="knowledge", response_language="es", temperature=0.0,
    )
    assert "**" not in final
    assert final == IDEAS.replace("**", "")
    assert writer.calls == 1
