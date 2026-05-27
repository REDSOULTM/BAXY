"""System prompt + per-tool rules + builder (lazy-load from ``prompts/``).

Extracted from :mod:`gemma4_agent.agent` in Sprint 5b. Originally the
two literals (``CORE_PROMPT``, ``TOOL_RULES``) were inline string
literals (~550 LOC of prose embedded in Python).

Post-plan (this commit): the literals live in markdown files under
``gemma4_agent/prompts/``. This module loads them ONCE at import time
into module-level singletons that preserve the SAME object identity
semantics as before (i.e. when two tool aliases share a rule, they
share the same ``str`` object — ``id(rule_a) == id(rule_b)``). That
identity is load-bearing: ``build_system_prompt`` deduplicates by
``id(rule)`` to avoid repeating a shared rule when multiple aliases
of it land in the same subset.

API público preservado (idéntico al pre-refactor):
    CORE_PROMPT: str
    TOOL_RULES: dict[str, str]   (35 keys, 26 distinct string objects)
    SYSTEM_PROMPT: str
    build_system_prompt(selected_tool_names) -> str

agent.py re-exports them so existing callers and tests do not need
to change.

Why lazy-load instead of eager-literal:
- Iterating on the prompt no longer requires editing Python source.
- Each rule lives in its own ``.md`` file → easier diffing.
- ``CORE_PROMPT`` (~8.7 KB) and each rule (50-5000 chars) are loaded
  once per process; SYSTEM_PROMPT is still cached as a single string.

Why we don't lazy-load PER-CALL (i.e. only when the rule is needed):
- ``build_system_prompt`` is called every turn. Disk IO per turn is
  not free.
- The total prompt content is ~26 KB, negligible compared to the
  KV cache of a 4 GB GGUF.

Byte-level invariance: the resulting ``SYSTEM_PROMPT`` is guaranteed
to be sha256-identical to the pre-refactor version, validated by
``test_system_prompt_scope.py`` and the SHA snapshot in the Sprint
5b.2c / Sprint 6 commits.
"""
from __future__ import annotations

from pathlib import Path


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_CORE_PATH = _PROMPTS_DIR / "core.md"
_CORE_LEAN_PATH = _PROMPTS_DIR / "core_lean.md"
_TOOL_RULES_DIR = _PROMPTS_DIR / "tool_rules"

# Per-profile CORE selection (2026-05-21). The repo's own latency research
# (latency_golden_eras.md) flagged prompt thickening as the cold-start Achilles
# heel; RAG-MCP (arXiv:2505.03275) and EasyTool (arXiv:2401.06201) show a
# shorter prompt is BOTH faster (less prefill) AND more accurate (less attention
# dilution) — especially on the smaller models. So low-VRAM profiles (small/
# weak models, where latency hurts most) get the LEAN core (~920 tok); larger
# profiles get the FULL core (~2900 tok) with all the nuance. Env override:
# GEMMA4_CORE_TIER=lean|full.
#
# 2026-05-26: el único perfil operante es vram4 (E2B-Q4) -> LEAN core (~920 tok):
# es el tier más chico y más sensible a latencia (voz en GPU modesta), donde el
# prompt corto es a la vez más rápido (menos prefill) y más preciso (menos
# dilución de atención). El live tool-call test (2026-05-21) lo validó en E4B:
# 7/7 correcto y más rápido con lean. standby no corre server (su tier es
# irrelevante). Override manual: GEMMA4_CORE_TIER=lean|full.
_LEAN_PROFILES = {"vram4"}
_FULL_PROFILES = {"standby"}


def _core_for_profile() -> str:
    """Return the CORE prompt for the ACTIVE profile. Lean for small-model
    tiers, full otherwise. Falls back to full on any error."""
    import os
    tier = (os.environ.get("GEMMA4_CORE_TIER") or "").strip().lower()
    if tier == "lean":
        return CORE_LEAN_PROMPT
    if tier == "full":
        return CORE_PROMPT
    try:
        from .profiles import get_active_profile
        name = get_active_profile().name
        if name in _LEAN_PROFILES:
            return CORE_LEAN_PROMPT
    except Exception:
        pass
    return CORE_PROMPT


# Tools that share a rule by aliasing the canonical key. Each entry is
# ``(canonical_name, [alias_1, alias_2, ...])``. The canonical name's
# ``.md`` file is the source of truth; all aliases point to the SAME
# string object as the canonical to preserve ``id(rule)`` deduplication
# in ``build_system_prompt``.
_SHARED_RULE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "contacts",
        (
            "notes_tasks",
            "local_calendar",
            "habit_tracker",
            "source_manager",
            "local_search",
            "dependency",
            "printer_scanner",
            "desktop_layout",
            "backup_sync",
        ),
    ),
)


def _read_prompt(path: Path) -> str:
    """Read a prompt markdown file as UTF-8 text, no transformation."""
    return path.read_text(encoding="utf-8")


