"""Structural tool-loop detection.

Hoy `max_agent_turns` corta loops por count duro, pero gasta N turns enteros
antes de detener. Este módulo detecta 5 patrones de stuck por evidencia
estructural — sin keywords ni heurística de lenguaje — y corta en el momento
exacto en que el progreso se detuvo.

Patrones detectados:
    1. generic_repeat: misma (tool, args, result_sig) N veces consecutivas.
    2. unknown_tool_repeat: tool inexistente >=R veces.
    3. ping_pong: alternancia A↔B sin progreso.
    4. global_circuit_breaker: total tool calls > G en la sesión.
    5. vision_locate_visible_false_repeat: vision devuelve visible=False
       repetidamente (caso especial: cada screenshot tiene path distinto pero
       el patrón semántico "no encontré el target" es loop genuino).

Two-tier escalation (Reflexion pattern, NeurIPS 2023):
    Primer match → warning (self-correction prompt al LLM).
    Match después del warning → critical (abort del turn).

Result-aware hashing:
    El hash incluye result_signature filtrado (sin timestamps/pids/latencias)
    para distinguir polling legítimo (output cambia) de loop genuino (output
    idéntico). Sin esto, llamar `system.processes` dos veces se confundía con
    un loop.

Opt-out: GEMMA4_LOOP_DETECTOR_OFF=1 deshabilita todo (devuelve None siempre).

Wiring esperado en agent.run_content:
    loop_state = LoopState()  # nuevo por turn O por sesión
    for cada tool_call:
        result = dispatch(name, args)
        loop_state.record(name, args, exists=spec_exists, result=result)
        stuck = loop_state.detect_stuck()
        if stuck and stuck.level == "critical":
            break  # cortar el turn
        if stuck and stuck.level == "warning":
            # inyectar mensaje al LLM como tool_result virtual
            ...
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# Constantes ajustables. Two-tier: WARNING dispara self-correction, CRITICAL
# aborta el turn. UNKNOWN_TOOL siempre es critical (no tiene sentido reintentar
# una tool que no existe en el registry).
REPEAT_WARNING = 3
REPEAT_CRITICAL = 5
UNKNOWN_TOOL_LIMIT = 3
PING_PONG_WINDOW = 6
GLOBAL_CIRCUIT_BREAKER = 30
VISION_NOT_FOUND_LIMIT = 3


def _detector_enabled() -> bool:
    """Opt-out via env var. Default ON."""
    raw = (os.environ.get("GEMMA4_LOOP_DETECTOR_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def _result_signature(result: dict | None) -> str:
    """Hash compacto del result para distinguir polling legítimo de loops.

    Polling cambia output (timestamps, counts, etc.). Loop genuino devuelve
    el mismo result. Hashear el result JSON canonicalizado da firma única.

    Filtramos campos ruidosos que cambian entre calls aunque la semántica sea
    la misma:
      - timestamps: ts, _ts, timestamp, created_at, scheduled_in_seconds
      - identificadores volátiles: pid, hwnd
      - latencias: latency_ms, elapsed_ms, elapsed_s
      - mediciones de frame: frame_diff_fraction
    """
    if not result:
        return "empty"
    try:
        filtered = {
            k: v for k, v in result.items()
            if k not in {
                "ts", "_ts", "timestamp", "created_at", "scheduled_in_seconds",
                "pid", "hwnd",
                "latency_ms", "elapsed_ms", "elapsed_s",
                "frame_diff_fraction",
                "id",  # uuids generados por turn
            }
        }
        canonical = json.dumps(filtered, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        # Fallback for non-serializable / unsortable results. NOTE: a dict with
        # mixed-type keys breaks BOTH json.dumps(sort_keys=True) AND
        # sorted(items()) with TypeError — and this is a SAFETY NET that must
        # NEVER crash the turn it protects. So we sort by repr (always
        # comparable) and wrap everything so any failure degrades to a coarse
        # repr rather than propagating into the agent loop.
        try:
            if isinstance(result, dict):
                canonical = repr(sorted(result.items(), key=lambda kv: repr(kv[0])))
            else:
                canonical = repr(result)
        except Exception:
            canonical = repr(result)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _hash_tool_call(tool_name: str, args: dict, result_sig: str = "") -> str:
    """Hash que incluye result_signature (result-aware).

    MUST never raise: this feeds the loop detector, a safety net that must not
    crash the turn it protects. `default=str` handles non-serializable values;
    the fallback sorts by repr (always comparable) since mixed-type arg keys
    break both json.dumps(sort_keys=True) and sorted(items())."""
    try:
        args_canonical = json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        try:
            args_canonical = repr(sorted((args or {}).items(), key=lambda kv: repr(kv[0])))
        except Exception:
            args_canonical = repr(args)
    payload = f"{tool_name}::{args_canonical}::{result_sig}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class StuckSignal:
    """Señal estructural de loop. Niveles: warning (self-correct) o critical (abort)."""
    level: str            # 'warning' | 'critical'
    pattern: str          # 'generic_repeat' | 'unknown_tool' | 'ping_pong' | 'circuit_breaker' | 'vision_not_found'
    message: str          # mensaje a inyectar al LLM como tool_result virtual
    detail: dict = field(default_factory=dict)


@dataclass
class LoopState:
    """Estado de detección de loops a través de un turn (o una sesión).

    `record()` se llama DESPUÉS de cada tool execution (necesita el result).
    `record_evidence()` se llama cuando algo cambió en el estado del SO
    (e.g. archivo creado, ventana cerrada, volumen modificado). Reset del
    warning_count al haber evidencia de progreso real.
    `detect_stuck()` devuelve el primer StuckSignal aplicable o None.

    Reset al inicio de cada turn o cuando agent.clear() — depende de cómo el
    caller lo use. Recomendación: por-turn para evitar carry-over que confunda
    al LLM en preguntas no relacionadas.
    """
    history: deque = field(default_factory=lambda: deque(maxlen=PING_PONG_WINDOW * 2))
    unknown_tool_count: dict[str, int] = field(default_factory=dict)
    global_count: int = 0
    evidence_keys_changed: set[str] = field(default_factory=set)
    warning_count: int = 0
    vision_not_found_count: int = 0

    def record(
        self,
        tool_name: str,
        args: dict,
        *,
        exists: bool,
        result: dict | None = None,
    ) -> None:
        """Registra un tool call. Llamar DESPUÉS de ejecutar (para tener result)."""
        self.global_count += 1
        result_sig = _result_signature(result)
        h = _hash_tool_call(tool_name, args, result_sig)
        self.history.append((tool_name, h, exists, result_sig))
        if not exists:
            self.unknown_tool_count[tool_name] = self.unknown_tool_count.get(tool_name, 0) + 1
        # Semantica per-tool: vision_locate con visible=False acumula.
        # visible=True resetea (encontramos algo => progreso).
        if isinstance(result, dict) and (
            tool_name == "vision"
            or tool_name == "vision_locate_target"
            or tool_name == "vision_locate"
        ):
            if result.get("visible") is False:
                self.vision_not_found_count += 1
            elif result.get("visible") is True:
                self.vision_not_found_count = 0

    def record_evidence(self, evidence_key: str) -> None:
        """Marca que algo cambió en el estado del SO.

        Lo que llamemos "evidence" es lo que el verifier por-tool (TIER 1 #2)
        confirma como un cambio real medido. Ejemplos canónicos de keys:
          - "app:Steam"           tras app.open verificado con tasklist
          - "file:C:/...".         tras filesystem.write verificado con stat
          - "window:Notepad"      tras window.focus verificado con GetForegroundWindow
          - "volume:50"           tras audio.set_volume verificado con pycaw

        Si hay evidencia de progreso real, reseteamos warning_count para no
        escalar a critical en escenarios donde el LLM SÍ está progresando
        aunque repita una tool intermedia.
        """
        self.evidence_keys_changed.add(evidence_key)
        self.warning_count = 0

    def reset(self) -> None:
        self.history.clear()
        self.unknown_tool_count.clear()
        self.global_count = 0
        self.evidence_keys_changed.clear()
        self.warning_count = 0
        self.vision_not_found_count = 0

    def detect_stuck(self) -> Optional[StuckSignal]:
        """Si hay un patrón problemático, devuelve StuckSignal. Si no, None.

        Two-tier escalation:
          - Primer match consecutivo → warning (self-correct).
          - Si después de warning el modelo sigue repitiendo → critical (abort).

        Orden de evaluación (más restrictivo primero):
          1. global_circuit_breaker (siempre critical)
          2. unknown_tool_repeat (siempre critical)
          3. vision_not_found_repeat (siempre critical)
          4. generic_repeat (warning → critical)
          5. ping_pong (siempre critical)
        """
        if not _detector_enabled():
            return None

        # 1. global_circuit_breaker
        if self.global_count >= GLOBAL_CIRCUIT_BREAKER:
            return StuckSignal(
                level="critical",
                pattern="circuit_breaker",
                message=(
                    f"[loop-detector CRITICAL] El agente emitió {self.global_count} "
                    f"tool_calls en esta sesión. Excede el circuit-breaker global "
                    f"({GLOBAL_CIRCUIT_BREAKER}). DETÉN los tool_calls. Reportá al "
                    "usuario el estado actual y pedí instrucciones."
                ),
                detail={"count": self.global_count},
            )

        # 2. unknown_tool_repeat
        for tool_name, count in self.unknown_tool_count.items():
            if count >= UNKNOWN_TOOL_LIMIT:
                return StuckSignal(
                    level="critical",
                    pattern="unknown_tool",
                    message=(
                        f"[loop-detector CRITICAL] La tool '{tool_name}' NO existe "
                        f"en el catálogo y fue invocada {count} veces. NO la vuelvas "
                        "a llamar. Si necesitás esa capacidad, decí honestamente que "
                        "no tenés la herramienta y proponé alternativa con tools del "
                        "catálogo."
                    ),
                    detail={"tool": tool_name, "count": count},
                )

        # 3. vision_locate visible=False repetido sin progreso.
        # Cada screenshot_path es distinto => generic_repeat no dispara,
        # pero el patrón semántico ("no encuentro el target") es loop real.
        if self.vision_not_found_count >= VISION_NOT_FOUND_LIMIT:
            return StuckSignal(
                level="critical",
                pattern="vision_not_found",
                message=(
                    f"[loop-detector CRITICAL] vision devolvió visible=False "
                    f"{self.vision_not_found_count} veces sin progreso. El target NO "
                    "está en pantalla, o la ventana correcta no tiene foco. ABORTÁ "
                    "esta línea de acción. Reportá al user que no podés encontrar el "
                    "elemento; sugerí que te diga dónde mirar o que cambie el foco de "
                    "ventana manualmente."
                ),
                detail={"count": self.vision_not_found_count},
            )

        # 4. generic_repeat: mismo hash N veces consecutivas (two-tier)
        if len(self.history) >= REPEAT_WARNING:
            recent_warning = list(self.history)[-REPEAT_WARNING:]
            hashes_w = [h for (_, h, _, _) in recent_warning]
            if len(set(hashes_w)) == 1:
                tool_name = recent_warning[-1][0]
                # Si ya tenemos REPEAT_CRITICAL repetidos -> critical
                if len(self.history) >= REPEAT_CRITICAL:
                    recent_critical = list(self.history)[-REPEAT_CRITICAL:]
                    hashes_c = [h for (_, h, _, _) in recent_critical]
                    if len(set(hashes_c)) == 1:
                        return StuckSignal(
                            level="critical",
                            pattern="generic_repeat",
                            message=(
                                f"[loop-detector CRITICAL] Repetiste '{tool_name}' "
                                f"con args+result idénticos {REPEAT_CRITICAL} veces. "
                                "ABORTÁ esta línea de acción. Reportá UNVERIFIED al "
                                "usuario."
                            ),
                            detail={"tool": tool_name, "count": REPEAT_CRITICAL},
                        )
                # Solo warning (primer escalation)
                self.warning_count += 1
                return StuckSignal(
                    level="warning",
                    pattern="generic_repeat",
                    message=(
                        f"[loop-detector] Estás repitiendo '{tool_name}' con "
                        f"args+result idénticos. Esto NO progresa. PROBÁ una "
                        "estrategia distinta: otros args, otra tool, o admitir "
                        "UNVERIFIED honestamente."
                    ),
                    detail={"tool": tool_name, "count": REPEAT_WARNING},
                )

        # 5. ping_pong: A->B->A->B->A->B sin progreso
        if len(self.history) >= PING_PONG_WINDOW:
            recent = list(self.history)[-PING_PONG_WINDOW:]
            hashes = [h for (_, h, _, _) in recent]
            even_set = set(hashes[::2])
            odd_set = set(hashes[1::2])
            if (
                len(even_set) == 1
                and len(odd_set) == 1
                and even_set != odd_set
            ):
                names = (recent[-2][0], recent[-1][0])
                return StuckSignal(
                    level="critical",
                    pattern="ping_pong",
                    message=(
                        f"[loop-detector CRITICAL] Alternás entre '{names[0]}' y "
                        f"'{names[1]}' sin progreso. SALÍ del loop: probá otra "
                        "estrategia o reportá honestamente al usuario."
                    ),
                    detail={"tools": list(names)},
                )

        return None
