"""M134 (rounds v4i–v4l2, 2026-10-02): turns with no final because every draft was refused, with phrasings of our own.

1. DEV-F F-w22-t2, F-w24-t4, DEV-D D-w15-t3 (every round): a read of a known file failed (known_file_not_found) and
   every draft named the file it tried («lease.pdf», «cotización-pisos.pdf», «informe_trimestral.txt»); each died as
   internal_code. What a failure says it tried («target», «attempted») is the person's thing named back
   (``llm._attempted_targets``; App twin ObservedResponseLiterals, M134RedaccionTests), compared without accents.
2. D-w15-t3: «traducelo al ingles que es para mi jefa» with the file not found was told in English, the language of a
   translation that never happened; a failure is told in the language the person speaks (``_addressed_to_the_person``).
   The App refused «The file was not found…» as reversed_result; its twin now reads «not found» as the mind does.
3. DEV-F F-w59-t2 (v4l2): a task titled «…, mañana a las 18:30» quoted back died as an invented clock; a clock written
   in an observed title is the title's words.
4. DEV-D D-p35-t1 (v4j–v4l2): the SWOT kept by M124 said «…una noche de fiesta en los 80» in one point; every draft
   died as unsourced_figures. That point is left out when the analysis keeps its form; the figure is never published.
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime


class _Drafts(LlmRuntime):
    """The drafts stand in for the model in order (the last one repeats); every request is kept."""

    def __init__(self, drafts: list[str], finish: str = "stop") -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.finish = finish
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": self.finish}]}


def _not_found(operation: str, file_name: str, folder: str) -> str:
    return json.dumps({
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {
            "kind": "operation", "operation": operation, "polarity": "failure", "verified": False,
            "succeeded": False, "error": "known_file_not_found", "target": file_name,
            "attempted": {"fileName": file_name, "folder": folder},
        },
    }, ensure_ascii=False)


CONTRACT = _not_found("document.pdf.read", "arriendo-depto.pdf", "downloads")
BUDGET = _not_found("document.pdf.read", "presupuesto-cocina.pdf", "downloads")
MINUTES = _not_found("document.text.read", "acta_reunion.txt", "documents")


# ------------------------------------------------------------------ 1. the file a failed read tried


@pytest.mark.parametrize(("situation", "said", "draft"), [
    (CONTRACT, "can you sum up the rental lease in there?",
     "I couldn't read arriendo-depto.pdf because it is not in your Downloads folder."),
    (BUDGET, "y cuánto me sale la cocina?",
     "No pude ver el precio porque el archivo presupuesto-cocina.pdf no está en Descargas."),
    # Written with its accent: the same file.
    (_not_found("document.pdf.read", "cotizacion-muebles.pdf", "downloads"), "y eso cuánto sale?",
     "No pude leer cotización-muebles.pdf: no se encontró en la carpeta de descargas."),
    (MINUTES, "pásalo a limpio", "No encontré acta_reunion.txt en tu carpeta Documentos."),
])
def test_the_file_a_failed_read_tried_is_named_back(situation: str, said: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", said, {"situation": situation}) == ""
    assert _Drafts([draft]).compose_user_message(said, "error", {"situation": situation}) == draft


@pytest.mark.parametrize("draft", [
    "No pude leer arriendo-depto.pdf: document.pdf.read no lo encontró.",
    "No pude leer arriendo-depto.pdf por known_file_not_found.",
    "No encontré otro-arriendo.pdf en Descargas.",
])
def test_what_the_failure_did_not_try_is_still_internal_code(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", "resume el arriendo", {"situation": CONTRACT}) == "internal_code"


def test_only_what_was_tried_is_exempt() -> None:
    tokens = llm._observed_identifier_tokens(json.loads(CONTRACT))
    assert "arriendo-depto.pdf" in tokens
    assert "document.pdf.read" not in tokens
    assert llm._identifier_key("Cotización-Baños.PDF") == "cotizacion-banos.pdf"


# ------------------------------------------------------------------ 2. a failure is told in the person's language


def test_a_failed_translation_is_told_in_the_language_the_person_speaks() -> None:
    writer = _Drafts([
        "The minutes file was not found in your Documents folder.",
        "No pude traducirla porque no encontré acta_reunion.txt en la carpeta Documentos.",
    ])
    reply = writer.compose_user_message("pasame el acta al ingles que es para el cliente", "error", {"situation": MINUTES})
    assert reply == "No pude traducirla porque no encontré acta_reunion.txt en la carpeta Documentos."


def test_an_english_speaker_hears_the_failure_in_english() -> None:
    draft = "I couldn't translate it because acta_reunion.txt is not in your Documents folder."
    writer = _Drafts([draft])
    assert writer.compose_user_message(
        "translate the minutes into Spanish for my client", "error", {"situation": MINUTES},
    ) == draft


def test_a_translation_written_is_still_in_the_language_asked() -> None:
    assert llm._addressed_to_the_person("status", {"kind": "operation", "polarity": "success"}) is False
    assert llm._addressed_to_the_person("conversation", {"kind": "conversation"}) is False
    assert llm._addressed_to_the_person("error", {}) is True
    assert llm._addressed_to_the_person("status", {"kind": "failure"}) is True


# ------------------------------------------------------------------ 3. a clock written in an observed title


def _task(title: str) -> str:
    return json.dumps({
        "kind": "operation", "operation": "task.create", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {
            "taskId": "1b0c4a2e-0000-4000-8000-000000000001", "title": title, "details": "", "completed": False,
            "deleted": False, "createdAtUtc": "2026-10-02T22:29:04.6964848+00:00",
            "updatedAtUtc": "2026-10-02T22:29:04.6964848+00:00", "version": 1,
        },
    }, ensure_ascii=False)


def test_a_clock_in_the_task_title_is_the_title_s_words() -> None:
    situation = _task("pasar por la farmacia, el viernes a las 19:15")
    draft = 'He creado la tarea "pasar por la farmacia, el viernes a las 19:15".'
    assert _Drafts([draft]).compose_user_message("dale, el viernes 7:15 pm", "status", {"situation": situation}) == draft


def test_a_clock_the_title_does_not_carry_is_still_invented() -> None:
    situation = _task("pasar por la farmacia, el viernes a las 19:15")
    reply = _Drafts(['He creado la tarea "pasar por la farmacia" para las 20:45.']).compose_user_message(
        "dale, el viernes 7:15 pm", "status", {"situation": situation},
    )
    assert "20:45" not in reply
    # The UTC timestamps of the record are never a local clock to say.
    assert llm._clocks_written_in_observed_titles(json.loads(situation)["observed"]) == frozenset({"19:15"})


# ------------------------------------------------------------------ 4. an analysis point with an unsourced figure


SWOT = (
    "Mira, esta cadena tiene lo suyo, te lo cuento como colega.\n\n"
    "**Fortalezas:**\n- Una marca que suena a los 90 y a recreo.\n- Tiendas en muchas ciudades.\n\n"
    "**Debilidades:**\n- Precios que asustan a más de uno.\n\n"
    "**Oportunidades:**\n- Vender más por internet.\n\n"
    "**Amenazas:**\n- Rivales que copian todo al tiro."
)
SWOT_SOURCED = SWOT.replace("- Una marca que suena a los 90 y a recreo.\n", "")


def _unsourced(page: str):  # noqa: ANN202
    return lambda part: bool(llm._reference_unsourced_figures(part, page, [], None))


def test_the_point_with_an_unsourced_figure_is_left_out() -> None:
    page = "Ripley es una empresa chilena de tiendas por departamento con tiendas en muchas ciudades."
    assert llm._analysis_without_unsourced_points(SWOT, _unsourced(page)) == SWOT_SOURCED
    # A sentence of the prose opening goes the same way; the rest stays.
    opening = "Mira, esta cadena tiene lo suyo. Desde 1956 que la veo crecer.\n\n"
    assert llm._analysis_without_unsourced_points(
        opening + SWOT_SOURCED.split("\n\n", 1)[1], _unsourced(page),
    ) == "Mira, esta cadena tiene lo suyo.\n\n" + SWOT_SOURCED.split("\n\n", 1)[1]


def test_a_section_left_with_no_point_is_no_analysis() -> None:
    page = "Ripley es una empresa chilena."
    only_threat = SWOT_SOURCED.replace("Rivales que copian todo al tiro.", "Unos 40 rivales que copian todo.")
    assert llm._analysis_without_unsourced_points(only_threat, _unsourced(page)) == ""


RIPLEY_READ = {
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "query": "Ripley empresa", "count": 1, "results": [
        {"title": "Ripley - Wikipedia", "url": "https://es.wikipedia.org/wiki/Ripley",
         "snippet": "Ripley es una empresa chilena de tiendas por departamento con tiendas en muchas ciudades."},
    ]},
}


def test_the_consulted_analysis_is_published_without_the_figure_when_no_draft_passes() -> None:
    # Temperature 0 writes the same point again: the retry is refused too and the sourced part is the answer.
    swot = SWOT.replace("esta cadena", "Ripley")
    writer = _Drafts([swot + "\n\nEn resumen, Ripley"], finish="length")
    reply = writer.compose_user_message(
        "haz un FODA de la empresa Ripley con un tono relajado", "status", {"situation": RIPLEY_READ},
    )
    assert reply == SWOT_SOURCED.replace("esta cadena", "Ripley")
    assert "90" not in reply
    assert len(writer.requests) == 2


def test_a_retry_that_passes_is_still_the_answer() -> None:
    # The sourced part is a last resort: a whole draft with no unsourced figure wins (M121's retry).
    swot = SWOT.replace("esta cadena", "Ripley")
    whole = swot.replace("- Una marca que suena a los 90 y a recreo.", "- Una marca que todos conocen.")
    writer = _Drafts([swot, whole])
    reply = writer.compose_user_message(
        "haz un FODA de la empresa Ripley con un tono relajado", "status", {"situation": RIPLEY_READ},
    )
    assert reply == whole
