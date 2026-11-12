"""TPV1 (dueño, 10-11-2026, prueba en vivo de la 1.3.4: asked to remember a fact, BAXY said its memory was off and to
turn it on in Settings; «la tiene que activar, no tiene que delegar al usuario nada»). A tool profile without the memory
shows none of its tools (operation-labels «ficha»: false), so the person's system text says it is off and the call that
switches to the smallest profile that has it, which waits for the person's «sí» by itself (OwnBrakes)."""
import json
import pathlib

from baxy_mind.mind import MEMORY_OFF_FACT, SYSTEM
from test_mind_final import _mind

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETTINGS = {"name": "baxy.settings.set", "description": "Cambia un ajuste propio de BAXY.",
            "argumentsSchema": {"type": "object", "properties": {"setting": {"type": "string"},
                                                                 "value": {"type": "string"}}},
            "risk": "low_reversible", "confirms": []}
MEMORY_OFF = [{"name": "memory.save"}, {"name": "memory.recall"}, {"name": "memory.enable"}]


def test_a_profile_without_the_memory_says_so_and_the_call_that_brings_it(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": MEMORY_OFF})
    call = 'baxy_settings_set {"setting": "tool_profile", "value": "diario"}'
    assert MEMORY_OFF_FACT.format(call=call) in mind.system
    assert "Ajustes" not in MEMORY_OFF_FACT and "Settings" not in MEMORY_OFF_FACT
    # No stub of the memory: the 4B claimed to have saved with them (VIVO1 F8).
    assert not any(tool["function"]["name"].startswith("memory_") for tool in mind.tools)


def test_with_the_memory_in_the_profile_or_no_settings_tool_nothing_is_said(tmp_path: pathlib.Path) -> None:
    head = MEMORY_OFF_FACT.split("{")[0]
    with_memory, _ = _mind(tmp_path / "a", [])
    with_memory.configure({"capabilities": [SETTINGS], "withheld": [{"name": "package.install", "title": "Install"}]})
    without_call, _ = _mind(tmp_path / "b", [])
    without_call.configure({"capabilities": [], "withheld": MEMORY_OFF})
    assert head not in with_memory.system
    assert head not in without_call.system
    assert head not in SYSTEM


def test_diario_is_the_smallest_profile_with_the_memory() -> None:
    # The text names Diario: it must stay the first profile that has memory.save (ToolProfile's presets, level 2).
    labels = json.loads((ROOT / "src" / "Baxy.App" / "Assets" / "operation-labels.v1.json").read_text(encoding="utf-8"))
    assert labels["operations"]["memory.save"]["p"] == 2
    assert labels["operations"]["baxy.settings.set"]["p"] == 0
