"""Lectores de feature-flags por env var del turn-path, extraídos de agent.py
(split del archivo-dios, 2026-06-19). Agrupados acá para tener UN lugar donde ver
todos los gates de comportamiento y sus defaults. Cada uno lee su GEMMA4_* y
devuelve bool; sin estado. agent.py los re-exporta para sus métodos.

(Los gates de latencia fast_info/research/experience viven en latency_helpers.py;
GEMMA4_GUARDS / GEMMA4_FG_ROUTER se leen al import-time en agent.py por su orden.)
"""
from __future__ import annotations

import os


def _stream_tts_enabled() -> bool:
    """Stream the reply to TTS sentence by sentence (GEMMA4_STREAM_TTS).
    Default OFF: voice must match the final chat reply unless this experimental
    low-latency path is explicitly enabled. Solo afecta modo voz:
    _stream_this exige _active_tts_sink (texto/GUI/CLI pasan tts_sink=None ->
    no-op)."""
    return (
        os.environ.get("GEMMA4_STREAM_TTS", "0") or "0"
    ).strip().lower() in {"1", "true", "yes", "on"}


def _summary_keep_tools_enabled() -> bool:
    """Keep the tool schemas in the SUMMARY pass so its prompt PREFIX stays
    byte-identical to pass-1 -> the llama.cpp prefix-cache HITS instead of
    re-prefilling ~5k tokens. **Default ON, validated live.**

    Why both fixes are needed: keep-tools ALONE looks like a loss (pass-2 still
    re-prefills 5919) because a SECOND prefix divergence — toggling
    `enable_thinking` in chat_template_kwargs (pass-1 True / summary False) —
    re-renders the template from token ~0 (MEASURED cache_n=4). With BOTH fixed
    (keep tools + match enable_thinking, success-gated in _execute_turn), pass-2
    prefill drops 5229->82 tokens, ~1s saved per successful action turn. SOAK: 7/8
    cache hits, 0 runaways, replies correct. Cache-mode is SUCCESS-GATED (failures
    use the slim/thinking-off path — enable_thinking=True makes the model re-engage
    with a failed action). Toggle off with GEMMA4_SUMMARY_KEEP_TOOLS=0."""
    return (
        os.environ.get("GEMMA4_SUMMARY_KEEP_TOOLS", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _error_recovery_enabled() -> bool:
    """Recuperación por TIPO de error. Cuando una tool falla
    (confirmed=False), en vez del nudge genérico "reintentá", clasificamos el error
    (missing_precondition/param_mismatch/transient) y damos una directiva ESPECÍFICA
    para que el loop se auto-corrija (replan/amend) o pare honesto (skip). Capa
    GENÉRICA (el LLM decide la recuperación), no macro-por-intención. Opt-in
    GEMMA4_ERROR_RECOVERY, default ON (validado en vivo + suite verde;
    kill-switch GEMMA4_ERROR_RECOVERY=0). Sin costo por-turno: sólo
    actúa en el path de fallo de una tool, no en el hot-path de cada turno."""
    return (
        os.environ.get("GEMMA4_ERROR_RECOVERY", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _memory_tools_enabled() -> bool:
    """Tool-picking guiado por memoria. Agrega al subset las
    tools que tuvieron ÉXITO en turnos PASADOS con intención similar (experience
    recall por embedding, ya computado en _recent_recalls). El LLM sigue decidiendo
    si llamarlas; sólo ensanchamos los candidatos (como exemplar/semantic), así una
    tool que funcionó antes está disponible aunque el router no la elija hoy.
    GEMMA4_MEMORY_TOOLS default ON; kill-switch =0. SEGURO: latency-free
    (reusa _recent_recalls, ya computado para el recall_hint — sin embed extra); el recall
    es TIGHT (max_distance=0.9≈cos0.55, anti-degradation) → solo agrega tools de éxitos
    GENUINAMENTE similares; cap=3; el 4B decide; no-op si no hay historial relevante."""
    return (
        os.environ.get("GEMMA4_MEMORY_TOOLS", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _skills_autoinject_enabled() -> bool:
    """Trigger-inject de skills. MEDIDO: el 4B nunca emite skill_load
    (0/5 directo, 0/6727 prod) — no hace el meta-paso cargar->seguir. En vez de
    esperar skill_load, inyectamos la receta de la skill que matchea semánticamente
    el pedido (como microagents). GEMMA4_SKILLS_AUTOINJECT default ON
    (validado en vivo: el 4B SIGUE la receta — screenshot->gui+vision, backup->backup_sync+
    filesystem, research->web; 0 falsos positivos /10; kill-switch =0). Perf OK: costo real
    ~2-4ms MEDIANA < budget 5ms; el embed del user-text es cache-hit (el router corre antes
    de _system_message, mismo LRU) + scan_skills cacheado. El perf-test mide mediana, no
    la media (un pico aislado de ~6ms es flake del suite en box degradado, no costo real)."""
    return (
        os.environ.get("GEMMA4_SKILLS_AUTOINJECT", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}
