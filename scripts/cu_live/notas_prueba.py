"""Test notes of the harness in Sticky Notes' local store (plum.sqlite), written with the app CLOSED.

State notas_sin_cuenta (estado/notas_sin_cuenta.ps1). Pasada r9: Sticky Notes sat on its sign-in screen, so v3-36
(search «dentista») and t-drag-3 (drag the note «baxy prueba») had no note to work on. The app works without an
account (its onboarding can be skipped); the notes those cases need are written here.

Each harness note has a FIXED id (uuid5 of its text): it is recognised as the harness's, rewritten in place, and never
duplicated. A note of anybody else is never touched. --abierta opens it (IsOpen=1) at the centre of a WxH screen,
400x400 like a new note; --cerrar-demas closes every other open harness note; --cerrar-vacias closes (never deletes)
open notes with no text and nothing else in them (an image or ink is content). --quitar <texto> removes the note an
earlier run of a case left (v3-34 «llamar al dentista el martes», v3-35 «pagar la luz»): Sticky Notes reopens the
notes left open, and the judge saw the earlier attempt's note (revision 2026-10-08). Only a note whose whole text is
exactly that (ignoring case, blanks and a final period), with no image or ink. Prints one JSON line.

Nothing is written while the store holds an account (a SyncState row or a note with a RemoteId): harness notes would
sync to the owner's account (resultado «con_cuenta», verificado false).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import uuid

NS = uuid.UUID("6d1f3a52-5b1e-4f0e-9a51-0b4a2f6c7e01")
TICKS_EPOCH = 621355968000000000  # .NET ticks at 1970-01-01


def note_id(text: str) -> str:
    return str(uuid.uuid5(NS, "nota:" + text))


def paragraph(text: str) -> str:
    # Sticky Notes keeps each paragraph as «\id=<guid> <text>».
    return "\\id=" + str(uuid.uuid5(NS, "parrafo:" + text)) + " " + text


def is_empty(text: str | None) -> bool:
    # Only paragraph ids («\id=<guid>») and blanks: a note with nothing written in it.
    return re.sub(r"\\id=[0-9a-fA-F-]{36}", "", text or "").strip() == ""


def plain(text: str | None) -> str:
    # The note's words, for --quitar: paragraph ids out, blanks collapsed, case and a final period ignored.
    t = re.sub(r"\\id=[0-9a-fA-F-]{36}", " ", text or "")
    return re.sub(r"\s+", " ", t).strip().rstrip(".").strip().casefold()


def has_table(cur: sqlite3.Cursor, name: str) -> bool:
    return cur.execute("select 1 from sqlite_master where type='table' and name=?", (name,)).fetchone() is not None


def has_account(cur: sqlite3.Cursor) -> bool:
    # Sticky Notes signed in keeps a SyncState row and a RemoteId on each synced note.
    if has_table(cur, "SyncState") and cur.execute("select count(*) from SyncState").fetchone()[0]:
        return True
    return bool(cur.execute("select count(*) from Note where RemoteId is not null and RemoteId != ''").fetchone()[0])


def has_content(cur: sqlite3.Cursor, nid: str) -> bool:
    # An image (Media) or ink (Stroke) of the note: content even when its text is empty.
    for table in ("Media", "Stroke"):
        if has_table(cur, table) and cur.execute(
                f'select count(*) from "{table}" where ParentId=? and DeletedAt is null', (nid,)).fetchone()[0]:
            return True
    return False


def position(screen_w: int, screen_h: int, device: str | None) -> str:
    x, y = max(0, screen_w // 2 - 200), max(0, screen_h // 2 - 200)
    pos = f"Position={x},{y};Size=400,400"
    return (f"ManagedPosition=DeviceId:{device};" + pos) if device else pos


def ensure(db: str, texts: list[str], open_text: str | None, screen: tuple[int, int], close_others: bool,
           close_empty: bool = False, remove: list[str] | None = None) -> dict:
    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        if has_account(cur):
            return {"resultado": "con_cuenta", "verificado": False, "hechos": []}
        parent = cur.execute('select Id from "User" limit 1').fetchone()
        if parent is None:
            return {"resultado": "sin_usuario"}
        device = None
        for (wp,) in cur.execute('select WindowPosition from Note where WindowPosition like "ManagedPosition=DeviceId:%"'):
            device = wp.split(";", 1)[0][len("ManagedPosition=DeviceId:"):]
            break
        now = int(time.time() * 10_000_000) + TICKS_EPOCH
        mine = {note_id(t) for t in texts}
        hechos = []
        for t in texts:
            nid = note_id(t)
            is_open = 1 if t == open_text else 0
            row = cur.execute("select Text, IsOpen, DeletedAt from Note where Id=?", (nid,)).fetchone()
            wp = position(screen[0], screen[1], device)
            if row is None:
                cur.execute('insert into Note (Text, WindowPosition, IsOpen, IsAlwaysOnTop, Theme, IsFutureNote, '
                            'PendingInsightsScan, Id, ParentId, CreatedAt, UpdatedAt) values (?,?,?,0,"Yellow",0,0,?,?,?,?)',
                            (paragraph(t), wp, is_open, nid, parent[0], now, now))
                hechos.append("creada:" + t)
            elif row[0] != paragraph(t) or row[1] != is_open or row[2] is not None or is_open:
                cur.execute("update Note set Text=?, IsOpen=?, DeletedAt=NULL, WindowPosition=?, UpdatedAt=? where Id=?",
                            (paragraph(t), is_open, wp, now, nid))
                hechos.append("rehecha:" + t)
        if close_others:
            # Only the harness's own notes are ever closed: an open note of anybody else stays as it is.
            keep = note_id(open_text) if open_text else None
            ids = [r[0] for r in cur.execute("select Id from Note where IsOpen=1").fetchall() if r[0] in mine and r[0] != keep]
            for nid in ids:
                cur.execute("update Note set IsOpen=0 where Id=?", (nid,))
        if close_empty:
            # An EMPTY open note (an earlier case's «crea una nota» that never got its text) holds no data: closed,
            # never deleted, so it does not sit over the case.
            for nid, text in cur.execute("select Id, Text from Note where IsOpen=1 and DeletedAt is null").fetchall():
                if not is_empty(text) or has_content(cur, nid):
                    continue
                cur.execute("update Note set IsOpen=0 where Id=?", (nid,))
                hechos.append("vacia_cerrada")
        quitar = {plain(t) for t in (remove or []) if plain(t)}
        if quitar:
            for nid, text in cur.execute("select Id, Text from Note").fetchall():
                if nid in mine or plain(text) not in quitar or has_content(cur, nid):
                    continue
                cur.execute("delete from Note where Id=?", (nid,))
                hechos.append("quitada:" + plain(text))
        con.commit()
        leidas = {r[0]: r for r in cur.execute("select Id, Text, IsOpen, DeletedAt from Note")}
        ok = all(note_id(t) in leidas and leidas[note_id(t)][1] == paragraph(t) and leidas[note_id(t)][3] is None
                 for t in texts)
        if open_text:
            ok = ok and leidas[note_id(open_text)][2] == 1
        if quitar:
            ok = ok and not any(plain(r[1]) in quitar for nid, r in leidas.items() if nid not in mine
                                and not has_content(cur, nid))
        return {"resultado": "ok" if not hechos else "corregido", "verificado": ok, "hechos": hechos}
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--texto", action="append", default=[])
    ap.add_argument("--abierta")
    ap.add_argument("--pantalla", default="1920x1080")
    ap.add_argument("--cerrar-demas", action="store_true")
    ap.add_argument("--cerrar-vacias", action="store_true")
    ap.add_argument("--quitar", action="append", default=[])
    a = ap.parse_args()
    w, h = (int(x) for x in a.pantalla.lower().split("x"))
    texts = list(dict.fromkeys(a.texto + ([a.abierta] if a.abierta else [])))
    print(json.dumps(ensure(a.db, texts, a.abierta, (w, h), a.cerrar_demas, a.cerrar_vacias,
                            a.quitar), ensure_ascii=False))


if __name__ == "__main__":
    main()
