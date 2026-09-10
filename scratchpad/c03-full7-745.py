"""Run the inherited complete gate on the canonical publication candidate."""
from pathlib import Path
import importlib.util
import os

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("full_gate_runner742", ROOT / "scratchpad/c03-full6-742.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.OUT = ROOT / "artifacts/comprobaciones/C03/FULL7_745"
runner.PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-full7-745-private"
original_write = runner.write


def write_with_current_reason(path, value):
    if path.name == "PREREG.json":
        value["reason"] = (
            "Full6 terminal:4574 .NET pass,11398 Python pass,only stale current __main__ allowlist pin failed. "
            "744 updates that current pin and canonicalizes live Python LF plus current STT tree declarations. "
            "111 owner tests passed,1 environmental skip. Revalidate combined705+712+730+738+740+744 before adoption."
        )
        value["runner"] = "scratchpad/c03-full7-745.py reuses unchanged frozen Full6 runner; only output locations and this preregistration reason differ."
    original_write(path, value)


runner.write = write_with_current_reason

if __name__ == "__main__":
    runner.main()
