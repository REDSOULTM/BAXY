"""Neutral edits of the prompt as replicas (Renew al máximo, palanca 12.3).

usage: py -3.12 scripts/renew/neutras.py <src dir> <out dir> [<bank.json> ...] [--n 3]

A seed does not show the scenes' noise (the same scenes for seeds 0, 1 and 2) and shows only part of decision2's: one
trailing space in the description of a tool no case calls moved the scenes 34 → 32 (2026-10-17). The comparisons of
the fase B are made on replicas that each change one meaningless character of the prompt.

Writes <out dir>/pA, pB, pC... each a copy of <src dir>/baxy_mind whose tool_descriptions.en.v1.json has one trailing
space at the end of the description of one tool that no case of the given banks names (their «op» and «ops»), a
different tool for each copy, chosen in a fixed order. Each copy is used as --src <out dir>/pX by bench_decision.py and
bench_escenas.py, or as BAXY_MIND_PYTHONPATH by the product (e2e). Prints each copy and the tool it touched.
"""
import json
import shutil
import sys
from pathlib import Path

NAMES = "ABCDEFGH"


def named_operations(value) -> set[str]:
    """Every operation a case expects or names, wherever it sits in the case."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("op", "operation") and isinstance(item, str):
                found.add(item)
            elif key in ("ops", "operations") and isinstance(item, list):
                found.update(str(op) for op in item)
            else:
                found |= named_operations(item)
    elif isinstance(value, list):
        for item in value:
            found |= named_operations(item)
    return found


def main() -> None:
    args = sys.argv[1:]
    count = 3
    if "--n" in args:
        at = args.index("--n")
        count = int(args[at + 1])
        args = args[:at] + args[at + 2:]
    if len(args) < 2 or not 1 <= count <= len(NAMES):
        sys.exit(__doc__)
    source, out, banks = Path(args[0]), Path(args[1]), [Path(bank) for bank in args[2:]]
    used: set[str] = set()
    for bank in banks:
        used |= named_operations(json.loads(bank.read_text(encoding="utf-8")))
    descriptions = source / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"
    tools = json.loads(descriptions.read_text(encoding="utf-8"))["tools"]
    untouched = sorted(name for name in tools if name not in used)
    if len(untouched) < count:
        sys.exit(f"only {len(untouched)} tools no case names")
    step = len(untouched) // count
    for number in range(count):
        tool = untouched[number * step]
        copy = out / f"p{NAMES[number]}"
        if copy.exists():
            shutil.rmtree(copy)
        shutil.copytree(source / "baxy_mind", copy / "baxy_mind", ignore=shutil.ignore_patterns("__pycache__"))
        target = copy / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"
        text = target.read_bytes().decode("utf-8")
        old = json.dumps(tools[tool], ensure_ascii=False)
        if text.count(old) != 1:
            sys.exit(f"the description of {tool} is not written once as json.dumps writes it")
        target.write_bytes(text.replace(old, json.dumps(tools[tool] + " ", ensure_ascii=False)).encode("utf-8"))
        edited = json.loads(target.read_text(encoding="utf-8"))["tools"]
        changed = [name for name in tools if edited[name] != tools[name]]
        assert changed == [tool], changed
        print(f"{copy}: {tool}")


if __name__ == "__main__":
    main()
