"""The answer after a tool (w7-breve, 2026-10-23): on the holdout v4 turn.continue wrote more, predicted p50 399 → 487 ms.
Aid «facts_once»: the facts line says each long wording of how a call ended once; every call keeps its entry, and what
it says of failures, unverified effects and parts read stays."""
import json
import pathlib

import pytest

from test_mind_final import _call, _mind, _say
from test_mind_w6_lat import _results

READ = json.dumps({"status": "completed", "verification": "output_only", "observed": {"title": "RFC 2324"}},
                  separators=(",", ":"))
SENT = json.dumps({"status": "completed", "verification": "delivered_only", "observed": {"delivered": True}},
                  separators=(",", ":"))
SAME = json.dumps({"status": "completed", "verification": "unchanged", "observed": {"completed": True}},
                  separators=(",", ":"))
PART = json.dumps({"status": "completed", "verification": "output_only",
                   "observed": {"fromLine": 1, "toLine": 200, "totalLines": 3000, "readInPart": True, "text": "x"}},
                  separators=(",", ":"))
FAILED = json.dumps({"status": "failed", "error": "window_not_found"}, separators=(",", ":"))


def _line(tool: str) -> str:
    return tool[tool.index("\n[En este turno: ") + len("\n[En este turno: "):].split("]\n")[0].removesuffix("]")


def _turn(tmp_path: pathlib.Path, calls: list[tuple[str, str]]) -> str:
    """The facts line the model reads after the last of these calls (wire name, result)."""
    mind, server = _mind(tmp_path, [*(_call(wire, {"n": i}) for i, (wire, _) in enumerate(calls)), _say("Listo.")])
    mind.risk.update({"web_fetch": "read_only", "task_list": "read_only", "file_read": "read_only"})
    mind.decide(1, "hazlo")
    for index, (_, result) in enumerate(calls):
        mind.continue_turn(2 + index, result)
    return _line(_results(server)[-1])


@pytest.mark.parametrize("setting", ["all", "facts_once"])
def test_a_wording_is_said_in_full_once_and_every_call_keeps_its_entry(tmp_path: pathlib.Path, monkeypatch,
                                                                         setting: str) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    line = _turn(tmp_path, [("web_fetch", READ), ("web_fetch", READ), ("input_text_type", SENT),
                            ("input_text_type", SENT), ("task_complete", SAME), ("task_complete", SAME),
                            ("app_close", FAILED)])
    assert line == ("web_fetch → lectura: sólo miró, sin abrir, cerrar ni cambiar nada; "
                    "web_fetch → lectura: sólo miró; "
                    "input_text_type → enviado sin verificar: no se volvió a mirar si hizo efecto; "
                    "input_text_type → enviado sin verificar; "
                    "task_complete → ya estaba así antes de esta llamada: no hizo falta cambiar nada; "
                    "task_complete → ya estaba así antes de esta llamada; "
                    "app_close → falló (window_not_found)")


def test_without_the_aid_the_line_is_the_one_of_before(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "result_dedup,short_refs")
    line = _turn(tmp_path, [("web_fetch", READ), ("web_fetch", READ)])
    full = "web_fetch → lectura: sólo miró, sin abrir, cerrar ni cambiar nada"
    assert line == f"{full}; {full}"


def test_a_later_part_read_keeps_how_much_it_read(tmp_path: pathlib.Path, monkeypatch) -> None:
    # The second read says it read in part and which lines; what a «no está» covers was said once, before it.
    monkeypatch.setenv("BAXY_AYUDAS", "all")
    line = _turn(tmp_path, [("file_read", PART), ("file_read", PART)])
    first, second = line.split("; file_read → ")
    assert first.endswith("leído en parte: líneas 1–200 de 3000; lo demás no se leyó: un «no está» vale sólo para lo "
                          "leído")
    assert second == "lectura: sólo miró; leído en parte: líneas 1–200 de 3000"


def test_a_lone_call_and_different_outcomes_are_said_as_before(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "all")
    assert _turn(tmp_path, [("web_fetch", READ)]) == (
        "web_fetch → lectura: sólo miró, sin abrir, cerrar ni cambiar nada")
    assert _turn(tmp_path, [("input_text_type", SENT), ("web_fetch", READ), ("app_close", FAILED)]) == (
        "input_text_type → enviado sin verificar: no se volvió a mirar si hizo efecto; "
        "web_fetch → lectura: sólo miró, sin abrir, cerrar ni cambiar nada; "
        "app_close → falló (window_not_found)")


def test_the_unsure_and_the_failed_are_never_shortened() -> None:
    from baxy_mind.mind import SAID_AGAIN, _said_once
    done = ["app_open → sin confirmar: pudo o no ocurrir", "app_open → sin confirmar: pudo o no ocurrir",
            "app_close → falló (window_not_found)", "app_close → falló (window_not_found)",
            "audio_volume → completado y verificado", "audio_volume → completado y verificado"]
    assert _said_once(done) == done
    # What a later call says is still the start of its full wording: none drops what happened.
    for full, again in SAID_AGAIN.items():
        assert full.startswith(again) or full.endswith(again)
