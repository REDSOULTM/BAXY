"""A chat read from the lines its window draws (encargo IMP4), for a client whose accessible tree holds no message text.

imp3 imp-wa-leer: the open WhatsApp chat exposes only «Enviado», «Tú:» and dates to UI Automation, and «lo último que me
escribieron» could not be answered. The App reads the window's own drawing once, with each line's box in fractions of the
window (``chatLines``), for an application whose data declare where it draws its conversation (app_places.v1.json
«conversation»: the region, the band where dates sit centred, and the edge the person's own bubbles reach). Here those
lines become bubbles: in the region, a centred line is the client's own (a date, «Hoy»), a line that starts right of the
centre or ends at the own edge is the person's, any other is someone else's. A bubble is its lines, one right under the
other, closed by the time drawn under or beside its last line (a line that is only a time, with the read marks the client
draws after it). Encargo WR: text with no time of its own (a separator «Ayer», a button «Enviar documento», a tooltip,
the chat list's column on a narrow window) is no message, and two readings of one box («2311», «23:11») are one line.
Encargo WA-LEER: the lines arrive whole (every place a text is read, all of them past the facts' list bound), so a time
closes only the bubble it is drawn in or beside. No application is named here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# «19:14», «4:35 u» (the read marks read as a letter or two), «12:40 p. m.».
_TIME = re.compile(r"^(?P<time>\d{1,2}:\d{2}(?:\s*[ap]\.?\s?m\.?)?)(?:\s+\S{1,2})?$", re.IGNORECASE)
_OWN, _OTHER, _CLIENT = "own", "other", "client"


@dataclass(frozen=True)
class Bubble:
    side: str
    texts: tuple[str, ...]
    time: str


@dataclass(frozen=True)
class LastWritten:
    """The last bubble not the person's own: its text, its time and its author (a group's bubble names who wrote it on
    its first line; "" otherwise)."""

    text: str
    time: str
    author: str


@dataclass(frozen=True)
class _Line:
    top: float
    bottom: float
    left: float
    right: float
    side: str
    text: str


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _placed(line: object, region: dict) -> _Line | None:
    """The line with its box and side when it lies inside the region; None outside it or without a box."""

    if not isinstance(line, dict):
        return None
    x, y, w, h = (_number(line.get(key)) for key in ("x", "y", "w", "h"))
    if x is None or y is None or w is None or h is None:
        return None
    left, right = float(region["left"]), float(region["right"])
    if not (left <= x and x + w <= right + 0.01 and float(region["top"]) <= y and y + h <= float(region["bottom"])):
        return None
    centre = (left + right) / 2
    if abs(x + w / 2 - centre) <= float(region["centerBand"]):
        side = _CLIENT
    elif x >= centre or x + w >= float(region["ownEdge"]):
        side = _OWN
    else:
        side = _OTHER
    return _Line(y, y + h, x, x + w, side, " ".join(str(line.get("text") or "").split()))


def _one_reading(lines: list[_Line]) -> list[_Line]:
    """Encargo WR (wab2: «2311» and «23:11» read from one box made a bubble «2311» timed 23:11): lines on the same box
    are one line read twice; the reading that is a time is kept, else the first."""

    kept: list[_Line] = []
    for line in lines:
        twin = next((
            index for index, other in enumerate(kept)
            if abs(other.top - line.top) <= (line.bottom - line.top) / 2
            and min(other.right, line.right) - max(other.left, line.left)
            >= min(other.right - other.left, line.right - line.left) / 2), None)
        if twin is None:
            kept.append(line)
        elif _TIME.match(line.text) and not _TIME.match(kept[twin].text):
            kept[twin] = line
    return kept


def bubbles(lines: object, region: dict) -> list[Bubble]:
    """The bubbles the lines draw inside the region, top to bottom, each closed by its time."""

    placed = sorted(
        (found for line in (lines if isinstance(lines, list) else ()) if (found := _placed(line, region)) is not None),
        key=lambda line: line.top)
    found: list[Bubble] = []
    # Encargo WA-LEER: the bubbles still open, each where it is drawn. Read whole, the lines of the chat list's column
    # (a date «Ayer» at x 0.30 on a narrow window) fall between a bubble's text and its time; each line goes on the open
    # bubble it is drawn in, so a line of the list neither joins a bubble nor parts one from its time.
    runs: list[list[_Line]] = []
    for line in _one_reading(placed):
        timed = _TIME.match(line.text)
        if not line.text or line.side == _CLIENT and timed is None:
            runs = []
            continue
        # A line goes on a bubble above when it is no further under its last line than a line's height and lies across
        # it: a text on the same side, the time at the bubble's end (a long bubble of someone else's ends with its time
        # past the centre, even in the band where dates sit: a date is never a bare time), starting within the bubble
        # or right after its widest line, closer than the time is wide.
        runs = [run for run in runs if line.top - run[-1].bottom <= max(
            run[-1].bottom - run[-1].top, line.bottom - line.top)]
        reach = line.right - line.left if timed is not None else 0.0
        open_ = next((
            run for run in reversed(runs)
            if line.left <= max(part.right for part in run) + reach and line.right >= min(part.left for part in run)
            and (timed is not None or line.side == run[-1].side)), None)
        if timed is not None:
            if open_ is not None:
                found.append(Bubble(open_[0].side, tuple(part.text for part in open_), timed.group("time")))
                runs.remove(open_)
            continue
        if open_ is None:
            runs.append([line])
        else:
            open_.append(line)
    return found


def last_written(lines: object, region: dict) -> LastWritten | str | None:
    """The last bubble not the person's own (``LastWritten``); "own" when every bubble read is the person's; None when
    no bubble was read (nothing reliable to say)."""

    read = bubbles(lines, region)
    others = [bubble for bubble in read if bubble.side == _OTHER]
    if others:
        last = others[-1]
        # A group's bubble may name its author on its first line; a wrapped message does too in shape, so the first line
        # is only offered as the author (the answer names it only when it is who the question asked about).
        return LastWritten(" ".join(last.texts), last.time, last.texts[0] if len(last.texts) > 1 else "")
    return _OWN if read else None
