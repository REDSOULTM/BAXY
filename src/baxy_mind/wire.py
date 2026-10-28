"""The name the model sees for each operation of the catalog (its wire name) and the way back, in one place.

A wire name is the operation's id with «.» → «_» (app.open → app_open), except where that name would be a proper prefix
of another name the model is shown (audio_volume ⊂ audio_volume_adjust): choosing the short one then means *closing*
the name where the other goes on writing, and the 4B tends to go on (PC-C72: a level to end at, asked with a lowering verb,
came out as the adjusting tool in 0 of 4 seeds). The short one gets a suffix of its own (audio_volume_set), so the two
names part on a token with content; a suffix that would clash by shape with another name (the same name, a prefix
either way, the same letters but for «_», the same parts in another order) is _2set, _3set... Only the shape of the
names decides this, never what an operation does.
"""
from __future__ import annotations

import itertools
import re
from collections.abc import Iterable

SUFFIX = "_set"


def plain(operation: str) -> str:
    """The wire name an operation had before this module: its id with «.» → «_» (older receipts and histories)."""
    return operation.replace(".", "_")


def operation_of(name: str) -> str:
    """An operation from a name without its catalog at hand: an id is itself, a plain wire name goes back «_» → «.»."""
    return name if "." in name else name.replace("_", ".")


def _shape(name: str) -> tuple[str, tuple[str, ...]]:
    """What two names may not share: the same letters but for «_», or the same parts in another order."""
    return name.replace("_", ""), tuple(sorted(name.split("_")))


def _clashes(name: str, others: Iterable[str]) -> bool:
    shape = _shape(name)
    return any(o.startswith(name) or name.startswith(o) or _shape(o)[0] == shape[0] or _shape(o)[1] == shape[1]
               for o in others)


def _shorts(names: dict[str, str], fixed: tuple[str, ...]) -> list[str]:
    """The operations whose name is a prefix of another name shown (or the same name as another one)."""
    return [op for op, name in names.items()
            if any(o != op and n.startswith(name) for o, n in names.items()) or any(f.startswith(name) for f in fixed)]


class Wires:
    """The wire names of one catalog: ``name(op)`` the one the model sees, ``known(name)`` the way back, which also
    reads the plain name an older catalog gave it (receipts, kept sessions), and ``cite(text)`` a text of the catalog
    with the names it cites as they are shown. ``fixed``: names the model is shown besides the catalog's (ask_user)."""

    def __init__(self, operations: Iterable[str], fixed: Iterable[str] = ()) -> None:
        names = {op: plain(op) for op in dict.fromkeys(str(o) for o in operations)}
        fixed = tuple(fixed)
        # Each round gives every short name a suffix that clashes with no name that stays; a renamed name that is
        # still short is renamed again in the next round, and each round renames, so the names of a catalog settle.
        for _ in range(len(names) + 1):
            shorts = _shorts(names, fixed)
            if not shorts:
                break
            taken = [*fixed, *(n for o, n in names.items() if o not in shorts)]
            for op in shorts:
                names[op] = next(c for k in itertools.count(1)
                                 if not _clashes(c := f"{names[op]}_{k if k > 1 else ''}{SUFFIX[1:]}", taken))
                taken.append(names[op])
        self._names = names
        self._back = {name: op for op, name in names.items()}
        self._old = {plain(op): op for op, name in names.items() if name != plain(op)}
        alternatives = "|".join(map(re.escape, sorted(self._old, key=len, reverse=True)))
        self._cite = re.compile(r"\b(" + alternatives + r")\b") if self._old else None

    def name(self, operation: str) -> str:
        """The wire name of an operation; one this catalog does not have keeps its plain name."""
        return self._names.get(operation) or plain(operation)

    def known(self, name: str) -> str | None:
        """The operation of a wire name of this catalog (or of the plain name an older one gave it), or None."""
        return self._back.get(name) or self._old.get(name)

    def cite(self, text: str) -> str:
        """A text of the catalog (a tool's description) with each plain wire name it cites as the name now shown: a
        whole name only (audio_volume, never inside audio_volume_adjust)."""
        if self._cite is None or not text:
            return text
        return self._cite.sub(lambda hit: self._names[self._old[hit.group(1)]], text)
