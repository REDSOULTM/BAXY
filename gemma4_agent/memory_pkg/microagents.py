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
    python -m gemma4_agent.memory_pkg.microagents --list
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

import numpy as np  # dep core (ya cargada en runtime); usada en select_microagents

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
    # Selección SEMÁNTICA. `examples` son frases multilingües que el usuario
    # diría para necesitar este microagent — se embeben y scorean por coseno
    # multi-vector (igual que skills). Reemplaza el substring matching de
    # `triggers`, que daba FP graves ("RAG" ⊂ "Dragon", "que es" ⊂ "estoy").
    # `triggers` se mantiene como guarda LÉXICA word-boundary (no substring) SOLO
    # para términos técnicos exactos (siglas universales: HKCR, GGUF, VRAM) que un
    # encoder de intención no captura. Ver documentacion/router/08_MICROAGENT_*.
    examples: tuple[str, ...] = ()


# ============================================================================
# Frontmatter parser (subset YAML)
# ============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _split_inline_list(inner: str) -> list[str]:
    """Parte una lista YAML inline `"a, b", "c"` por comas TOP-LEVEL, respetando
    las comillas. Un `re.split(r",\\s*", inner)` ingenuo parte también las comas
    DENTRO de un string entre comillas ("qué hacés, mostrame" → 2 items en vez de
    1, duplicando `examples`). Acá una coma dentro de comillas no parte."""
    items: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in inner:
        if quote is not None:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in ('"', "'"):
            quote = ch
        elif ch == ",":
            part = "".join(buf).strip()
            if part:
                items.append(part)
            buf = []
        else:
            buf.append(ch)
    part = "".join(buf).strip()
    if part:
        items.append(part)
    return items


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
            meta[k] = _split_inline_list(inner)
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
    """Directorio default: gemma4_agent/microagents/ (vive en el paquete padre)."""
    return Path(__file__).parent.parent / "microagents"


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
        triggers = [str(t) for t in triggers_raw if str(t).strip()] \
            if isinstance(triggers_raw, (list, tuple)) else []
        examples_raw = meta.get("examples") or []
        examples = tuple(
            str(e).strip() for e in examples_raw if str(e).strip()
        ) if isinstance(examples_raw, (list, tuple)) else ()
        # Un microagent es válido si tiene name + (examples semánticos O
        # triggers léxicos): basta cualquiera de los dos mecanismos de match.
        if not name or (not triggers and not examples):
            logger.warning(
                "microagent missing name/(examples|triggers): %s", path.name)
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
            examples=examples,
        ))
    _MICROAGENT_CACHE[cache_key] = (sig, out)
    return out


# ============================================================================
# Selector
# ============================================================================

_MA_EMB_CACHE: dict = {}


def reset_microagent_emb_cache() -> None:
    _MA_EMB_CACHE.clear()


def _ma_semantic_threshold() -> float:
    """Umbral de coseno para disparar un microagent por intención semántica.
    Calibrado sobre mensajes reales. Gate GEMMA4_MICROAGENT_THRESHOLD."""
    try:
        return float(os.environ.get("GEMMA4_MICROAGENT_THRESHOLD", "0.60"))
    except ValueError:
        return 0.60


def _ma_semantic_margin() -> float:
    """Margen top1−top2 para abstención (evita inyectar 2 microagents que
    empatan ambiguamente). Gate GEMMA4_MICROAGENT_MARGIN."""
    try:
        return float(os.environ.get("GEMMA4_MICROAGENT_MARGIN", "0.03"))
    except ValueError:
        return 0.03


# Tokeniza en palabras Unicode-aware (letras+dígitos), para word-boundary
# matching SIN substring. "RAG" NO matchea dentro de "Dragon"; "VRAM" sí matchea
# como palabra suelta. Universal (siglas técnicas son iguales en todo idioma) —
# NO es una lista de keywords por idioma, es una guarda de FORMA (límite de token).
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _word_boundary_hit(trigger: str, text_words: set[str], text_folded: str) -> bool:
    """True si `trigger` aparece en el texto respetando límites de palabra.
    Para triggers de UNA palabra: la palabra debe estar entre las tokens del
    texto (no como substring). Para triggers multi-palabra (frase): se exige la
    frase folded delimitada por espacios (no substring de una palabra mayor)."""
    tf = _fold(trigger)
    parts = tf.split()
    if len(parts) == 1:
        return tf in text_words
    return f" {tf} " in f" {text_folded} "


