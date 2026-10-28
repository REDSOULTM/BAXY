"""The name the model sees for each operation of the catalog (its wire name) and the way back, in one place.

A wire name is the operation's id with «.» → «_» (app.open → app_open), except where that name would be a proper prefix
of another one of the same catalog (audio_volume ⊂ audio_volume_adjust): choosing the short one then means *closing*
the name where the other goes on writing, and the 4B tends to go on (PC-C72: «baja el volumen a 20», a level to end at,
came out as the adjusting tool in 0 of 4 seeds). The short one gets a suffix of its own (audio_volume_set), so the two
names part on a token with content. Only the shape of the names decides this, never what an operation does.
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
    return any(o == name or o.startswith(name + "_") or name.startswith(o + "_") or _shape(o)[0] == shape[0]
               or _shape(o)[1] == shape[1] for o in others)


def _shorts(names: dict[str, str]) -> list[str]:
    values = set(names.values())
    return [op for op, name in names.items() if any(o.startswith(name + "_") for o in values)]


class Wires:
    """The wire names of one catalog: ``name(op)`` the one the model sees, ``operation(name)`` the way back, which also
    reads a name an older catalog gave it (plain), and ``cite(text)`` a text of the catalog with its renamed names."""

    def __init__(self, operations: Iterable[str]) -> None:
        names = {op: plain(op) for op in dict.fromkeys(str(o) for o in operations)}
        # Each round gives every short name the suffix (or, where that meets a name that stays, the next one free:
        # _set2, _set3); a renamed name that is still short is renamed again in the next round.
        for _ in range(len(names) + 1):
            shorts = _shorts(names)
            if not shorts:
                break
            taken = [n for o, n in names.items() if o not in shorts]
            for op in shorts:
                candidate = next(c for k in itertools.count(1)
                                 if not _clashes(c := names[op] + SUFFIX + (str(k) if k > 1 else ""), taken))
                names[op] = candidate
                taken.append(candidate)
        if _shorts(names):
            raise ValueError("wire names: no shape without a proper prefix")
        self._names = names
        self._back = {name: op for op, name in names.items()}
        self._old = {plain(op): op for op, name in names.items() if name != plain(op)}
        self._cite = re.compile(r"\b(" + "|".join(map(re.escape, sorted(self._old, key=len, reverse=True))) + r")\b") \
            if self._old else None

    def name(self, operation: str) -> str:
        """The wire name of an operation; one this catalog does not have keeps its plain name."""
        return self._names.get(operation) or plain(operation)

    def operation(self, name: str) -> str:
        """The operation of a wire name of this catalog, of the plain name an older one gave it, or, for any other
        name, what operation_of reads in it."""
        return self._back.get(name) or self._old.get(name) or operation_of(name)

    def known(self, name: str) -> str | None:
        """The operation of a wire name of this catalog (or of its older plain name), or None."""
        return self._back.get(name) or self._old.get(name)

    def renamed(self) -> dict[str, str]:
        """Each operation whose wire name is not its plain one, with its wire name."""
        return {op: name for op, name in self._names.items() if name != plain(op)}

    def cite(self, text: str) -> str:
        """A text of the catalog (a tool's description) with each plain wire name it cites as the name now shown."""
        if self._cite is None or not text:
            return text
        return self._cite.sub(lambda hit: self._names[self._old[hit.group(1)]], text)
