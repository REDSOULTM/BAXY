"""Tests for skills_registry.

NO toca LLM. Usa tmpdirs y los skills shipped en gemma4_agent/skills/.

Run:
    python -m gemma4_agent.test_skills
    pytest gemma4_agent/tests/test_skills.py -q
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from gemma4_agent.tools_pkg.skills_registry import (
    CAP_PER_PROFILE,
    SkillMeta,
    _is_valid_skill_name,
    _parse_yaml_simple,
    build_critical_block,
    build_menu,
    check_skill_eligibility,
    get_skill_cap,
    load_skill_content,
    scan_skills,
)


# ============================================================================
# Name validation
# ============================================================================

def test_valid_skill_names() -> None:
    assert _is_valid_skill_name("install-steam-game")
    assert _is_valid_skill_name("a")
    assert _is_valid_skill_name("purchase-guard")
    assert _is_valid_skill_name("ab-cd-ef-1-2-3")


def test_invalid_skill_names() -> None:
    assert not _is_valid_skill_name("Install-Steam-Game")  # uppercase
    assert not _is_valid_skill_name("install_steam_game")  # underscore
    assert not _is_valid_skill_name("-leading-hyphen")
    assert not _is_valid_skill_name("trailing-hyphen-")
    assert not _is_valid_skill_name("")
    assert not _is_valid_skill_name("x" * 65)  # >64 chars


# ============================================================================
# YAML parser
# ============================================================================

def test_yaml_scalar_and_list() -> None:
    text = """
name: foo
description: hello world
priority: high
triggers: ["a", "b", "c"]
"""
    parsed = _parse_yaml_simple(text)
    assert parsed["name"] == "foo"
    assert parsed["description"] == "hello world"
    assert parsed["priority"] == "high"
    assert parsed["triggers"] == ["a", "b", "c"]


def test_yaml_block_dict() -> None:
    text = """
name: bar
requires:
  bins: [steam, steam.exe]
  any_bins: [chrome, edge]
  os: [windows]
"""
    parsed = _parse_yaml_simple(text)
    assert parsed["name"] == "bar"
    req = parsed["requires"]
    assert isinstance(req, dict)
    assert req["bins"] == ["steam", "steam.exe"]
    assert req["any_bins"] == ["chrome", "edge"]
    assert req["os"] == ["windows"]


def test_yaml_nested_sublists_under_metadata() -> None:
    """R3.2 (2026-05-30): metadata con VARIAS sub-listas anidadas (examples,
    when_to_use, limitations) debe parsearse como dict con cada lista SEPARADA.
    Antes del fix el parser aplanaba las tres a una sola lista mezclada — eso
    haría que un `limitations` ("no para imprimir") se tratara como POSITIVO y
    rompiera la supresión de hard-negatives."""
    text = """
name: zzz
description: a skill
metadata:
  examples:
    - ejemplo uno
    - ejemplo dos
  when_to_use:
    - cuando pasa esto
  limitations:
    - no para esto otro
    - tampoco para aquello
requires:
  os: [windows]
