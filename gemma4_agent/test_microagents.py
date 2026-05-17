"""Tests for microagents loader / selector / format.

NO toca LLM ni filesystem real (tmpdir aislado para load tests).

Run:
    python -m gemma4_agent.test_microagents
    pytest gemma4_agent/test_microagents.py -q
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from gemma4_agent.microagents import (
    Microagent,
    _fold,
    _parse_frontmatter,
    build_microagents_section,
    format_microagents_for_prompt,
    load_microagents,
    select_microagents,
)


# ============================================================================
# fold
# ============================================================================

def test_fold_lowercases() -> None:
    assert _fold("HOLA") == "hola"


def test_fold_strips_accents() -> None:
    assert _fold("qué") == "que"
    assert _fold("Año") == "ano"
    assert _fold("ÑOÑO") == "nono"


def test_fold_empty() -> None:
    assert _fold("") == ""
    assert _fold(None) == ""  # type: ignore[arg-type]


# ============================================================================
# frontmatter parser
# ============================================================================

def test_frontmatter_basic() -> None:
    text = """---
name: test
triggers: ["a", "b"]
priority: high
---

body content here"""
    parsed = _parse_frontmatter(text)
    assert parsed is not None
    meta, body = parsed
    assert meta["name"] == "test"
    assert meta["triggers"] == ["a", "b"]
    assert meta["priority"] == "high"
    assert body.strip() == "body content here"


def test_frontmatter_missing_returns_none() -> None:
    assert _parse_frontmatter("just body, no frontmatter") is None


def test_frontmatter_with_comments_in_yaml() -> None:
    text = """---
# this is a comment
name: test
triggers: ["x"]
---

body"""
    parsed = _parse_frontmatter(text)
    assert parsed is not None
    meta, _ = parsed
    assert meta["name"] == "test"


def test_frontmatter_quoted_strings() -> None:
    text = """---
name: "quoted"
triggers: ["a", "b"]
---
body"""
    parsed = _parse_frontmatter(text)
    assert parsed and parsed[0]["name"] == "quoted"


# ============================================================================
# load_microagents (with tmpdir)
# ============================================================================

def _write_microagent(directory: Path, filename: str, content: str) -> Path:
    p = directory / filename
    p.write_text(content, encoding="utf-8")
    return p


def test_load_skips_readme() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_microagent(d, "README.md", "# README, no frontmatter")
        _write_microagent(d, "ok.md", """---
name: ok
triggers: ["test"]
---
body
""")
        loaded = load_microagents(d)
        assert len(loaded) == 1
        assert loaded[0].name == "ok"


def test_load_skips_without_frontmatter() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_microagent(d, "broken.md", "no frontmatter at all")
        _write_microagent(d, "good.md", """---
