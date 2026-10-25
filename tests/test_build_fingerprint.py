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


def test_a_data_file_a_project_embeds_from_outside_its_folder_changes_the_fingerprint(tmp_path: Path) -> None:
    # Calidad PC 2026-10-25: Baxy.App, Baxy.Kernel and Baxy.Providers.Windows embed JSON from src/baxy_mind/data
    # (EmbeddedResource Include="..\baxy_mind\data\..."); a change there was «sin cambios» and the old App ran on.
    root = _worktree(tmp_path / "uno")
    (root / "src" / "Baxy.App" / "Baxy.App.csproj").write_text(
        r'<Project><ItemGroup><EmbeddedResource Include="..\baxy_mind\data\memory_subjects.v1.json" />'
        "</ItemGroup></Project>",
        encoding="utf-8",
    )
    data = root / "src" / "baxy_mind" / "data"
    data.mkdir(parents=True)
    (data / "memory_subjects.v1.json").write_text("{}", encoding="utf-8")
    before = main.source_fingerprint(root)
    (data / "memory_subjects.v1.json").write_text('{"a": 1}', encoding="utf-8")
    assert main.source_fingerprint(root) != before


def test_the_real_projects_embedded_data_is_part_of_the_fingerprint() -> None:
    inputs = {path.relative_to(main.ROOT).as_posix() for path in main.source_files()}
    assert "src/baxy_mind/data/memory_subjects.v1.json" in inputs
    assert "src/baxy_mind/data/world_acts.v1.json" in inputs
    assert "src/baxy_mind/data/keypad_keys.v1.json" in inputs


def test_building_another_worktree_does_not_make_this_one_recompile(tmp_path: Path, monkeypatch) -> None:
    # Calidad PC 2026-10-25: the state file was one per user and the fingerprint carries the worktree, so building
    # worktree B overwrote A's record and A recompiled with nothing changed.
    monkeypatch.setattr(main, "STATE_DIRECTORY", tmp_path / "estado")
    first = _worktree(tmp_path / "uno")
    second = _worktree(tmp_path / "dos")
    main.record_fingerprint(first, main.source_fingerprint(first))
    main.record_fingerprint(second, main.source_fingerprint(second))
    assert main.recorded_fingerprint(first) == main.source_fingerprint(first)
    assert main.recorded_fingerprint(second) == main.source_fingerprint(second)
