"""El driver de tandas convierte la tanda a la sonda y une el informe por turno."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "scripts" / "uso_real" / "tanda_driver.py"
T1 = ROOT / "scripts" / "uso_real" / "tandas" / "t1.json"
RUN_BAXY = ROOT / "scripts" / "run_baxy.ps1"
TANDA_PS1 = ROOT / "scripts" / "uso_real" / "tanda.ps1"


def _driver():
    spec = importlib.util.spec_from_file_location("tanda_driver", DRIVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TANDA = {
    "conversations": [
        {
            "id": "c1",
            "speaker": "s1",
            "turns": [
                {"text": "sube el volumen", "expect": "sube"},
                {"text": "  ", "expect": "nada"},
                {"text": "un poco más", "expect": "más"},
            ],
        },
        {"id": "c2", "speaker": "s2", "turns": [{"text": "hola", "expect": "saluda"}]},
    ]
}


def test_convert_opens_a_session_before_each_conversation_and_tags_turns() -> None:
    lines = _driver().probe_lines(TANDA)

    assert lines == [
        {"cmd": "session.new", "conversation": "c1"},
        {"text": "sube el volumen", "conversation": "c1", "turn": 1},
        {"text": "un poco más", "conversation": "c1", "turn": 3},
        {"cmd": "session.new", "conversation": "c2"},
        {"text": "hola", "conversation": "c2", "turn": 1},
    ]


def test_real_tanda_converts_with_one_session_per_conversation() -> None:
    driver = _driver()
    tanda = driver.load_tanda(T1)
    lines = driver.probe_lines(tanda)

    sessions = [line for line in lines if line.get("cmd") == "session.new"]
    turns = [line for line in lines if "text" in line]
    assert len(sessions) == len(tanda["conversations"])
    assert len(turns) == sum(len(c["turns"]) for c in tanda["conversations"])
    assert lines[0]["cmd"] == "session.new"


def test_load_tanda_rejects_a_conversation_without_turns(tmp_path: Path) -> None:
    path = tmp_path / "mala.json"
    path.write_text(json.dumps({"conversations": [{"id": "x"}]}), encoding="utf-8")

    with pytest.raises(ValueError):
        _driver().load_tanda(path)


def _probe_turn(conversation, turn, text, reply, send="sent", settled=True):
    return {
        "type": "ui.turn",
        "conversation": conversation,
        "turn": turn,
        "text": text,
        "send": send,
        "settled": settled,
        "elapsed_ms": 1234,
        # El orden real de la ventana: la fila más nueva primero.
        "new_rows": [
            {"src": "BAXY", "msg": reply, "ts": ""},
            {"src": "SYSTEM", "msg": "progreso", "ts": ""},
            {"src": "YOU", "msg": text, "ts": ""},
        ],
    }


def test_report_joins_visible_reply_and_latency_by_order_and_text() -> None:
    driver = _driver()
    probe = [
        {"type": "meta"},
        {"type": "ui.session.new", "conversation": "c1"},
        _probe_turn("c1", 1, "sube el volumen", "Listo, 60 %."),
        _probe_turn("c1", 3, "un poco más", "Subido a 70 %."),
        {"type": "ui.session.new", "conversation": "c2"},
        _probe_turn("c2", 1, "hola", "Hola."),
    ]
    log = [
        # De una tanda anterior: queda fuera por la hora.
        {"utc": "2026-10-07T09:00:00Z", "role": "user", "text": "hola"},
        {"utc": "2026-10-07T09:00:01Z", "role": "assistant", "text": "viejo", "latency_ms": 1},
        {"utc": "2026-10-07T10:00:00.1234567Z", "role": "user", "text": "sube el volumen"},
        {"utc": "2026-10-07T10:00:02Z", "role": "assistant", "text": "Listo, 60 %.", "latency_ms": 2000, "route": "r"},
        {"utc": "2026-10-07T10:00:05Z", "role": "user", "text": "un  poco más"},
        {"utc": "2026-10-07T10:00:06Z", "role": "assistant", "text": "Subiendo…", "latency_ms": 900},
        {"utc": "2026-10-07T10:00:08Z", "role": "assistant", "text": "Subido a 70 %.", "latency_ms": 3100},
        {"utc": "2026-10-07T10:00:10Z", "role": "user", "text": "hola"},
        {"utc": "2026-10-07T10:00:11Z", "role": "assistant", "text": "Hola.", "latency_ms": 700},
    ]
    since = datetime(2026, 10, 7, 9, 30, tzinfo=timezone.utc)

    report = driver.join_report(TANDA, probe, log, since)

    assert [(row["conversation"], row["turn"]) for row in report] == [("c1", 1), ("c1", 3), ("c2", 1)]
    assert report[0]["response"] == "Listo, 60 %."
    assert report[0]["latency_ms"] == 2000
    assert report[0]["routes"] == ["r"]
    assert report[1]["latency_first_ms"] == 900
    assert report[1]["latency_ms"] == 3100
    assert report[1]["response_log"] == "Subiendo…\nSubido a 70 %."
    # Contracaso: el «hola» viejo no presta su latencia.
    assert report[2]["latency_ms"] == 700
    assert report[2]["expect"] == "saluda"


def test_two_turn_capture_takes_each_reply_from_the_newest_first_prefix() -> None:
    # Forma de una captura real: la lista se pinta con la más nueva primero
    # y new_rows es su prefijo nuevo. El turno 2 no hereda «Hola.» del 1.
    driver = _driver()
    tanda = {
        "conversations": [
            {"id": "c1", "speaker": "s", "turns": [{"text": "hola"}, {"text": "¿Qué hora es?"}]}
        ]
    }
    first = [
        {"src": "BAXY", "msg": "Hola.", "ts": "10:00:02"},
        {"src": "YOU", "msg": "hola", "ts": "10:00:01"},
    ]
    second = [
        {"src": "BAXY", "msg": "Son las diez.", "ts": "10:00:06"},
        {"src": "SYSTEM", "msg": "consultando la hora", "ts": "10:00:05"},
        {"src": "BAXY", "msg": "Un momento.", "ts": "10:00:05"},
        {"src": "YOU", "msg": "¿Qué hora es?", "ts": "10:00:04"},
    ]
    session = [{"src": "SYSTEM", "msg": "new session", "ts": "10:00:00"}]
    probe = [
        {"type": "ui.session.new", "conversation": "c1", "status": "200", "reset": True},
        {"type": "ui.turn", "conversation": "c1", "turn": 1, "send": "sent", "settled": True,
         "new_rows": first, "rendered": first + session},
        {"type": "ui.turn", "conversation": "c1", "turn": 2, "send": "sent", "settled": True,
         "new_rows": second, "rendered": second + first + session},
    ]

    report = driver.join_report(tanda, probe, [], None)

    assert report[0]["response"] == "Hola."
    # En orden de llegada, no en el de la ventana.
    assert report[1]["response"] == "Un momento.\nSon las diez."
    assert report[1]["session_reset"] is True


def test_failed_session_reset_marks_its_conversation() -> None:
    # Contracaso: una sesión nueva sin 2xx deja la conversación sobre el
    # contexto anterior; el informe lo dice en vez de puntuarla limpia.
    driver = _driver()
    probe = [
        {"type": "ui.session.new", "conversation": "c1", "status": "200"},
        _probe_turn("c1", 1, "sube el volumen", "Listo."),
        {"type": "ui.session.new", "conversation": "c2", "status": "409", "reset": False},
        _probe_turn("c2", 1, "hola", "", send="session_not_reset", settled=False),
    ]

    report = driver.join_report(TANDA, probe, [], None)
    markdown = driver.render_markdown(report, "Tanda prueba")

    assert report[0]["session_reset"] is True
    assert report[2]["session_reset"] is False
    assert report[2]["session_status"] == "409"
    assert "(sin respuesta: session_not_reset) (sesión no reiniciada: 409)" in markdown
    assert "en sesión no reiniciada: 1" in markdown


def test_log_reply_without_a_visible_one_is_marked_not_shown_as_seen() -> None:
    # Contracaso: la medición es la ventana. Si no mostró nada, la respuesta
    # del registro aparece marcada y se cuenta aparte.
    driver = _driver()
    probe = [_probe_turn("c2", 1, "hola", "")]
    log = [
        {"utc": "2026-10-07T10:00:10Z", "role": "user", "text": "hola"},
        {"utc": "2026-10-07T10:00:11Z", "role": "assistant", "text": "Hola.", "latency_ms": 700},
    ]

    report = driver.join_report(TANDA, probe, log, None)
    markdown = driver.render_markdown(report, "Tanda prueba")

    assert report[2]["response"] == ""
    assert report[2]["response_log"] == "Hola."
    assert "(no visible; registro: Hola.)" in markdown
    assert "Sin respuesta visible pero con registro: 1" in markdown


def test_turn_the_log_never_received_keeps_no_latency() -> None:
    # Contracaso: si la ventana rechazó un turno, el siguiente no le cede la suya.
    driver = _driver()
    probe = [
        _probe_turn("c1", 1, "sube el volumen", "", send="input_disabled", settled=False),
        _probe_turn("c1", 3, "un poco más", "Subido."),
    ]
    log = [
        {"utc": "2026-10-07T10:00:05Z", "role": "user", "text": "un poco más"},
        {"utc": "2026-10-07T10:00:06Z", "role": "assistant", "text": "Subido.", "latency_ms": 800},
    ]

    report = driver.join_report(TANDA, probe, log, None)

    assert report[0]["latency_ms"] is None
    assert report[0]["send"] == "input_disabled"
    assert report[1]["latency_ms"] == 800
    assert report[2]["send"] == "not_reached"


def test_markdown_table_escapes_cells_and_flags_unsettled_turns() -> None:
    driver = _driver()
    report = driver.join_report(
        TANDA,
        [_probe_turn("c1", 1, "sube el volumen", "a | b\nc", settled=False)],
        [],
        None,
    )

    markdown = driver.render_markdown(report, "Tanda prueba")

    assert "| conversación | turno | texto | respuesta | latencia (ms) | expect |" in markdown
    assert "a \\| b<br>c (sin asentarse: sent)" in markdown
    assert "(sin respuesta: not_reached)" in markdown
    assert "Turnos: 3 · asentados: 0 · con latencia: 0" in markdown


def test_hung_view_is_marked_and_the_next_turn_still_reported() -> None:
    # Encargo PH (n3 t4): la vista dejó de devolver lecturas tras un turno; la
    # sonda marca ese turno colgado y sigue. El informe lo dice; un turno
    # normal sin asentarse no se marca colgado (contracaso).
    driver = _driver()
    hung = _probe_turn("c1", 1, "sube el volumen", "", settled=False)
    hung["hung"] = True
    probe = [hung, _probe_turn("c1", 3, "un poco más", "Subido.", settled=False)]

    report = driver.join_report(TANDA, probe, [], None)
    markdown = driver.render_markdown(report, "Tanda prueba")

    assert report[0]["hung"] is True
    assert report[1]["hung"] is False
    assert "(sin respuesta: sent) (vista colgada)" in markdown
    assert "Subido. (sin asentarse: sent) |" in markdown


def test_cli_writes_both_result_files(tmp_path: Path) -> None:
    driver = _driver()
    tanda = tmp_path / "t.json"
    tanda.write_text(json.dumps(TANDA, ensure_ascii=False), encoding="utf-8")
    probe = tmp_path / "ui-probe.jsonl"
    probe.write_text(json.dumps(_probe_turn("c2", 1, "hola", "Hola.")) + "\n", encoding="utf-8")
    log = tmp_path / "conversation.v1.jsonl"
    log.write_text("", encoding="utf-8")

    assert driver._main(["convert", str(tanda), str(tmp_path / "turnos.jsonl")]) == 0
    assert driver._main(["report", str(tanda), str(probe), str(log), "-", str(tmp_path)]) == 0

    rows = [json.loads(line) for line in (tmp_path / "tanda_resultado.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert rows[2]["response"] == "Hola."
    assert (tmp_path / "tanda_resultado.md").read_bytes().count(b"\r") == 0


def test_launcher_profile_and_probe_instrumentation() -> None:
    launcher = RUN_BAXY.read_text(encoding="utf-8")
    harness = TANDA_PS1.read_text(encoding="utf-8")

    # Sin -Profile sigue el perfil de siempre.
    assert 'Join-Path $env:LOCALAPPDATA "BAXY\\dev-mente-v2"' in launcher
    assert "[string]$Profile" in launcher
    assert '$env:BAXY_VOICE_WAKE_ON_START = "0"' in launcher
    for variable in (
        "BAXY_APP_TRACE",
        "BAXY_MIND_MODEL_CALL_AUDIT_PATH",
        "BAXY_MIND_RAW_REPLY_AUDIT_PATH",
        "BAXY_MIND_TURN_AUDIT_PATH",
        "BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH",
    ):
        assert f"$env:{variable} = Join-Path $evidence" in launcher
    # Una sonda con BAXY abierta saldría con 0 sin escribir: se corta antes.
    assert "exit 3" in launcher
    # Una sonda colgada no deja esperando para siempre: tope y cierre por PID.
    assert "$probe.WaitForExit()" not in launcher
    assert "$probe.WaitForExit([int]$budgetMs)" in launcher
    assert "taskkill.exe /PID $probe.Id /T /F" in launcher
    assert "exit 7" in launcher
    # La tanda nunca usa el perfil vivo del dueño.
    assert "[string]$Profile = 'uso-real-v3'" in harness
    assert "dev-mente-v2 es el perfil vivo" in harness
    assert "semantic_replay_state.ps1" in harness
    assert "finally" in harness
    # Lo que la tanda abrió se cierra con el libro (foto antes del arranque, cierre en el finally).
    assert harness.index("-Foto -Libro $fotoTanda") < harness.index("(Join-Path $scripts 'run_baxy.ps1')")
    assert harness.index("-Cerrar -Libro $fotoTanda") > harness.index("finally")
    assert "[switch]$SinCierre" in harness


def test_last_turn_of_a_conversation_does_not_take_the_next_greeting() -> None:
    # Medido en t1-base: tras el último turno de una conversación, el registro
    # anota el saludo de la sesión nueva con el mismo número de turno; su
    # latencia se tomaba como la del turno.
    driver = _driver()
    probe = [
        {"type": "ui.session.new", "conversation": "c1", "requested_utc": "2026-10-07T09:59:58Z"},
        _probe_turn("c1", 1, "sube el volumen", "Listo, 60 %."),
        _probe_turn("c1", 3, "un poco más", "Subido a 70 %."),
        {"type": "ui.session.new", "conversation": "c2", "requested_utc": "2026-10-07T10:00:09.5Z"},
        _probe_turn("c2", 1, "hola", "Hola."),
    ]
    log = [
        {"utc": "2026-10-07T10:00:00Z", "role": "user", "text": "sube el volumen"},
        {"utc": "2026-10-07T10:00:02Z", "role": "assistant", "text": "Listo, 60 %.", "latency_ms": 2000},
        {"utc": "2026-10-07T10:00:05Z", "role": "user", "text": "un poco más"},
        {"utc": "2026-10-07T10:00:06Z", "role": "assistant", "text": "Subiendo…", "latency_ms": 900},
        {"utc": "2026-10-07T10:00:08Z", "role": "assistant", "text": "Subido a 70 %.", "latency_ms": 3100},
        {"utc": "2026-10-07T10:00:12Z", "role": "assistant", "text": "Hola, soy BAXY.", "latency_ms": 9000,
         "route": "welcome"},
        {"utc": "2026-10-07T10:00:14Z", "role": "user", "text": "hola"},
        {"utc": "2026-10-07T10:00:15Z", "role": "assistant", "text": "Hola.", "latency_ms": 700},
    ]

    report = driver.join_report(TANDA, probe, log, None)

    assert report[1]["latency_ms"] == 3100
    assert report[1]["response_log"] == "Subiendo…\nSubido a 70 %."
    assert report[1]["reply_wall_ms"] == 3000
    assert report[1]["reply_utc"] == "2026-10-07T10:00:08Z"
    # Contracaso: sin sesión nueva en medio, las respuestas siguen siendo del turno.
    assert report[0]["latency_ms"] == 2000
    assert report[2]["latency_ms"] == 700


def test_without_session_times_every_reply_stays_with_its_turn() -> None:
    # Contracaso: una captura vieja sin requested_utc no pierde respuestas.
    driver = _driver()
    probe = [{"type": "ui.session.new", "conversation": "c2"}, _probe_turn("c2", 1, "hola", "Hola.")]
    log = [
        {"utc": "2026-10-07T10:00:10Z", "role": "user", "text": "hola"},
        {"utc": "2026-10-07T10:00:11Z", "role": "assistant", "text": "Hola.", "latency_ms": 700},
        {"utc": "2026-10-07T10:00:13Z", "role": "assistant", "text": "Algo más.", "latency_ms": 2500},
    ]

    report = driver.join_report(TANDA, probe, log, None)

    assert report[2]["latency_ms"] == 2500
    assert report[2]["latency_first_ms"] == 700
