"""Camino C dinamico: set de tools CORE adaptado por usuario.

Disenio:
  - Boot del agente -> read_user_core_tools() lee ~/.gemma4/core_tools_pareto.json
    si existe. Sino, devuelve el default global (hardcoded en agent_prompt.py
    CORE_TOOL_RULE_NAMES).
  - Periodicamente (background, en otro thread del agente) ->
    recompute_and_persist() recorre el trace y calcula los top 15 por uso real
    del usuario.
  - Si el nuevo set difiere "lo suficiente" del cacheado (Jaccard < THRESHOLD),
    se persiste. Si no, se mantiene el viejo (evita churn por ruido).
  - La PROXIMA sesion del agente carga el set actualizado. La SESION ACTUAL
    queda con el set viejo (cache estable durante la sesion -> prefix-cache
    de llama-server alcanza ~87%).

NO se aplica el set nuevo en caliente porque:
  - cambiar las CORE_TOOL_RULES en medio de la sesion rompe el cache (Camino C
    se basa en bytes estables turno-a-turno)
  - el usuario no notaria nada inmediato salvo una latencia subida en el turn
    que cambio
  - mejor estabilidad: cambia entre sesiones donde el costo de reset es 1 turn

Histeresis (Jaccard threshold = 0.20): si el nuevo set comparte >=80% con el
viejo, NO actualizar. Asi un fin de semana atipico no contamina el set base.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


# Cuantos tools tener en el core (set always-on de tool-rules en el system
# prompt). Fijado en 6 (no 15): con 15 reglas always-on el piso del system
# prompt era ~9.4k tok -> CADA turno cruzaba la zona del crash CUDA #22527 (con
# FA on) y enlentecia el prefill (con FA off). Con 6 reglas el piso baja a ~5k
# tok; medido tool-calling EN VIVO 8/8 correcto, porque las reglas de los tools
# del subset se inyectan on-demand via build_tool_rules_extras_for_user_msg, asi
# que reducir el always-on NO quita guia a los tools del turno. Override:
# GEMMA4_CORE_RULES.
CORE_SIZE = 6

# Umbral de cambio: si el nuevo set comparte >=80% (Jaccard) con el viejo,
# NO actualizar. Evita churn por dia atipico.
JACCARD_PERSIST_THRESHOLD = 0.20

# Minimo de tool_calls historicos para considerar el set adaptado representativo.
# Por debajo de esto, usamos el default global.
MIN_HISTORICAL_CALLS = 100

_USER_HOME = Path.home() / ".gemma4"
_CORE_TOOLS_PATH = _USER_HOME / "core_tools_pareto.json"


def _default_core_tools() -> tuple[str, ...]:
    """Default global del set always-on: 6 tools universales por voz. El resto
    de las reglas se inyectan on-demand cuando su tool entra al subset del turno
    (extras en el user msg), asi que esto NO quita guia a
    media/browser/whatsapp/gui/etc cuando se usan. Medido EN VIVO: 8/8
    tool-calling correcto + piso del system prompt ~5k tok (vs ~9.4k con 15
    reglas always-on). Override explicito: GEMMA4_CORE_RULES=a,b,c."""
    return ("app", "audio", "session", "system", "web", "window")


def read_user_core_tools() -> tuple[str, ...]:
    """Lee el set CORE adaptado del usuario, o devuelve el default global.

    Llamado UNA VEZ al boot del agente. La sesion actual queda con este set
    fijo (no cambia turno-a-turno -> prefix-cache estable).
    """
    # Override explicito del set always-on via GEMMA4_CORE_RULES (lista
    # separada por comas). Achica el piso del system prompt (~9.4k tok con 15
    # reglas always-on) que empuja CADA turno a la zona del crash CUDA #22527 y
    # enlentece el prefill con flash-attn off. Las reglas de los tools del
    # subset SIGUEN incluyendose on-demand via
    # build_tool_rules_extras_for_user_msg, asi que reducir el set always-on no
    # quita guia a los tools relevantes del turno. Unset/vacio = default.
    # Fuentes: RAG-MCP (arXiv:2505.03275), EasyTool (arXiv:2401.06201) -> prompt
    # de tools mas corto = mas rapido Y mas preciso en modelos chicos.
    _override = (os.environ.get("GEMMA4_CORE_RULES") or "").strip()
    if _override:
        names = tuple(sorted(t.strip() for t in _override.split(",") if t.strip()))
        if names:
            return names
    if not _CORE_TOOLS_PATH.is_file():
        return _default_core_tools()
    try:
        data = json.loads(_CORE_TOOLS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("core_tools_pareto: read failed (%s); using default", exc)
        return _default_core_tools()
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, list) or len(tools) < 5:
        # Set chico/invalido -> default
        return _default_core_tools()
    # Sorted para garantizar bytes estables al construir el prompt
    return tuple(sorted(str(t) for t in tools if isinstance(t, str)))


def compute_core_tools_from_trace(
    trace_path: Path,
    *,
    size: int = CORE_SIZE,
    min_calls: int = MIN_HISTORICAL_CALLS,
) -> Optional[tuple[str, ...]]:
    """Recorre el trace.jsonl y devuelve los top `size` tools por uso real.

    Devuelve None si el trace tiene menos de `min_calls` tool_calls (no hay
    suficiente data del usuario para personalizar).
    """
    if not trace_path.is_file():
        return None
    counter: Counter[str] = Counter()
    try:
        with open(trace_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "tool_call" not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("kind") != "tool_call":
                    continue
                name = ev.get("name")
                if isinstance(name, str) and name:
                    counter[name] += 1
    except OSError as exc:
        logger.warning("compute_core_tools: trace read failed: %s", exc)
        return None
    total = sum(counter.values())
    if total < min_calls:
        return None
    top = [name for name, _ in counter.most_common(size)]
    # Si el counter dio MENOS que `size` items (universe de tools chico),
    # solo devolver si tenemos al menos min(5, size) — guard contra resultados
    # degenerados.
    min_tools = min(5, size)
    if len(top) < min_tools:
        return None
    return tuple(sorted(top))


def _jaccard_distance(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Distancia 1 - |A intersect B| / |A union B|. 0 = identicos, 1 = disjuntos."""
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        return 0.0
    inter = sa & sb
    return 1.0 - len(inter) / len(union)


