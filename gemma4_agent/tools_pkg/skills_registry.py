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
# turn. Escala con el context_size del perfil. standby NO carga skills.
# 2026-05-26: colapsado a un solo perfil operante (vram4, ctx 16K) + standby.
# vram4 = 3 (coherente con su ctx 16K — antes ese tier era el de vram8). Las
# claves legacy y los nombres viejos por-VRAM se mantienen como alias -> 3 para
# no romper callers viejos; cualquier clave desconocida cae al default 3
# (ver _cap_for_profile abajo).
CAP_PER_PROFILE: dict[str, int] = {
    "standby":      0,
    "vram4":        3,   # ctx 16K (único perfil)
    # aliases legacy / nombres viejos por-VRAM -> mismo cap que vram4
    "vram3":        3,
    "vram6":        3,
    "vram8":        3,
    "vram12":       3,
    "vram16":       3,
    "light":        3,
    "balanced":     3,
    "balanced_8gb": 3,
    "performance":  3,
}


@dataclass(frozen=True)
class SkillMeta:
    """Metadata de un skill (no incluye el body — lazy).

    `examples` (R3, 2026-05-30): fraseos de ejemplo que el usuario diría para
    disparar la skill. NO son keywords — son queries semánticas multilingües que
    el auto-inject embebe como VECTORES SEPARADOS y scorea por MAX contra la
    query (técnica Re-Invoke / document-expansion, arXiv:2408.01875). Resuelve
    el intent-mismatch medido ("investiga"→debug) y el recall bajo de la
    descripción abstracta. Ver documentacion/router/07_SKILL_RETRIEVAL_research.md.
    """
    name: str
    description: str
    priority: Priority
    path: Path              # ruta al SKILL.md
    requires: dict = field(default_factory=dict)
    examples: tuple[str, ...] = ()
    # Document-expansion (R3.2, 2026-05-30, arXiv:2510.22670 "Tools are
    # under-documented"). Dos campos en prosa natural multilingüe — NO keyword
    # lists:
    #   when_to_use: fraseos/situaciones POSITIVAS extra. Se suman al pool de
    #     vectores MAX (refuerzan el recall del intent correcto).
    #   limitations: fraseos de lo que la skill NO cubre ("no para imprimir, no
    #     para subir brillo"). Se embeben como vectores de PENALIZACIÓN: si la
    #     query matchea más un `limitations` que el mejor positivo, se suprime el
    #     disparo. Resuelve el hard-negative de solapamiento por sustantivo
    #     (brillo/pantalla, mutea/micrófono) que un umbral global no separa
    #     (TP 0.457 < FP 0.656 medido). Ver
    #     documentacion/router/07_SKILL_RETRIEVAL_research.md.
    when_to_use: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


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


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_yaml_simple(text: str) -> dict:
    """YAML subset que cubre frontmatter de SKILL.md:
       - scalars
       - inline lists `key: [a, b]`
       - block sub-dict/sub-lists indentados con "  "
       - block sub-dict CON sub-listas anidadas (`metadata:` con `examples:`,
         `when_to_use:`, `limitations:` cada uno con items `- `) — R3.2
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
            # Block sub-dict o sub-lista. Puede contener sub-claves con sus
            # propias sub-listas anidadas (2 niveles), p.ej.:
            #   metadata:
            #     examples:
            #       - a
            #     limitations:
            #       - b
            base_indent = _indent(line)
            sub_items: list = []
            sub_dict: dict = {}
            i += 1
            while i < len(lines):
                sub_line = lines[i]
                if sub_line.strip() and _indent(sub_line) <= base_indent:
                    break
                stripped = sub_line.strip()
                if not stripped:
                    i += 1
                    continue
                if stripped.startswith("- "):
                    sub_items.append(stripped[2:].strip().strip('"').strip("'"))
                    i += 1
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
                        i += 1
                    elif sv == "":
                        # sub-clave con su propia sub-lista anidada
                        sub_indent = _indent(sub_line)
                        nested: list[str] = []
                        i += 1
                        while i < len(lines):
                            nl = lines[i]
                            if nl.strip() and _indent(nl) <= sub_indent:
                                break
                            ns = nl.strip()
                            if ns.startswith("- "):
                                nested.append(ns[2:].strip().strip('"').strip("'"))
                            i += 1
                        sub_dict[sk] = nested
                    else:
                        sub_dict[sk] = sv.strip('"').strip("'")
                        i += 1
                else:
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


def _extract_meta_list(meta_dict: dict, key: str) -> tuple[str, ...]:
    """Lee una sub-lista (`examples`, `when_to_use`, `limitations`) del
    frontmatter, tolerante a las variantes del parser simple:
      - `metadata: {<key>: [a, b]}`  (estándar Anthropic, dict)  ← caso actual
      - `<key>: [a, b]` top-level (legacy)
      - SOLO para `examples`: `metadata:` aplanado a lista por parsers viejos.
    Devuelve tupla de strings no vacíos."""
    raw = None
    md = meta_dict.get("metadata")
    if isinstance(md, dict) and md.get(key):
        raw = md[key]
    elif key == "examples" and isinstance(md, list) and md:
        # Compat: parser viejo aplanaba `metadata:\n examples:\n - a` a lista.
        raw = md
    elif meta_dict.get(key):
        raw = meta_dict[key]
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(e).strip() for e in raw if str(e).strip())


def _extract_examples(meta_dict: dict) -> tuple[str, ...]:
    """Back-compat wrapper: fraseos `examples` para el auto-inject multi-vector."""
    return _extract_meta_list(meta_dict, "examples")


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
    """Default: gemma4_agent/skills/ (reorg 2026-05-28: ahora en el paquete padre)."""
    return Path(__file__).parent.parent / "skills"


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_SKILLS_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


# Cache de scan_skills: evita re-leer+parsear las carpetas SKILL.md de disco cada
# turno (_system_message corre por turno; ver test_perf_budget). Keyed por (dir,
# mtime-del-dir) -> se invalida al agregar/quitar/renombrar skills, o vía
# reset_autoinject_cache(). Edits de contenido dentro de una skill existente se ven
# al reiniciar (skills estáticas en runtime).
_SCAN_CACHE: dict = {}


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

    _cache_key = None
    try:
        _cache_key = (str(skills_dir.resolve()), skills_dir.stat().st_mtime_ns)
        _cached = _SCAN_CACHE.get(_cache_key)
        if _cached is not None:
            return _cached
    except OSError:
        _cache_key = None

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
            # examples (R3): fraseos de ejemplo multilingües para el auto-inject
            # multi-vector. Estándar Anthropic Agent Skills: campos custom van bajo
            # `metadata:`. Aceptamos `metadata.examples` (estándar) o `examples`
            # top-level (legacy). El parser simple aplana `metadata:\n examples:\n
            # - a\n - b` a una lista directa -> también lo tomamos.
            examples_raw = _extract_examples(meta_dict)
            # Document-expansion (R3.2): when_to_use (positivo extra) +
            # limitations (negativo estructural). Prosa multilingüe, no keywords.
            when_to_use_raw = _extract_meta_list(meta_dict, "when_to_use")
            limitations_raw = _extract_meta_list(meta_dict, "limitations")
            skills.append(SkillMeta(
                name=name,
                description=description,
                priority=priority,  # type: ignore[arg-type]
                path=skill_md,
                requires=requires,
                examples=examples_raw,
                when_to_use=when_to_use_raw,
                limitations=limitations_raw,
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill frontmatter invalido en %s: %s", skill_md, exc)
            continue

    # Filter eligibility ANTES de sort para no contar las que no aplican
    skills = [s for s in skills if check_skill_eligibility(s)]
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    skills.sort(key=lambda s: (priority_order.get(s.priority, 2), s.name))
    if _cache_key is not None:
        _SCAN_CACHE[_cache_key] = skills
    return skills


# ============================================================================
# Builders del system_prompt
# ============================================================================

# R1 (2026-05-30): el menú "# SKILLS AVAILABLE" ocupaba ~558 tokens en CADA
# turno del system prompt y le decía al 4B "llamá skill_load(...)". MEDIDO sobre
# 117.764 eventos reales: el 4B emite skill_load 1 SOLA vez — no hace el meta-paso
# "ver menú → cargar → seguir". Las skills lazy YA entran por AUTO-INJECT
# (autoinject_skill por embeddings, 41 disparos reales), que NO depende de que el
# 4B decida. Y la skill `purchase-guard` (critical, seguridad) entra por
# build_critical_block, NO por este menú. Conclusión: el menú es ~558 tok/turno de
# ruido puro que el 4B ignora. DEFAULT OFF (menú vacío). Gate GEMMA4_SKILLS_MENU=1
# lo restaura (por si un modelo futuro sí usa skill_load).
def _menu_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_SKILLS_MENU") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def build_menu(skills: list[SkillMeta], max_chars_per_entry: int = 200) -> str:
    """Construye el menu compacto inyectado al system_prompt al boot.

    R1 (2026-05-30): DEFAULT vacío. El 4B no emite skill_load (1/117.764); las
    skills entran por auto-inject. El menú solo gastaba ~558 tok/turno. Restaurar
    con GEMMA4_SKILLS_MENU=1 (un modelo más grande sí lo aprovecharía).

    Cuando está habilitado: una linea por skill `- **name** [tag]: description`.
    Critical skills con [ALWAYS LOADED], resto [lazy, priority=X].
    """
    if not skills or not _menu_enabled():
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
# Trigger-inject semántico (2026-05-29)
# ============================================================================
# MEDIDO en vivo: el 4B NUNCA emite skill_load (0/5 con pedidos directos, 0/6727
# en prod) — no hace el meta-paso "cargar receta -> seguirla" (2 pasos, y el 4B no
# encadena). Igual que data_analysis/document. Fix consistente con la lección
# (auto-inyectar lo que el 4B no pide): si el pedido matchea SEMÁNTICAMENTE la
# description de una skill (embeddings multilingües, NO keywords), inyectamos la
# receta al prompt automáticamente. Umbral 0.45 calibrado (scripts/_calibrate_skills_match.py):
# matches reales 0.50-0.73, charla/control <0.21.
_DESC_EMB_CACHE: dict = {}


def reset_autoinject_cache() -> None:
    _DESC_EMB_CACHE.clear()
    _SCAN_CACHE.clear()


def _autoinject_threshold() -> float:
    """Umbral absoluto del auto-inject multi-vector. RECALIBRADO 0.45→0.62 (R3,
    2026-05-30) al pasar a multi-vector; con `limitations`+gap-rule (R3.2) el
    umbral absoluto baja un poco (0.58) porque el gap relativo y la supresión por
    negativos hacen el trabajo fino, no el umbral solo. Gate GEMMA4_SKILLS_THRESHOLD."""
    import os as _os_th
    try:
        return float(_os_th.environ.get("GEMMA4_SKILLS_THRESHOLD", "0.58"))
    except ValueError:
        return 0.58


def _autoinject_margin() -> float:
    """Margen mínimo top1−top2 (gap-rule, arXiv:2410.02914 score-refinement). El
    síntoma medido — un TP legítimo (0.457) puntúa MÁS BAJO que un FP por
    solapamiento de sustantivo (0.656) — prueba que el umbral ABSOLUTO es el
    estadístico equivocado. El gap relativo entre la mejor skill y la segunda es
    robusto a ese solapamiento: si dos skills empatan alto, ninguna es claramente
    la correcta → abstener. Gate GEMMA4_SKILLS_MARGIN."""
    import os as _os_th
    try:
        return float(_os_th.environ.get("GEMMA4_SKILLS_MARGIN", "0.05"))
    except ValueError:
        return 0.05


def _autoinject_neg_guard() -> float:
    """Cuánto margen necesita un `limitations` (negativo) sobre el positivo para
    SUPRIMIR la skill. Si el match a "lo que la skill NO hace" supera al positivo
    por este margen, la skill se descarta. 0.0 = suprime si neg≥pos. Gate
    GEMMA4_SKILLS_NEGGUARD."""
    import os as _os_th
    try:
        return float(_os_th.environ.get("GEMMA4_SKILLS_NEGGUARD", "0.0"))
    except ValueError:
        return 0.0


def _skill_vectors(s, _emb):
    """Vectores (pos, neg) de una skill, cacheados. pos = description + examples
    + when_to_use (Re-Invoke multi-vector). neg = limitations (hard-negatives en
    prosa, arXiv:2510.22670). Lista vacía si el encoder falló para todos."""
    cached = _DESC_EMB_CACHE.get(s.name)
    if cached is not None:
        return cached
    pos = []
    for text in (s.description, *s.examples, *getattr(s, "when_to_use", ())):
        e = _emb(text)
        if e is not None:
            pos.append(e)
    neg = []
    for text in getattr(s, "limitations", ()):
        e = _emb(text)
        if e is not None:
            neg.append(e)
    cached = (pos, neg)
    _DESC_EMB_CACHE[s.name] = cached
    return cached


def autoinject_skill(user_text: str, skills, *, embed_fn, threshold: float | None = None):
    """Devuelve (name, recipe_body) de la skill NON-critical que mejor matchea
    user_text, o (None, '') si ninguna supera el gate. Tres mecanismos, todos
    embeddings/estructurales (NO keyword lists), todos CPU, fallback seguro:

    1. MULTI-VECTOR MAX (Re-Invoke arXiv:2408.01875): cada skill = varios vectores
       POSITIVOS (description + examples + when_to_use). Score = MAX coseno. NO se
       promedia (concatenar DILUYE — Tool-DE arXiv:2510.22670).
    2. SUPRESIÓN POR `limitations` (hard-negatives en prosa, arXiv:2510.22670):
       cada skill tiene vectores de lo que NO hace ("no para imprimir, no para
       subir brillo"). Si la query matchea MÁS un negativo que el mejor positivo,
       la skill se SUPRIME. Resuelve el solapamiento por sustantivo (pantalla→
       brillo, micrófono→mutear) que un umbral global no separa.
    3. GAP-RULE / margin (score-refinement arXiv:2410.02914): dispara solo si
       top1 ≥ threshold Y (top1 − top2) ≥ margin. El gap relativo es robusto al
       caso medido TP 0.457 < FP 0.656: si dos skills empatan alto, abstiene.

    Multilingüe (es/en/pt). Ver documentacion/router/07_SKILL_RETRIEVAL_research.md."""
    import numpy as np
    if threshold is None:
        threshold = _autoinject_threshold()
    margin = _autoinject_margin()
    neg_guard = _autoinject_neg_guard()
    txt = (user_text or "").strip()
    if len(txt) < 6 or embed_fn is None:
        return None, ""
    cands = [s for s in skills if s.priority != "critical"]
    if not cands:
        return None, ""

    def _emb(t):
        v = embed_fn(t)
        if v is None:
            return None
        v = np.asarray(v, dtype="float32")
        n = float(np.linalg.norm(v))
        return v / n if n else v

    try:
        q = _emb(txt)
        if q is None:
            return None, ""
        scored = []  # (pos_sim, skill) — solo skills NO suprimidas por negativo
        for s in cands:
            pos, neg = _skill_vectors(s, _emb)
            if not pos:
                continue
            pos_sim = max(float(q @ v) for v in pos)
            # Supresión estructural: si la query se parece más a "lo que la skill
            # NO hace" que a lo que sí hace, descartar esta skill.
            if neg:
                neg_sim = max(float(q @ v) for v in neg)
                if neg_sim >= pos_sim - neg_guard:
                    continue
            scored.append((pos_sim, s))
        if not scored:
            return None, ""
        scored.sort(key=lambda t: t[0], reverse=True)
        top_sim, top = scored[0]
        second_sim = scored[1][0] if len(scored) > 1 else 0.0
        # Gate: umbral absoluto Y gap relativo sobre la 2da skill.
        if top_sim >= threshold and (top_sim - second_sim) >= margin:
            body = load_skill_content(top.name)
            if body:
                return top.name, body
    except Exception:
        pass
    return None, ""


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
