"""The name the model sees for each operation of the product catalog (its wire name), for a script with no catalog at
hand: the reference file tests/fixtures/wire_names.v1.json, which the tests keep equal to baxy_mind.wire.Wires
(tests/test_mind_wire.py) and to the App's WireNames (tests/Baxy.Kernel.Tests/WireNamesTests.cs).

usage (rewrite the reference after the catalog changes): py -3.12 -X utf8 scripts/renew/wire_names.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests" / "fixtures" / "wire_names.v1.json"
CATALOG = ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"


@cache
def _names() -> dict[str, str]:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))["names"]


def wire(operation: str) -> str:
    """The wire name of an operation of the product catalog; one it does not have keeps its plain name."""
    return _names().get(operation) or operation.replace(".", "_")


@cache
def _renamed() -> dict[str, str]:
    return {op.replace(".", "_"): name for op, name in _names().items() if name != op.replace(".", "_")}


def current(name: str) -> str:
    """A wire name read from a file (a run's rivals, a catalog, a label written before a tool was renamed) as the model
    is shown it now: the plain name of a renamed operation (audio_volume) is its new one (audio_volume_set)."""
    return _renamed().get(name, name)


def _write() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.mind import ASK_USER, CALCULATE, CONFIRM  # noqa: PLC0415
    from baxy_mind.wire import Wires  # noqa: PLC0415

    # The operations in the catalog's order, the order in which the App sends them (ProductCatalog.ValidateAgainst);
    # WireNamesTests checks that this order is ProductCatalog.ToolDescriptors'.
    operations = re.findall(r'Descriptor\(\s*"([a-z0-9_.]+)"', CATALOG.read_text(encoding="utf-8"))
    fixed = [tool["function"]["name"] for tool in (ASK_USER, CONFIRM, CALCULATE)]
    wires = Wires(operations, fixed=fixed)
    document = {"fixed": fixed, "names": {op: wires.name(op) for op in operations}}
    REFERENCE.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{REFERENCE}: {len(operations)} operations, "
          f"{sum(name != op.replace('.', '_') for op, name in document['names'].items())} renamed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite the reference from the catalog and Wires")
    if parser.parse_args().write:
        _write()