def _load_core_prompt() -> str:
    return _read_prompt(_CORE_PATH)


def _load_tool_rules() -> dict[str, str]:
    """Load every ``<canonical>.md`` under tool_rules/, then add aliases
    pointing to the SAME string object as their canonical.

    Returns a fresh dict each call; module-level ``TOOL_RULES`` caches
    a single instance so call sites get the standard mapping.
    """
    rules: dict[str, str] = {}
    if not _TOOL_RULES_DIR.is_dir():
        return rules
    for md_path in sorted(_TOOL_RULES_DIR.iterdir()):
        if md_path.suffix != ".md":
            continue
        canonical = md_path.stem
        rules[canonical] = _read_prompt(md_path)
    # Add aliases by reference, NOT by re-reading. id(rules[alias]) ==
    # id(rules[canonical]) is required for build_system_prompt's
    # deduplication.
    for canonical, aliases in _SHARED_RULE_ALIASES:
        canonical_text = rules.get(canonical)
        if canonical_text is None:
            continue
        for alias in aliases:
            rules[alias] = canonical_text
    return rules


# Module-level singletons, loaded eagerly at import time. Both names
# are part of the public API (agent.py re-exports them).
CORE_PROMPT: str = _load_core_prompt()
TOOL_RULES: dict[str, str] = _load_tool_rules()


def _load_core_lean_prompt() -> str:
    try:
        return _CORE_LEAN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return CORE_PROMPT  # fall back to full if the lean file is missing


CORE_LEAN_PROMPT: str = _load_core_lean_prompt()


def build_core_only() -> str:
    """Solo el CORE estable del system prompt (sin TOOL_RULES por tool).

    Usado por el layout cache-friendly (inv: fragmentación de prompt): el CORE no
    depende del subset de tools del turno, así que va al PRINCIPIO del prompt y
    se cachea entre turnos aunque las tools cambien. Las TOOL_RULES (variables por
    subset) se mueven al final vía build_tool_rules_tail()."""
    return _core_for_profile()


def build_tool_rules_tail(selected_tool_names: list[str] | None = None) -> str:
    """Solo las TOOL_RULES del subset (sin el CORE). Cola variable del prompt.

    Devuelve "" si no hay reglas (smalltalk) o None-legacy se trata como todas."""
    if selected_tool_names is None:
        seen: set[int] = set()
        parts: list[str] = []
        for name in sorted(TOOL_RULES.keys()):
            rule = TOOL_RULES[name]
            rid = id(rule)
            if rid in seen:
                continue
            seen.add(rid)
            parts.append(rule)
        return "\n\n".join(parts)
    if not selected_tool_names:
        return ""
    seen_ids: set[int] = set()
    rules: list[str] = []
    for name in selected_tool_names:
        rule = TOOL_RULES.get(name)
        if rule is None:
            continue
        rid = id(rule)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        rules.append(rule)
    return "\n\n".join(rules)


def build_system_prompt(selected_tool_names: list[str] | None = None) -> str:
    """Construye el SYSTEM_PROMPT efectivo para este turno.

    `None`        → comportamiento legacy: CORE + TODAS las TOOL_RULES.
    `[]`          → smalltalk: solo CORE (no rules, no schemas).
    `[a,b,...]`   → CORE + solo las TOOL_RULES cuyas tools estan en el subset.

    Distinguir `None` vs `[]` es critico para latencia: smalltalk con None
    inyectaba 60+ TOOL_RULES innecesarias (~7K chars) y tools schemas (~46K
    chars) en cada turn, forzando full prompt reprocessing.
    """
    _core = _core_for_profile()
    if selected_tool_names is None:
        # Legacy: incluir todas las reglas, deduplicadas, en orden estable.
        seen: set[int] = set()
        parts = [_core]
        for name in sorted(TOOL_RULES.keys()):
            rule = TOOL_RULES[name]
            rid = id(rule)
            if rid in seen:
                continue
            seen.add(rid)
            parts.append(rule)
        return "\n\n".join(parts)

    if not selected_tool_names:
        # Smalltalk explicito: solo el CORE.
        return _core

    # Subset: filtrar reglas por nombre de tool, deduplicar por identidad.
    seen_ids: set[int] = set()
    rules: list[str] = []
    for name in selected_tool_names:
        rule = TOOL_RULES.get(name)
        if rule is None:
            continue
        rid = id(rule)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        rules.append(rule)
    if not rules:
        return _core
    return _core + "\n\n" + "\n\n".join(rules)


# Backwards-compat: algunos modulos importan SYSTEM_PROMPT directo (tests, GUI,
# server.py /agent/system_prompt endpoint). Lo mantenemos como el prompt full
# para que GET /agent/system_prompt siga mostrando algo util al usuario.
SYSTEM_PROMPT = build_system_prompt()
