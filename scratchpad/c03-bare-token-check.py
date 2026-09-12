"""Comprueba el guardia de palabra suelta contra todo lo que las tandas publicaron de verdad.

La regla tiene que rechazar «SIEMPRE» —vocabulario del prompt que CLOCK1034 publicó dos veces— y no
tocar ninguna de las respuestas reales que sí eran respuestas. El material son los terminales publicados
de las cinco tandas de esta sesión, no ejemplos inventados.

Uso:
    python scratchpad/c03-bare-token-check.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BASE = pathlib.Path.home() / "AppData/Local/BAXY"

BATCHES = ["apps1029", "repair1030", "repair1031", "repair1032", "repair1033", "clock1034"]
MUST_REJECT = {"SIEMPRE"}


def main() -> int:
    from baxy_mind.__main__ import _conversation_reply_is_a_bare_prompt_token as bare

    # Casos que la regla no debe tocar aunque sean cortos.
    for value in ("Sí", "No", "OK", "Sí.", "03:01", "Abrí Steam."):
        if bare(value):
            print(f"BAD  would reject a legitimate short reply: {value!r}")
            return 1

    rejected: list[tuple[str, str]] = []
    kept = 0
    for batch in BATCHES:
        path = BASE / f"C03-{batch}-private/run/capture/events.jsonl"
        if not path.is_file():
            print(f"   (no capture for {batch})")
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("type") != "terminal":
                continue
            final = (row.get("final") or "").strip()
            if not final:
                continue
            if bare(final):
                rejected.append((batch, final))
            else:
                kept += 1

    print(f"published finals kept: {kept}")
    print(f"published finals rejected: {len(rejected)}")
    for batch, value in rejected:
        print(f"   {batch}: {value!r}")
    values = {value for _, value in rejected}
    if values != MUST_REJECT:
        print(f"BAD  expected to reject exactly {MUST_REJECT}, rejected {values}")
        return 1
    print("OK   rejects only the shouted prompt keyword, keeps every real answer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