def recompute_and_persist(
    trace_path: Path,
    *,
    size: int = CORE_SIZE,
    threshold: float = JACCARD_PERSIST_THRESHOLD,
) -> Optional[tuple[str, ...]]:
    """Recalcula el set CORE desde el trace y persiste si el cambio es
    suficiente (Jaccard distance >= threshold).

    Devuelve el set persistido (nuevo o viejo), o None si no se pudo computar.
    """
    new_set = compute_core_tools_from_trace(trace_path, size=size)
    if new_set is None:
        logger.info("core_tools_pareto: trace insuficiente, no actualizar")
        return None

    old_set = read_user_core_tools()
    distance = _jaccard_distance(old_set, new_set)
    if distance < threshold:
        logger.info(
            "core_tools_pareto: Jaccard=%.2f < %.2f, no persistir "
            "(set estable)", distance, threshold)
        return old_set

    # Persistir el nuevo set
    try:
        _USER_HOME.mkdir(parents=True, exist_ok=True)
        payload = {
            "tools": list(new_set),
            "size": size,
            "computed_at": __import__("datetime").datetime.now(
                tz=__import__("datetime").timezone.utc).isoformat(),
            "previous": list(old_set),
            "jaccard_distance": round(distance, 3),
        }
        _CORE_TOOLS_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "core_tools_pareto: persisted %d tools, "
            "Jaccard=%.2f (vs prev)", size, distance)
        return new_set
    except OSError as exc:
        logger.warning("core_tools_pareto: persist failed: %s", exc)
        return None


def maybe_recompute_in_background(trace_path: Path) -> None:
    """Lanza un thread daemon que recalcula el set sin bloquear.

    Llamar al boot del agente DESPUES de cargar el set actual. La proxima
    sesion vera el resultado.
    """
    import threading

    def _bg() -> None:
        try:
            recompute_and_persist(trace_path)
        except Exception as exc:  # noqa: BLE001 (best-effort, no propaga)
            logger.warning("core_tools_pareto: bg recompute failed: %s", exc)

    t = threading.Thread(target=_bg, name="core-tools-pareto-bg", daemon=True)
    t.start()
