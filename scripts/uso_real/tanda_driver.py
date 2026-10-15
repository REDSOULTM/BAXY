"""Tandas de uso real en la ventana oficial: convertir y unir el informe.

La sonda de la ventana (``FieldUiProbe``) lee un JSONL de turnos y escribe lo
que la ventana muestra; el registro del perfil (``conversation.v1.jsonl``)
guarda la latencia de cada respuesta. Este módulo hace las dos puntas que
faltaban, sin lanzar nada:

``convert <tanda.json> <turnos.jsonl>``
    Una tanda ``{"conversations":[{"id","speaker","turns":[{"text","expect"}]}]}``
    pasa a líneas de la sonda: ``{"cmd":"session.new"}`` antes de cada
    conversación y ``{"text","conversation","turn"}`` por turno.

``report <tanda.json> <ui-probe.jsonl> <conversation.v1.jsonl> <desde_utc> <carpeta>``
    Une por turno la respuesta que se vio, la del registro y su latencia, y
    escribe ``tanda_resultado.jsonl`` y ``tanda_resultado.md`` listos para
    puntuar con el ``expect`` de cada turno.

``scripts/uso_real/tanda.ps1`` es quien lo llama alrededor del arranque.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BAXY_SOURCE = "BAXY"
RESULT_JSONL = "tanda_resultado.jsonl"
RESULT_MARKDOWN = "tanda_resultado.md"


def load_tanda(path: Path) -> dict[str, Any]:
    tanda = json.loads(path.read_text(encoding="utf-8-sig"))
    conversations = tanda.get("conversations") if isinstance(tanda, dict) else None
    if not isinstance(conversations, list) or not conversations:
        raise ValueError(f"tanda sin conversations: {path}")
    for conversation in conversations:
        if not isinstance(conversation, dict) or not conversation.get("id"):
            raise ValueError(f"conversación sin id en {path}")
        if not isinstance(conversation.get("turns"), list):
            raise ValueError(f"conversación {conversation.get('id')} sin turns en {path}")
    return tanda


def probe_lines(tanda: dict[str, Any]) -> list[dict[str, Any]]:
    """Líneas de la sonda: sesión nueva antes de cada conversación."""
    lines: list[dict[str, Any]] = []
    for conversation in tanda["conversations"]:
        conversation_id = str(conversation["id"])
        lines.append({"cmd": "session.new", "conversation": conversation_id})
        for number, turn in enumerate(conversation["turns"], start=1):
            text = str(turn.get("text") or "").strip()
            if not text:
                continue
            lines.append({"text": text, "conversation": conversation_id, "turn": number})
    return lines


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _utc(value: str | None) -> datetime | None:
    if not value or value.strip() in {"", "-"}:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # .NET escribe siete decimales; fromisoformat admite hasta seis.
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _same_text(left: str, right: str) -> bool:
    return " ".join(left.split()) == " ".join(right.split())


def conversation_exchanges(
    rows: Iterable[dict[str, Any]], since: datetime | None
) -> list[dict[str, Any]]:
    """Cada mensaje del usuario con las respuestas que lo siguen en el registro."""
    exchanges: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in rows:
        stamp = _utc(row.get("utc"))
        if since is not None and (stamp is None or stamp < since):
            continue
        if row.get("role") == "user":
            current = {"text": str(row.get("text") or ""), "utc": row.get("utc"), "replies": []}
            exchanges.append(current)
        elif row.get("role") == "assistant" and current is not None:
            current["replies"].append(row)
    return exchanges


def session_boundaries(probe_rows: Iterable[dict[str, Any]]) -> list[datetime]:
    """Horas en que la sonda pidió una sesión nueva, en orden.

    Lo que el registro anota después de una de ellas (el saludo de la sesión
    nueva) ya no es respuesta del turno anterior.
    """
    stamps = [
        _utc(row.get("requested_utc"))
        for row in probe_rows
        if row.get("type") == "ui.session.new"
    ]
    return sorted(stamp for stamp in stamps if stamp is not None)


def replies_of_turn(exchange: dict[str, Any], boundaries: list[datetime]) -> list[dict[str, Any]]:
    """Las respuestas del turno: las anteriores a la siguiente sesión nueva.

    Sin la hora del usuario o sin límites conocidos se quedan todas.
    """
    replies = list(exchange.get("replies") or [])
    asked = _utc(exchange.get("utc"))
    if asked is None:
        return replies
    limit = next((stamp for stamp in boundaries if stamp > asked), None)
    if limit is None:
        return replies
    return [reply for reply in replies if (_utc(reply.get("utc")) or asked) < limit]


def _wall_ms(start: Any, end: Any) -> int | None:
    begin, finish = _utc(start), _utc(end)
    if begin is None or finish is None or finish < begin:
        return None
    return int((finish - begin).total_seconds() * 1000)


def _visible_reply(turn: dict[str, Any]) -> str:
    """Lo que BAXY mostró en este turno, en orden de llegada.

    La ventana pinta la lista con la más nueva primero y la sonda guarda
    ``new_rows`` en ese mismo orden (el prefijo nuevo de ``rendered``).
    """
    rows = list(reversed(turn.get("new_rows") or []))
    return "\n".join(
        str(row.get("msg") or "").strip()
        for row in rows
        if isinstance(row, dict) and row.get("src") == BAXY_SOURCE and str(row.get("msg") or "").strip()
    )


def join_report(
    tanda: dict[str, Any],
    probe_rows: list[dict[str, Any]],
    log_rows: list[dict[str, Any]],
    since: datetime | None,
) -> list[dict[str, Any]]:
    """Una fila por turno de la tanda, en su orden, aunque la sonda no llegara."""
    probe_turns = {
        (str(row.get("conversation")), int(row.get("turn"))): row
        for row in probe_rows
        if row.get("type") == "ui.turn" and row.get("conversation") is not None and row.get("turn") is not None
    }
    # La última sesión nueva pedida para cada conversación: si no devolvió
    # 2xx, la conversación corrió (o no corrió) sobre el contexto anterior.
    sessions = {
        str(row.get("conversation")): row
        for row in probe_rows
        if row.get("type") == "ui.session.new" and row.get("conversation") is not None
    }
    exchanges = conversation_exchanges(log_rows, since)
    boundaries = session_boundaries(probe_rows)
    cursor = 0
    report: list[dict[str, Any]] = []
    for conversation in tanda["conversations"]:
        conversation_id = str(conversation["id"])
        session = sessions.get(conversation_id)
        session_reset = _session_reset(session) if session is not None else None
        for number, turn in enumerate(conversation["turns"], start=1):
            text = str(turn.get("text") or "").strip()
            if not text:
                continue
            probe = probe_turns.get((conversation_id, number))
            exchange = None
            if probe is not None and probe.get("send") == "sent":
                # Por orden y por texto: un turno que el registro no recibió
                # (rechazado, sin admisión) no se queda con la latencia del siguiente.
                for index in range(cursor, len(exchanges)):
                    if _same_text(exchanges[index]["text"], text):
                        exchange = exchanges[index]
                        cursor = index + 1
                        break
            # El último turno de una conversación no se queda con el saludo de
            # la siguiente: el registro lo anota con el mismo número de turno.
            replies = replies_of_turn(exchange, boundaries) if exchange else []
            latencies = [reply.get("latency_ms") for reply in replies if isinstance(reply.get("latency_ms"), int)]
            report.append(
                {
                    "conversation": conversation_id,
                    "speaker": conversation.get("speaker"),
                    "turn": number,
                    "text": text,
                    "expect": turn.get("expect"),
                    "response": _visible_reply(probe) if probe else "",
                    "response_log": "\n".join(str(reply.get("text") or "") for reply in replies),
                    "routes": [reply.get("route") for reply in replies if reply.get("route")],
                    "latency_ms": latencies[-1] if latencies else None,
                    "latency_first_ms": latencies[0] if latencies else None,
                    # Reloj de pared del registro: del mensaje a la última respuesta del turno.
                    "reply_utc": replies[-1].get("utc") if replies else None,
                    "reply_wall_ms": _wall_ms(exchange.get("utc"), replies[-1].get("utc")) if replies else None,
                    "probe_elapsed_ms": probe.get("elapsed_ms") if probe else None,
                    "send": probe.get("send") if probe else "not_reached",
                    "settled": bool(probe.get("settled")) if probe else False,
                    # La vista dejó una lectura sin volver: la sonda siguió con el siguiente.
                    "hung": bool(probe.get("hung")) if probe else False,
                    "window_restored": bool(probe.get("window_restored")) if probe else False,
                    "session_reset": session_reset,
                    "session_status": session.get("status") if session is not None else None,
                    "sent_utc": probe.get("sent_utc") if probe else None,
                }
            )
    return report


def _session_reset(session: dict[str, Any]) -> bool:
    if isinstance(session.get("reset"), bool):
        return session["reset"]
    return bool(re.fullmatch(r"2\d\d", str(session.get("status") or "")))


def _shown_response(row: dict[str, Any]) -> str:
    """La respuesta de la columna: la vista; la del registro, sólo marcada."""
    response = row["response"]
    if not response and row["response_log"]:
        response = f"(no visible; registro: {row['response_log']})"
    if not row["settled"]:
        response = f"{response} (sin asentarse: {row['send']})" if response else f"(sin respuesta: {row['send']})"
    if row.get("hung"):
        response = f"{response} (vista colgada)"
    if row.get("session_reset") is False:
        response = f"{response} (sesión no reiniciada: {row.get('session_status') or '—'})"
    return response


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def render_markdown(report: list[dict[str, Any]], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "| conversación | turno | texto | respuesta | latencia (ms) | expect |",
        "|---|---|---|---|---|---|",
    ]
    for row in report:
        response = _shown_response(row)
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row["conversation"],
                    row["turn"],
                    row["text"],
                    response,
                    row["latency_ms"],
                    row["expect"],
                )
            )
            + " |"
        )
    measured = [row["latency_ms"] for row in report if isinstance(row["latency_ms"], int)]
    settled = sum(1 for row in report if row["settled"])
    log_only = sum(1 for row in report if not row["response"] and row["response_log"])
    not_reset = sum(1 for row in report if row.get("session_reset") is False)
    lines += [
        "",
        f"Turnos: {len(report)} · asentados: {settled} · con latencia: {len(measured)}"
        + (f" · mediana: {sorted(measured)[len(measured) // 2]} ms" if measured else ""),
        f"Sin respuesta visible pero con registro: {log_only} · en sesión no reiniciada: {not_reset}",
        "",
    ]
    return "\n".join(lines)


def _main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "convert":
        tanda = load_tanda(Path(argv[1]))
        lines = probe_lines(tanda)
        write_jsonl(Path(argv[2]), lines)
        print(json.dumps({"lines": len(lines)}))
        return 0
    if len(argv) >= 6 and argv[0] == "report":
        tanda_path = Path(argv[1])
        tanda = load_tanda(tanda_path)
        report = join_report(
            tanda,
            read_jsonl(Path(argv[2])),
            read_jsonl(Path(argv[3])),
            _utc(argv[4]),
        )
        out = Path(argv[5])
        write_jsonl(out / RESULT_JSONL, report)
        (out / RESULT_MARKDOWN).write_text(
            render_markdown(report, f"Tanda {tanda_path.stem}"), encoding="utf-8", newline="\n"
        )
        print(json.dumps({"turns": len(report), "settled": sum(1 for row in report if row["settled"])}))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
