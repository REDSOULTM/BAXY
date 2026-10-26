"""scripts/run_renew.cmd as a launcher of the environment, without BAXY: the real file is copied beside a main.py that
only prints what it was given, so `py -3.12 "%ROOT%\\main.py"` shows the variables and nothing starts."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("BAXY_MIND_PYTHONPATH", "BAXY_S1_GGUF", "BAXY_S1_DOUBT", "BAXY_RENEW_TTS_DIR", "BAXY_MIND_MMPROJ",
         "BAXY_MIND_LLAMA_PORT", "BAXY_VISION_ENDPOINT")
DUMP = (
    "import json, os\n"
    f"print(json.dumps({{name: os.environ.get(name) for name in {NAMES!r}}}))\n"
)


def _checkout(root: Path) -> Path:
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts" / "run_renew.cmd", root / "scripts" / "run_renew.cmd")
    (root / "main.py").write_text(DUMP, encoding="utf-8")
    return root


def _run(command: str, local: Path) -> list[dict]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith(("BAXY_", "VISION_"))}
    environment["LOCALAPPDATA"] = str(local)
    done = subprocess.run(f'cmd /d /s /c "{command}"', capture_output=True, text=True, env=environment,
                          check=True, timeout=120)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]


def test_a_second_checkout_run_from_the_same_console_takes_its_own_mind(tmp_path: Path) -> None:
    # Calidad PC 2026-10-25: without setlocal, run from a cmd console the launcher left its variables behind, and the
    # next checkout started from that console kept the first one's BAXY_MIND_PYTHONPATH (it is only set if undefined).
    first, second = _checkout(tmp_path / "uno"), _checkout(tmp_path / "dos")
    runs = _run(f'call "{first}\\scripts\\run_renew.cmd" & call "{second}\\scripts\\run_renew.cmd"', tmp_path)
    assert [run["BAXY_MIND_PYTHONPATH"] for run in runs] == [f"{first}\\src", f"{second}\\src"]


def test_switching_system_one_off_holds_in_the_same_console(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "uno")
    switch = tmp_path / "BAXY" / "renew" / "system_one.off"
    switch.parent.mkdir(parents=True)
    launcher = f'"{checkout}\\scripts\\run_renew.cmd"'
    runs = _run(f'call {launcher} & type nul > "{switch}" & call {launcher}', tmp_path)
    assert [run["BAXY_S1_GGUF"] is not None for run in runs] == [True, False]


def test_vision_off_still_reaches_the_launch(tmp_path: Path) -> None:
    # The file is checked out with LF (.gitattributes): `goto run` must still find its label.
    checkout = _checkout(tmp_path / "uno")
    runs = _run(f'set "BAXY_VISION_OFF=1" & call "{checkout}\\scripts\\run_renew.cmd"', tmp_path)
    assert [(run["BAXY_MIND_MMPROJ"], run["BAXY_S1_GGUF"] is not None) for run in runs] == [(None, True)]


def test_a_bench_keeps_the_voice_it_sets(tmp_path: Path) -> None:
    # Calidad PC 2026-10-25: every other path of the launcher is kept when it comes defined; the voice was not.
    checkout = _checkout(tmp_path / "uno")
    voice = tmp_path / "otra-voz"
    runs = _run(f'set "BAXY_RENEW_TTS_DIR={voice}" & call "{checkout}\\scripts\\run_renew.cmd"', tmp_path)
    assert [run["BAXY_RENEW_TTS_DIR"] for run in runs] == [str(voice)]


def test_the_launcher_leaves_system_one_and_the_vision_wiring_to_the_product(tmp_path: Path) -> None:
    # Entrega 1.1.0: System One's thresholds are the mind's defaults (mind.SYSTEM_ONE), and the vision's port, endpoint
    # and slot are set by the App from the projector (MindRuntimeDiscovery, which keeps a bench's port), as in BAXY
    # installed, which has no launcher.
    checkout = _checkout(tmp_path / "uno")
    runs = _run(f'call "{checkout}\\scripts\\run_renew.cmd"', tmp_path)
    assert [(run["BAXY_S1_DOUBT"], run["BAXY_MIND_LLAMA_PORT"], run["BAXY_VISION_ENDPOINT"]) for run in runs] == [
        (None, None, None)]
