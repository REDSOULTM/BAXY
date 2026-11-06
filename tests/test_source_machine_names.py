"""El C# no nombra las máquinas de desarrollo: el código se publica y los comentarios van con él. Los nombres son
privados: llegan por el entorno (BAXY_PRIVATE_NAMES, separados por comas) y nunca están en el repositorio; sin ella,
no hay nada que comprobar."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NAMES = [name.strip() for name in os.environ.get("BAXY_PRIVATE_NAMES", "").split(",") if name.strip()]


def _csharp_files() -> list[Path]:
    return [
        path
        for folder in ("src", "tests")
        for path in (REPO / folder).rglob("*.cs")
        if not {"bin", "obj"} & set(path.parts)
    ]


@pytest.mark.skipif(not NAMES, reason="BAXY_PRIVATE_NAMES is not set")
def test_csharp_sources_do_not_name_the_development_machine() -> None:
    machine = re.compile(r"\b(?:" + "|".join(re.escape(name) for name in NAMES) + r")\b", re.IGNORECASE)
    files = _csharp_files()
    assert files, "no C# sources found"
    named = [
        f"{path.relative_to(REPO)}:{number}"
        for path in files
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if machine.search(line)
    ]
    assert not named, named