name: good
triggers: ["x"]
---
body
""")
        loaded = load_microagents(d)
        assert len(loaded) == 1
        assert loaded[0].name == "good"


def test_load_skips_empty_triggers() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_microagent(d, "bad.md", """---
name: bad
triggers: []
---
body
""")
        loaded = load_microagents(d)
        assert len(loaded) == 0


def test_load_normalizes_invalid_priority_to_medium() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_microagent(d, "p.md", """---
name: p
triggers: ["x"]
priority: super-mega
---
body
""")
        loaded = load_microagents(d)
        assert len(loaded) == 1
        assert loaded[0].priority == "medium"


def test_load_real_dir_has_4_microagents() -> None:
    """Sanity check: el directorio shipped con el repo tiene 4 microagents."""
    loaded = load_microagents()  # default dir
    names = {m.name for m in loaded}
    expected = {"glossary", "windows-commands", "troubleshoot", "tools-cheat-sheet"}
    assert expected.issubset(names), f"esperado {expected}, encontrado {names}"


# ============================================================================
# select_microagents
# ============================================================================

def _make(name: str, triggers: list[str], priority: str = "medium",
          content: str = "body") -> Microagent:
    return Microagent(name=name, triggers=triggers, priority=priority,
                      content=content)


def test_select_no_match_returns_empty() -> None:
    mas = [_make("a", ["foo"]), _make("b", ["bar"])]
    assert select_microagents("hola mundo", mas) == []


def test_select_matches_substring() -> None:
    mas = [_make("a", ["abre"]), _make("b", ["bar"])]
    matched = select_microagents("abre Steam", mas)
    assert len(matched) == 1
    assert matched[0].name == "a"


def test_select_case_insensitive() -> None:
    mas = [_make("a", ["ABRE"])]
    matched = select_microagents("abre steam", mas)
    assert len(matched) == 1


def test_select_accent_insensitive() -> None:
    mas = [_make("a", ["qué"])]
    matched = select_microagents("que paso", mas)
    assert len(matched) == 1


def test_select_sort_by_priority() -> None:
    mas = [
        _make("low_one", ["x"], priority="low"),
        _make("high_one", ["x"], priority="high"),
        _make("med_one", ["x"], priority="medium"),
    ]
    matched = select_microagents("hello x world", mas)
    assert [m.name for m in matched] == ["high_one", "med_one", "low_one"]


def test_select_caps_at_max() -> None:
    mas = [_make(f"m{i}", ["x"], priority="medium") for i in range(10)]
    matched = select_microagents("x", mas, max_microagents=3)
    assert len(matched) == 3


def test_select_each_microagent_matches_only_once() -> None:
    """Un microagent con 5 triggers que TODOS matchean no debe aparecer 5 veces."""
    mas = [_make("once", ["x", "y", "z"])]
    matched = select_microagents("x y z all match", mas)
    assert len(matched) == 1


# ============================================================================
# format_microagents_for_prompt
# ============================================================================

def test_format_empty_returns_empty() -> None:
    assert format_microagents_for_prompt([]) == ""


def test_format_includes_name_and_content() -> None:
    mas = [_make("test", ["x"], content="body here")]
    out = format_microagents_for_prompt(mas)
    assert "# CONTEXT MICROAGENTS" in out
    assert "## test" in out
    assert "body here" in out


# ============================================================================
# build_microagents_section (high-level API)
# ============================================================================

def test_build_section_empty_text_returns_empty() -> None:
    section, cached = build_microagents_section("")
    assert section == ""
    assert cached == []


def test_build_section_caches_match() -> None:
    """Primer turn: match → cached. Segundo turn sin match → cached preservado."""
    section1, cached1 = build_microagents_section("qué significa mmproj")
    assert len(cached1) >= 1
    # Segundo turn sin trigger: el cache se preserva
    section2, cached2 = build_microagents_section("hola", cached=cached1)
    cached1_names = {m.name for m in cached1}
    cached2_names = {m.name for m in cached2}
    assert cached1_names.issubset(cached2_names), (
        f"cache deberia preservarse; {cached1_names} no esta en {cached2_names}"
    )


def test_build_section_opt_out() -> None:
    os.environ["GEMMA4_MICROAGENTS_OFF"] = "1"
    try:
        section, cached = build_microagents_section("qué significa mmproj")
        assert section == ""
        assert cached == []
    finally:
        os.environ.pop("GEMMA4_MICROAGENTS_OFF", None)


def test_build_section_merges_dedupes() -> None:
    """Si el mismo microagent aparece en cache Y en fresh match, dedupea."""
    section1, cached1 = build_microagents_section("qué significa mmproj")
    name = cached1[0].name if cached1 else "(none)"
    # Segundo turn matchea el mismo
    section2, cached2 = build_microagents_section("qué significa HKCR", cached=cached1)
    final_names = [m.name for m in cached2]
    assert final_names.count(name) == 1, f"dup: {final_names}"


# ============================================================================
# Real microagents content sanity
# ============================================================================

def test_real_glossary_matches_definicional_query() -> None:
    loaded = load_microagents()
    matched = select_microagents("qué significa mmproj", loaded)
    assert any(m.name == "glossary" for m in matched)


def test_real_troubleshoot_matches_failure_query() -> None:
    loaded = load_microagents()
    matched = select_microagents("no funciona el audio", loaded)
    assert any(m.name == "troubleshoot" for m in matched)


def test_real_microagents_no_match_returns_empty() -> None:
    loaded = load_microagents()
    matched = select_microagents("abre Steam", loaded)
    # Probable que "abre Steam" no matchee NINGUN microagent (no es definicional,
    # no es troubleshoot, no menciona comando/powershell/etc).
    # Si en el futuro agregamos un microagent con trigger genérico, esto puede
    # fallar — entonces ajustar el trigger, no este test.
    assert matched == [], f"esperado no match para 'abre Steam', got {[m.name for m in matched]}"


# ============================================================================
# Runner
# ============================================================================
TESTS = [
    test_fold_lowercases,
    test_fold_strips_accents,
    test_fold_empty,
    test_frontmatter_basic,
    test_frontmatter_missing_returns_none,
    test_frontmatter_with_comments_in_yaml,
    test_frontmatter_quoted_strings,
    test_load_skips_readme,
    test_load_skips_without_frontmatter,
    test_load_skips_empty_triggers,
    test_load_normalizes_invalid_priority_to_medium,
    test_load_real_dir_has_4_microagents,
    test_select_no_match_returns_empty,
    test_select_matches_substring,
    test_select_case_insensitive,
    test_select_accent_insensitive,
    test_select_sort_by_priority,
    test_select_caps_at_max,
    test_select_each_microagent_matches_only_once,
    test_format_empty_returns_empty,
    test_format_includes_name_and_content,
    test_build_section_empty_text_returns_empty,
    test_build_section_caches_match,
    test_build_section_opt_out,
    test_build_section_merges_dedupes,
    test_real_glossary_matches_definicional_query,
    test_real_troubleshoot_matches_failure_query,
    test_real_microagents_no_match_returns_empty,
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
