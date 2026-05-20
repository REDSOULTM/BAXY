"""Skills registry — Anthropic Agent Skills spec con extensiones de Carter.

Pattern: Anthropic Agent Skills. Cada skill es una carpeta con SKILL.md.
Frontmatter YAML declara name + description + priority + requires.

Boot flow:
  1. scan_skills() → list[SkillMeta]    (al boot del agente, ~10ms)
  2. build_menu(skills) → str           (inyectado al system_prompt como
                                         "# SKILLS AVAILABLE" + 1 linea
                                         por skill: 50 tokens c/u)
  3. build_critical_block(skills)       (skills con priority=critical se
                                         eager-loaded full body)
  4. load_skill_content(name) → str     (lazy: llamado por skill_load tool
                                         cuando el LLM lo pide)

Diferencia vs microagents:
  - microagent: contexto eager por trigger (knowledge en glossary, troubleshoot)
  - skill: receta lazy on-demand. El LLM ve un MENU (name + description) y
    decide SEMANTICAMENTE cual cargar via skill_load(). Sin keyword matching.

`priority` extension (no esta en spec oficial Anthropic):
  - critical: eager-loaded full body en cada turn. Reservado para safety/
    honestidad universales (e.g. purchase-guard).
  - high/medium/low: solo aparecen en el menu (lazy). Cap por profile de
    cuantas skill_load() puede emitir el LLM en un turn.

`requires` extension (eligibility filter):
  - bins: lista de exes que deben estar en PATH (e.g. ["steam.exe"])
  - any_bins: al menos uno debe estar en PATH (e.g. ["chrome", "edge"])
  - env: lista de env vars que deben estar set (no vacias)
  - os: lista de OS aceptados ("windows" | "linux" | "darwin")
  Skills con requirements no cumplidos se ocultan del menu (LLM no las
  selecciona).

Opt-out:
  GEMMA4_SKILLS_OFF=1 desactiva todo el sistema (menu vacio, skill_load
  retorna "skills disabled").

Limite por profile (cuantas skill_load() puede emitir el LLM en 1 turn):
  standby:     0
  light:       1
  balanced:    2
  balanced_8gb: 3
  performance: 5

Refs:
  - https://www.anthropic.com/news/agent-skills (spec oficial)
  - Inspirado en carter_v5/skills/registry.py (extension priority + requires)
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Datatype + constants
# ============================================================================

Priority = Literal["critical", "high", "medium", "low"]

# Cap por profile de Gemma 4: cuantas skill_load() puede emitir el LLM en un
# turn. Escala con el context_size del perfil (menos ctx -> menos skills caben).
# standby NO carga skills. Las claves legacy (light/balanced/...) se conservan
# como alias para no romper callers viejos; las nuevas son vramN.
CAP_PER_PROFILE: dict[str, int] = {
    "standby":      0,
    # nuevos (por VRAM / context_size)
    "vram3":        1,   # ctx 2K
    "vram4":        1,   # ctx 4K
    "vram6":        2,   # ctx 8K
    "vram8":        3,   # ctx 16K
    "vram12":       5,   # ctx 32K
    "vram16":       5,   # ctx 32K
    # legacy aliases (compat)
    "light":        1,
    "balanced":     2,
    "balanced_8gb": 3,
    "performance":  5,
}


@dataclass(frozen=True)
class SkillMeta:
    """Metadata de un skill (no incluye el body — lazy)."""
    name: str
    description: str
    priority: Priority
    path: Path              # ruta al SKILL.md
    requires: dict = field(default_factory=dict)


# ============================================================================
# Frontmatter parser (subset YAML)
# ============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_VALID_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")


def _is_valid_skill_name(name: str) -> bool:
    """Anthropic Agent Skills: lowercase letters/digits/hyphens, max 64,
    no leading/trailing hyphen.
    """
    return bool(_VALID_NAME_RE.match(name)) and len(name) <= 64


def _parse_yaml_simple(text: str) -> dict:
    """YAML subset que cubre frontmatter de SKILL.md:
       - scalars
       - inline lists `key: [a, b]`
       - block sub-dict/sub-lists indentados con "  "
       - booleans
    NO soporta block scalar `|`, anchors, ni tipos complejos.
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val == "":
            # Block sub-dict o sub-lista
            sub_items: list = []
            sub_dict: dict = {}
            i += 1
            while i < len(lines):
                sub_line = lines[i]
                if not sub_line.startswith("  ") and sub_line.strip():
                    break
                stripped = sub_line.strip()
                if not stripped:
                    i += 1
                    continue
                if stripped.startswith("- "):
                    sub_items.append(stripped[2:].strip().strip('"').strip("'"))
                elif ":" in stripped:
                    sk, _, sv = stripped.partition(":")
                    sk = sk.strip()
                    sv = sv.strip()
                    if sv.startswith("[") and sv.endswith("]"):
                        inner = sv[1:-1].strip()
                        items_inline: list[str] = []
                        for part in re.split(r",\s*", inner):
                            p = part.strip().strip('"').strip("'")
                            if p:
                                items_inline.append(p)
                        sub_dict[sk] = items_inline
                    else:
                        sub_dict[sk] = sv.strip('"').strip("'")
                i += 1
            out[key] = sub_items if sub_items else (sub_dict if sub_dict else "")
            continue

        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items: list[str] = []
            for part in re.split(r",\s*", inner):
                p = part.strip().strip('"').strip("'")
                if p:
                    items.append(p)
            out[key] = items
            i += 1
            continue

        cleaned = val.strip('"').strip("'")
        if cleaned.lower() in {"true", "false"}:
            out[key] = (cleaned.lower() == "true")
        else:
            out[key] = cleaned
        i += 1
    return out


