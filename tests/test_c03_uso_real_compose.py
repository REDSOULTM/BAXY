"""Uso real 2026-09-23: visible answers that died as ⚠ after a right decision and a
verified operation. Each shape of the real drafts is replayed here (paraphrased,
with synthetic pages): the honest draft publishes, the dishonest one still falls.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from baxy_mind import llm
from test_c03_cpu_actor import Recorder

# --- web.search reports --------------------------------------------------------

_RATE_RESULTS = [
    {
        "title": "Peso chileno a Yen. Cambio de CLP a JPY | Diario Divisas",
        "url": "https://www.diariodivisas.com/conversor/peso-yen",
        "snippet": "Nuestro conversor de moneda le permite conocer el cambio del peso chileno "
        "en relación con el yen en tiempo real con tasas actualizadas.",
    },
    {
        "title": "JPY a CLP - Conversión de yen japonés a pesos chilenos",
        "url": "https://www.tasas-hoy.org/es/conversor/jpy-clp",
        "snippet": "Utiliza el conversor de JPY a CLP para obtener tipos de cambio precisos y "
        "actualizados. Convierte yen japonés en pesos chilenos con datos en tiempo real.",
    },
    {
        "title": "Conversor de Divisas - Calculadora",
        "url": "https://www.calculadora.cl/conversor-divisas",
        "snippet": "Convierte entre las principales divisas del mundo con tasas de mercado "
        "actualizadas diariamente: peso chileno, dólar, euro, yen.",
    },
]
_RATE_ASK = "a cuánto está el yen frente al peso chileno"


def _search_payload(results: list[dict]) -> dict:
    return {"operation": "web.search", "seen": {"query": "q", "count": len(results), "results": results}}


def _search_situation(results: list[dict]) -> dict:
    return {
        "kind": "operation",
        "operation": "web.search",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "query": "q", "count": len(results), "results": results},
    }


def test_a_pasted_snippet_speaking_as_the_page_is_not_baxys_voice() -> None:
    pasted = (
        "Nuestro conversor de moneda le permite conocer el cambio del peso chileno en relación "
        "con el yen en tiempo real. Utiliza el conversor de JPY a CLP en tasas-hoy.org."
    )
    assert llm._payload_fact_defect(pasted, _search_payload(_RATE_RESULTS), _RATE_ASK) == "search_report_page_voice"
    told = "Según su página, en diariodivisas.com le decimos cuánto vale el yen hoy."
    assert llm._payload_fact_defect(told, _search_payload(_RATE_RESULTS), _RATE_ASK) == "search_report_page_voice"
    english = "Our converter on diariodivisas.com gives the rate in real time."
    assert llm._payload_fact_defect(english, _search_payload(_RATE_RESULTS), "yen to chilean peso") == "search_report_page_voice"


def test_the_page_voice_inside_a_quotation_or_the_persons_own_words_is_not_baxys() -> None:
    quoted = "La página de diariodivisas.com dice «Nuestro conversor de moneda le permite conocer el cambio»."
    assert llm._search_report_speaks_as_a_page(quoted, _search_payload(_RATE_RESULTS), _RATE_ASK) is False
    assert llm._search_report_speaks_as_a_page(
        "diariodivisas.com tiene un conversor para nuestra moneda.",
        _search_payload(_RATE_RESULTS),
        "a cuánto está nuestra moneda frente al yen",
    ) is False
    # The generic «we» of an idiom is not a page talking.
    generic = "History of AI on example.org states that AI as we know it is a collective effort."
    assert llm._search_report_speaks_as_a_page(generic, _search_payload(_RATE_RESULTS), "who created ai") is False


def test_an_honest_report_with_grammar_words_and_plurals_is_grounded() -> None:
    # Owner rule 2026-09-24: the answer names no page; the grammar words and plurals are what is judged here.
    honest = (
        "Hay conversores que tienen el cambio del peso chileno en relación con el yen, en tiempo real, "
        "y permiten convertir yenes a pesos chilenos y a diversas divisas con tasas actualizadas diariamente."
    )
    assert llm._search_report_unsourced_words(honest, _search_payload(_RATE_RESULTS), _RATE_ASK) == []
    assert llm._payload_fact_defect(honest, _search_payload(_RATE_RESULTS), _RATE_ASK) == ""


def test_a_claim_no_result_carries_still_falls_even_named_after_a_page() -> None:
    # WEB1879/WEB1889: naming the page does not vouch for «problemas de conexión».
    results = [
        {"title": "¿Se cayó WhatsApp? Fallas en tiempo real", "url": "https://fallas.mx/whatsapp",
         "snippet": "Reportes de usuarios sobre fallas de WhatsApp en las últimas 24 horas."},
        {"title": "WhatsApp down? Current problems", "url": "https://downdetector.mx/whatsapp",
         "snippet": "Problemas en tiempo real con WhatsApp."},
    ]
    invented = "Encontré fallas.mx y downdetector.mx, que mencionan problemas de conexión y servidores caídos."
    assert llm._search_report_unsourced_claim(invented, _search_payload(results), "por qué falla whatsapp") is True
    words = llm._search_report_unsourced_words(invented, _search_payload(results), "por qué falla whatsapp")
    assert "conexion" in words and "servidores" in words
    # A paraphrase of the page with the model's own content words still falls.
    reworded = "calculadora.cl requiere registrarse para servir cotizaciones históricas."
    assert llm._search_report_unsourced_claim(reworded, _search_payload(_RATE_RESULTS), _RATE_ASK) is True


def test_a_site_named_by_its_own_words_shows_the_search() -> None:
    # This test once let «El Tiempo» name eltiempo.com. Owner rule 2026-09-24 reverses that intent: a source
    # named by its proper name shows the lookup, and the answer itself is grounded without it.
    results = [
        {"title": "Última: la canción final del disco", "url": "https://www.eltiempo.com/cultura/ultima",
         "snippet": "La canción final del disco."},
    ]
    asked = "busca la canción última"
    assert llm._payload_fact_defect(
        "Según El Tiempo, es la canción final del disco.", _search_payload(results), asked
    ) == "search_report_shows_the_search"
    assert llm._payload_fact_defect("Es la canción final del disco.", _search_payload(results), asked) == ""


def test_a_search_title_is_page_prose_not_a_name_to_cut() -> None:
    results = [
        {"title": "Cambio Dólar Hoy · USD/CLP Actualizado | Casa de Cambio",
         "url": "https://www.casadecambio.cl/dolar-hoy", "snippet": "Precio publicado diariamente."},
    ]
    draft = "Según casadecambio.cl, el precio del dólar se actualiza durante el día."
    assert llm._truncated_fact_word(draft, _search_payload(results)) is False
    # A window title is still a name: «Configur» is a cut of it.
    window = {"operation": "window.resolve", "seen": {"windows": [{"title": "Configuración", "processName": "SystemSettings"}]}}
    assert llm._truncated_fact_word("Abrí la ventana Configur del sistema.", window) is True


def test_the_registrable_site_of_a_result_host_is_observed_not_code() -> None:
    results = [
        {"title": "Lentejas estofadas. La receta de las abuelas",
         "url": "https://recetasdecocina.elmundo.es/2026/01/lentejas.html",
         "snippet": "Una receta súper tradicional que en cada casa se hace de una manera."},
    ]
    report = "«Lentejas estofadas. La receta de las abuelas», de elmundo.es, menciona una receta súper tradicional."
    facts = {"situation": _search_situation(results)}
    assert llm.compose_visible_defect(report, "status", "cómo se hacen las lentejas", facts) == ""
    assert llm.compose_visible_defect(report + " Usé media.status.", "status", "cómo se hacen las lentejas", facts) == "internal_code"


def test_a_generic_search_answer_publishes_on_the_first_stage_without_its_sites() -> None:
    # Owner rule 2026-09-24 reverses the former intent (hand the writer the sites to name): the answer is said
    # as something BAXY knows, so the writer is told never to name a source, and still never to speak as a page.
    honest = "Hay conversores para conocer el cambio del peso chileno en relación con el yen en tiempo real."
    client = Recorder([honest])
    assert client.compose_user_message(_RATE_ASK, "status", {"situation": _search_situation(_RATE_RESULTS)}) == honest
    assert len(client.payloads) == 1
    sent = client.payloads[0]["messages"][-1]["content"]
    assert "diariodivisas.com, tasas-hoy.org, calculadora.cl" not in sent
    assert "Nunca menciones la búsqueda, las páginas, los sitios ni ninguna fuente" in sent
    assert "nunca como la página" in sent


def test_a_page_voice_draft_is_repaired_with_its_own_hint() -> None:
    pasted = "Nuestro conversor de moneda le permite conocer el cambio del peso chileno en relación con el yen."
    honest = "Hay un conversor para conocer el cambio del peso chileno en relación con el yen."
    client = Recorder([pasted, honest])
    assert client.compose_user_message(_RATE_ASK, "status", {"situation": _search_situation(_RATE_RESULTS)}) == honest
    retry_system = client.payloads[1]["messages"][0]["content"]
    assert "nunca hables como la página" in retry_system


# --- a failure that is an absence (media.status with nothing found) -------------

def _absence_facts(error: str = "youtube_tab_not_found") -> dict:
    return {
        "situation": {
            "kind": "failure",
            "polarity": "failure",
            "cause": "mission_failed",
            "stepCount": 0,
            "steps": [],
            "reason": {"kind": "operation", "operation": "media.status", "polarity": "failure",
                       "verified": False, "succeeded": False, "error": error},
        }
    }


@pytest.mark.parametrize(
    "asked,draft",
    [
        ("qué música se está reproduciendo", "No hay ningún video de YouTube sonando ahora mismo."),
        ("qué música se está reproduciendo", "No se está reproduciendo nada: no encuentro ningún video de YouTube abierto."),
        ("qué música se está reproduciendo", "Ahora no está sonando nada en YouTube."),
        ("what music is playing", "Nothing is playing right now: there is no YouTube video open."),
    ],
)
def test_the_absence_told_is_the_failure_told(asked: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", asked, _absence_facts()) == ""


@pytest.mark.parametrize(
    "draft",
    [
        "Está sonando tu música favorita en YouTube.",
        "Te pongo algo de música.",
    ],
)
def test_a_draft_that_hides_the_absence_still_misses_the_failure(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", "qué música se está reproduciendo", _absence_facts()) == "missing_failure"


def test_an_absence_does_not_tell_a_failure_that_is_not_one() -> None:
    # A timeout is not an absence: «no hay música» would hide it.
    assert llm.compose_visible_defect(
        "No hay música sonando.", "error", "qué música se está reproduciendo", _absence_facts("timeout")
    ) == "missing_failure"


# --- notification.list ---------------------------------------------------------

def _alarm_facts(*utc: str) -> dict:
    return {
        "situation": {
            "kind": "operation", "operation": "notification.list", "polarity": "success",
            "verified": True, "succeeded": True,
            "observed": {"version": 1, "count": len(utc), "notifications": [
                {"kind": "alarm", "nextRunUtc": stamp, "state": "Ready"} for stamp in utc
            ]},
        }
    }


def _local(stamp: str) -> str:
    return datetime.fromisoformat(stamp).astimezone().strftime("%H:%M")


def test_the_listed_alarms_are_named_with_their_local_times() -> None:
    first, second = "2026-09-24T08:00:00.0000000+00:00", "2026-09-24T10:30:00+00:00"
    draft = f"Hay 2 alarmas programadas: una a las {_local(first)} y otra a las {_local(second)}."
    assert llm.compose_visible_defect(draft, "status", "qué alarmas hay puestas", _alarm_facts(first, second)) == ""


def test_a_time_no_listed_alarm_has_is_invented() -> None:
    first = "2026-09-24T08:00:00+00:00"
    other = "23:59" if _local(first) != "23:59" else "23:58"
    draft = f"Hay 1 alarma programada, a las {other}."
    assert llm.compose_visible_defect(draft, "status", "qué alarmas hay puestas", _alarm_facts(first)) == "extra_claim"


# --- capture.screenshot ---------------------------------------------------------

def _capture_facts() -> dict:
    return {
        "situation": {
            "kind": "operation", "operation": "capture.screenshot", "polarity": "success",
            "verified": True, "succeeded": True,
            "observed": {"version": 1, "captureId": "capture_0123", "width": 1920, "height": 1080,
                         "sha256": "ab" * 32, "scope": "virtual_screen"},
        }
    }


def test_a_verified_capture_is_described_to_the_writer_and_told_on_the_first_stage() -> None:
    told = "Tomé una captura de toda la pantalla, de 1920 x 1080, y queda guardada en privado en este PC."
    client = Recorder([told])
    assert client.compose_user_message("haz una captura de pantalla", "status", _capture_facts()) == told
    assert len(client.payloads) == 1
    assert "Never say you cannot take screenshots" in client.payloads[0]["messages"][-1]["content"]


def test_denying_the_verified_capture_is_never_published() -> None:
    denied = "No puedo hacer una captura de pantalla. No tengo acceso a la pantalla."
    client = Recorder([denied] * 3)
    assert client.compose_user_message("haz una captura de pantalla", "status", _capture_facts()) == ""


# --- weather named as the person named the place ---------------------------------

def _weather_payload(location: str = "Londres") -> dict:
    return {"operation": "weather.current", "seen": {
        "location": location, "country": "Reino Unido", "temperatureC": 15.7, "apparentC": 14.1,
        "humidityPercent": 65, "windKmh": 10.1, "precipitationMm": 0, "condition": "despejado",
        "today": {"maxC": 22.4, "minC": 13.7, "rainProbabilityPercent": 0},
        "tomorrow": {"maxC": 24.4, "minC": 15.2, "rainProbabilityPercent": 0, "condition": "nublado"},
    }}


def test_the_place_named_as_the_person_named_it_is_the_place() -> None:
    reply = "In London, the temperature is 15.7°C with clear skies."
    assert llm._weather_fact_defect(reply, _weather_payload(), "what's the weather like in london") == ""
    assert llm._weather_fact_defect(reply, _weather_payload(), "what's the weather like in paris") == "missing_state"
    assert llm._weather_fact_defect("It is 15.7°C with clear skies.", _weather_payload(), "what's the weather like in london") == "missing_state"


# --- media.control said with a verb --------------------------------------------

def _stopped_facts() -> dict:
    return {"situation": {
        "kind": "operation", "operation": "media.control", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"version": 1, "sourceAppUserModelId": "MSEdge", "title": "",
                                        "artist": "", "playbackStatus": "stopped", "authority": "windows_smtc"},
    }}


@pytest.mark.parametrize("draft", ["La reproducción se detuvo.", "Dejé de reproducir.", "Paré la reproducción."])
def test_a_verified_stop_said_with_a_verb_names_the_state(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", "para de reproducir", _stopped_facts()) == ""


def test_a_stop_denied_is_still_reversed() -> None:
    assert llm.compose_visible_defect("La reproducción no se detuvo.", "status", "para de reproducir", _stopped_facts()) == "reversed_result"


# --- conversation retry hint -----------------------------------------------------

def test_a_conversation_that_said_it_cannot_is_retried_as_a_conversation() -> None:
    refused = "No, no puedo reírme como un villano."
    played = "¡Muajajajá! Así me río cuando nadie me ve."
    client = Recorder([refused, played])
    facts = {"situation": {"kind": "conversation", "polarity": "success"}}
    assert client.compose_user_message("ríete como un villano", "conversation", facts) == played
    retry_system = client.payloads[1]["messages"][0]["content"]
    assert "es una conversación" in retry_system
    assert "Success. State what was seen." not in retry_system
