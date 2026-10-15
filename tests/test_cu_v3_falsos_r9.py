"""Dos falsos éxitos de la pasada v3 r9 (cu-v3/v3_pasada_r9_parcial_veredictos.json), con lo que se vio en vivo.

- v3-27 «abre el mapa de caracteres y copia el simbolo del euro»: el decisor eligió input.keyboard.open (turn_audit de
  cu-universal-evidencia/v2-v3-27), se abrió el Teclado en pantalla, no corrió ninguna misión y el redactor publicó
  «Abrió el mapa de caracteres y copió el símbolo del euro.» (compose_audit: el primer borrador en primera persona cayó
  por unbacked_act; el tercero, en tercera persona sin sujeto, pasó). La ruta está en test_cu_v3_cobertura.py; aquí el
  libro de actos sobre el payload real.
- v3-42 «en el panel de control anda a programas y caracteristicas y busca chrome»: los dos sub-objetivos se dieron por
  cumplidos en la página «Programas» (el enlace «Programas y características» pasó por encabezado; el título repetía lo
  tecleado). El juicio es del shell (ComputerUseMissionTests / ComputerUseLoopTests, con las mismas vistas); aquí, que
  sobre la vista real el paso siguiente es pulsar ese enlace.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import cu_rules
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind.semantic import claims

ROOT = Path(__file__).resolve().parent
V3_42 = json.loads((ROOT / "data" / "cu_v3_r9_v3_42_vistas.json").read_text(encoding="utf-8"))

# The live situation of v3-27 (compose_audit.jsonl, stage «third»): one verified input.keyboard.open.
V3_27_REQUEST = "abre el mapa de caracteres y copia el simbolo del euro"
V3_27_SITUATION = {
    "kind": "operation", "operation": "input.keyboard.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "ok": True, "effectObserved": True, "action": "keyboard", "pointerAction": "", "layout": "",
        "language": "other", "openedProcessId": 15988, "acceptedEvents": 1, "expectedEvents": 1, "inputSize": 40,
        "lastWin32Error": 0, "foregroundProcessIdBefore": 45452, "foregroundProcessIdAfter": 45452,
        "foregroundTitleBefore": "BAXY usuario simulado", "authority": "windows_osk_process_window_visible_postread",
    },
}


def _defect(reply: str, request: str = V3_27_REQUEST) -> str:
    return compose_visible_defect(
        reply, "status", request, {"situation": json.dumps(V3_27_SITUATION, ensure_ascii=False)},
    )


def test_v3_27_the_published_final_tells_a_copy_no_step_made() -> None:
    assert _defect("Abrió el mapa de caracteres y copió el símbolo del euro.") == "unbacked_act"
    assert _defect("Listo, abrió el mapa de caracteres y copió el símbolo del euro.") == "unbacked_act"
    assert _defect("Opened Character Map and copied the euro sign.", "open character map and copy the euro sign") == (
        "unbacked_act"
    )


@pytest.mark.parametrize(
    "reply",
    [
        # what the operation did, told in the first person or with no subject
        "Abrí el teclado en pantalla.",
        "Abrió el teclado en pantalla.",
        # the person's words quoted, or what they asked, are no act told
        "Me pediste abrir el mapa de caracteres y copiar el símbolo del euro; abrí el teclado en pantalla.",
        "Dijiste «abrió el mapa y copió el símbolo», pero sólo abrí el teclado en pantalla.",
        "Dijiste que copió el símbolo del euro; yo sólo abrí el teclado en pantalla.",
        # a denial
        "Abrí el teclado en pantalla, pero no copió el símbolo del euro.",
    ],
)
def test_v3_27_contracase_what_was_done_quoted_or_denied_is_published(reply: str) -> None:
    assert _defect(reply) == "", reply


@pytest.mark.parametrize(
    ("text", "acts"),
    [
        ("Abrió el mapa de caracteres y copió el símbolo del euro.", ["abrió", "copió"]),
        ("Listo, ya escribió el texto.", ["escribió"]),
        ("Opened Character Map, then copied the euro sign.", ["opened", "copied"]),
        # a subject, a periphrasis, a pro-verb, the present or an English imperative tell no act of BAXY's
        ("La ventana se cerró y abrió otra.", []),
        ("Empezó a sonar la canción.", []),
        ("Lo hizo.", []),
        ("Copio el texto cuando quieras.", []),
        ("Set a timer if you want.", []),
        ("Dijiste que abrió el mapa y copió el símbolo.", []),
    ],
)
def test_the_book_reads_a_past_told_with_no_subject(text: str, acts: list[str]) -> None:
    assert [word for word, _ in claims.claimed_acts(text)] == acts
    # A failure explains what happened in the third person: the reading is a success's only.
    assert [word for word, _ in claims.claimed_acts(text, third_person=False)] == []


def test_v3_42_on_the_page_reached_the_next_step_is_the_link_to_the_place() -> None:
    view = V3_42["programas_seq494"]
    clicked = [{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Programas",
                "arguments": {"label": "Programas"}}]
    step = cu_rules.deterministic_step(goal="ir a programas y caracteristicas", view=view, history=clicked)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Programas y características", "index": 19}
    # The view is the live one: the link is a Hyperlink at the top left, the page's title is «Programas».
    link = view["controls"][19]
    assert (link["kind"], link["zone"], view["window"]["title"]) == ("Hyperlink", "TL", "Programas")
    searched = V3_42["buscado_seq506"]
    assert searched["window"]["title"] == "chrome - Programas"
    assert "Ningún elemento coincide con el criterio de búsqueda." in searched["text"]["T"]
