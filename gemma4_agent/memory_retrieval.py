"""Memoria en capas para el prompt (investigación 2, §1) — core + retrieval.

PROBLEMA: hoy memory.prompt_summary() vuelca TODOS los hechos al system prompt
cada turno. Con ≤10 hechos relevantes va bien; cuando crece (la visión de RED:
>50 contactos, >30 apps, >100 artistas) infla el prompt y mete ruido que el 4B
no necesita para ESTE turno (Letta/LoCoMo 2025: retrieval simple bien hecho >
volcado plano). Cada token pinned reduce calidad en un 4B.

SOLUCIÓN (3 capas, sin self-editing — un 4B Q4 no razona fiable "qué guardar"):
  - CORE (siempre): identidad estable del usuario (nombre, idioma, zona, alias
    críticos tipo "mamá"). Pocos, siempre inyectados.
  - RETRIEVAL (por turno): top-k hechos SEMÁNTICAMENTE relevantes al enunciado
    actual. Solo cuando el store es grande; si es chico, se inyecta todo (cero
    riesgo, == comportamiento previo).
  - EPISODIC: el ExperienceMemory ya existente (no se toca acá).

UNIVERSAL: el retrieval usa el encoder multilingüe que ya está en el proyecto
(semantic_router.embed), NO keywords español. [[feedback_no_monolingual_regex]]
FALLBACK SEGURO: sin encoder o ante la duda -> inyectar todo (nunca esconder un
hecho que podría importar). Cabe en vram4 (encode cacheado, K chico).
"""
from __future__ import annotations

from typing import Any

# Si hay <= esto hechos, inyectamos TODOS (no vale la pena retrieval; el costo de
# perder un hecho relevante supera el de unos tokens extra). Medido: el store
# real hoy tiene ~6. El retrieval recién aporta cuando crece.
_INLINE_ALL_THRESHOLD = 12
# Cuántos hechos relevantes traer cuando el store es grande (además del core).
_RETRIEVAL_TOP_K = 6
# Piso de similitud coseno para considerar un hecho RELEVANTE al turno. Por
# debajo es ruido; mejor no inyectarlo. Conservador.
_RELEVANCE_FLOOR = 0.25

# Keys (o sufijos tras "auto:") que son IDENTIDAD ESTABLE -> siempre core.
# Multilingüe a propósito (el extractor puede nombrarlas en varios idiomas).
_CORE_KEY_HINTS = (
    "nombre", "name", "nome", "idioma", "language", "lang", "lengua",
    "zona", "timezone", "tz", "ubicacion", "ubicación", "location", "ciudad",
    "city", "pais", "país", "country",
    # alias de personas críticas
    "mama", "mamá", "papa", "papá", "mom", "dad", "jefe", "boss", "pareja",
    "esposa", "esposo", "wife", "husband", "hijo", "hija",
)


def _is_core(key: str) -> bool:
    """True si el hecho es identidad estable (siempre inyectado)."""
    k = key.lower()
    bare = k[5:] if k.startswith("auto:") else k
    # explicit (no auto:) se trata como core: el usuario lo guardó a propósito.
    if not k.startswith("auto:"):
        return True
    return any(hint in bare for hint in _CORE_KEY_HINTS)


def _fact_line(key: str, entry: dict[str, Any]) -> str:
    return f"- {key}: {entry.get('value', '')}"


def build_memory_section(items: dict[str, dict[str, Any]],
                         user_text: str | None) -> str:
    """Devuelve el bloque de memoria para el prompt: core (siempre) + relevantes
    al turno (retrieval). Nunca lanza; ante cualquier problema, vuelca todo."""
    if not items:
        return "No persistent memory saved."

    # Store chico -> inyectar todo (igual que antes, sin riesgo).
    if len(items) <= _INLINE_ALL_THRESHOLD:
        return "\n".join(_fact_line(k, v) for k, v in sorted(items.items()))

    core = {k: v for k, v in items.items() if _is_core(k)}
    rest = {k: v for k, v in items.items() if k not in core}

    relevant = _retrieve_relevant(rest, user_text)
    # Si el retrieval no está disponible (sin encoder), fallback seguro: volcar
    # todo (nunca esconder hechos a ciegas).
    if relevant is None:
        return "\n".join(_fact_line(k, v) for k, v in sorted(items.items()))

    chosen = {**core, **relevant}
    if not chosen:
        # nada core y nada relevante: al menos el core vacío -> volcar todo por
        # seguridad (no dejar al modelo sin contexto).
        return "\n".join(_fact_line(k, v) for k, v in sorted(items.items()))
    lines = [_fact_line(k, v) for k, v in sorted(chosen.items())]
    hidden = len(items) - len(chosen)
    if hidden > 0:
        lines.append(f"- (+{hidden} hechos guardados no relevantes a este turno; "
                     "usá memory.recall si los necesitás)")
    return "\n".join(lines)


def _retrieve_relevant(rest: dict[str, dict[str, Any]],
                       user_text: str | None) -> dict[str, dict[str, Any]] | None:
    """Top-k de `rest` por similitud semántica al user_text. None si no hay
    encoder (-> el caller hace fallback a volcar todo). Dict vacío si hay encoder
    pero nada supera el piso de relevancia."""
    if not rest:
        return {}
    txt = (user_text or "").strip()
    if not txt:
        return {}  # sin turno, no hay con qué rankear -> solo core
    try:
        from . import semantic_router as sr
        import numpy as np
        qe = sr.embed(txt)
        if qe is None:
            return None  # sin encoder -> fallback a todo
        qe = np.asarray(qe, dtype="float32")
        scored: list[tuple[float, str]] = []
        for k, v in rest.items():
            # embebemos "key: value" (la key da contexto: 'plataforma: disney').
            doc = f"{k.replace('auto:', '').replace('_', ' ')}: {v.get('value', '')}"
            de = sr.embed(doc)
            if de is None:
                continue
            de = np.asarray(de, dtype="float32")
            scored.append((float(qe @ de), k))
        scored.sort(key=lambda t: -t[0])
        top = {k: rest[k] for s, k in scored[:_RETRIEVAL_TOP_K]
               if s >= _RELEVANCE_FLOOR}
        return top
    except Exception:
        return None
