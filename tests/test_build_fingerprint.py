"""The development launcher's build fingerprint (main.py; FT/proveedores goal, 2026-10-19): the build state is one per
user, so two worktrees with the same sources must not share a fingerprint, or a worktree whose own build is stale is
told «sin cambios» after another one built (the final lot's old App closed at start)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def _worktree(root: Path) -> Path:
    app = root / "src" / "Baxy.App"
    app.mkdir(parents=True)
    (app / "Program.cs").write_text("class Program {}", encoding="utf-8")
    return root


def test_two_worktrees_with_the_same_sources_do_not_share_a_fingerprint(tmp_path: Path) -> None:
    first = _worktree(tmp_path / "uno")
    second = _worktree(tmp_path / "dos")
    assert main.source_fingerprint(first) != main.source_fingerprint(second)


def test_a_worktree_keeps_its_fingerprint_until_a_source_changes(tmp_path: Path) -> None:
    root = _worktree(tmp_path / "uno")
    before = main.source_fingerprint(root)
    assert main.source_fingerprint(root) == before
    (root / "src" / "Baxy.App" / "Program.cs").write_text("class Program { }", encoding="utf-8")
    assert main.source_fingerprint(root) != before
