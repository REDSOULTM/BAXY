"""Study domain tool (flashcards + SM-2 spaced repetition) — extracted from
domain_tools.py (R2 sprint 2026-05-28).

Flashcards locales, persistencia SQLite en <state_dir>/study.sqlite. Algoritmo
SM-2 (Wozniak 1990) por carta — el clásico de spaced-repetition. NO cloud, NO
sync — todo local.

Funciones extraídas (12):
  study_tool                     (entry, 10 acciones)
  _study_connect                 (init schema decks + cards)
  _today_iso                     (helper de fecha)
  _study_deck_create / _list / _delete
  _study_card_add / _list / _delete
  _study_due                     (cartas vencidas hoy)
  _study_review                  (aplica SM-2 sobre grade 0..5)
  _study_stats

Helpers compartidos: solo _ok/_err desde _shared. AgentState para state.path.
Auto-contenido (sqlite3, time, uuid, datetime; nada de domain_tools)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..tool_result import ToolResult
from ..state import AgentState


__all__ = [
    "study_tool",
    "_study_connect",
    "_today_iso",
    "_study_deck_create",
    "_study_deck_list",
    "_study_deck_delete",
    "_study_card_add",
    "_study_card_list",
    "_study_card_delete",
    "_study_due",
    "_study_review",
    "_study_stats",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def study_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local flashcards + SM-2 spaced repetition.

    Actions: status, deck_create, deck_list, deck_delete, card_add,
    card_list, card_delete, due, review (grade card with q in 0..5), stats.
    Storage: SQLite at <state_dir>/study.sqlite. SM-2 per Wozniak 1990.
    """
    action = str(args.get("action") or "status").casefold()
    db_path = state.path.parent / "study.sqlite"
    conn = _study_connect(db_path)
    try:
        if action == "status":
            cur = conn.cursor()
            decks = cur.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
            cards = cur.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            due_today = cur.execute("SELECT COUNT(*) FROM cards WHERE due_at <= ?", (_today_iso(),)).fetchone()[0]
            return _ok_tr(db=str(db_path), decks=decks, cards=cards, due_today=due_today, algorithm="SM-2 (Wozniak 1990)")
        if action == "deck_create":
            return _study_deck_create(conn, args)
        if action == "deck_list":
            return _study_deck_list(conn)
        if action == "deck_delete":
            return _study_deck_delete(conn, args)
        if action == "card_add":
            return _study_card_add(conn, args)
        if action == "card_list":
            return _study_card_list(conn, args)
        if action == "card_delete":
            return _study_card_delete(conn, args)
        if action == "due":
            return _study_due(conn, args)
        if action == "review":
            return _study_review(conn, args)
        if action == "stats":
            return _study_stats(conn, args)
        return _err_tr(
            "unknown study action", action=action,
            valid_actions=[
                "status", "deck_create", "deck_list", "deck_delete",
                "card_add", "card_list", "card_review", "card_delete",
                "due_cards", "stats",
            ],
            status="needs_user",
        )
    finally:
        conn.close()