"""
    parsed = _parse_yaml_simple(text)
    md = parsed["metadata"]
    assert isinstance(md, dict), f"metadata debe ser dict, fue {type(md)}"
    assert md["examples"] == ["ejemplo uno", "ejemplo dos"]
    assert md["when_to_use"] == ["cuando pasa esto"]
    assert md["limitations"] == ["no para esto otro", "tampoco para aquello"]
    # requires (sub-dict hermano) sigue intacto tras el bloque metadata
    assert parsed["requires"]["os"] == ["windows"]


def test_real_skills_have_limitations_loaded() -> None:
    """Las skills con FP medidos (screenshot, download, voice-record, research,
    safe-file-cleanup) deben exponer `limitations` no vacíos tras scan_skills —
    si no, la supresión de hard-negatives está rota silenciosamente."""
    by_name = {s.name: s for s in scan_skills()}
    for nm in ("screenshot-and-analyze", "download-file",
               "voice-record-transcribe", "research-and-summarize",
               "safe-file-cleanup"):
        if nm in by_name:  # tolerante a eligibility por OS
            assert by_name[nm].limitations, f"{nm} sin limitations cargadas"


def test_yaml_booleans() -> None:
    text = "honest_critical: true\nlazy: false"
    parsed = _parse_yaml_simple(text)
    assert parsed["honest_critical"] is True
    assert parsed["lazy"] is False


def test_yaml_comments_skipped() -> None:
    text = "# this is a comment\nname: ok"
    parsed = _parse_yaml_simple(text)
    assert parsed["name"] == "ok"


# ============================================================================
# Eligibility
# ============================================================================

def _mk_skill(name: str, **kwargs) -> SkillMeta:
    return SkillMeta(
        name=name,
        description=kwargs.get("description", "desc"),
        priority=kwargs.get("priority", "medium"),
        path=Path("/tmp/x.md"),
        requires=kwargs.get("requires", {}),
    )


def test_eligibility_empty_requires_always_eligible() -> None:
    s = _mk_skill("x", requires={})
    assert check_skill_eligibility(s) is True


def test_eligibility_os_filter() -> None:
    # OS actual (Windows en este host) acepta windows
    s = _mk_skill("x", requires={"os": ["windows", "linux"]})
    assert check_skill_eligibility(s) is True
    # OS no listado → rechazado
    s2 = _mk_skill("y", requires={"os": ["solaris", "haiku"]})
    assert check_skill_eligibility(s2) is False


def test_eligibility_bins_missing_rejects() -> None:
    s = _mk_skill("x", requires={"bins": ["definitely_not_a_real_bin_xyz_2026"]})
    assert check_skill_eligibility(s) is False


def test_eligibility_any_bins_one_match_passes() -> None:
    """python deberia estar disponible en cualquier host que corre tests."""
    s = _mk_skill("x", requires={
        "any_bins": ["python", "python3", "definitely_not_real_xyz"],
    })
    assert check_skill_eligibility(s) is True


def test_eligibility_env_missing_rejects() -> None:
    var = "DEFINITELY_NOT_SET_ENV_XYZ_2026"
    os.environ.pop(var, None)
    s = _mk_skill("x", requires={"env": [var]})
    assert check_skill_eligibility(s) is False


def test_eligibility_env_set_passes() -> None:
    var = "GEMMA4_TEST_TEMP_VAR_XYZ"
    os.environ[var] = "1"
    try:
        s = _mk_skill("x", requires={"env": [var]})
        assert check_skill_eligibility(s) is True
    finally:
        os.environ.pop(var, None)


# ============================================================================
# Cap per profile
# ============================================================================

def test_cap_per_profile() -> None:
    # 2026-05-26: colapsado a un solo perfil operante (vram4, ctx 16K -> cap 3)
    # + standby (0). Los nombres legacy ahora mapean todos al mismo cap que
    # vram4 (3) para no romper callers viejos; standby sigue en 0.
    assert get_skill_cap("standby") == 0
    assert get_skill_cap("vram4") == 3
    assert get_skill_cap("light") == 3
    assert get_skill_cap("balanced") == 3
    assert get_skill_cap("balanced_8gb") == 3
    assert get_skill_cap("performance") == 3
    assert get_skill_cap("unknown_profile") == 3  # default


# ============================================================================
# scan_skills (con tmpdir)
# ============================================================================

def _write_skill(folder: Path, content: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_scan_finds_valid_skill() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "my-skill", """---
name: my-skill
description: A test skill
priority: high
---

# Body
""")
        skills = scan_skills(d)
        assert len(skills) == 1
        assert skills[0].name == "my-skill"
        assert skills[0].priority == "high"


def test_scan_skips_invalid_name() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "InvalidName", """---
name: InvalidName
description: bad name
priority: high
---
body
""")
        skills = scan_skills(d)
        assert len(skills) == 0


def test_scan_skips_without_description() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "no-desc", """---
name: no-desc
priority: high
---
body
""")
        skills = scan_skills(d)
        assert len(skills) == 0


def test_scan_normalizes_invalid_priority() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "ok", """---
name: ok
description: x
priority: super-duper
---
body
""")
        skills = scan_skills(d)
        assert len(skills) == 1
        assert skills[0].priority == "medium"


def test_scan_sort_by_priority() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "zzz-low", """---
name: zzz-low
description: low
priority: low
---
""")
        _write_skill(d / "aaa-medium", """---
name: aaa-medium
description: med
priority: medium
---
""")
        _write_skill(d / "mmm-critical", """---
name: mmm-critical
description: crit
priority: critical
---
""")
        skills = scan_skills(d)
        assert [s.name for s in skills] == ["mmm-critical", "aaa-medium", "zzz-low"]


def test_scan_filters_ineligible() -> None:
    """Un skill con requires no cumplido se oculta."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_skill(d / "eligible", """---
name: eligible
description: ok
priority: high
---
""")
        _write_skill(d / "not-eligible", """---
name: not-eligible
description: ko
priority: high
requires:
  bins: [definitely_not_real_bin_xyz_2026]
