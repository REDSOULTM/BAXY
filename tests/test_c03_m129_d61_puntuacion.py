"""M129 — D61 (owner, 2026-10-02) in ``comprension_eval.py score``: the alternative decisions the owner accepts
(``--accept FILE``) and a recipe or figure looked up first by D35 where the gold talks (``--d35``) are counted only
when asked, after the gold's own figures; without the options the score is the same, byte for byte."""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import comprension_eval as ce  # noqa: E402

_ROWS = [
    # A recipe the gold answers by talking; the mind looked it up first (D35).
    {"id": "Z-s001", "kind": "single", "source": "t", "text": "cómo se hace el pebre", "gold": ["talk"], "args": {}},
    # Obsidian is not installed: saying so is accepted (D61.2).
    {"id": "Z-s002", "kind": "single", "source": "t", "text": "abre obsidian", "gold": ["op:app.open"],
     "args": {"op:app.open": [["obsidian"]]}},
    # Looked up without the D35 stage: still the gold's miss.
    {"id": "Z-s003", "kind": "single", "source": "t", "text": "quién ganó ayer", "gold": ["talk"], "args": {}},
    {"id": "Z-c01-t1", "kind": "conv", "source": "t", "text": "hola", "gold": ["talk"], "args": {}, "dep": False},
    # A company's analysis is looked up by D59.8, not by D35.
    {"id": "Z-c01-t2", "kind": "conv", "source": "t", "text": "un FODA de una empresa", "gold": ["talk"], "args": {},
     "dep": True},
    # A turn that failed is never counted.
    {"id": "Z-s004", "kind": "single", "source": "t", "text": "receta de arepas", "gold": ["talk"], "args": {}},
]
_SEARCH = {"kind": "action", "operation": "web.search", "effects": ["web.search"], "conversation_kind": None}
_RUN = [
    {"id": "Z-s001", "turn_id": "t1", **_SEARCH, "reply": "Pebre:", "latency_s": 2.0},
    {"id": "Z-s002", "turn_id": "t2", "kind": "action", "operation": "app.installed", "effects": ["app.installed"],
     "reply": "Obsidian no está instalada.", "latency_s": 1.0},
    {"id": "Z-s003", "turn_id": "t3", **_SEARCH, "reply": "Ganó…", "latency_s": 3.0},
    {"id": "Z-c01-t1", "turn_id": "t4", "kind": "conversation", "conversation_kind": "social", "effects": [],
     "reply": "Hola.", "latency_s": 1.0},
    {"id": "Z-c01-t2", "turn_id": "t5", **_SEARCH, "reply": "FODA…", "latency_s": 4.0},
    {"id": "Z-s004", "turn_id": "t6", **_SEARCH, "reply": "", "error": "composition_failed", "latency_s": 9.0},
]
_STAGES = {
    "t1": [{"name": "validated_raw"}, {"name": "reference_looked_up", "mode": "action"}],
    "t3": [{"name": "validated_raw"}],
    "t5": [{"name": "reference_looked_up", "kind": "analysis"}],
    "t6": [{"name": "reference_looked_up", "kind": "recipe"}],
}
_ACCEPT = [{"id": "Z-s002", "accept": ["op:app.installed"], "reason": "D61.2: la app no está instalada."}]


