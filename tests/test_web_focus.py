"""Goal h-web (2026-10-25): what the model reads of a web.fetch page with BAXY_WEB_FOCUS=1 (src/baxy_mind/web_focus.py).
Pages written for the test, shaped as the provider gives them (one block per line); no network."""

import json

import pytest

from baxy_mind import web_focus

FILLER = ("La red se amplió con nuevas estaciones y talleres durante esos años, según las memorias anuales de la "
          "empresa, que detallan obras, presupuestos y licitaciones de cada tramo.")

HISTORY = "\n".join(
    ["Nuestra Historia", "Ir al contenido",
     "1968", "El 24 de octubre se firmó el decreto que marca el nacimiento del Metro de Santiago, relevante medio de "
     "transporte público en la historia de Chile.", "Ver Galería"]
    + [f"{1980 + i}\n{FILLER}\nVer Galería" for i in range(12)]
    + ["1975", "El 15 de septiembre se inauguró oficialmente el trayecto San Pablo - La Moneda, iniciándose así la "
       "operación de Metro de Santiago.", "Ver Galería"]
    + [f"{2000 + i}\n{FILLER}" for i in range(12)])


def _receipt(text: str, offset: int = 0, total: int | None = None, has_more: bool = True) -> str:
    observed = {"version": 1, "requestedUrl": "https://example.org/historia", "finalUrl": "https://example.org/historia/",
                "title": "Nuestra historia", "totalCharacters": total or offset + len(text) + 9000,
                "bodyTruncated": False, "offset": offset, "hasMore": has_more, "endReached": not has_more,
                "authority": "public_http_get_html_text", "text": text}
    if has_more:
        observed["nextOffset"] = offset + len(text)
    return json.dumps({"status": "completed", "verification": "output_only", "observed": observed},
                      ensure_ascii=False)


@pytest.fixture
def focus_on(monkeypatch):
    monkeypatch.setenv("BAXY_WEB_FOCUS", "1")


def test_off_by_default_the_page_and_the_call_are_as_today(monkeypatch):
    monkeypatch.delenv("BAXY_WEB_FOCUS", raising=False)
    receipt = _receipt(HISTORY)
    assert web_focus.focus(receipt, ["en qué año se inauguró el Metro de Santiago"], {"url": "x"}) == receipt
    assert web_focus.widen({"url": "x"}) == {"url": "x"}


def test_the_call_reads_a_wider_part_unless_the_model_asked_a_size(focus_on):
    assert web_focus.widen({"url": "x"}) == {"url": "x", "maximumCharacters": web_focus.WINDOW}
    assert web_focus.widen({"url": "x", "maximumCharacters": 3000}) == {"url": "x", "maximumCharacters": 3000}


def test_the_paragraph_that_answers_is_shown_with_the_lead_under_the_cap(focus_on):
    receipt = _receipt(HISTORY)
    shown = json.loads(web_focus.focus(receipt, ["busca en internet en qué año se inauguró el Metro de Santiago"],
                                       {"url": "https://example.org/historia"}))
    page = shown["observed"]
    text = page["text"]
    assert "El 15 de septiembre se inauguró oficialmente" in text
    assert text.startswith("Nuestra Historia")
    assert "Ver Galería" not in text and "Ir al contenido" not in text
    body = text.split("\n[recortado:")[0]
    assert len(body) <= web_focus.CAP
    assert page["omittedCharacters"] > 0 and page["readInPart"] is True
    # The source, the offsets and the verification stay as the App gave them; the note says how to read it whole.
    assert shown["verification"] == "output_only" and shown["status"] == "completed"
    for field in ("requestedUrl", "finalUrl", "title", "totalCharacters", "offset", "nextOffset", "hasMore"):
        assert page[field] == json.loads(receipt)["observed"][field]
    assert f"offset 0 y maximumCharacters {len(HISTORY)}" in text
    assert "https://example.org/historia/" in text
    assert f"offset {len(HISTORY)}" in text


def test_the_turns_search_query_counts_too(focus_on):
    lines = [f"Párrafo {i}: {FILLER}" for i in range(30)]
    lines[20] = "El Volga es el río más largo de Europa, con unos 3690 km de longitud desde su fuente."
    receipt = _receipt("\n".join(lines))
    shown = json.loads(web_focus.focus(receipt, ["dime su nombre", "río más largo de Europa"], {"url": "x"}))
    assert "El Volga es el río más largo de Europa" in shown["observed"]["text"]


def test_a_page_within_the_cap_an_asked_size_or_an_error_comes_as_it_came(focus_on):
    short = _receipt("Texto corto de la página.", has_more=False)
    assert web_focus.focus(short, ["metro"], {"url": "x"}) == short
    long = _receipt(HISTORY)
    assert web_focus.focus(long, ["metro"], {"url": "x", "maximumCharacters": 8000}) == long
    failed = json.dumps({"status": "failed", "error": "web_fetch_timeout"})
    assert web_focus.focus(failed, ["metro"], {"url": "x"}) == failed
    assert web_focus.focus("no es json", ["metro"], {"url": "x"}) == "no es json"


def test_nothing_related_shows_the_start_of_the_text(focus_on):
    receipt = _receipt(HISTORY)
    text = json.loads(web_focus.focus(receipt, ["zzzz qqqq"], {"url": "x"}))["observed"]["text"]
    assert text.startswith("Nuestra Historia\nIr al contenido")
    assert len(text.split("\n[recortado:")[0]) <= web_focus.CAP


def test_a_later_part_has_no_lead_and_says_where_it_goes_on(focus_on):
    receipt = _receipt(HISTORY, offset=8000)
    page = json.loads(web_focus.focus(receipt, ["se inauguró"], {"url": "x", "offset": 8000}))["observed"]
    assert page["text"].startswith("…\n")  # no lead: the part starts with what was left out
    assert "El 15 de septiembre se inauguró oficialmente" in page["text"]
    assert "caracteres 8001–" in page["text"]
    assert f"offset {8000 + len(HISTORY)}" in page["text"]
