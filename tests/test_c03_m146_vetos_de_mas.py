"""M146 (2026-10-03): composition vetoes that killed correct replies (⚠ with no final), DEV-D/F/G/H v4m–v4q.

The corpus is every window turn whose RUN row carries ``composition_failed: …`` or ``filtered: …`` (29 turns, 20 rows;
DEV-E never opened). Each fix below carries the row's recorded draft and payload (``compose-audit.jsonl`` of the same
run, trace «t» + ordinal), phrasings of our own, and what must still be refused. Twins in the App:
``tests/Baxy.Integration.Tests/M146VetosDeMasTests.cs``.

1. G-s087 «resúmeme el pdf del contrato de alquiler…» (file absent): «contrato» is the prompt's word for its own
   contract and died as internal_code; a word of that list the person said is theirs.
2. G-s116 «abrí spotify y ponime algo de jazz tranqui…» (app.open + media.play.query verified): the playback's title
   names what plays in a mission too (missing_name ×3).
3. H-w37-t1 «toy conectado a internet?…»: the understood request («¿Está conectado el router a internet?») lifted the
   jargon ban on «router» in the mind while the App reads the person's own words; now both read the person's.
4. H-s001 «a como anda el dolar hoy?» over «1 USD = 981.19 CLP»: a currency code the pages write is said with its name.
5. F-w47-t4 «Apúntamelo en una nota…»: the veto stands (every draft invented a rate); the retry hint names the item by
   its quoted title and forbids answering what it says.
6. D-p35-t1 (SWOT of Adidas): the analysis without its unsourced point (M134) is the last resort also when the retry
   cannot be asked inside the request's own budget or fails.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m146_evidence.json").read_text(encoding="utf-8"))
FORBIDDEN_TERMS = [
    "planner", "router", "tool", "catálogo", "catalogo", "schema", "operación", "operacion", "capacidad interna",
    "language model", "modelo de lenguaje", "qwen", "resolver el efecto", "el efecto '", "opaque identity",
    "observed profile", "grounding", "checkpoint", "reconciliación", "reconciliacion", "motor local", "core",
    "datos verificables", "pasos verificables", "identificador interno", "wmi",
]


class _Drafts(LlmRuntime):
    """The drafts stand in for the model in order (the last one repeats); every request is kept. A draft that is an
    exception instance is raised instead."""

    def __init__(self, drafts: list[object], finish: str = "stop") -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.finish = finish
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        if isinstance(content, BaseException):
            raise content
        return {"choices": [{"message": {"content": content}, "finish_reason": self.finish}]}


def _system_text(payload: dict) -> str:
    return "\n".join(str(item.get("content") or "") for item in payload["messages"] if item.get("role") == "system")


# ------------------------------------------------------------------ 1. G-s087: the person's «contrato»

PDF_ABSENT = json.dumps({
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {"kind": "operation", "operation": "document.pdf.read", "polarity": "failure", "verified": False,
               "succeeded": False, "error": "known_file_not_found", "target": "contrato de alquiler.pdf",
               "attempted": {"fileName": "contrato de alquiler.pdf", "folder": "documents"}},
})
G_S087 = "resúmeme el pdf del contrato de alquiler que tengo en documentos, porfa"


@pytest.mark.parametrize(
    ("said", "draft"),
    [
        # G-s087 v4p/v4q: the first and the third draft, word for word.
        (G_S087, "No pude leer el contrato de alquiler porque el archivo no se encontró en la carpeta documentos."),
        (G_S087, "No pude leer el contrato porque el archivo no se encontró en la carpeta de documentos."),
        ("léeme el contrato de trabajo que bajé ayer", "No encontré el contrato de trabajo en tus documentos."),
        ("summarize the rental contrato pdf in my documents", "I couldn't find the rental contrato in Documents."),
    ],
)
def test_the_word_the_person_said_is_not_the_prompt_leaking(said: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", said, {"situation": PDF_ABSENT}, said=said) == ""


@pytest.mark.parametrize(
    ("said", "draft"),
    [
        # What does not change: nobody said «contrato», and the prompt's other words stay refused.
        ("resúmeme el pdf del alquiler que tengo en documentos", "No pude leer el contrato de alquiler."),
        (G_S087, "No pude leer el contrato de alquiler: no tengo acceso a tus documentos."),
        (G_S087, "Según la situación del turno, no encontré el contrato de alquiler."),
    ],
)
def test_the_prompts_own_words_are_still_internal_code(said: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", said, {"situation": PDF_ABSENT}, said=said) == "internal_code"


# ------------------------------------------------------------------ 2. G-s116: a mission's playback names its title

def _mission(title: str, operation: str = "media.play.query", status: str = "playing") -> str:
    steps = [
        {"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
         "observed": {"appId": "Spotify", "displayName": "Spotify", "alreadyRunning": True, "windowHandle": 262790},
         "readOnly": False},
        {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
         "observed": {"version": 1, "provider": "spotify", "title": title, "query": "jazz tranquilo",
                      "playbackStatus": status, "authority": "spotify_windows_uia_postread"},
         "readOnly": False},
    ]
    return json.dumps({"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
                       "steps": [json.dumps(step) for step in steps],
                       "completedRequest": "Abrí Spotify y pon algo de jazz tranquilo."})


VENDLA = _mission("Vendla - After Winter Comes Spring")
G_S116 = "abrí spotify y ponime algo de jazz tranqui, que estoy laburando y necesito algo de fondo"


@pytest.mark.parametrize(
    ("said", "draft"),
    [
        # G-s116 v4p/v4q: the first and the third draft.
        (G_S116, 'Abrí Spotify y reproduciendo "Vendla - After Winter Comes Spring" para que tengas jazz tranquilo '
                 "mientras trabajas."),
        (G_S116, 'Abrí Spotify y ya está reproduciendo "Vendla - After Winter Comes Spring" en modo jazz tranquilo.'),
        ("open spotify and put on some chill jazz",
         'I opened Spotify and it is playing "Vendla - After Winter Comes Spring".'),
        ("abre spotify y pon jazz", "Abrí Spotify y suena «Vendla - After Winter Comes Spring»."),
    ],
)
def test_a_mission_playback_is_named_by_its_title(said: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", said, {"situation": VENDLA}, said=said) == ""


def test_the_mission_publishes_its_first_draft() -> None:
    first = ('Abrí Spotify y ya está reproduciendo "Vendla - After Winter Comes Spring" en modo jazz tranquilo.')
    writer = _Drafts([first])
    assert writer.compose_user_message(G_S116, "status", {"situation": VENDLA}, said=G_S116) == first
    assert len(writer.requests) == 1


@pytest.mark.parametrize(
    ("situation", "draft"),
    [
        # What does not change: the title must still be said, it must be the observed one, and a playback that was
        # not verified playing does not lend its title.
        (VENDLA, "Abrí Spotify y puse jazz tranquilo para que trabajes."),
        (VENDLA, 'Abrí Spotify y suena "Take Five" de Dave Brubeck.'),
        (_mission("Vendla - After Winter Comes Spring", status="paused"),
         'Abrí Spotify y ya está reproduciendo "Vendla - After Winter Comes Spring".'),
    ],
)
def test_a_mission_without_the_observed_playing_title_is_still_missing_its_name(situation: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", G_S116, {"situation": situation}, said=G_S116) == (
        "missing_name"
    )


# ------------------------------------------------------------------ 3. H-w37-t1: jargon asked only in the person's words

ONLINE = json.dumps({
    "kind": "operation", "operation": "network.status", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "online": True, "connectedInterfaceCount": 14, "interfaceTypes": ["53", "ethernet"]},
})


@pytest.mark.parametrize(
    ("understood", "said", "first", "kept"),
    [
        # H-w37-t1 v4q: the decider's understood request, the person's message, the draft the App refused.
        ("¿Está conectado el router a internet?", "toy conectado a internet? me anda re lento todo",
         "El router está conectado a internet.", "Sí, estás conectado a internet."),
        ("Is the router connected to the internet?", "am I online? everything is crawling",
         "Your router is online.", "Yes, you're online."),
        ("¿El core del sistema está conectado?", "oye estoy con internet o no",
         "El core del sistema tiene internet.", "Sí, tienes internet."),
    ],
)
def test_a_term_only_the_understood_request_says_stays_forbidden(understood: str, said: str, first: str,
                                                                   kept: str) -> None:
    writer = _Drafts([first, kept])
    facts = {"situation": ONLINE, "forbiddenResponseTerms": FORBIDDEN_TERMS}
    assert writer.compose_user_message(understood, "status", facts, said=said) == kept
    assert len(writer.requests) == 2


@pytest.mark.parametrize(
    ("said", "prior", "draft"),
    [
        # What does not change: the person said it now, or earlier in the conversation.
        ("mi router está conectado a internet?", None, "Sí, el router está conectado a internet."),
        ("¿y está conectado?", ["tengo un router nuevo, ¿lo detectas?"], "Sí, el router está conectado a internet."),
    ],
)
def test_a_term_the_person_wrote_is_theirs(said: str, prior: list[str] | None, draft: str) -> None:
    writer = _Drafts([draft])
    facts = {"situation": ONLINE, "forbiddenResponseTerms": FORBIDDEN_TERMS}
    if prior:
        facts["priorRequests"] = prior
    assert writer.compose_user_message("¿Está conectado el router a internet?", "status", facts, said=said) == draft


# ------------------------------------------------------------------ 4. H-s001: a currency code read is said with its name

def _rate(title: str, snippet: str, query: str) -> dict:
    return {"seen": {"query": query, "count": 1, "results": [{"title": title, "url": "https://api.frankfurter.dev/v2/rates",
                                                              "snippet": snippet}],
                     "authority": "frankfurter_reference_rates"}, "operation": "web.search"}


USD_CLP = _rate("1 USD = 981.19 CLP", "Reference rate on 2026-10-02: 1 USD = 981.19 CLP.",
                "¿A cuánto está hoy el dólar en pesos?")
EUR_MXN = _rate("1 EUR = 21.48 MXN", "Reference rate on 2026-10-02: 1 EUR = 21.48 MXN.", "euro a pesos mexicanos hoy")
CLP_USD = _rate("1 CLP = 0.001 USD", "Reference rate on 2026-10-02: 1 CLP = 0.00102 USD.",
                "cuantos pesos me dan por un dolar hoy dia que tengo que pagar la cuota del viaje a cancun")
H_S001 = "oye, ¿me podrias decir a como anda el dolar hoy?"


@pytest.mark.parametrize(
    ("payload", "said", "draft"),
    [
        # H-s001 v4o (the first draft) and v4q (the third).
        (USD_CLP, H_S001, "Hoy el dólar está a 981.19 pesos chilenos."),
        (USD_CLP, H_S001, "Hoy el dólar vale 981,19 pesos chilenos."),
        (USD_CLP, "how much is the dollar today", "Today the dollar is at 981.19 Chilean pesos."),
        (EUR_MXN, "a cuánto el euro hoy en méxico", "Hoy el euro está a 21.48 pesos mexicanos."),
    ],
)
def test_the_currency_a_code_names_is_sourced(payload: dict, said: str, draft: str) -> None:
    assert llm._payload_fact_defect(draft, payload, said, said=said) == ""


@pytest.mark.parametrize(
    ("payload", "draft"),
    [
        # What does not change: a figure the page does not give, and a currency it does not write.
        (USD_CLP, "Hoy el dólar está a 975 pesos chilenos."),
        (USD_CLP, "Hoy la libra esterlina está a 981.19 pesos chilenos."),
        (EUR_MXN, "Hoy el euro está a 21.48 pesos argentinos."),
        # H-s048 v4o/v4q: the rate was read the other way round (1 CLP = 0.00102 USD); its inverse is no page's figure.
        (CLP_USD, "Hoy un dólar vale aproximadamente 980 pesos chilenos."),
    ],
)
def test_a_figure_or_currency_no_page_gives_is_still_unsourced(payload: dict, draft: str) -> None:
    assert llm._payload_fact_defect(draft, payload, H_S001, said=H_S001) == "search_report_unsourced_claim"


# ------------------------------------------------------------------ 5. F-w47-t4: the veto stands, the hint names the title

BOSTON_NOTE = json.dumps({
    "kind": "operation", "operation": "note.create", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"title": "en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro",
                 "content": "En noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro?",
                 "createdAtUtc": "2026-10-03T14:18:14.6818232+00:00", "updatedAtUtc": "2026-10-03T14:18:14.6818232+00:00",
                 "revision": 1, "isTrashed": False},
})
F_W47_T4 = "Apúntamelo en una nota, que luego se me olvida"


@pytest.mark.parametrize(
    "draft",
    [
        # F-w47-t4 v4p: the three drafts, each with a rate nothing read.
        "He guardado la nota sobre tu viaje a Boston en noviembre. Hoy, por cada euro te dan aproximadamente 1,08 dólares.",
        "Te doy 0.92 dólares por cada euro hoy.",
        "Hoy, por cada euro te dan 1,09 dólares.",
    ],
)
def test_a_note_report_that_answers_the_note_is_still_refused(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", F_W47_T4, {"situation": BOSTON_NOTE}, said=F_W47_T4) == (
        "missing_name"
    )


def test_the_retry_names_the_note_by_its_quoted_title_and_does_not_answer_it() -> None:
    kept = "Guardé la nota «en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro»."
    writer = _Drafts(["Hoy, por cada euro te dan 1,09 dólares.", kept])
    assert writer.compose_user_message(F_W47_T4, "status", {"situation": BOSTON_NOTE}, said=F_W47_T4) == kept
    hint = _system_text(writer.requests[1])
    assert "«en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro»" in hint
    assert "No respondas, expliques ni añadas nada a lo que dice." in hint


def test_an_english_task_retry_gets_the_same_hint() -> None:
    task = json.dumps({"kind": "operation", "operation": "task.create", "polarity": "success", "verified": True,
                       "succeeded": True, "observed": {"title": "what time does the pharmacy close"}})
    writer = _Drafts(["The pharmacy closes at 9 pm.", 'I added the task "what time does the pharmacy close".'])
    writer.compose_user_message("add that to my tasks", "status", {"situation": task}, said="add that to my tasks")
    hint = _system_text(writer.requests[1])
    assert "«what time does the pharmacy close»" in hint and "Do not answer, explain or add to what it says." in hint


def test_other_reports_keep_their_own_hint() -> None:
    # What does not change: a report with no titled write keeps the hint it had (here, an app opened).
    opened = json.dumps({"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
                         "succeeded": True, "observed": {"appId": "windows.calculator", "displayName": "Calculadora",
                                                         "alreadyRunning": False, "windowHandle": 1234}})
    writer = _Drafts(["Abrí la aplicación.", "Abrí la Calculadora."])
    writer.compose_user_message("ábreme la calculadora", "status", {"situation": opened}, said="ábreme la calculadora")
    hint = _system_text(writer.requests[1])
    assert "Nombra la app que abriste: «Calculadora»" in hint
    assert "nómbralo por su título" not in hint


@pytest.mark.parametrize(
    "draft",
    [
        # What does not change: the stored title's own «¿…» is the note's name, BAXY's question is still its own.
        "Guardé la nota «en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro». ¿Quieres algo más?",
        "Guardé la nota. ¿Quieres que te diga a cuánto está el euro?",
    ],
)
def test_a_question_of_baxys_own_after_the_note_is_still_an_extra_claim(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", F_W47_T4, {"situation": BOSTON_NOTE}, said=F_W47_T4) in {
        "extra_claim", "missing_name",
    }


# ------------------------------------------------------------------ 6. D-p35-t1: the sourced part when no retry comes

ADIDAS = EVIDENCE["D-p35-t1"]


def test_the_sourced_part_is_published_when_the_retry_fails() -> None:
    # v4m–v4p: one consulted_analysis record per composition, ~7 s each, no retry record and no sourced part.
    writer = _Drafts([ADIDAS["draft"], ConnectionError("el servidor cerró la conexión")])
    reply = writer.compose_user_message(ADIDAS["user"], "status", {"situation": ADIDAS["situation"]})
    assert reply.startswith("Oye, mira, Adidas sigue siendo esa leyenda urbana")
    assert "en los 80" not in reply and "**Amenazas:**" in reply
    assert len(writer.requests) == 2


def test_the_retry_is_not_asked_without_the_request_budget_for_it() -> None:
    import time

    writer = _Drafts([ADIDAS["draft"], AssertionError("no retry was to be asked")])
    writer._request_deadline = time.monotonic() + 1.5
    writer._request_maximum_timeout = 9.0
    reply = writer.compose_user_message(ADIDAS["user"], "status", {"situation": ADIDAS["situation"]})
    assert "en los 80" not in reply and reply.startswith("Oye, mira, Adidas")
    assert len(writer.requests) == 1


def test_with_nothing_kept_a_failed_retry_still_raises() -> None:
    # What does not change: an analysis whose every point carries an unsourced figure keeps nothing, and the failure
    # is the caller's as before.
    only_figures = (
        "Aquí va el FODA de Adidas:\n\n**Fortalezas:**\n- Vende 25 millones de pares al año.\n\n**Debilidades:**\n"
        "- Perdió un 12 % de cuota.\n\n**Oportunidades:**\n- Puede crecer un 30 % en Asia.\n\n**Amenazas:**\n"
        "- Nike le saca 40 puntos."
    )
    writer = _Drafts([only_figures, ConnectionError("el servidor cerró la conexión")])
    with pytest.raises(ConnectionError):
        writer.compose_user_message(ADIDAS["user"], "status", {"situation": ADIDAS["situation"]})