def _study_connect(db_path: Path):
    import sqlite3
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS decks (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            deck_id TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            ef REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetitions INTEGER NOT NULL DEFAULT 0,
            due_at TEXT NOT NULL,
            last_reviewed_at TEXT,
            last_grade INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )"""
    )
    conn.commit()
    return conn


def _today_iso() -> str:
    return time.strftime("%Y-%m-%d")


def _study_deck_create(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err_tr("missing deck name")
    import uuid
    deck_id = f"deck_{uuid.uuid4().hex[:10]}"
    conn.execute("INSERT INTO decks(id, name, created_at) VALUES (?, ?, ?)", (deck_id, name, _today_iso()))
    conn.commit()
    return _ok_tr(deck_id=deck_id, name=name)


def _study_deck_list(conn: Any) -> dict[str, Any]:
    rows = conn.execute("SELECT id, name, created_at FROM decks ORDER BY created_at DESC").fetchall()
    decks = []
    for row in rows:
        card_count = conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ?", (row["id"],)).fetchone()[0]
        due_count = conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND due_at <= ?", (row["id"], _today_iso())).fetchone()[0]
        decks.append({"deck_id": row["id"], "name": row["name"], "created_at": row["created_at"], "cards": card_count, "due_today": due_count})
    return _ok_tr(decks=decks, count=len(decks))


def _study_deck_delete(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or args.get("id") or "").strip()
    if not deck_id:
        return _err_tr("missing deck_id")
    conn.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    cur = conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
    return _ok_tr(deck_id=deck_id, deleted=cur.rowcount)


def _study_card_add(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    front = str(args.get("front") or args.get("question") or "").strip()
    back = str(args.get("back") or args.get("answer") or "").strip()
    if not deck_id or not front or not back:
        return _err_tr("card_add requires deck_id, front, back")
    if not conn.execute("SELECT id FROM decks WHERE id = ?", (deck_id,)).fetchone():
        return _err_tr("deck not found", deck_id=deck_id)
    import uuid
    card_id = f"card_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO cards(id, deck_id, front, back, ef, interval_days, repetitions, due_at, created_at) VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)",
        (card_id, deck_id, front, back, _today_iso(), _today_iso()),
    )
    conn.commit()
    return _ok_tr(card_id=card_id, deck_id=deck_id, front=front, back=back, due_at=_today_iso())


def _study_card_list(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    if deck_id:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at, last_grade FROM cards WHERE deck_id = ? ORDER BY due_at", (deck_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at, last_grade FROM cards ORDER BY due_at LIMIT 500").fetchall()
    cards = [dict(row) for row in rows]
    return _ok_tr(cards=cards, count=len(cards))


def _study_card_delete(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    card_id = str(args.get("card_id") or args.get("id") or "").strip()
    if not card_id:
        return _err_tr("missing card_id")
    cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    return _ok_tr(card_id=card_id, deleted=cur.rowcount)


def _study_due(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    limit = int(args.get("limit", 20))
    if deck_id:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at FROM cards WHERE deck_id = ? AND due_at <= ? ORDER BY due_at LIMIT ?", (deck_id, _today_iso(), limit)).fetchall()
    else:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at FROM cards WHERE due_at <= ? ORDER BY due_at LIMIT ?", (_today_iso(), limit)).fetchall()
    return _ok_tr(due_cards=[dict(row) for row in rows], count=len(rows), today=_today_iso())


def _study_review(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Apply SM-2 to a single card's grade q in 0..5."""
    card_id = str(args.get("card_id") or args.get("id") or "").strip()
    q = args.get("q") if args.get("q") is not None else args.get("grade")
    if not card_id or q is None:
        return _err_tr("review requires card_id and q (0..5)")
    try:
        q = int(q)
    except (TypeError, ValueError):
        return _err_tr("q must be an integer 0..5")
    if not (0 <= q <= 5):
        return _err_tr("q out of range; must be 0..5")
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        return _err_tr("card not found", card_id=card_id)
    ef = float(row["ef"])
    interval = int(row["interval_days"])
    repetitions = int(row["repetitions"])
    # SM-2 EF update happens regardless of q (per Wozniak 1990).
    ef = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ef))
        repetitions += 1
    from datetime import datetime as _dt, timedelta as _td
    due_at = (_dt.today() + _td(days=interval)).strftime("%Y-%m-%d")
    conn.execute(
        "UPDATE cards SET ef = ?, interval_days = ?, repetitions = ?, due_at = ?, last_reviewed_at = ?, last_grade = ? WHERE id = ?",
        (ef, interval, repetitions, due_at, _today_iso(), q, card_id),
    )
    conn.commit()
    return _ok_tr(card_id=card_id, q=q, ef=round(ef, 4), interval_days=interval, repetitions=repetitions, due_at=due_at)


def _study_stats(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    where_clause = "WHERE deck_id = ?" if deck_id else ""
    params: tuple[Any, ...] = (deck_id,) if deck_id else tuple()
    total = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause}", params).fetchone()[0]
    due_today = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause + (' AND ' if where_clause else 'WHERE ')}due_at <= ?", (*params, _today_iso())).fetchone()[0]
    avg_ef = conn.execute(f"SELECT AVG(ef) FROM cards {where_clause}", params).fetchone()[0] or 2.5
    new_cards = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause + (' AND ' if where_clause else 'WHERE ')}repetitions = 0", params).fetchone()[0]
    return _ok_tr(deck_id=deck_id or None, total=total, due_today=due_today, new=new_cards, avg_ef=round(float(avg_ef), 4))
