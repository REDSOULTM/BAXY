"""REM7 (REV15 D-1, REV14 B-E2): the memory fact said «está apagada en este PC: no hay nada guardado» without looking at
the store, and whatever the switch was: the person who saved with the memory on and then turned it off, or chose Esencial
with it on, heard a falsehood. The fact says only what is known: the switch the App read (catalog.configure «memoryOff»),
or that the memory's tools are out of the profile, and that nothing is read nor saved meanwhile; never that the store is
empty."""
import pathlib

from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, REST, SETTINGS, _memory_line
from test_mind_final import _mind


def _fact(tmp_path: pathlib.Path, **switch: bool) -> str:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST], **switch})
    return _memory_line(mind._system())


def test_the_memory_fact_never_says_the_store_is_empty(tmp_path: pathlib.Path) -> None:
    for switch in ({}, {"memoryOff": True}, {"memoryOff": False}):
        line = _fact(tmp_path, **switch)
        assert line, switch
        assert "nada guardado" not in line and "no hay nada" not in line, (switch, line)
        assert "no lees" in line and "ni guardas nada" in line, (switch, line)


def test_with_the_switch_on_the_fact_says_the_profile_not_that_it_is_off(tmp_path: pathlib.Path) -> None:
    on = _fact(tmp_path, memoryOff=False)
    off = _fact(tmp_path, memoryOff=True)
    assert "apagada" not in on and "perfil de herramientas" in on, on
    assert "está apagada en este PC" in off, off
    assert _fact(tmp_path) == off, "an App that does not say keeps the switch-off wording"
