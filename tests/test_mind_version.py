"""VER2 (10-11-2026, 1.3.3 recién instalada): asked which version it is, it said it had no information on it; the system
text then said the installed version as a fact of this PC (catalog.configure «baxyVersion»).
VER3 (13-11-2026): that one character moved the whole bench with each release (INT34C: the same tree saying «1.5.0»
answered as 1.5.0 in 148 of 148 rows, saying «1.5.1» it did not; INT35: «1.5.2» alone, a near-tie row 0 → 7 of 10). The
prefix (tools and system text) no longer carries the version: it is read when asked, assistant.status scope version (the
App's stamp, the one Ajustes → General shows), and baxy.update's check still says it beside the latest published."""
import json
import pathlib

from baxy_mind.mind import _ENGLISH_FILE, VERSION_NEWER, VERSION_WHERE
from test_mind_final import _mind

OPEN = {"name": "app.open", "description": "Abre una app.", "argumentsSchema": {"type": "object", "properties": {}},
        "risk": "low_reversible", "confirms": []}
STATUS = {"name": "assistant.status", "description": "Lee lo que la vista muestra de BAXY.",
          "argumentsSchema": {"type": "object", "properties": {"scope": {
              "type": "string", "enum": ["confirmation", "internet", "model", "version"]}},
              "required": ["scope"], "additionalProperties": False},
          "risk": "read_only", "group": "Sistema", "confirms": []}
UPDATE = {"name": "baxy.update", "description": "Busca una versión más nueva de BAXY.",
          "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["check", "install"]}}},
          "risk": "low_reversible", "group": "Sistema", "confirms": []}


def _prefix(tmp_path: pathlib.Path, message: dict) -> tuple[str, str, str]:
    mind, _ = _mind(tmp_path, [])
    mind.configure(message)
    return mind._system(), json.dumps(mind.tools, ensure_ascii=False, sort_keys=True), mind._system(beat=True)


def test_two_releases_build_the_same_prefix_byte_for_byte(tmp_path: pathlib.Path) -> None:
    # The App still states its stamp in catalog.configure; the tools, the system text and the heartbeat's are the same
    # whatever it says, with memory on, off or unsaid.
    for memory in (None, True, False):
        base = {"capabilities": [OPEN, STATUS]} | ({} if memory is None else {"memoryOff": memory})
        made = [_prefix(tmp_path / f"{memory}-{version}", base | ({"baxyVersion": version} if version else {}))
                for version in ("1.5.2", "9.9.9", None)]
        assert made[0] == made[1] == made[2]
        assert not any("1.5.2" in part or "9.9.9" in part for part in made[0])


def test_the_version_is_read_from_assistant_status_when_asked(tmp_path: pathlib.Path) -> None:
    # Where the model finds it: the description of the tool that reads BAXY's own state names the scope, and where the
    # number stood the system text says where it is read (without it, «Soy la versión 1.0.0» with no call).
    described = json.loads(_ENGLISH_FILE.read_text(encoding="utf-8"))["tools"]["assistant.status"]
    assert "scope version" in described
    system, _, beat = _prefix(tmp_path / "with", {"capabilities": [OPEN, STATUS], "baxyVersion": "1.5.2"})
    assert VERSION_WHERE.format(call="assistant_status", newer="") in system
    assert "assistant_status" not in beat
    # A copy whose catalog lacks the tool is told no way it cannot take.
    without, _, _ = _prefix(tmp_path / "without", {"capabilities": [OPEN], "baxyVersion": "1.5.2"})
    assert VERSION_WHERE.split(":")[0] not in without


def test_where_a_newer_one_is_looked_for_is_said_beside_it(tmp_path: pathlib.Path) -> None:
    # VER3B: without the number, «¿estás al día?» went unasked 6 of 24 (answered from memory, or «¿de BAXY o de un
    # programa?»). The same fixed sentence names the tool that looks for a newer one, when the profile has it; the same
    # words whatever the release.
    made = [_prefix(tmp_path / version, {"capabilities": [OPEN, STATUS, UPDATE], "baxyVersion": version})
            for version in ("1.5.2", "9.9.9")]
    assert made[0] == made[1]
    newer = VERSION_NEWER.format(call="baxy_update")
    assert VERSION_WHERE.format(call="assistant_status", newer=newer) in made[0][0]
    without, _, _ = _prefix(tmp_path / "sin", {"capabilities": [OPEN, STATUS], "baxyVersion": "1.5.2"})
    assert "baxy_update" not in without