def select_microagents(
    user_text: str,
    microagents: list[Microagent],
    *,
    max_microagents: int = 3,
    embed_fn=None,
) -> list[Microagent]:
    """Elige hasta `max_microagents` microagents relevantes al user_text.

    DOS mecanismos, ambos multilingües/estructurales, NO substring matching
    (que da FP graves: "RAG" ⊂ "Dragon", "que es" ⊂ "estoy"):

      1. SEMÁNTICO (primario): si el microagent tiene `examples`, se embeben y se
         scorea coseno multi-vector MAX contra la query. Dispara si top ≥ umbral
         Y gap top1−top2 ≥ margen (abstención calibrada). Multilingüe vía el
         encoder. Requiere embed_fn; sin encoder, se omite (fallback a léxico).

      2. LÉXICO word-boundary (secundario): los `triggers` se matchean por LÍMITE
         DE PALABRA (no substring). Reservado para términos técnicos exactos
         (siglas universales HKCR/GGUF/VRAM) que el encoder de intención no capta.
         Por límite de palabra, "House of Dragon" no dispara "RAG".

    Sort por priority (high → medium → low), tie-break alfabético. Fallback
    seguro: sin encoder y sin triggers → no dispara (no inyecta ruido)."""
    if not user_text or not microagents:
        return []
    text_folded = _fold(user_text)
    text_words = {_fold(w) for w in _WORD_RE.findall(user_text)}
    matched: dict[str, Microagent] = {}

    # --- 2. Léxico word-boundary (rápido, siempre disponible) ---
    for ma in microagents:
        for trig in ma.triggers:
            if _word_boundary_hit(trig, text_words, text_folded):
                matched[ma.name] = ma
                break

    # --- 1. Semántico (si hay encoder) ---
    sem = [ma for ma in microagents if ma.examples]
    if embed_fn is not None and sem:
        try:
            def _emb(t):
                v = embed_fn(t)
                if v is None:
                    return None
                v = np.asarray(v, dtype="float32")
                n = float(np.linalg.norm(v))
                return v / n if n else v

            q = _emb(user_text)
            if q is not None:
                scored = []
                for ma in sem:
                    vecs = _MA_EMB_CACHE.get(ma.name)
                    if vecs is None:
                        vecs = [e for e in (_emb(x) for x in ma.examples)
                                if e is not None]
                        if not vecs:
                            continue
                        _MA_EMB_CACHE[ma.name] = vecs
                    sim = max(float(q @ v) for v in vecs)
                    scored.append((sim, ma))
                scored.sort(key=lambda t: t[0], reverse=True)
                thr = _ma_semantic_threshold()
                mgn = _ma_semantic_margin()
                if scored:
                    top_sim, top = scored[0]
                    second = scored[1][0] if len(scored) > 1 else 0.0
                    if top_sim >= thr and (top_sim - second) >= mgn:
                        matched[top.name] = top
        except Exception:
            pass

    out = list(matched.values())
    priority_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda m: (priority_order.get(m.priority, 1), m.name))
    return out[:max_microagents]


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

def _default_embed_fn():
    """Encoder multilingüe del proyecto (mismo que skills/router). None si no
    carga (fallback seguro: el selector cae a léxico word-boundary)."""
    try:
        from ..routing.semantic_router import embed
        return embed
    except Exception:
        return None


def build_microagents_section(
    user_text: str,
    *,
    cached: list[Microagent] | None = None,
    max_microagents: int = 3,
    embed_fn=None,
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
    if embed_fn is None:
        embed_fn = _default_embed_fn()
    matched = select_microagents(
        user_text or "", all_ma,
        max_microagents=max_microagents, embed_fn=embed_fn)

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
