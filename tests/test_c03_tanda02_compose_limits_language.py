"""Tanda 2 (2026-09-23, 50 unseen real messages): visible answers after a right decision.

Replayed here with paraphrased requests and synthetic pages, never the private literals:

- web.search reports: the writer copied the example «… en ese sitio dice que …», pasted
  whole snippets with their questions, and seven of eleven searches spent three drafts and
  ended in the list of pages. Owner rule 2026-09-24: the lookup is invisible — the answer
  itself, never a source, a site, the search or a list of pages — so the list of pages is
  no longer a final and a budget run out with nothing publishable raises like any turn.
- limits: «Pido leer …», «… no es una acción que realice BAXY», «Abrir … no está en lo que
  hago»: BAXY's no is his, in the first person.
- language: a new bare request in a Spanish word keeps Spanish after an English turn; only an
  answer to BAXY's question inherits the language of the request it answers.
- a bare request for jokes tells one; a clarification asks only what is missing.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind_main
from baxy_mind import llm
from baxy_mind.semantic.request import read_request
from test_c03_cpu_actor import Recorder

# --- web.search reports ----------------------------------------------------------

_PARK_ASK = "cómo llego a parquelandia"
_PARK_RESULTS = [
    {
        "title": "Cómo llegar a Parquelandia Resort",
        "url": "https://parquelandia.parque.com/es/como-llegar/",
        "snippet": "Obtén indicaciones de manejo e información sobre estacionamientos para tu "
        "viaje a Parquelandia Resort.",
    },
    {
        "title": "Dirección de Parquelandia y cómo llegar",
        "url": "https://www.entradas-parques.com/es/parquelandia/direccion/",
        "snippet": "Encuentra la dirección exacta de Parquelandia, cómo llegar desde el aeropuerto "
        "y las mejores opciones de transporte. Compara costes y rutas.",
    },
    {
        "title": "[GRATIS] Guía de Parquelandia: ¿vale la pena el tren?",
        "url": "https://www.viajeroslibres.com/guia-parquelandia/",
        "snippet": "¿Vale la pena tomar el tren a Parquelandia? Esta guía te ayudará a realizar el "
        "traslado de la forma más fácil.",
    },
]


def _situation(results: list[dict], query: str = _PARK_ASK) -> dict:
    return {
        "kind": "operation",
        "operation": "web.search",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "query": query, "count": len(results), "results": results},
    }


def _payload(results: list[dict], query: str = _PARK_ASK) -> dict:
    return {"operation": "web.search", "seen": {"query": query, "count": len(results), "results": results}}


def test_the_report_instruction_asks_for_the_answer_itself_never_its_sources() -> None:
    # Owner rule 2026-09-24 reverses this test's former intent (name a real site in the example): the answer
    # is said as something BAXY knows, and the instruction names no site at all.
    honest = "Para llegar a Parquelandia Resort hay indicaciones de manejo e información sobre estacionamientos."
    client = Recorder([honest])
    assert client.compose_user_message(_PARK_ASK, "status", {"situation": _situation(_PARK_RESULTS)}) == honest
    assert len(client.payloads) == 1
    sent = client.payloads[0]["messages"][-1]["content"]
    assert "Nunca menciones la búsqueda, las páginas, los sitios ni ninguna fuente" in sent
    assert "parquelandia.parque.com" not in sent.split("seen.results son")[1]
    assert "no el fragmento entero" in sent

    english = Recorder(["Parquelandia Resort has driving directions and parking information."] * 3)
    english.compose_user_message("how do I get to parquelandia", "status", {"situation": _situation(_PARK_RESULTS)})
    sent_en = english.payloads[0]["messages"][-1]["content"]
    assert "Never mention the search, the pages, the sites or any source" in sent_en


@pytest.mark.parametrize(
    "shown",
    [
        # The copied example, with or without its site.
        "En ese sitio dice que se obtienen indicaciones de manejo e información sobre estacionamientos.",
        "Según parquelandia.parque.com, se obtienen indicaciones de manejo para tu viaje a Parquelandia Resort.",
        "Busqué en internet y encontré estas páginas: «Cómo llegar a Parquelandia Resort».",
    ],
)
def test_an_answer_that_shows_the_search_falls(shown: str) -> None:
    assert llm._payload_fact_defect(shown, _payload(_PARK_RESULTS), _PARK_ASK) == "search_report_shows_the_search"


def test_an_honest_answer_that_the_pages_do_not_answer_publishes() -> None:
    results = [
        {"title": "Vocabulario de ropa | Fichas", "url": "https://fichas.example.org/ropa",
         "snippet": "Estudia fichas con términos como ¿Debo ponerme algo elegante esta noche?"},
        {"title": "Completar la conversación con pronombres", "url": "https://tareas.example.net/q/1",
         "snippet": "Completa la conversación usando pronombres: ¿Debo ponerme esta corbata? Sí, la debes poner."},
    ]
    asked = "¿me pongo bufanda esta noche?"
    honest = "No encontré si debes ponerte bufanda esta noche."
    facts = {"situation": _situation(results, asked)}
    assert llm.compose_visible_defect(honest, "status", asked, facts) == ""
    assert llm._payload_fact_defect(honest, _payload(results, asked), asked) == ""
    # Answering the question anyway is still a claim no page makes.
    invented = "Esta noche hará frío, así que sí, ponte la bufanda."
    assert llm._payload_fact_defect(invented, _payload(results, asked), asked) == "search_report_unsourced_claim"


def test_a_question_quoted_verbatim_from_a_page_is_not_the_assistant_asking() -> None:
    facts = {"situation": _situation(_PARK_RESULTS)}
    quoted = (
        "Según viajeroslibres.com, la guía dice «¿Vale la pena tomar el tren a Parquelandia?» y "
        "ayuda a realizar el traslado de la forma más fácil."
    )
    assert llm.compose_visible_defect(quoted, "status", _PARK_ASK, facts) == ""
    # The same question unquoted is BAXY asking the person.
    asked = "Según viajeroslibres.com, ¿vale la pena tomar el tren a Parquelandia?"
    assert llm.compose_visible_defect(asked, "status", _PARK_ASK, facts) == "extra_claim"
    # A quotation the pages do not carry is not the page's either.
    invented = "Según viajeroslibres.com, la guía pregunta «¿Quieres que te reserve el tren?»."
    assert llm.compose_visible_defect(invented, "status", _PARK_ASK, facts) == "extra_claim"


def test_a_bracketed_result_title_is_observed_text_not_a_template_hole() -> None:
    facts = {"situation": _situation(_PARK_RESULTS)}
    answer = "Hay una guía [GRATIS] para hacer el traslado a Parquelandia de la forma más fácil."
    assert llm._bracket_is_observed("[GRATIS]", facts) is True
    assert llm.compose_visible_defect(answer, "status", _PARK_ASK, facts) == ""
    assert llm.compose_visible_defect(
        "La guía cuesta [precio del tren].", "status", _PARK_ASK, facts
    ) == "copied_instruction"


def test_a_host_label_that_prefixes_a_query_word_is_the_page_name_not_a_cut() -> None:
    assert llm._truncated_fact_word("Parquelandia.parque.com da indicaciones de manejo.", _payload(_PARK_RESULTS)) is False
    # A word the model cut from the query is still a cut.
    assert llm._truncated_fact_word("Busqué cómo llegar a parquelan.", _payload(_PARK_RESULTS)) is True


def test_three_rejected_drafts_no_longer_end_in_a_list_of_pages() -> None:
    # Owner rule 2026-09-24 reverses this test's former intent: the list of pages was a fixed final that showed
    # the search; three drafts that fall now publish nothing, like any other turn.
    shown = "En ese sitio dice que hay indicaciones de manejo."
    client = Recorder([shown] * 3)
    reply = client.compose_user_message(_PARK_ASK, "status", {"situation": _situation(_PARK_RESULTS)})
    assert "encontré estas páginas" not in reply
    assert "parquelandia.parque.com" not in reply


class _SlowRecorder(Recorder):
    """The model answers the first drafts and then runs out of time."""

    def __init__(self, replies, fail_at: int):
        super().__init__(replies)
        self.fail_at = fail_at

    def _post(self, payload, timeout=None, max_attempts=2, cancellation=None):
        if len(self.payloads) + 1 == self.fail_at:
            self.payloads.append(payload)
            raise TimeoutError("se agotó la espera")
        return super()._post(payload)


@pytest.mark.parametrize("fail_at", [2, 3])
def test_a_budget_run_out_before_the_last_draft_raises_instead_of_listing_pages(fail_at: int) -> None:
    # Owner rule 2026-09-24: the verified pages are no final of their own any more.
    shown = "En ese sitio dice que hay indicaciones de manejo."
    client = _SlowRecorder([shown] * 3, fail_at)
    with pytest.raises(TimeoutError):
        client.compose_user_message(_PARK_ASK, "status", {"situation": _situation(_PARK_RESULTS)}, timeout=20)
    assert len(client.payloads) == fail_at


def test_a_budget_run_out_with_nothing_verified_to_report_still_raises() -> None:
    facts = {"situation": {"kind": "conversation", "polarity": "success"}}
    client = _SlowRecorder(["No puedo hacerlo."] * 3, 2)
    with pytest.raises(TimeoutError):
        client.compose_user_message("cuéntame algo", "conversation", facts, timeout=20)


# --- limits in BAXY's own first person ---------------------------------------------


@pytest.mark.parametrize(
    "limit",
    [
        "Pido leer esa novela desde el capítulo dos, pero está fuera de lo que hago en este PC.",
        "Leer esa novela desde el capítulo dos no forma parte de lo que hago.",
        "Abrir la app del tiempo no está en lo que hago aquí.",
        "Ir al inicio no lo hago.",
        "Eso no lo hago: activar el modo pirata no es algo que haga aquí.",
        "Opening the weather app isn't something I do.",
        "I want to read that novel, but that's outside what I do.",
    ],
)
def test_a_limit_that_echoes_the_request_is_not_baxys_no(limit: str) -> None:
    assert llm.limit_voice_defect(limit, "x") == "limit_echoes_request"


@pytest.mark.parametrize(
    "limit",
    [
        "Eso no lo hago: el modo pirata no es algo que tenga BAXY.",
        "No tengo un modo pirata; eso BAXY no lo hace.",
        "That's not something BAXY does.",
    ],
)
def test_a_limit_that_speaks_of_baxy_in_the_third_person_is_not_his_no(limit: str) -> None:
    assert llm.limit_voice_defect(limit, "activa el modo pirata") == "limit_third_person"


@pytest.mark.parametrize(
    "limit",
    [
        "Eso no lo hago: los hábitos no los llevo yo.",
        "Eso no lo hago: no tengo un modo pirata.",
        "Eso no lo hago: las novelas no las leo en voz alta.",
        "I don't do that: I don't have a pirate mode.",
        "Soy BAXY y eso no lo hago: no manejo cámaras.",
    ],
)
def test_a_first_person_limit_is_baxys_own(limit: str) -> None:
    assert llm.limit_voice_defect(limit, "x") == ""


def test_the_self_close_limit_may_name_how_baxy_closes() -> None:
    reply = "No me cierro desde el chat; BAXY se cierra con la X de su ventana o con Alt+F4."
    assert llm.limit_voice_defect(reply, "ciérrate") == ""


def test_the_unsupported_contract_rejects_an_echoed_or_third_person_limit() -> None:
    request = "activa el modo pirata"
    assert llm._unsupported_answer_contract_failure(
        "Eso no lo hago: activar el modo pirata no es una acción que realice BAXY.", request
    ) == "unsupported_limit_echoes_request"
    assert llm._unsupported_answer_contract_failure(
        "Eso no lo hago: el modo pirata no lo tiene BAXY.", request
    ) == "unsupported_limit_third_person"
    assert llm._unsupported_answer_contract_failure("Eso no lo hago: no tengo un modo pirata.", request) == ""


def _out_of_catalog() -> dict:
    return {"situation": {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}}


def test_an_out_of_catalog_limit_is_retried_until_it_is_said_in_the_first_person() -> None:
    echoed = "Abrir la app del tiempo no está en lo que hago aquí."
    own = "Eso no lo hago: la app del tiempo no la abro yo."
    client = Recorder([echoed, own])
    assert client.compose_user_message("abre la app del tiempo", "error", _out_of_catalog()) == own
    first_sent = client.payloads[0]["messages"][-1]["content"]
    assert "en tu primera persona: que eso no lo haces" in first_sent
    assert "nunca hables de BAXY en tercera persona" in first_sent
    retry_system = client.payloads[1]["messages"][0]["content"]
    assert "El límite es tuyo" in retry_system


def test_an_out_of_catalog_limit_that_names_no_boundary_gets_a_spanish_hint() -> None:
    vague = "La app del tiempo no forma parte de mis funciones."
    own = "Eso no lo hago: la app del tiempo no la abro yo."
    client = Recorder([vague, own])
    assert client.compose_user_message("abre la app del tiempo", "error", _out_of_catalog()) == own
    retry_system = client.payloads[1]["messages"][0]["content"]
    assert "Di llanamente, en primera persona, que eso no lo haces" in retry_system
    assert "Say the request is outside" not in retry_system


def test_an_english_out_of_catalog_limit_in_the_third_person_is_retried() -> None:
    third = "That's outside what BAXY does on this PC."
    own = "I don't do that: weather apps are not something I open."
    client = Recorder([third, own])
    assert client.compose_user_message("open the weather app", "error", _out_of_catalog()) == own
    assert "never «BAXY does not»" in client.payloads[1]["messages"][0]["content"]


# --- language of a bare request -------------------------------------------------------


@pytest.mark.parametrize(
    "text,language",
    [
        ("chistes", "es"),
        ("un chiste", "es"),
        ("recetas", "es"),
        ("adivinanzas", "es"),
        ("jokes", "en"),
        ("a riddle", "en"),
        ("recipes", "en"),
    ],
)
def test_a_bare_content_noun_is_language_evidence(text: str, language: str) -> None:
    reading = read_request(text)
    assert reading.language == language
    assert tuple(reading.evidence) != (0, 0)
    assert mind_main._decisive_request_language(text) == language


def test_a_proper_name_alone_is_still_no_language_evidence() -> None:
    assert tuple(read_request("Minecraft").evidence) == (0, 0)
    assert mind_main._decisive_request_language("Minecraft") is None


def test_only_an_answer_to_baxys_question_is_read_as_an_answer() -> None:
    asked = [
        {"role": "user", "content": "Play a song on Spotify."},
        {"role": "assistant", "content": "Which song should I play?"},
        {"role": "user", "content": "Queen"},
    ]
    told = [
        {"role": "user", "content": "what time is it"},
        {"role": "assistant", "content": "It is 10:24."},
        {"role": "user", "content": "Minecraft"},
    ]
    assert mind_main._answers_the_last_question(asked, "Queen") is True
    assert mind_main._answers_the_last_question(told, "Minecraft") is False
    assert mind_main._answers_the_last_question([], "Minecraft") is False
    assert mind_main._answers_the_last_question(None, "Minecraft") is False


class _LanguageLlm:
    detected = 0

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        }

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return False, None

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @classmethod
    def detect_response_language(cls, _text: str) -> str:
        cls.detected += 1
        return "es"

    @staticmethod
    def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
        return "Listo." if kwargs["response_language"] == "es" else "Done.", []


class _NoEvidence:
    @staticmethod
    def candidate_families(_text: str, _encoder: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


def _conversation_language(text: str, history: list[dict]) -> str:
    from baxy_mind.planner import PlannerCatalog

    tool = {
        "type": "function",
        "function": {
            "name": "network_status", "canonical_name": "network.status",
            "description": "Read the current network status.", "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }
    result = mind_main._prepare_turn_result(
        {"id": "tanda02-language", "text": text, "history": history},
        llm=_LanguageLlm(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"network.status": tool},
    )
    return str(result["responseLanguage"])


def test_a_new_request_with_no_language_of_its_own_asks_the_detector_not_the_last_turn() -> None:
    _LanguageLlm.detected = 0
    history = [
        {"role": "user", "content": "what time is it"},
        {"role": "assistant", "content": "It is 10:24."},
        {"role": "user", "content": "Minecraft"},
    ]
    assert _conversation_language("Minecraft", history) == "es"
    assert _LanguageLlm.detected == 1


def test_an_answer_to_baxys_question_keeps_the_language_of_the_request_it_answers() -> None:
    _LanguageLlm.detected = 0
    history = [
        {"role": "user", "content": "Play a song on Spotify."},
        {"role": "assistant", "content": "Which song should I play?"},
        {"role": "user", "content": "Queen"},
    ]
    assert _conversation_language("Queen", history) == "en"
    assert _LanguageLlm.detected == 0


def test_a_bare_spanish_noun_after_an_english_question_is_answered_in_spanish() -> None:
    _LanguageLlm.detected = 0
    history = [
        {"role": "user", "content": "switch on the camera"},
        {"role": "assistant", "content": "Which camera do you mean?"},
        {"role": "user", "content": "chistes"},
    ]
    assert _conversation_language("chistes", history) == "es"
    assert _LanguageLlm.detected == 0


# --- a bare request for jokes tells one ------------------------------------------------


@pytest.mark.parametrize("text", ["chistes", "un chiste", "otro chiste", "jokes", "a joke", "cuéntame un chiste"])
@pytest.mark.parametrize("has_history", [False, True])
def test_a_bare_request_for_jokes_is_free_content_with_or_without_history(text: str, has_history: bool) -> None:
    assert llm._conversation_presentation_shape(
        text, conversation_kind="knowledge", has_history=has_history
    ) == "free_content"


def test_open_content_stays_a_first_turn_reading() -> None:
    assert llm._conversation_presentation_shape(
        "contame algo", conversation_kind="knowledge", has_history=False
    ) == "free_content"
    assert llm._conversation_presentation_shape(
        "contame algo", conversation_kind="knowledge", has_history=True
    ) != "free_content"
    assert llm._conversation_presentation_shape(
        "chistes de programadores sobre bases de datos antiguas", conversation_kind="knowledge", has_history=True
    ) != "free_content"


def test_asking_which_topic_misses_the_free_content_contract() -> None:
    assert llm._shaped_conversation_answer_violates_contract(
        "¡Claro! ¿Quieres un chiste de algún tema? Por ejemplo, de trabajo o de amor.", "chistes", "free_content"
    )


# --- a reworded clarification asks only what is missing ---------------------------------


def test_the_clarification_rewording_asks_only_what_is_missing() -> None:
    question = "¿Quieres que baje un poco el volumen de la música?"
    client = Recorder([question])
    facts = {"situation": {"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request"}}
    assert client.compose_user_message("turn dwn un pelín la música", "clarification", facts) == question
    sent = client.payloads[0]["messages"][-1]["content"]
    assert "the one thing that is missing" in sent
    assert "do not offer alternatives or options the person did not name" in sent
