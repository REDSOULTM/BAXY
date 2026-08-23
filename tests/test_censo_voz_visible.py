from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from censo_voz_visible import censar  # noqa: E402


def test_censo_voz_visible_is_zero() -> None:
    hits = censar(str(ROOT / "src"))
    assert hits == [], (
        "prosa visible fija: %d literales en %d ficheros\n%s"
        % (
            len(hits),
            len({path for path, _, _ in hits}),
            "\n".join(f"{path}:{line}: {text}" for path, line, text in hits[:40]),
        )
    )
