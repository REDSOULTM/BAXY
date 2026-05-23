"""Loader de los 540 tests oficiales (18 categorias x 30 cases).

Parsea tests_540.md y devuelve la lista de Case objects. Standalone — no
importa Carter ni nada externo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GUIDE = ROOT / "tests_540.md"


@dataclass
class Case:
    cid: str            # "C01-01"
    category: int       # 1..18
    severity: str       # P0|P1|P2
    prompt: str
    expected: str
    expected_tools: str
    forbidden: str
    pass_rule: str
    category_name: str = ""


_HEADING_RE = re.compile(r"^## C(?P<cat>\d{2})\s*[—-]\s*(?P<name>.+?)\s*$")
_ROW_RE = re.compile(r"^\|\s*C(?P<cat>\d{2})-(?P<num>\d{2})\s*\|")


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def load_cases() -> list[Case]:
    if not GUIDE.exists():
        raise FileNotFoundError(f"Guia oficial no encontrada: {GUIDE}")
    cases: list[Case] = []
    cat_names: dict[int, str] = {}
    for line in GUIDE.read_text(encoding="utf-8").splitlines():
        h = _HEADING_RE.match(line)
        if h:
            cat_names[int(h.group("cat"))] = h.group("name").strip()
            continue
        if not _ROW_RE.match(line):
            continue
        cells = _split_row(line)
        if len(cells) < 7:
            continue
        cid = cells[0]
        sev = cells[1]
        prompt = cells[2]
        expected = cells[3]
        expected_tools = cells[4]
        forbidden = cells[5]
        pass_rule = cells[7] if len(cells) >= 8 else cells[6]
        category = int(cid.split("-", 1)[0].replace("C", ""))
        cases.append(Case(
            cid=cid, category=category, severity=sev,
            prompt=prompt, expected=expected,
            expected_tools=expected_tools, forbidden=forbidden,
            pass_rule=pass_rule,
            category_name=cat_names.get(category, ""),
        ))
    return cases


if __name__ == "__main__":
    cs = load_cases()
    print(f"loaded {len(cs)} cases")
    by_cat: dict[int, int] = {}
    for c in cs:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
    for cat in sorted(by_cat.keys()):
        print(f"  C{cat:02d}: {by_cat[cat]} cases")
    print(f"\nFirst 3 cases:")
    for c in cs[:3]:
        print(f"  {c.cid} [{c.severity}]: {c.prompt!r}")
        print(f"    expected: {c.expected!r}")
        print(f"    tools: {c.expected_tools!r}")
        print(f"    pass_rule: {c.pass_rule[:80]!r}")
