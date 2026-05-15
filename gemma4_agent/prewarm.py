"""Pre-warm del KV cache con el system prompt al startup (Sprint 7 /
item I1 #4 del informe de optimizacion externa).

Mientras issue ggml-org/llama.cpp #21468 (cache-reuse roto en Gemma 4 por
shared-KV) este abierto, el PRIMER turno con el system prompt + 62 tools
puede tardar 60-90 s (medido por el reporter del bug con ~46K tokens). Si
disparamos una request sintetica al server durante el splash de boot, el
server procesa el prefix una vez y lo deja cacheado para el primer turno
real del usuario.

Diseño minimo invasivo:
  - prewarm_kv(client, system_prompt, ...) hace POST /v1/chat/completions
    con la conversacion ['system': prompt, 'user': '.'] y max_tokens=1.
  - Sin tools (asi no triggerea el parser de tool calls).
  - max_tokens=1 deja procesar el prefix pero responde casi instantaneo.
  - Timeout configurable (default 90s); si falla, se ignora silencioso
    (el agente puede arrancar igual, solo se pierde el speedup).
  - Publica al BUS dos boot_stage events: prewarm_start / prewarm_done
    para que la UI pueda mostrar progreso.

NOTA: el module NO importa de agent.py. La caller passa el system_prompt
ya construido. Esto preserva el constraint de no tocar agent.py.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# Env var opt-out (default ON). El usuario puede deshabilitar pre-warm si
# tiene una build que ya soporta cache-reuse (post PR #22288 merged).
ENV_OPT_OUT = "GEMMA4_DISABLE_PREWARM"


def prewarm_enabled() -> bool:
    """True por default. False si GEMMA4_DISABLE_PREWARM esta seteado a
    1/true/yes/on (case-insensitive)."""
    raw = (os.environ.get(ENV_OPT_OUT) or "").strip().lower()
    return raw not in {"1", "true", "yes", "on", "enabled"}


def prewarm_kv(
    client: Any,
    system_prompt: str,
    *,
    tools: list[dict[str, Any]] | None = None,
    timeout_s: float = 90.0,
    publish: Any = None,
) -> dict[str, Any]:
    """Lanza una request sintetica para precargar el KV cache.

    Args:
        client: instancia de LLMClient (o cualquier objeto con .chat()).
        system_prompt: el prompt completo armado por el agente.
        tools: opcional. Si se pasa, se incluye en el body para que el
               server procese tambien la seccion de tool schemas (esto
               aprovecha el calentamiento al maximo).
        timeout_s: limite duro. El primer turno con 46K tokens puede
                   tardar 60-90s segun el reporter de #21468.
        publish: callable opcional para publicar al BUS de eventos. Si
                 no se pasa, intenta importar BUS de events_bus.

    Returns:
        dict con keys: ok, elapsed_s, error (si aplica).
    """
    if not prewarm_enabled():
        logger.info("prewarm: disabled by GEMMA4_DISABLE_PREWARM")
        return {"ok": False, "skipped": True, "reason": "disabled_by_env"}

    if not system_prompt or not system_prompt.strip():
        logger.info("prewarm: empty system_prompt, skipping")
        return {"ok": False, "skipped": True, "reason": "empty_prompt"}

    # Resolver publish callable
    if publish is None:
        try:
            from .events_bus import BUS
            publish = BUS.publish
        except Exception:
            publish = lambda _evt: None  # noqa: E731

    started = time.monotonic()
    try:
        publish({
            "kind": "boot_stage",
            "stage": "prewarm_start",
            "msg": "warming KV cache with system prompt",
            "system_prompt_chars": len(system_prompt),
        })
    except Exception:
        pass

    # Construir conversacion minima. user='.' es un input neutro que no
    # cambia comportamiento de Gemma 4 (no es interpretable como pregunta).
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "."},
    ]

    try:
        result = client.chat(
            messages=messages,
            tools=tools,
            max_tokens=1,
            timeout_s=timeout_s,
        )
        elapsed = time.monotonic() - started
        # Si el server devolvio algo (aunque sea 1 token), el prefix quedo cacheado.
        ok = bool(result)
        logger.info("prewarm: completed in %.1fs (ok=%s)", elapsed, ok)
        try:
            publish({
                "kind": "boot_stage",
                "stage": "prewarm_done",
                "elapsed_s": round(elapsed, 2),
                "ok": ok,
            })
        except Exception:
            pass
        return {"ok": ok, "elapsed_s": elapsed}
    except Exception as exc:  # noqa: BLE001
        # No bloqueamos el arranque del agente si prewarm falla. El usuario
        # va a pagar el TTFT alto en su primer turno pero la app levanta.
        elapsed = time.monotonic() - started
        logger.warning("prewarm failed after %.1fs: %s", elapsed, exc)
        try:
            publish({
                "kind": "boot_stage",
                "stage": "prewarm_done",
                "elapsed_s": round(elapsed, 2),
                "ok": False,
                "error": str(exc)[:200],
            })
        except Exception:
            pass
        return {"ok": False, "elapsed_s": elapsed, "error": str(exc)}
