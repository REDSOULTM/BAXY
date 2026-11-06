"""The package ships the mind's sources and data and the worker scripts as text: none of them names the machines BAXY is
built and measured on, nor the folders it is measured in. The names are private, so they come from the environment
(BAXY_PRIVATE_NAMES, comma-separated) and never live in the repository; without it there is nothing to check."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
SHIPPED = [
    *sorted((SRC / "baxy_mind").rglob("*.py")),
    *sorted((SRC / "baxy_mind" / "data").glob("*.json")),
    *sorted((SRC / "Baxy.Providers.Windows" / "External").glob("*.ps1")),
]
NAMES = [name.strip() for name in os.environ.get("BAXY_PRIVATE_NAMES", "").split(",") if name.strip()]


@pytest.mark.skipif(not NAMES, reason="BAXY_PRIVATE_NAMES is not set")
@pytest.mark.parametrize("path", SHIPPED, ids=lambda path: path.name)
def test_shipped_text_names_no_internal_machine_or_folder(path: Path) -> None:
    internal = re.compile(r"\b(?:" + "|".join(re.escape(name) for name in NAMES) + r")\b", re.IGNORECASE)
    assert internal.findall(path.read_text(encoding="utf-8")) == []
