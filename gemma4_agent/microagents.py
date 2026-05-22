"""Microagents loader — markdown files conditionally injected to system prompt.

Pattern adoptado de OpenHands (`.openhands/microagents/`). Cada microagent es
un archivo markdown con frontmatter YAML declarando `name`, `triggers` (lista
de substrings) y `priority`. Cuando ALGUNA palabra del trigger matchea el
user_text del turn, el body del markdown se appendea al system_prompt como
"# CONTEXT MICROAGENTS / ## <name>".

Diferencia ortogonal con TOOL_RULES (agent.py):
  - TOOL_RULES["smart_home"]: cómo usar la tool smart_home cuando esta en el
    subset del router (regla de uso).
  - microagent glossary.md: qué SIGNIFICA "HKCR", "mmproj", "deeplink"
    (conocimiento de dominio).

Ambos coexisten en el system_prompt sin colisión.

Cache:
  Por defecto los microagents que matchearon en el primer turn de la sesión
  se cachean para los turns siguientes (mismo system_prompt = KV cache hit
  en llama-server). Si el usuario inicia un tema nuevo, los microagents
  matched del nuevo turn se mergean con los del cache (deduplicados por
  name) y se mantienen.

  Para invalidar el cache: `agent.clear()` lo resetea junto con history.

Opt-out: GEMMA4_MICROAGENTS_OFF=1 desactiva todo el sistema.

Cap defensivo:
  - max_microagents=3 por selección (evita inflar el system_prompt con
    demasiados glossaries en una pregunta ambigua).
  - Soft warning si un microagent body supera 2000 chars.

Formato esperado:

    ---
    name: glossary
    triggers: ["qué significa", "que significa", "vocabulario"]
    priority: medium
    ---

    # Glossary
    - **HKCR**: ...

Run-test rápido:
    python -m gemma4_agent.microagents --list
"""
from __future__ import annotations

import logging
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Datatype
# ============================================================================

@dataclass(frozen=True)
class Microagent:
    name: str
    triggers: list[str]
    priority: str            # "high" | "medium" | "low"
    content: str             # body markdown (sin frontmatter)
    source_path: Optional[Path] = None


# ============================================================================
# Frontmatter parser (subset YAML)
# ============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> Optional[tuple[dict, str]]:
    """Parse el frontmatter YAML simple. Soporta:
      - scalars (string entre comillas o sin)
      - listas inline: triggers: ["a", "b"]
      - booleans (true/false)
    """
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return None
    fm_raw = m.group(1)
    body = m.group(2)
    meta: dict = {}
    for line in fm_raw.splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            items: list[str] = []
            for part in re.split(r",\s*", inner):
                p = part.strip().strip('"').strip("'")
                if p:
                    items.append(p)
            meta[k] = items
        elif v.lower() in {"true", "false"}:
            meta[k] = (v.lower() == "true")
        else:
            meta[k] = v.strip('"').strip("'")
    return meta, body


# ============================================================================
# Folding (case + accent insensitive matching)
# ============================================================================

