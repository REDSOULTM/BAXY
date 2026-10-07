"""Voice audit 2026-10-07, round 17: the register checks judge BAXY's own words. Typed text, a title on screen or the
person's request said in the reply unquoted are theirs, and a demonym ending in -í is no misspelled preterite."""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic import voice_register


def _mission(observed: dict) -> dict:
    return {
        "kind": "operation",
        "operation": "mission.computer.use",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "cause": "mission_completed",
        "observed": observed,
    }


def _defect(text: str, situation: dict, said: str = "") -> str:
    return llm.compose_visible_defect(text, "status", said, {"situation": json.dumps(situation, ensure_ascii=False)})


@pytest.mark.parametrize(
    "draft, observed",
    [
        ("Ya escribí he llegado tarde en el Bloc de notas.", {"typedText": "he llegado tarde", "reached": True}),
        ("Lo puse a reproducir: el video se llama Te he echado de menos.", {"title": "Te he echado de menos"}),
        ("Abrí el correo y el título dice Hemos actualizado nuestra política.",
         {"title": "Hemos actualizado nuestra política", "reached": True}),
        ("Abrí la canción Estamos en la cima.", {"title": "Estamos en la cima"}),
    ],
)
def test_the_screens_or_typed_words_are_theirs(draft: str, observed: dict) -> None:
    # as compose_visible_defect hears it: the request, the screen's words and the facts' texts
    heard = json.dumps({"situation": json.dumps(_mission(observed), ensure_ascii=False)}, ensure_ascii=False)
    assert llm.own_voice_defect(draft, heard, act_report=True, preterite_floor=True) == ""
    # without the facts the same words would read as BAXY's own perfect or plural
    assert llm.own_voice_defect(draft, "", act_report=True, preterite_floor=True) != ""


def test_the_persons_words_are_theirs() -> None:
    said = "escribí he llegado tarde en el bloc de notas"
    assert not voice_register.tells_own_act_in_peninsular_perfect("Ya escribí he llegado tarde.", said=said)
    assert not voice_register.tells_own_act_in_plural(
        "Busqué Hemos llegado en Spotify.", said="busca hemos llegado en spotify"
    )


def test_baxys_own_perfect_or_plural_beside_their_words_is_still_vetoed() -> None:
    observed = {"typedText": "he llegado tarde", "reached": True}
    assert _defect("Ya he escrito he llegado tarde en el Bloc de notas.", _mission(observed)) == "peninsular_perfect"
    assert _defect("Ya estamos en el Bloc de notas con he llegado tarde.", _mission(observed)) == "plural_own_act"
    # a word of the span alone is not the span: «llegado» said does not make «he llegado» theirs
    assert voice_register.tells_own_act_in_peninsular_perfect("Ya he llegado a Bluetooth.", said="llegado")
    assert voice_register.tells_own_act_in_plural("Ya estamos en la sección de Sonido.", said="la sección de sonido")


@pytest.mark.parametrize(
    "draft",
    [
        "Busqué el riyal qatarí en el conversor.",
        "Busqué la Embajada Qatarí.",
        "Encontré el dinar iraquí, el rial omaní y el dírham marroquí.",
        "Puse la bandera israelí, la paquistaní, la pakistaní y la bengalí.",
        "Busqué un negligé en la tienda.",
        "Elegí el color carmesí.",
    ],
)
def test_a_demonym_or_loan_is_not_a_misspelled_preterite(draft: str) -> None:
    assert voice_register.misspelled_own_preterite(draft) == ""


def test_a_real_misspelling_beside_a_demonym_is_still_found() -> None:
    assert voice_register.misspelled_own_preterite("Abrazé el riyal qatarí.") == "abrazé"