def _write(path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


@pytest.fixture()
def capture(tmp_path: pathlib.Path) -> pathlib.Path:
    """A window run: RUN.jsonl joined to the turn audit through the shell trace (comprension_window records)."""
    _write(tmp_path / "SET.jsonl", _ROWS)
    _write(tmp_path / "RUN.jsonl", _RUN)
    trace, audit, seq = [], [], 0
    for record in _RUN:
        turn = record["turn_id"]
        request = f"req-{turn}"
        for row in (
            {"scope": "bridge", "stage": "submit.received", "id": turn, "ms": 0},
            {"scope": "turn", "stage": "mind.request.start", "id": f"m-{turn}", "detail": f"turn.decide.id.{request}"},
            {"scope": "bridge", "stage": "response.final", "id": turn, "ms": 1000},
        ):
            seq += 1
            trace.append({"seq": seq, **row})
        audit.append({"phase": "final", "request_id": request, "decision_path": "explicit_conversation",
                      "stages": _STAGES.get(turn, []), "final": {"kind": record["kind"]}})
    _write(tmp_path / "shell-trace.jsonl", trace)
    _write(tmp_path / "turn-audit.jsonl", audit)
    _write(tmp_path / "ACCEPT.jsonl", _ACCEPT)
    return tmp_path


def _score(module: types.ModuleType, folder: pathlib.Path, *options: str, set_path: pathlib.Path | None = None,
           run: pathlib.Path | None = None) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        module.main(["score", "--set", str(set_path or folder / "SET.jsonl"), "--run", str(run or folder / "RUN.jsonl"),
                     *options])
    return out.getvalue()


# The pre-D61 scorer's own output on the fixture (comprension_eval.py at 7e764107), byte for byte.
_BEFORE = (
    "SET.jsonl: 6/6 turnos puntuados, errores de réplica 1\n"
    "  total         1/6 = 16.7 %   (sólo decisión 1/6)\n"
    "  sueltos       0/4 = 0.0 %   (sólo decisión 0/4)\n"
    "  conversación  1/2 = 50.0 %   (sólo decisión 1/2)\n"
    "  seguimientos  0/1 = 0.0 %   (sólo decisión 0/1)\n"
    "  latencia de decisión p50 3.0 s, p90 9.0 s\n"
    "  por fuente: t 1/6\n"
    "  fallos (oro principal, obtenido): ('talk', 'action:web.search')×3, ('op:app.open', 'action:app.installed')×1, "
    "('talk', 'error')×1\n"
    "  NO Z-s001 [?] ['talk'] -> action:web.search | cómo se hace el pebre || Pebre:\n"
    "  NO Z-s002 [?] ['op:app.open'] -> action:app.installed | abre obsidian || Obsidian no está instalada.\n"
    "  NO Z-s003 [?] ['talk'] -> action:web.search | quién ganó ayer || Ganó…\n"
    "  NO Z-c01-t2 [?] ['talk'] -> action:web.search | un FODA de una empresa || FODA…\n"
    "  NO Z-s004 [?] ['talk'] -> error | receta de arepas || composition_failed\n"
)


def test_without_the_options_the_score_is_unchanged(capture: pathlib.Path) -> None:
    assert _score(ce, capture) == _BEFORE
    assert _score(ce, capture, "--blind") == _BEFORE.partition("  fallos")[0]


def test_the_options_add_their_figures_after_the_gold(capture: pathlib.Path) -> None:
    printed = _score(ce, capture, "--accept", str(capture / "ACCEPT.jsonl"), "--d35")

    before, _, after = printed.partition("  con D61")
    assert "  total         1/6 = 16.7 %" in before
    assert after.startswith(" (aceptadas de ACCEPT.jsonl + D35 buscar primero): +2 turnos (aceptadas 1, D35 1;")
    assert "    total         3/6 = 50.0 %" in after
    assert "    D61 Z-s001 [D35]" in after and "    D61 Z-s002 [aceptada]" in after
    # Neither the search without the D35 stage, the company analysis (D59.8) nor the failed turn counts.
    assert "Z-s003" not in after and "Z-c01-t2" not in after and "Z-s004" not in after


@pytest.mark.parametrize(
    ("options", "total"),
    [(("--d35",), "2/6 = 33.3 %"), (("--accept", "ACCEPT"), "2/6 = 33.3 %")],
)
def test_each_option_alone(capture: pathlib.Path, options: tuple[str, ...], total: str) -> None:
    options = tuple(str(capture / "ACCEPT.jsonl") if option == "ACCEPT" else option for option in options)
    printed = _score(ce, capture, *options)
    assert f"    total         {total}" in printed.partition("  con D61")[2]


def test_blind_prints_no_row(capture: pathlib.Path) -> None:
    printed = _score(ce, capture, "--blind", "--d35", "--accept", str(capture / "ACCEPT.jsonl"))

    assert "Z-" not in printed and "pebre" not in printed
    assert "+2 turnos" in printed and "    total         3/6 = 50.0 %" in printed


def test_an_accept_row_needs_a_reason_and_known_labels(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError):
        ce.read_accepted(_write(tmp_path / "a.jsonl", [{"id": "x", "accept": ["op:app.installed"]}]))
    with pytest.raises(ValueError):
        ce.read_accepted(_write(tmp_path / "b.jsonl", [{"id": "x", "accept": ["maybe"], "reason": "r"}]))


# ------------------------------------------------------------------ an existing run, against the pre-D61 scorer

_WINDOW = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "BAXY" / "comprension-2026-09-25"
_BASELINE_COMMIT = "7e764107"


def _scorer_before_d61() -> types.ModuleType:
    source = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{_BASELINE_COMMIT}:scripts/comprension_eval.py"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    module = types.ModuleType("comprension_eval_before_d61")
    module.__file__ = str(ROOT / "scripts" / "comprension_eval.py")
    exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.mark.skipif(
    not (_WINDOW / "window" / "v4j-devF" / "RUN.jsonl").is_file(), reason="la corrida v4j-devF no está en esta máquina"
)
@pytest.mark.parametrize("name", ["F", "D"])
def test_an_existing_run_scores_the_same_as_before_d61(name: str) -> None:
    set_path = _WINDOW / "sets" / f"DEV-{name}.jsonl"
    run = _WINDOW / "window" / f"v4j-dev{name}" / "RUN.jsonl"
    audit = ["--audit", str(run.parent / "turn-audit.jsonl")]

    assert _score(ce, run.parent, *audit, set_path=set_path, run=run) == _score(
        _scorer_before_d61(), run.parent, *audit, set_path=set_path, run=run
    )
