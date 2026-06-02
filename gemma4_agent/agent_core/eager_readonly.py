"""Pre-ejecución EAGER de tools READ-ONLY (opt-in, 2026-06-02).

QUÉ HACE
========
Cuando el router ofrece una tool de SOLO-LECTURA de alta confianza, dispara
la llamada en BACKGROUND **en paralelo** al pase-1 del LLM. Si el LLM
efectivamente la pide, el resultado YA está listo (ahorra el tiempo de la
tool, ~0.1-1 s percibidos). Si el LLM NO la pide o pide otra cosa, el
resultado eager se DESCARTA — no afecta nada, porque era una lectura pura.

REGLA DURA (no negociable, CLAUDE.md + brief): **NUNCA pre-ejecutar una
ESCRITURA / acción con efectos secundarios.** Pre-ejecutar un envío de
WhatsApp, un borrado, un brillo, un volumen = catastrófico e irreversible.
El eager-exec SÓLO toca tools 100% read-only / idempotentes / sin efectos
observables.

POR QUÉ UNA TABLA (tool, action) Y NO UN FLAG EN EL SCHEMA
=========================================================
Las tools de este repo son COMPUESTAS: el campo ``action`` decide si la
llamada lee o escribe. ``system`` tiene ``time`` (lectura) Y ``shutdown``
(apagar la PC). Marcar la TOOL entera read-only sería falso y peligroso.
La marca tiene que vivir a nivel (tool, action). Mantenerla en una tabla
declarativa dedicada (en vez de inyectar una clave ``read_only`` en
``COMPOUND_TOOL_SCHEMAS``) tiene dos ventajas medibles:
  1. No contamina el JSON que ve el LLM (una clave no-OpenAI en el schema
     se filtraría al prompt) ni arriesga el literal verbatim que los
     contract-tests vigilan.
  2. Es ESTRUCTURAL igual: una declaración única, por (tool, action),
     verificada entrada-por-entrada — NO una lista de keywords por idioma
     ni lógica if/else dispersa (CLAUDE.md (b)/(c)).

DEFENSA EN PROFUNDIDAD
======================
La pertenencia a la tabla NO alcanza por sí sola para disparar. Toda
candidata pasa ADEMÁS por el clasificador de seguridad existente
(``safety.classify_tool_call``): si éste la juzga riesgosa, NO se dispara
(aunque esté en la tabla). Dos verificadores independientes deben coincidir
en "esto no tiene efectos". Y SOLO disparamos la llamada FIJA ``{action}``
(sin args extra del usuario): así el resultado eager es idéntico sin
importar qué parámetros invente el LLM, y nunca ejecutamos una variante con
efectos.

FAIL-SAFE
=========
El eager es PURA optimización. Si falla, da error, tarda, o el LLM elige
otro camino → el turno es idéntico al actual (el dispatch normal ejecuta la
tool como siempre). Nunca cambia el resultado ni rompe el turno.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable


# ---------------------------------------------------------------------------
# TABLA DECLARATIVA: (tool, action) que son 100% READ-ONLY / idempotentes /
# sin efectos observables. Cada entrada está verificada contra su impl en
# tools.py (2026-06-02) y justificada. NO agregar nada acá sin leer la impl
# y confirmar que NO escribe estado, NO toca el SO de forma observable, NO es
# irreversible. El default del producto es NO pre-ejecutar; esta tabla es la
# ÚNICA puerta, y es chica a propósito.
#
# Restricción adicional: solo (tool, action) cuya llamada de lectura no
# necesita NINGÚN parámetro más que ``action`` (así la podemos disparar
# especulativamente con args fijos {action} y el resultado es estable).
# ---------------------------------------------------------------------------
EAGER_READONLY_CALLS: frozenset[tuple[str, str]] = frozenset({
    # system_time(): datetime.now() -> string. Lectura pura. (tools.py:3529)
    ("system", "time"),
    # system_cpu_ram_gpu(): Get-CimInstance read-only de CPU/OS/GPU. Sin
    # escritura ni efecto. (tools.py:3652)
    ("system", "cpu_ram_gpu"),
    # system_disk(): psutil.disk_partitions/usage + CIM Win32_LogicalDisk de
    # solo lectura. (tools.py:3672)
    ("system", "disk"),
    # system_battery(): psutil.sensors_battery() — lectura del sensor. Sin
    # efecto en desktops (None limpio). (tools.py:3711)
    ("system", "battery"),
})


def is_enabled() -> bool:
    """Gate ``GEMMA4_EAGER_READONLY``. **Default OFF** — es una optimización
    riesgosa; opt-in hasta validación en vivo exhaustiva. Cualquier valor
    truthy ('1','true','yes','on') la activa."""
    return (os.environ.get("GEMMA4_EAGER_READONLY", "0") or "0").strip().lower() \
        in {"1", "true", "yes", "on"}


# BARRERA ESTRUCTURAL sobre la FORMA del nombre de la acción (no listas por
# idioma del usuario: son verbos del PROTOCOLO de las tools, identificadores en
# inglés del schema — guarda sobre la forma del identificador, CLAUDE.md (b)).
#
# IMPORTANTE (finding 2026-06-02): el clasificador de seguridad
# (safety.classify_tool_call) NO sirve como barrera read-only — sólo decide
# CONFIRMACIÓN (irreversible/alto-riesgo). MUCHAS escrituras de bajo riesgo
# (audio.set_volume, media.play, brightness por algunos paths) devuelven
# requires_confirmation=False y se colarían. Por eso la 2da barrera es un
# allowlist de VERBOS DE LECTURA: la acción DEBE empezar con/ser un verbo de
# lectura conocido Y NO contener ningún verbo de mutación. El clasificador queda
# como 3ra barrera que SÓLO puede endurecer (nunca aflojar).
_READ_ACTION_PREFIXES = (
    "time", "get", "list", "read", "status", "info", "describe", "inspect",
    "battery", "disk", "cpu", "ram", "gpu", "processes", "now_playing",
    "current", "find", "search", "query", "stat", "show", "view", "active",
)
_MUTATION_VERB_TOKENS = (
    "set", "play", "pause", "stop", "mute", "unmute", "next", "previous",
    "open", "close", "launch", "install", "uninstall", "send", "create",
    "delete", "remove", "write", "move", "rename", "shutdown", "restart",
    "sleep", "fetch", "download", "run", "exec", "kill", "start", "connect",
    "click", "type", "press", "scroll", "drag", "switch", "toggle", "add",
    "import", "export", "restore", "rollback", "cleanup", "backup", "update",
    "edit", "enable", "disable", "cancel", "confirm", "save", "brightness_set",
    "brightness_up", "brightness_down",
)


def _action_is_read_verb(action: str) -> bool:
    """True si el nombre de la acción es estructuralmente una LECTURA: empieza
    con un verbo de lectura conocido Y no contiene ningún token de mutación.
    Fail-closed (acción desconocida -> False)."""
    a = (action or "").strip().lower()
    if not a:
        return False
    if any(tok in a for tok in _MUTATION_VERB_TOKENS):
        return False
    return any(a == p or a.startswith(p) for p in _READ_ACTION_PREFIXES)


def _safety_clears(tool: str, action: str, args: dict[str, Any]) -> bool:
    """3ra barrera (sólo endurece): el clasificador de seguridad no debe pedir
    confirmación. NO es suficiente por sí solo para read-only (ver nota arriba),
    pero si pide confirmación es señal extra de NO disparar. Fail-CLOSED."""
    try:
        from ..safety_pkg.safety import classify_tool_call
        decision = classify_tool_call(tool, {**args, "action": action})
        return not bool(getattr(decision, "requires_confirmation", True))
    except Exception:
        return False


def is_eager_safe(tool: str, action: str, args: dict[str, Any] | None = None) -> bool:
    """True SÓLO si las TRES barreras independientes coinciden en "esto no tiene
    efectos", y los args no traen nada con efectos:
      1. (tool, action) está en la TABLA declarativa EAGER_READONLY_CALLS.
      2. el nombre de la acción es estructuralmente un verbo de LECTURA
         (allowlist de read-verbs + denylist de mutation-verbs) — la barrera
         clave que atrapa escrituras de bajo riesgo que el clasificador deja
         pasar (audio.set_volume, media.play, ...).
      3. el clasificador de seguridad no pide confirmación (sólo endurece).
    Garantiza que JAMÁS se pre-ejecute una escritura. Pura/barata (CPU-only).
    """
    a = dict(args or {})
    action = str(action or a.get("action") or "").strip()
    tool = str(tool or "").strip()
    # Barrera 1: tabla declarativa.
    if (tool, action) not in EAGER_READONLY_CALLS:
        return False
    # La llamada eager es SIEMPRE {action} pelado. Si el caller trae args extra
    # (que podrían cambiar el efecto), NO la tratamos como segura para eager.
    extra = {k: v for k, v in a.items() if k != "action"}
    if extra:
        return False
    # Barrera 2: la acción debe ser estructuralmente una lectura.
    if not _action_is_read_verb(action):
        return False
    # Barrera 3: el clasificador de seguridad no debe pedir confirmación.
    return _safety_clears(tool, action, {})


def eager_candidates(subset_names: list[str] | tuple[str, ...] | set[str] | None) -> list[tuple[str, str]]:
    """Dado el subset de tools que el router ofreció ESTE turno, devuelve las
    (tool, action) read-only a disparar en background. Una candidata exige que:
      - el flag esté ON,
      - la TOOL esté en el subset (el router la ofreció), y
      - (tool, action) sea eager-safe (tabla + clasificador).
    Si el flag está OFF o el subset es vacío -> [] (no-op total)."""
    if not is_enabled():
        return []
    names = {str(n) for n in (subset_names or [])}
    if not names:
        return []
    out: list[tuple[str, str]] = []
    for (tool, action) in EAGER_READONLY_CALLS:
        if tool in names and is_eager_safe(tool, action, {}):
            out.append((tool, action))
    return out


class EagerReadOnlyCache:
    """Cache per-turn de resultados de tools read-only pre-ejecutadas en
    background. Vive sólo durante un turno (se crea en _decide_turn, se
    consulta en el dispatch de _execute_turn, se descarta al terminar).

    Thread-safety: los futures escriben su slot bajo lock; el reader sólo lee
    el slot terminado. Las tools read-only no comparten estado mutable, así que
    correrlas en paralelo entre sí y con el LLM es seguro.
    """

    def __init__(self, execute_fn: Callable[[str, dict[str, Any]], dict[str, Any]]):
        self._execute = execute_fn
        self._lock = threading.Lock()
        self._results: dict[tuple[str, str], dict[str, Any]] = {}
        self._threads: list[threading.Thread] = []
        self._fired: list[tuple[str, str]] = []

    @property
    def fired(self) -> list[tuple[str, str]]:
        """(tool, action) que efectivamente se dispararon eager (para trace/test)."""
        return list(self._fired)

    def fire(self, candidates: list[tuple[str, str]]) -> None:
        """Lanza cada candidata en su propio thread daemon. Idempotente por
        candidata (no relanza una ya disparada). Re-verifica is_eager_safe ANTES
        de ejecutar — la tabla podría haber sido mal-poblada; esta es la última
        barrera antes de tocar la tool."""
        for (tool, action) in candidates:
            key = (tool, action)
            with self._lock:
                if key in self._results or key in self._fired:
                    continue
                # Última barrera: nunca disparar algo que no sea eager-safe.
                if not is_eager_safe(tool, action, {}):
                    continue
                self._fired.append(key)
            t = threading.Thread(
                target=self._run_one, args=(tool, action), daemon=True,
                name=f"eager-ro-{tool}.{action}")
            t.start()
            self._threads.append(t)

    def _run_one(self, tool: str, action: str) -> None:
        try:
            res = self._execute(tool, {"action": action})
        except Exception:
            res = None  # fail-safe: sin resultado eager -> dispatch normal lo corre
        if isinstance(res, dict):
            with self._lock:
                self._results[(tool, action)] = res

    def get(self, tool: str, action: str, args: dict[str, Any] | None) -> dict[str, Any] | None:
        """Devuelve el resultado pre-ejecutado para una llamada del LLM, SOLO si:
          - (tool, action, args) es eager-safe (read-only + sin args extra +
            clasificador OK), y
          - tenemos un resultado terminado para ese (tool, action).
        Si la llamada del LLM trae args con efectos, o no es read-only, o el
        future aún no terminó / falló -> None (el caller ejecuta normal)."""
        a = dict(args or {})
        action = str(action or a.get("action") or "").strip()
        tool = str(tool or "").strip()
        # Re-verificar eager-safety contra los args REALES del LLM: si trae algo
        # con efectos (p.ej. level=, delta=) NO servimos el cache.
        if not is_eager_safe(tool, action, a):
            return None
        with self._lock:
            return self._results.get((tool, action))
