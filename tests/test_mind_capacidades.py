"""What BAXY can do, as the model may tell it (feria 2026-10-27): asked «¿qué puedes hacer?» five times, it answered five
ways and named things no tool does. The system text says to name only what its tools do, with the catalog's own groups
(the App's panel «Qué puedo hacer», sent with each tool), once, in the cached prefix."""
from pathlib import Path

from baxy_mind.mind import BEAT_SYSTEM, SYSTEM

from test_mind_final import _mind


def _tool(name: str, group: str | None) -> dict:
    tool = {"name": name, "description": "Does it.", "risk": "read_only"}
    return tool if group is None else {**tool, "group": group}


def test_the_rule_names_the_catalogs_groups_once_each_in_its_order(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [_tool("app.open", "Apps y ventanas"), _tool("web.search", "Web y navegador"),
                                     _tool("app.close", "Apps y ventanas")]})
    system = mind._system()
    assert system.startswith(SYSTEM) and system.endswith(" Por áreas: Apps y ventanas; Web y navegador.")
    assert "qué sabes o puedes hacer" in SYSTEM.splitlines()[-1]


def test_without_groups_the_rule_stands_alone_and_the_heartbeat_reads_none_of_it(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [_tool("app.open", None)]})
    assert mind._system() == SYSTEM
    assert "puedes hacer" not in BEAT_SYSTEM and mind._system(beat=True) == BEAT_SYSTEM
