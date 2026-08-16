from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.skill_registry import (  # noqa: E402
    MAX_SKILL_PROMPT_CHARS,
    PlannerSkill,
    SkillContractError,
    SkillRegistry,
    parse_skill,
)


def catalog_operations() -> set[str]:
    source = (ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs").read_text(
        encoding="utf-8"
    )
    return set(re.findall(r'Descriptor\(\s*"([a-z0-9.]+)"', source))


def test_every_shipped_skill_is_closed_over_the_public_catalog():
    registry = SkillRegistry.load_default(catalog_operations())
    assert len(registry.skills) >= 16
    assert len({skill.name for skill in registry.skills}) == len(registry.skills)
    assert all(skill.operations for skill in registry.skills)
    assert all(
        not operation.startswith("memory.")
        for skill in registry.skills
        for operation in skill.operations
    )


def test_retrieval_requires_tool_overlap_and_prompt_is_bounded():
    skills = (
        PlannerSkill(
            "spotify-playback",
            "play exact spotify music",
            ("media.play.exact",),
            90,
            "Use exact playback and verify now-playing.",
            "fixture",
        ),
        PlannerSkill(
            "discord-messaging",
            "send discord message",
            ("message.send",),
            90,
            "Resolve then send.",
            "fixture",
        ),
    )
    registry = SkillRegistry(
        skills,
        {"media.play.exact", "message.send"},
    )
    selected = registry.select("play Billie Jean on Spotify", {"media.play.exact"})
    assert [skill.name for skill in selected] == ["spotify-playback"]
    assert len(registry.compact_prompt(selected)) <= MAX_SKILL_PROMPT_CHARS


def test_explicit_skill_trigger_filters_semantically_unrelated_visible_skills():
    skills = (
        PlannerSkill(
            "filesystem-safe-changes",
            "hash and safely edit filesystem files",
            ("filesystem.hash",),
            80,
            "Observe then hash.",
            "fixture",
        ),
        PlannerSkill(
            "spotify-playback",
            "play spotify music",
            ("media.play.exact",),
            99,
            "Play music.",
            "fixture",
        ),
    )
    registry = SkillRegistry(
        skills,
        {"filesystem.hash", "media.play.exact"},
    )
    selected = registry.select(
        "hash the exact file",
        {"filesystem.hash", "media.play.exact"},
    )
    assert [skill.name for skill in selected] == ["filesystem-safe-changes"]


def test_lexical_retrieval_derives_common_and_rare_terms_from_its_corpus():
    skills = (
        PlannerSkill(
            "alpha-path",
            "zorple quasar alpha workflow",
            ("alpha.run",),
            1,
            "Alpha.",
            "fixture",
        ),
        PlannerSkill(
            "beta-path",
            "zorple nebula beta workflow",
            ("beta.run",),
            99,
            "Beta.",
            "fixture",
        ),
        PlannerSkill(
            "gamma-path",
            "zorple comet gamma workflow",
            ("gamma.run",),
            50,
            "Gamma.",
            "fixture",
        ),
    )
    operations = {"alpha.run", "beta.run", "gamma.run"}
    registry = SkillRegistry(skills, operations)

    # ``zorple`` appears in every skill document, so the corpus-derived IDF
    # mass is distributed and the encoder-free path abstains fail-closed.
    assert registry.select("zorple", operations) == ()
    # ``quasar`` is rare in that same corpus and selects its matching skill
    # despite that skill having the lowest advisory priority.
    assert [skill.name for skill in registry.select("quasar", operations)] == [
        "alpha-path"
    ]


def test_skill_retrieval_has_no_manual_stopword_or_trigger_vocabulary():
    source = (ROOT / "src/baxy_mind/skill_registry.py").read_text(
        encoding="utf-8"
    )

    assert "_GENERIC_TRIGGER_TOKENS" not in source
    assert "_trigger_tokens" not in source


def test_skill_cannot_smuggle_unknown_or_private_operations():
    with pytest.raises(SkillContractError):
        SkillRegistry(
            [PlannerSkill("bad", "bad", ("memory.recall",), 1, "bad", "fixture")],
            {"memory.recall"},
        )
    with pytest.raises(SkillContractError):
        SkillRegistry(
            [PlannerSkill("bad", "bad", ("invented.tool",), 1, "bad", "fixture")],
            {"system.time"},
        )


def test_skill_parser_rejects_unknown_metadata_and_folder_mismatch(tmp_path):
    folder = tmp_path / "wrong-folder"
    folder.mkdir()
    path = folder / "SKILL.md"
    path.write_text(
        "---\nname: intended-name\ndescription: test\nunknown: nope\n"
        "operations:\n  - system.time\n---\nDo the thing.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillContractError, match="unknown frontmatter"):
        parse_skill(path)

    path.write_text(
        "---\nname: intended-name\ndescription: test\n"
        "operations:\n  - system.time\n---\nDo the thing.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillContractError, match="incomplete skill contract"):
        parse_skill(path)