def _parse_skill_md(path: Path) -> Optional[tuple[dict, str]]:
    """Parse SKILL.md. Returns (frontmatter_dict, body) or None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("cannot read skill: %s (%s)", path, exc)
        return None
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        logger.warning("skill missing frontmatter: %s", path)
        return None
    meta = _parse_yaml_simple(m.group(1))
    body = m.group(2).strip()
    return meta, body


# ============================================================================
# Eligibility filter
# ============================================================================

def check_skill_eligibility(skill: SkillMeta) -> bool:
    """Decide si las requirements del skill estan cumplidas.

    Sin requires → siempre eligible.
    """
    requires = skill.requires or {}
    if not requires:
        return True

    import platform as _plat

    os_required = requires.get("os") or []
    if os_required:
        current_os = _plat.system().lower()
        if current_os not in {str(o).lower() for o in os_required}:
            logger.debug("skill '%s' skipped: OS %r not in %r",
                         skill.name, current_os, os_required)
            return False

    bins = requires.get("bins") or []
    for b in bins:
        if not shutil.which(str(b)):
            logger.debug("skill '%s' skipped: missing bin %r", skill.name, b)
            return False

    any_bins = requires.get("any_bins") or []
    if any_bins:
        if not any(shutil.which(str(b)) for b in any_bins):
            logger.debug("skill '%s' skipped: none of %r in PATH",
                         skill.name, any_bins)
            return False

    env_required = requires.get("env") or []
    for v in env_required:
        if not os.environ.get(str(v)):
            logger.debug("skill '%s' skipped: env %r not set", skill.name, v)
            return False

    return True


# ============================================================================
# Loader
# ============================================================================

def _default_skills_dir() -> Path:
    """Default: gemma4_agent/skills/ (sibling de este modulo)."""
    return Path(__file__).parent / "skills"


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_SKILLS_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def scan_skills(skills_dir: Optional[Path] = None) -> list[SkillMeta]:
    """Scan skills_dir/ y devuelve metadata de skills validos, eligibility-checked.

    Cada skill = carpeta con SKILL.md. Frontmatter requiere name + description.
    Sort: priority (critical > high > medium > low), tie-break alfabetico.
    """
    if not _enabled():
        return []
    if skills_dir is None:
        skills_dir = _default_skills_dir()
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    skills: list[SkillMeta] = []
    for folder in sorted(skills_dir.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name.startswith(("_", ".")):
            continue
        skill_md = folder / "SKILL.md"
        if not skill_md.exists():
            continue
        parsed = _parse_skill_md(skill_md)
        if parsed is None:
            continue
        meta_dict, _body = parsed
        try:
            name = str(meta_dict.get("name") or folder.name).strip()
            if not _is_valid_skill_name(name):
                logger.warning(
                    "skill '%s' invalido (lowercase + hyphens, <=64). Skipping %s.",
                    name, skill_md,
                )
                continue
            description = str(meta_dict.get("description") or "").strip()
            if not description:
                logger.warning("skill '%s' sin description; skipping", name)
                continue
            priority = str(meta_dict.get("priority") or "medium").lower()
            if priority not in {"critical", "high", "medium", "low"}:
                priority = "medium"
            requires_raw = meta_dict.get("requires") or {}
            requires = dict(requires_raw) if isinstance(requires_raw, dict) else {}
            skills.append(SkillMeta(
                name=name,
                description=description,
                priority=priority,  # type: ignore[arg-type]
                path=skill_md,
                requires=requires,
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill frontmatter invalido en %s: %s", skill_md, exc)
            continue

    # Filter eligibility ANTES de sort para no contar las que no aplican
    skills = [s for s in skills if check_skill_eligibility(s)]
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    skills.sort(key=lambda s: (priority_order.get(s.priority, 2), s.name))
    return skills


# ============================================================================
# Builders del system_prompt
# ============================================================================

def build_menu(skills: list[SkillMeta], max_chars_per_entry: int = 200) -> str:
    """Construye el menu compacto inyectado al system_prompt al boot.

    Una linea por skill: `- **name** [tag]: description`. El LLM ve esto
    y emite skill_load(name="X") cuando quiere usar uno.

    Critical skills aparecen con tag [ALWAYS LOADED] (eager).
    Resto aparecen con [lazy, priority=X].
    """
    if not skills:
        return ""
    lines = [
        "\n# SKILLS AVAILABLE",
        "Call `skill_load(name=\"<skill-name>\")` to load the full recipe.",
        "Critical skills are already loaded as constraints.",
        "",
    ]
    for s in skills:
        if s.priority == "critical":
            tag = "[ALWAYS LOADED]"
        else:
            tag = f"[lazy, priority={s.priority}]"
        desc = s.description.replace("\n", " ").strip()[:max_chars_per_entry]
        lines.append(f"- **{s.name}** {tag}: {desc}")
    return "\n".join(lines) + "\n"


def build_critical_block(skills: list[SkillMeta]) -> str:
    """Concatena full body de skills con priority=critical."""
    critical = [s for s in skills if s.priority == "critical"]
    if not critical:
        return ""
    parts = ["\n# CRITICAL SKILLS (always active)"]
    for s in critical:
        parsed = _parse_skill_md(s.path)
        if parsed is None:
            continue
        _, body = parsed
        parts.append(f"\n\n## {s.name}\n{body}")
    return "".join(parts)


def load_skill_content(
    name: str,
    skills_dir: Optional[Path] = None,
) -> Optional[str]:
    """Carga el body completo de un SKILL.md por name.

    Llamado por la tool skill_load cuando el LLM lo pide.
    Devuelve None si el skill no existe o falla el parsing.
    """
    if not _enabled():
        return None
    if skills_dir is None:
        skills_dir = _default_skills_dir()
    # name puede venir como "install-steam-game"; folder es igual.
    if not _is_valid_skill_name(name):
        return None
    skill_md = skills_dir / name / "SKILL.md"
    if not skill_md.is_file():
        return None
    parsed = _parse_skill_md(skill_md)
    if parsed is None:
        return None
    return parsed[1]


# ============================================================================
# Cap helpers
# ============================================================================

def get_skill_cap(profile_name: str) -> int:
    """Cuantas skill_load() puede emitir el LLM en un turn por profile."""
    return CAP_PER_PROFILE.get(profile_name, 3)


# ============================================================================
# CLI helper para debug
# ============================================================================

def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            enc = (sys.stdout.encoding or "utf-8")
            print(text.encode(enc, errors="replace").decode(enc, errors="replace"))
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii"))


def _cli_list() -> int:
    skills = scan_skills()
    if not skills:
        _safe_print("No skills found.")
        return 0
    _safe_print(f"Loaded {len(skills)} skill(s):\n")
    for s in skills:
        _safe_print(f"  - {s.name} (priority={s.priority})")
        _safe_print(f"      description: {s.description[:120]}")
        if s.requires:
            _safe_print(f"      requires:    {s.requires}")
    _safe_print("")
    _safe_print("Menu preview:")
    _safe_print(build_menu(skills))
    return 0


def _cli_load(name: str) -> int:
    body = load_skill_content(name)
    if body is None:
        _safe_print(f"Skill '{name}' not found or disabled.")
        return 1
    _safe_print(body)
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="gemma4_agent.skills_registry")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="Listar skills cargados + menu preview")
    load_p = sub.add_parser("load", help="Imprimir el body de un skill")
    load_p.add_argument("name", help="Nombre del skill (folder name)")
    args = p.parse_args(argv)
    if args.cmd == "list" or args.cmd is None:
        return _cli_list()
    if args.cmd == "load":
        return _cli_load(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