def _fold(s: str) -> str:
    """Lowercase + remove diacritics. "Qué Significa" -> "que significa"."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower()


# ============================================================================
# Loader
# ============================================================================

def _default_microagents_dir() -> Path:
    """Directorio default: gemma4_agent/microagents/ (sibling de este modulo)."""
    return Path(__file__).parent / "microagents"


# PERF (latencia, hot-path): build_microagents_section corre en CADA turno y
# llamaba load_microagents(), que re-leía y re-parseaba TODOS los *.md del disco
# (medido: ~1.13 ms/turno, >50% del costo de _system_message — 1400 read_text +
# 2800 stat en un profile de 200 turnos). Los microagents casi nunca cambian.
# Cacheamos el resultado por una FIRMA del directorio: {(name, mtime_ns, size)}
# de cada *.md. Recomputar la firma es solo stat (barato); re-leemos los cuerpos
# SOLO cuando la firma cambia. Esto preserva el live-edit (agregar/editar/borrar
# un microagent se refleja al siguiente turno, igual que antes) sin pagar el
# read+parse en cada turno. Cache por-directorio (normalmente uno solo).
_MICROAGENT_CACHE: dict[str, tuple[frozenset, list["Microagent"]]] = {}


def _dir_signature(directory: Path) -> frozenset:
    """Stat-only fingerprint of the *.md files in `directory`. Changes iff a
    file is added, removed, resized, or its mtime moves (i.e. an edit)."""
    sig = set()
    try:
        for path in directory.glob("*.md"):
            if path.name.lower() in {"readme.md"}:
                continue
            try:
                st = path.stat()
                sig.add((path.name, st.st_mtime_ns, st.st_size))
            except OSError:
                # Unreadable mid-scan -> include the name so the signature still
                # changes when it appears/disappears; the read below will skip it.
                sig.add((path.name, -1, -1))
    except OSError:
        pass
    return frozenset(sig)


def load_microagents(directory: Path | None = None) -> list[Microagent]:
    """Carga todos los *.md del directorio (skips README.md y archivos sin frontmatter).

    Devuelve lista en orden alfabético por filename. Errores de parsing se
    loggean con warning y se skipean (nunca crashean el agente). El resultado se
    cachea por firma del directorio (mtime/size); se relee solo si algo cambió.
    """
    if directory is None:
        directory = _default_microagents_dir()
    if not directory.exists():
        return []
    sig = _dir_signature(directory)
    cache_key = str(directory)
    cached = _MICROAGENT_CACHE.get(cache_key)
    if cached is not None and cached[0] == sig:
        return cached[1]
    out: list[Microagent] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() in {"readme.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("microagent read failed: %s (%s)", path.name, exc)
            continue
        parsed = _parse_frontmatter(text)
        if parsed is None:
            logger.warning("microagent missing frontmatter: %s", path.name)
            continue
        meta, body = parsed
        name = str(meta.get("name") or "").strip()
        triggers_raw = meta.get("triggers") or []
        if not name or not triggers_raw:
            logger.warning("microagent missing name/triggers: %s", path.name)
            continue
        triggers = [str(t) for t in triggers_raw if str(t).strip()]
        if not triggers:
            logger.warning("microagent has empty triggers: %s", path.name)
            continue
        priority = str(meta.get("priority") or "medium").lower()
        if priority not in {"high", "medium", "low"}:
            priority = "medium"
        body_clean = body.strip()
        if len(body_clean) > 5000:
            logger.warning(
                "microagent body very large (%d chars): %s",
                len(body_clean), path.name,
            )
        out.append(Microagent(
            name=name,
            triggers=triggers,
            priority=priority,
            content=body_clean,
            source_path=path,
        ))
    _MICROAGENT_CACHE[cache_key] = (sig, out)
    return out


# ============================================================================
# Selector
# ============================================================================

def select_microagents(
    user_text: str,
    microagents: list[Microagent],
    *,
    max_microagents: int = 3,
) -> list[Microagent]:
    """Elige hasta `max_microagents` microagents cuyos triggers matchean el
    user_text. Matching es case+accent insensitive (fold).

    Sort por priority (high → medium → low), tie-break alfabético.
    """
    if not user_text or not microagents:
        return []
    text_folded = _fold(user_text)
    matched: list[Microagent] = []
    for ma in microagents:
        for trig in ma.triggers:
            if _fold(trig) in text_folded:
                matched.append(ma)
                break  # un match por microagent es suficiente
    priority_order = {"high": 0, "medium": 1, "low": 2}
    matched.sort(key=lambda m: (priority_order.get(m.priority, 1), m.name))
    return matched[:max_microagents]


# ============================================================================
# Format
# ============================================================================

def format_microagents_for_prompt(microagents: list[Microagent]) -> str:
    """Concatena microagents seleccionados como bloque markdown para el
    system_prompt. Vacío si la lista es vacía."""
    if not microagents:
        return ""
    parts: list[str] = ["\n\n# CONTEXT MICROAGENTS"]
    for ma in microagents:
        parts.append(f"\n\n## {ma.name}\n{ma.content}")
    return "".join(parts)


# ============================================================================
# Opt-out
# ============================================================================

def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_MICROAGENTS_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


# ============================================================================
# High-level API for agent.py
# ============================================================================

def build_microagents_section(
    user_text: str,
    *,
    cached: list[Microagent] | None = None,
    max_microagents: int = 3,
) -> tuple[str, list[Microagent]]:
    """Función de alto nivel para `agent._system_message()`.

    Args:
        user_text: texto del primer mensaje del turn (e.g. extraido del
            content del user). Si vacío o None → no se inyecta nada.
        cached: lista de microagents ya cacheados de turns anteriores. Se
            mantienen + se mergean con los nuevos matched (dedupe por name).
        max_microagents: cap total post-merge.

    Returns:
        (section_text, microagents_final). section_text se concatena al
        system_prompt. microagents_final se cachea para próximo turn.
    """
    if not _enabled():
        return "", []
    all_ma = load_microagents()
    matched = select_microagents(user_text or "", all_ma, max_microagents=max_microagents)

    if cached:
        # Merge: cached + matched, dedupe por name, mantener orden por
        # priority (matched fresco puede pasar a primera fila).
        seen_names = {m.name for m in matched}
        merged = list(matched)
        for c in cached:
            if c.name not in seen_names:
                merged.append(c)
                seen_names.add(c.name)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        merged.sort(key=lambda m: (priority_order.get(m.priority, 1), m.name))
        merged = merged[:max_microagents]
    else:
        merged = matched

    return format_microagents_for_prompt(merged), merged


# ============================================================================
# CLI helper para debug
# ============================================================================

def _cli_list() -> int:
    mas = load_microagents()
    if not mas:
        print("No microagents found.")
        return 0
    print(f"Loaded {len(mas)} microagent(s):\n")
    for ma in mas:
        size = len(ma.content)
        print(f"  - {ma.name} (priority={ma.priority}, {size} chars)")
        print(f"      triggers: {ma.triggers}")
    return 0


def _cli_test(text: str) -> int:
    mas = load_microagents()
    matched = select_microagents(text, mas)
    if not matched:
        _safe_print(f"No microagents matched user_text={text!r}")
        return 0
    _safe_print(f"Matched {len(matched)} microagent(s) for user_text={text!r}:")
    for ma in matched:
        _safe_print(f"  - {ma.name} (priority={ma.priority}, {len(ma.content)} chars)")
    section = format_microagents_for_prompt(matched)
    _safe_print("")
    _safe_print(section)
    _safe_print(f"\n--- section length: {len(section)} chars ---")
    return 0


def _safe_print(text: str) -> None:
    """Print que tolera consoles con encoding distinto a UTF-8 (Windows cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            enc = (sys.stdout.encoding or "utf-8")
            print(text.encode(enc, errors="replace").decode(enc, errors="replace"))
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii"))


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="gemma4_agent.microagents")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="Listar microagents cargados")
    test_p = sub.add_parser("test", help="Test trigger match con texto")
    test_p.add_argument("text", help="Texto del usuario simulado")
    args = p.parse_args(argv)
    if args.cmd == "list" or args.cmd is None:
        return _cli_list()
    if args.cmd == "test":
        return _cli_test(args.text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
