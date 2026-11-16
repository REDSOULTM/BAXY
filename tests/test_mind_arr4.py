"""ARR4 (REVX1 A3-2 and A3-3, 15-11-2026): the stand-in of ARR3 acts only where 1.5.4 did not start.

The leader's decision: the identity says «funciona en una tarjeta de 4 GB en total con Windows abierto», and the cut rule
says what lowers a figure goes. So where the base started a profile the person chose, with the margin or without it, the
start is the same: the same profile and the same cells. Only where theirs alone launched no server («BAXY no logra
arrancar», VIVO23) a smaller ready-made one stands in for it (ARR3). And the fact of that start is English in English.
"""
import pathlib

import pytest

from baxy_mind import harness_language, llm_server
from test_mind_final import _mind
from test_mind_vram4b import AVANZADO, COMPLETO, DIARIO, ESENCIAL, OPEN, _started

ORDER = (COMPLETO, AVANZADO, DIARIO, ESENCIAL)
# REVX1's table (tmp\REVX1\arr3\pruebas\cabe.py), and a GTX 1650 of 4 GB in all with the desktop on the processor's
# GPU (INFORME_C1650X.md): 3,292 MiB free as BAXY 1.5.4 measured it (Esencial chosen by itself), 3,923 as nvidia-smi.
FREE = (None, 2500, 3100, 3264, 3292, 3300, 3400, 3527, 3528, 3600, 3700, 3879, 3880, 3923, 4082, 4083, 6000, 16000)


def _cells(command: list[str]) -> str:
    return command[command.index("-c") + 1]


@pytest.mark.parametrize("chosen", ORDER)
def test_where_theirs_alone_started_the_start_is_the_bases(tmp_path, monkeypatch, chosen) -> None:
    smaller = ",".join(str(need) for need in ORDER if need < chosen)
    for at, free in enumerate(FREE):
        monkeypatch.delenv(llm_server.CONTEXT_THEIRS_VARIABLE, raising=False)
        monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(chosen))
        base, alone = _started(monkeypatch, tmp_path / f"b{at}", free)
        monkeypatch.setenv(llm_server.CONTEXT_THEIRS_VARIABLE, "1")
        monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", ",".join(filter(None, (str(chosen), smaller))))
        now, listed = _started(monkeypatch, tmp_path / f"b{at}", free)
        if not base.card_refused:
            assert listed == alone, f"free {free}: the base started {_cells(alone[0])}"
            assert now.card_fit is None and now.card_short == base.card_short and not now.card_refused
        elif smaller:
            # ARR3's case: theirs launched nothing; the largest smaller one the card holds starts, and says it is one.
            monkeypatch.delenv(llm_server.CONTEXT_THEIRS_VARIABLE)
            factory, first = _started(monkeypatch, tmp_path / f"b{at}", free)
            assert listed == first and now.card_fit == factory.card_fit and now.card_refused == factory.card_refused


def test_arr3s_case_still_starts_in_the_largest_that_fits(tmp_path, monkeypatch) -> None:
    # VIVO23: Completo chosen, 3,400 MiB free. 1.5.4 launched nothing (test_mind_vram4b); now Esencial, said as a stand-in.
    monkeypatch.setenv(llm_server.CONTEXT_THEIRS_VARIABLE, "1")
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", ",".join(map(str, ORDER)))
    server, launched = _started(monkeypatch, tmp_path, 3400)
    assert _cells(launched[0]) == "32768" and not server.card_refused
    assert server.card_fit is not None and server.card_fit["needs"] == ESENCIAL


def test_diario_chosen_without_the_margin_keeps_diario(tmp_path, monkeypatch) -> None:
    # REVX1 A3-2: Diario chosen, 3,400 MiB free: 1.5.4 started Diario at 45,056 cells without the margin; ARR3, Esencial.
    monkeypatch.setenv(llm_server.CONTEXT_THEIRS_VARIABLE, "1")
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{DIARIO},{ESENCIAL}")
    server, launched = _started(monkeypatch, tmp_path, 3400)
    assert _cells(launched[0]) == "45056" and server.card_fit is None


@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
def test_theirs_alone_is_the_first_need_wherever_alone_it_launches(backend) -> None:
    automatic = 77824 if backend == "cuda" else 61440
    for chosen in ORDER:
        listed = [chosen, *(need for need in ORDER if need < chosen)]
        for free in FREE:
            cells = llm_server.fit_profiles(free, automatic, [chosen], backend)[0]
            launches = free is None or llm_server.card_mib(cells, backend) <= free
            assert llm_server.theirs_alone(free, automatic, listed, backend) == ([chosen] if launches else listed)


def test_only_a_one_says_theirs() -> None:
    assert llm_server.context_theirs({llm_server.CONTEXT_THEIRS_VARIABLE: "1"})
    for said in ("", "0", "true", "yes"):
        assert not llm_server.context_theirs({llm_server.CONTEXT_THEIRS_VARIABLE: said})
    assert not llm_server.context_theirs({})


@pytest.mark.parametrize("again", [None, False])
def test_the_stand_in_fact_is_english_in_english(tmp_path: pathlib.Path, again) -> None:
    # REVX1 A3-3: CARD_PROFILE_CHOSEN_FACT and _NOW had no English: a Spanish sentence in the English system text.
    card = {"profile": "Essential", "factory": "Complete", "freeMb": 3400, "needMb": 5200, "chosen": True}
    if again is not None:
        card["again"] = again
    mind, _ = _mind(tmp_path, [])
    try:
        mind.configure({"capabilities": [OPEN], "cardProfile": card, "lang": "en"})
        assert "The person chose the Complete tool profile" in mind.system
        assert "BAXY started with the Essential profile" in mind.system
        assert ("asks for it again" in mind.system) == (again is None)
        for spanish in ("La persona eligió", "arrancó con el perfil", "sigue guardada", "también ahora", "pidiéndotelo"):
            assert spanish not in mind.system
    finally:
        harness_language.use(harness_language.SPANISH)
