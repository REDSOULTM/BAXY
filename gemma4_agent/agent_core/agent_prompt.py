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


_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"  # gemma4_agent/prompts/ (reorg 2026-05-28)
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


# FR-CoT (v22-next, OPT-IN via GEMMA4_FRCOT=1, DORMANT por default). Plantilla de
# thinking ESTRUCTURADO y BREVE para turnos de accion. El thinking libre del E2B
# divaga (p90 268 tok ~4s @ 62 tok/s); FR-CoT lo acota a ~4 lineas (<=32 tok) Y sube
# la fiabilidad de tool-call (arXiv:2604.02155, Qi 2026: 44%->64%, alucinacion
# 3%->0%). NO validado en vivo todavia: un intento previo filtro el formato al reply
# y rompio media (6/6->3/6). Mitigacion: el formato se scopea al canal <think> Y hay
# una guarda estructural en reasoning.sanitize_text que lo borra del reply si se
# filtra. Validar EN VIVO antes de default-on. Ver SPRINT_frcot_latencia_accion.md.
FRCOT_DIRECTIVE = (
    "[BRIEF REASONING — action turns] When the user asks you to ACT (open/play/send/"
    "set/search/control something) and a tool can do it, reason BRIEFLY using EXACTLY "
    "this 4-line format INSIDE your thinking (the <think> block), then emit the native "
    "tool_call. Never deliberate past these 4 lines:\n"
    "INTENT: <open_app|search|media_control|system_setting|message|clarify_needed>\n"
    "TOOL: <exact function name from your tool list, or none>\n"
    "ARGS: <key=value, comma-separated, or —>\n"
    "GO\n"
    "This 4-line format lives ONLY inside <think>. Your VISIBLE reply to the user is "
    "ALWAYS natural spoken Spanish (e.g. \"Listo, abrí X\") — NEVER the INTENT/TOOL/"
    "ARGS/GO lines. If INTENT=clarify_needed, ask one short question and call no tool."
)


def _frcot_enabled() -> bool:
    import os
    return (os.environ.get("GEMMA4_FRCOT") or "").strip().lower() in {"1", "true", "yes", "on"}


def _core_for_profile() -> str:
    """Return the CORE prompt for the ACTIVE profile (+ FR-CoT directive si
    GEMMA4_FRCOT). Lean for small-model tiers, full otherwise. Falls back a full."""
    import os
    tier = (os.environ.get("GEMMA4_CORE_TIER") or "").strip().lower()
    if tier == "lean":
        base = CORE_LEAN_PROMPT
    elif tier == "full":
        base = CORE_PROMPT
    else:
        base = CORE_PROMPT
        try:
            from ..infra.profiles import get_active_profile
            if get_active_profile().name in _LEAN_PROFILES:
                base = CORE_LEAN_PROMPT
        except Exception:
            pass
    # FR-CoT directive: constante cuando el flag esta on -> el prefijo del system
    # prompt sigue byte-estable turno-a-turno (no rompe el prefix-cache de Camino C).
    if _frcot_enabled():
        return base + "\n\n" + FRCOT_DIRECTIVE
    return base


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
    # v22-next (OPT-IN GEMMA4_LEAN_RULES, dormant): si on, preferimos
    # ``<canonical>.lean.md`` (version DENSA, mismo contenido/anti-patrones, menos
    # prosa) cuando existe -> menos tokens de prompt -> menos prefill FA-off. Default
    # off = los .md de siempre (sin cambio). Validar EN VIVO antes de default-on
    # (cada rule codifica bugfixes; ver PLAN_optimizacion_prompt_tokens.md).
    import os as _os_lean
    # v22 2026-05-28: lean mode DEFAULT ON (validado EN VIVO: routing 12/12, p50
    # -28% vs full, hasta ARREGLA bugs de routing del baseline — menos dilución de
    # atención en el E2B débil). GEMMA4_LEAN_RULES=0 para opt-out (volver a .md full).
    _lean = (_os_lean.environ.get("GEMMA4_LEAN_RULES", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
    for md_path in sorted(_TOOL_RULES_DIR.iterdir()):
        if md_path.suffix != ".md" or md_path.name.endswith(".lean.md"):
            continue
        canonical = md_path.stem
        src = md_path
        if _lean:
            lean_path = md_path.with_name(canonical + ".lean.md")
            if lean_path.is_file():
                src = lean_path
        rules[canonical] = _read_prompt(src)
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


# PERF — Camino C del informe prefill_latency_llama_server_gemma4.md (2026-05-28):
# Los 15 tools mas usados como prefijo estable del system; el resto del subset
# va como hint al final del user msg (no rompe cache de prefix).
#
# DINAMICO (2026-05-28): el set se lee UNA vez al import del modulo desde
# ~/.gemma4/core_tools_pareto.json (si existe) o defaultea al top 15 global
# medido en research. core_tools_pareto.maybe_recompute_in_background() se
# llama al boot del agente para que la PROXIMA sesion vea el set adaptado al
# usuario.
#
# Por que NO se actualiza en caliente: cambiar las CORE_TOOL_RULES en medio de
# la sesion rompe el prefix-cache de llama-server (Camino C se basa en bytes
# estables turno-a-turno). Mejor estabilidad: el set queda fijo durante la
# sesion, se actualiza entre sesiones.
def _load_core_tool_rule_names() -> tuple[str, ...]:
    try:
        from .core_tools_pareto import read_user_core_tools
        return read_user_core_tools()
    except Exception:
        # Fallback al default si algo en core_tools_pareto falla
        return (
            "app", "audio", "browser", "device_settings", "filesystem", "gui",
            "media", "session", "steam", "system", "uia", "vision", "web",
            "whatsapp", "window",
        )


CORE_TOOL_RULE_NAMES: tuple[str, ...] = _load_core_tool_rule_names()


def build_core_tool_rules_stable() -> str:
    """Camino C 2026-05-28: reglas de los CORE_TOOL_RULE_NAMES SIEMPRE incluidas
    (sin filtrar por subset). Bytes byte-a-byte iguales turno-tras-turno -> el
    prefix-cache de llama-server alcanza ~99% hit. Las reglas para tools FUERA del
    core se inyectan via build_tool_rules_extras_for_user_msg() en el user msg.
    """
    seen_ids: set[int] = set()
    rules: list[str] = []
    # Orden CANONICO (sorted) para garantizar bytes estables.
    for name in sorted(CORE_TOOL_RULE_NAMES):
        rule = TOOL_RULES.get(name)
        if rule is None:
            continue
        rid = id(rule)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        rules.append(rule)
    return "\n\n".join(rules)


def build_tool_rules_extras_for_user_msg(selected_tool_names: list[str] | None) -> str:
    """Camino C: reglas de tools que estan en el subset pero NO en CORE.
    Devuelve un bloque chico para anteponer al user msg (NO al system).

    Devuelve "" si no hay extras o el subset es None/vacio."""
    if not selected_tool_names:
        return ""
    core = set(CORE_TOOL_RULE_NAMES)
    extras = [n for n in selected_tool_names if n not in core]
    if not extras:
        return ""
    seen_ids: set[int] = set()
    rules: list[str] = []
    for name in extras:
        rule = TOOL_RULES.get(name)
        if rule is None:
            continue
        rid = id(rule)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        rules.append(rule)
    if not rules:
        return ""
    return ("[EXTRA TOOL RULES for this turn (use only if needed):\n"
            + "\n\n".join(rules) + "\n]\n\n")


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
