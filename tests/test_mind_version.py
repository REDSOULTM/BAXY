"""VER2 (10-11-2026, 1.3.3 recién instalada): asked which version it is, it said it had no information on it.
The App knows the version it is (its stamp, the one Ajustes → General shows: UpdatePanel.Installed) and the model read it
nowhere: catalog.configure carries it (baxyVersion) and the person's system text says it as a fact of this PC, as it
names the catalog's areas (CAN_DO_AREAS)."""
import pathlib

from baxy_mind.mind import SYSTEM, VERSION_FACT
from test_mind_final import _mind

OPEN = {"name": "app.open", "description": "Abre una app.", "argumentsSchema": {"type": "object", "properties": {}},
        "risk": "low_reversible", "confirms": []}


def test_the_installed_version_the_app_sends_is_a_fact_of_the_system_text(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "baxyVersion": "1.3.3"})
    assert VERSION_FACT.format(version="1.3.3") in mind.system
    assert mind.system.count("1.3.3") == 1


def test_without_a_version_the_system_text_is_the_one_of_before(tmp_path: pathlib.Path) -> None:
    # A development copy (no stamp) or an older App sends none: nothing is said, never a version made up.
    for message in ({"capabilities": [OPEN]}, {"capabilities": [OPEN], "baxyVersion": ""},
                    {"capabilities": [OPEN], "baxyVersion": 133}):
        mind, _ = _mind(tmp_path / str(len(message)) / type(message.get("baxyVersion")).__name__, [])
        mind.configure(message)
        assert VERSION_FACT.split("{")[0] not in mind.system
    assert VERSION_FACT.split("{")[0] not in SYSTEM


def test_the_heartbeat_does_not_read_the_version(tmp_path: pathlib.Path) -> None:
    # Nobody asks the heartbeat anything: its text stays BEAT_SYSTEM, the same with or without a version.
    with_version, _ = _mind(tmp_path / "a", [])
    with_version.configure({"capabilities": [OPEN], "baxyVersion": "1.3.3"})
    without, _ = _mind(tmp_path / "b", [])
    without.configure({"capabilities": [OPEN]})
    assert with_version._system(beat=True) == without._system(beat=True)