---
""")
        skills = scan_skills(d)
        names = {s.name for s in skills}
        assert "eligible" in names
        assert "not-eligible" not in names


# ============================================================================
# Real skills shipped en repo
# ============================================================================

def test_real_skills_dir_has_purchase_guard_critical() -> None:
    skills = scan_skills()
    pg = [s for s in skills if s.name == "purchase-guard"]
    assert len(pg) == 1, f"purchase-guard no se cargo. skills: {[s.name for s in skills]}"
    assert pg[0].priority == "critical"


def test_real_skills_load_content() -> None:
    body = load_skill_content("purchase-guard")
    assert body is not None
    assert "Purchase guard" in body or "purchase-guard" in body.lower()


def test_load_invalid_name_returns_none() -> None:
    assert load_skill_content("Invalid_Name") is None
    assert load_skill_content("does-not-exist") is None


# ============================================================================
# Menu + critical block
# ============================================================================

def test_build_menu_empty() -> None:
    assert build_menu([]) == ""


def test_build_menu_empty_by_default() -> None:
    """R1 (2026-05-30): el menú "# SKILLS AVAILABLE" es OPT-IN. Por default está
    vacío — MEDIDO que el 4B emite skill_load 1/117764 veces (no hace el meta-paso
    menú→cargar→seguir). Las skills entran por auto-inject (embeddings), no por menú.
    Ahorra ~558 tok/turno. Ver project_audit / skills_registry._menu_enabled."""
    import os
    skills = [
        _mk_skill("crit-skill", priority="critical", description="critical thing"),
        _mk_skill("normal", priority="high", description="normal thing"),
    ]
    prev = os.environ.pop("GEMMA4_SKILLS_MENU", None)
    try:
        assert build_menu(skills) == ""  # default: vacío
        os.environ["GEMMA4_SKILLS_MENU"] = "1"
        menu = build_menu(skills)  # opt-in: se genera
        assert "# SKILLS AVAILABLE" in menu
        assert "crit-skill" in menu
        assert "[ALWAYS LOADED]" in menu
        assert "[lazy, priority=high]" in menu
    finally:
        if prev is None:
            os.environ.pop("GEMMA4_SKILLS_MENU", None)
        else:
            os.environ["GEMMA4_SKILLS_MENU"] = prev


def test_build_critical_block_only_critical() -> None:
    """build_critical_block solo lee skills con priority=critical."""
    skills = scan_skills()
    critical_names = [s.name for s in skills if s.priority == "critical"]
    block = build_critical_block(skills)
    if critical_names:
        for n in critical_names:
            assert f"## {n}" in block
    non_critical = [s.name for s in skills if s.priority != "critical"]
    for n in non_critical:
        # solo el header "## name" debe estar AUSENTE
        assert f"## {n}\n" not in block


# ============================================================================
# Opt-out
# ============================================================================

def test_opt_out_via_env() -> None:
    os.environ["GEMMA4_SKILLS_OFF"] = "1"
    try:
        assert scan_skills() == []
        assert load_skill_content("purchase-guard") is None
    finally:
        os.environ.pop("GEMMA4_SKILLS_OFF", None)


# ============================================================================
# Runner
# ============================================================================
TESTS = [
    # name validation
    test_valid_skill_names,
    test_invalid_skill_names,
    # YAML
    test_yaml_scalar_and_list,
    test_yaml_block_dict,
    test_yaml_nested_sublists_under_metadata,
    test_yaml_booleans,
    test_yaml_comments_skipped,
    # eligibility
    test_eligibility_empty_requires_always_eligible,
    test_eligibility_os_filter,
    test_eligibility_bins_missing_rejects,
    test_eligibility_any_bins_one_match_passes,
    test_eligibility_env_missing_rejects,
    test_eligibility_env_set_passes,
    # cap
    test_cap_per_profile,
    # scan
    test_scan_finds_valid_skill,
    test_scan_skips_invalid_name,
    test_scan_skips_without_description,
    test_scan_normalizes_invalid_priority,
    test_scan_sort_by_priority,
    test_scan_filters_ineligible,
    # real
    test_real_skills_dir_has_purchase_guard_critical,
    test_real_skills_load_content,
    test_real_skills_have_limitations_loaded,
    test_load_invalid_name_returns_none,
    # menu
    test_build_menu_empty,
    test_build_menu_empty_by_default,
    test_build_critical_block_only_critical,
    # opt-out
    test_opt_out_via_env,
]


def main() -> int:
    failures = 0
    for t in TESTS:
        try:
            ok = t()
            if not ok:
                print(f"[FAIL] {t.__name__}: returned falsy")
                failures += 1
        except AssertionError as exc:
            print(f"[FAIL] {t.__name__}: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
            failures += 1
    total = len(TESTS)
    print(f"\n{total - failures}/{total} pass")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
