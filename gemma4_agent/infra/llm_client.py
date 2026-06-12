"""Minimal OpenAI-compatible client for llama-server / Gemma 4."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterator

from .config import AgentConfig


logger = logging.getLogger(__name__)


# Connection-reset patterns que indican que el server crasheo/reloadeo
# durante el handshake. NO incluir genericos como "timeout" que pueden ser
# del LLM tardando legitimamente. Patrones ya normalizados (sin espacios
# ni underscores) para matchear despues del lower+replace en el helper.
_RECOVERABLE_CONN_ERRORS = (
    "10054",                  # WinError 10054 (forcibly closed by remote host)
    "10061",                  # WinError 10061 (no connection could be made)
    "connectionreset",        # ConnectionResetError / "connection reset"
    "connectionrefused",      # "connection refused"
    "brokenpipe",             # "broken pipe" / BrokenPipeError
    "connectionaborted",      # ConnectionAbortedError
    "remotedisconnected",     # http.client.RemoteDisconnected
)


def _is_recoverable_connection_error(exc: Exception) -> bool:
    """True si el error sugiere que vale la pena reintentar tras health-poll.

    Patron tipico: profile change -> server.stop() -> stop() libera el puerto;
    client manda request en la ventana siguiente -> server.start() en curso.
    El socket queda en estado inconsistente y devuelve 10054. Si esperamos
    a que /health vuelva (server arrancado de nuevo), el retry funciona.
    """
    s = str(exc).lower().replace(" ", "").replace("_", "")
    return any(token in s for token in _RECOVERABLE_CONN_ERRORS)


# ZOMBIE del proxy en router-mode. En router mode (front en :8080 +
# child por modelo), si el child worker MUERE (OOM CUDA en 4GB —issue #13085—, o
# un crash del child bajo carga), el FRONT sigue vivo y responde HTTP 500 con un
# body tipo "proxy error: Could not establish connection" / "Failed to read
# connection". NO es un connection-reset (el socket conecta y devuelve 200-OK a
# nivel TCP, con un 500 dentro), así que _is_recoverable_connection_error NO lo
# agarra y el turno moría con llm_http_error 500. El server NO se autorrecupera
# (#13085) -> hay que REINICIARLO. Detectamos por la firma del 500 del proxy.
_PROXY_ZOMBIE_MARKERS = (
    "couldnotestablishconnection",   # "Could not establish connection"
    "failedtoreadconnection",        # "Failed to read connection"
    "proxyerror",                    # "proxy error: ..."
)


# CORRUPCION SILENCIOSA del KV (b9090, misma familia que el crash CUDA #22527 /
# memory_seq_rm intra-batch). MEDIDO 2026-06-11 con replay byte-identico: tras
# cierta secuencia de requests el server queda en un estado donde CUALQUIER
# prompt largo (~>2K tok, incluso texto neutro) genera SOLO tokens <unusedN>
# (320/320 con finish=length), con HTTP 200 y /health OK — ni el recovery de
# zombies ni el health-check lo ven, y cada turno muere en el empty-reply
# fallback hasta reiniciar el server. Mismo body contra server fresco: respuesta
# correcta. Deteccion conservadora: >=8 tokens <unusedN> Y nada de texto real
# Y sin tool_calls — un reply legitimo nunca tiene esa forma.
_UNUSED_TOKEN_RE = re.compile(r"<unused\d+>")
_DEGEN_MIN_UNUSED = 8


def _degenerate_unused_reply(content: str | None, tool_calls: list | None) -> bool:
    """True si el contenido es una corrida degenerada de <unusedN> sin texto real
    ni tool_calls — la firma del KV corrupto del server."""
    if tool_calls:
        return False
    if not content:
        return False
    if len(_UNUSED_TOKEN_RE.findall(content)) < _DEGEN_MIN_UNUSED:
        return False
    return not _UNUSED_TOKEN_RE.sub("", content).strip()


def _is_proxy_zombie_error(exc: Exception) -> bool:
    """True si es un HTTP 500 del FRONT del router porque el child worker murió
    (server zombie, #13085). Requiere reinicio del server, no solo un retry."""
    s = str(exc).lower()
    if "llm_http_error 500" not in s:
        return False
    norm = s.replace(" ", "").replace("_", "")
    return any(m in norm for m in _PROXY_ZOMBIE_MARKERS)


def _try_restart_managed_server() -> bool:
    """Reinicia el llama-server que NOSOTROS gestionamos (no toca un server
    externo del usuario). Best-effort: True si quedó healthy. Import perezoso
    para no acoplar el cliente al manager en el happy-path.

    Diseño deliberadamente minimal: sólo hace mgr.restart() y reporta el
    status. Agregar smoke-probe (8s), _kill_server_on_port y wait largo lleva
    el recovery de ~3s a ~30s — a esa latencia el crash se percibe como
    "el server se cae". El falso-positivo de no smoke-probear (si el child
    re-crashea) es preferible a 30s de pausa cierta en cada crash."""
    try:
        from .llama_server import get_shared_manager
        from .profiles import get_active_profile
        mgr = get_shared_manager()
        # restart() ya no-opea sobre server externo / no-gestionado.
        if not mgr.is_running():
            return False
        status = mgr.restart(get_active_profile(), wait_health=True, timeout_s=90)
        ok = status in {"started", "already_running"}
        logger.warning("proxy-zombie recovery: server restart -> %s (healthy=%s)",
                       status, ok)
        return ok
    except Exception as exc:  # nunca romper el turno por el recovery
        logger.warning("proxy-zombie recovery failed: %s", exc)
        return False


def _smoke_probe_chat(timeout_s: float = 8.0) -> bool:
    """1 chat completion minimo (max_tokens=1) contra el endpoint real.

    True si responde 200 sin proxy-zombie / connection-reset. Esto cubre el
    gap entre /health y /v1/chat/completions del router-mode: el front
    puede estar vivo pero el child todavia no acepta requests.

    En router-mode el cfg.model="gemma-4" NO es valido (el server espera
    "vram4-text"). El smoke probe debe usar el modelo REAL del active
    profile (router_model_text del manager), no el cfg.
    """
    try:
        from .config import AgentConfig
        from .llama_server import get_shared_manager
        cfg = AgentConfig.from_env()
        # Resolver modelo real del router en runtime
        model_name = cfg.model
        try:
            mgr = get_shared_manager()
            if mgr.is_router_mode():
                router_model = mgr.router_model_for(has_image=False)
                if router_model:
                    model_name = router_model
        except Exception:
            pass
        body = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(cfg.chat_url, data=body,
                                     headers=_request_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except OSError:
            pass
        wrapped = RuntimeError(f"llm_http_error {exc.code}: {body}")
        if _is_proxy_zombie_error(wrapped):
            return False
        # 400 con "model not found" tambien es server-vivo. Otros 400/4xx
        # tambien (rechazo de body). 5xx = server caido o crashed child.
        return exc.code < 500
    except Exception as exc:
        logger.debug("smoke-probe error: %s", exc)
        return False


def _request_headers(content_type: str = "application/json", sse: bool = False) -> dict[str, str]:
    """Si GEMMA4_LLAMA_API_KEY esta seteado, añade el header
    Authorization: Bearer <key> que llama-server espera cuando arranca con
    --api-key. Si no esta seteado, headers sin Authorization (el server
    tampoco lo va a pedir)."""
    headers: dict[str, str] = {"Content-Type": content_type}
    if sse:
        headers["Accept"] = "text/event-stream"
    api_key = (os.environ.get("GEMMA4_LLAMA_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# Circuit breaker contra el crash CUDA illegal memory access en Gemma 4 +
# flash-attn + swa-full (llama.cpp issue #22527). El bug es INTRINSECO al
# modelo (PR #21309), no se arregla con flags ni body params (medido en
# stress test 50 turns con --ctx-checkpoints 0 + --cache-ram 2048: 45/50
# crashes, primer crash en turn 5).
#
# El crash dispara via memory_seq_rm intra-batch, no por checkpoints, así que
# manejar checkpoints no basta. El proxy erase NO esta disponible en
# router-mode (#18703).
#
# Mitigacion: cada N requests forzar restart preventivo del server gestionado
# antes del primer crash. Coste: ~1.5s cada N turns + reload child al primer
# chat post-restart.
#
# Gate GEMMA4_CIRCUIT_BREAKER_THRESHOLD=N (0 desactiva).
_CB_REQUEST_COUNTER = 0
_CB_LOCK = __import__("threading").Lock()


def _try_erase_slot(slot_id: int = 0, timeout_s: float = 1.0) -> bool:
    """POST /slots/{slot_id}?action=erase para limpiar KV del slot sin
    reiniciar el server. Devuelve True si el server lo acepto."""
    try:
        from .config import AgentConfig
        cfg = AgentConfig.from_env()
        url = f"{cfg.server_url.rstrip('/')}/slots/{slot_id}?action=erase"
        req = urllib.request.Request(url, method="POST",
                                     headers=_request_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.debug("erase slot %d failed: %s", slot_id, exc)
        return False


def _maybe_circuit_break_restart_async(*, risk_weight: int = 1) -> bool:
    """Version async del circuit breaker: si llega al threshold, dispara el
    restart en un thread daemon para no bloquear el caller. El proximo chat
    encuentra el server fresh sin pausa visible al usuario.

    Devuelve True si se programo el restart. False si counter no llego.
    """
    import threading
    global _CB_REQUEST_COUNTER
    threshold_raw = os.environ.get("GEMMA4_CIRCUIT_BREAKER_THRESHOLD", "0")
    try:
        threshold = int(threshold_raw)
    except ValueError:
        threshold = 0
    if threshold <= 0:
        return False
    with _CB_LOCK:
        _CB_REQUEST_COUNTER += max(1, int(risk_weight))
        if _CB_REQUEST_COUNTER < threshold:
            return False
        _CB_REQUEST_COUNTER = 0

    def _bg_restart() -> None:
        logger.info(
            "circuit breaker (async): reached threshold, restarting in bg")
        try:
            if not _try_erase_slot():
                _try_restart_managed_server()
        except Exception as exc:
            logger.warning("circuit breaker bg restart failed: %s", exc)

    t = threading.Thread(target=_bg_restart, name="cb-bg-restart",
                          daemon=True)
    t.start()
    return True


def _maybe_circuit_break_restart(*, risk_weight: int = 1) -> bool:
    """Incrementa el counter y limpia el slot (o reinicia el server) al
    llegar al threshold. Devuelve True si se hizo algo.

    risk_weight: cuanto incrementar el contador para ESTE turno. Default 1 =
    turno normal. Pasar 3-4 para turnos riesgosos (con thinking activo +
    prompt grande + tools) que aceleran el crash.

    Medido: el crash llega tras 2-3 turnos con thinking + 14K tokens de
    prompt (vs 15-20 turnos con prompts simples). Riesgo proporcional al
    tamano del prompt + thinking activo.
    """
    global _CB_REQUEST_COUNTER
    # Default 0: DESHABILITADO. Medido: el restart preventivo era PEOR que
    # dejar al server crashear (causaba 2 restarts por turno: cb + recovery).
    # Ahora solo recovery reactivo.
    threshold_raw = os.environ.get("GEMMA4_CIRCUIT_BREAKER_THRESHOLD", "0")
    try:
        threshold = int(threshold_raw)
    except ValueError:
        threshold = 0  # invalid -> disabled
    if threshold <= 0:
        return False
    with _CB_LOCK:
        _CB_REQUEST_COUNTER += max(1, int(risk_weight))
        if _CB_REQUEST_COUNTER < threshold:
            return False
        # Reset counter
        _CB_REQUEST_COUNTER = 0
    logger.info(
        "circuit breaker: reached %d requests, clearing slot to avoid "
        "CUDA crash accumulation (#22527)", threshold)
    # 1. Intentar erase del slot (rapido, ~10-50ms)
    erased = _try_erase_slot()
    if erased:
        logger.info("circuit breaker: slot erase OK")
        return True
    # 2. Si el erase fallo (router multi-modelo, etc.), restart full
    logger.info("circuit breaker: slot erase failed, falling back to restart")
    try:
        _try_restart_managed_server()
    except Exception as exc:
        logger.warning("circuit breaker restart failed: %s", exc)
    return True


class LLMClient:
    def __init__(self, config: AgentConfig):
        self.config = config

    def health(self, timeout_s: float = 2.0) -> bool:
        try:
            with urllib.request.urlopen(self.config.health_url, timeout=timeout_s) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _probe_slots_alive(self, timeout_s: float = 0.5) -> bool:
        """True si /slots responde HTTP en absoluto (server escucha y atiende).

        /health miente bajo carga — responde 200 aunque el slot del LLM no esté
        listo, así que un recovery que sólo mira /health reintenta el chat y
        falla ("server recuperado pero sigue roto"). El bootstrap
        (_wait_for_health) ya exige health AND slots; el recovery también debe.
        Este probe replica LlamaServerManager._probe_slots_alive (gemelo
        DELIBERADO: LLMClient no debe importar llama_server -> evita un ciclo de
        import, y el repo tiene historial de ciclos rompiendo el router). Si
        tocás uno, tocá el otro.

        CUALQUIER respuesta HTTP (200/400/404/503) = vivo; el build b9090 da 400
        a /slots y está perfectamente vivo. Solo connection-refused/timeout = muerto."""
        import urllib.error
        url = self.config.server_url.rstrip("/") + "/slots"

        def _is_alive_status(code: int) -> bool:
            if code == 503:
                return True
            return code < 500

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return _is_alive_status(resp.status)
        except urllib.error.HTTPError as exc:
            return _is_alive_status(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        force_tool: bool = False,
        thinking_budget: int | None = None,
        model: str | None = None,
        greedy: bool = False,
        sampling: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synchronous chat completion against the local llama-server.

        timeout_s overrides the per-call request timeout. Defaults to
        self.config.request_timeout_s. This is the wall-clock deadline of the
        HTTP request - if exceeded, raises RuntimeError('llm_timeout: ...').

        greedy=True: SAMPLING DETERMINISTA para el turno de ACCIÓN (decidir y
        emitir el tool-call). Los defaults de Gemma (temp=1.0/top_k=64) son
        para escritura creativa; en una decisión discreta
        (elegir 1 de 6 tools + args) la alta entropía del primer token hace al 4B
        "narrar" en vez de disparar <|tool_call|> (el 2/6 sin reasoning). Greedy
        (temp=0, top_k=1) reduce esa entropía -> tool-call más fiable SIN el costo
        del thinking. Sampling DUAL: greedy en acción, defaults en conversación.
        NO subir repeat_penalty en Gemma 4 (bug <unused49>, issue #21338).
        Gate: GEMMA4_GREEDY_TOOLCALL=0 desactiva (vuelve a sampling normal).
        """
        thinking = self.config.enable_thinking if enable_thinking is None else enable_thinking
        import os as _os
        _greedy_on = greedy and (
            _os.environ.get("GEMMA4_GREEDY_TOOLCALL", "1").strip().lower()
            not in {"0", "false", "no", "off"})
        # SAMPLING POR MODO: el modo puede pasar overrides
        # {temperature, top_p, top_k} para bajar la entropía en modos de acción /
        # info breve (los defaults de Gemma son para chat). Greedy GANA sobre esto
        # (la decisión de tool-call manda con temp=0). Gate GEMMA4_MODE_SAMPLING=0.
        _samp = sampling or {}
        if _os.environ.get("GEMMA4_MODE_SAMPLING", "1").strip().lower() \
                in {"0", "false", "no", "off"}:
            _samp = {}
        def _pick(key: str, cfg_default: Any) -> Any:
            v = _samp.get(key)
            return cfg_default if v is None else v
        body: dict[str, Any] = {
            # In router mode the agent passes the per-turn router preset name
            # ("<profile>-text" / "<profile>-vision"); else the configured model.
            "model": model or self.config.model,
            "stream": False,
            "messages": messages,
            "temperature": 0.0 if _greedy_on else _pick("temperature", self.config.temperature),
            "top_p": 1.0 if _greedy_on else _pick("top_p", self.config.top_p),
            "top_k": 1 if _greedy_on else _pick("top_k", self.config.top_k),
            "repeat_penalty": self.config.repeat_penalty,  # 1.0; NO subir (Gemma 4 bug)
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        # NOTA: cache_prompt=false fue probado y NO arregla el CUDA crash.
        # Causa raiz real: el llama-server b9090 hace `memory_seq_rm` interno
        # cuando un prompt >2048 tokens se procesa por batches (no por cache
        # reuse). El seq_rm intra-batch dispara el bug CUDA igual sin cache
        # reuse. Mantener cache_prompt default (true) da cache hit sin empeorar
        # la estabilidad.
        # El fix definitivo es downgrade del build a commit 149b2493c, o cambiar
        # a un modelo sin SWA (Llama-3.2-3B-Q4_K_M o Qwen2.5-3B-Q4_K_M).
        # Mientras tanto, soft-retry + restart en cliente cubre los crashes.
        if self.config.min_p is not None and not _greedy_on:
            body["min_p"] = self.config.min_p
        if self.config.seed is not None and int(self.config.seed) >= 0:
            body["seed"] = int(self.config.seed)
        if self.config.reasoning_format:
            body["reasoning_format"] = self.config.reasoning_format
        # Cap reasoning tokens (when thinking is on) so a turn can't run away
        # to 13k-15k thinking tokens and blow the latency budget. llama.cpp
        # honors `thinking_budget_tokens` (b9090). -1/None = unbounded.
        if thinking and thinking_budget is not None and int(thinking_budget) >= 0:
            body["thinking_budget_tokens"] = int(thinking_budget)
        if tools:
            body["tools"] = tools
            # tool_choice: ESTE build de llama.cpp (b9090) espera un STRING
            # estilo OpenAI ("auto"/"required"/"none"), NO el objeto {"type":..}
            # — pasar objeto lo rechaza con 'Expected string, using default'
            # (verificado en el err log). El default "auto" deja al modelo
            # elegir; force_tool=True usa "required" para OBLIGAR un tool-call.
            # Fix respaldado por la literatura (arXiv:2504.19277: los SLM fallan
            # por "uncontrolled generation"; la cura es constrained/structured
            # output, que tool_choice=required activa vía la gramática interna).
            body["tool_choice"] = "required" if force_tool else "auto"
            body["parse_tool_calls"] = self.config.parse_tool_calls
            body["parallel_tool_calls"] = self.config.parallel_tool_calls if parallel_tool_calls is None else parallel_tool_calls

        effective_timeout = float(timeout_s) if timeout_s is not None else self.config.request_timeout_s
        # Circuit breaker preventivo ANTES del chat: si el counter llego al
        # threshold, restart proactivo evita el crash CUDA (issue #22527).
        # El restart cuesta ~1.5s, el crash cuesta ~12s (soft-retry + recovery).
        #
        # Risk weight: cada turno cuenta como N en el contador segun riesgo.
        # Medido con tools + thinking + prompt 20K: crash en turn 2. Para
        # restartear ANTES del turn 2 con threshold 8: risk_weight=4 para
        # turno pesado.
        risk = 1
        try:
            prompt_chars = sum(
                len(str(m.get("content", "")))
                for m in (body.get("messages") or [])
            )
            if prompt_chars > 10000:
                risk += 2
            if thinking:
                risk += 2
            if body.get("tools"):
                risk += 1
        except Exception:
            risk = 1
        # Circuit breaker: DESHABILITADO por default.
        # Medido: restart preventivo causaba 2 restarts por turno (cb +
        # recovery del crash) totalizando ~15-20s/turno. Mejor dejar al
        # server vivir hasta crashear y restartear UNA vez (solo recovery).
        # Gate: GEMMA4_CIRCUIT_BREAKER_THRESHOLD=N>0 para reactivar (default 0).
        if os.environ.get("GEMMA4_CIRCUIT_BREAKER_THRESHOLD", "0") not in {"0",""}:
            try:
                _maybe_circuit_break_restart(risk_weight=risk)
            except Exception:
                pass
        response = self._post_chat_with_recovery(body, timeout=effective_timeout)
        response = self._recover_if_degenerate(body, response, timeout=effective_timeout)
        return _normalize_response_tool_calls(response)

    def _recover_if_degenerate(
        self, body: dict[str, Any], response: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        """Recovery del KV corrupto: HTTP 200 cuyo content son SOLO tokens
        <unusedN> (ver _degenerate_unused_reply). Restart del server gestionado
        + 1 reintento del mismo body (inferencia pura, sin efectos — reintentar
        es seguro). Si el restart o el retry fallan, devuelve la respuesta
        original (el empty-reply fallback del agente la maneja, como hasta
        ahora) — nunca empeora el comportamiento previo.
        Gate: GEMMA4_DEGEN_RECOVERY=0 desactiva."""
        try:
            if os.environ.get("GEMMA4_DEGEN_RECOVERY", "1").strip().lower() in {"0", "false", "no", "off"}:
                return response
            ch = ((response or {}).get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            if not _degenerate_unused_reply(msg.get("content"), msg.get("tool_calls")):
                return response
        except Exception:
            return response
        logger.warning(
            "llm degenerate reply (solo <unusedN>, KV del server corrupto); "
            "reiniciando server gestionado y reintentando una vez")
        try:
            restarted = _try_restart_managed_server()
        except Exception as exc:  # noqa: BLE001
            logger.warning("degen-recovery: restart lanzo %s; devuelvo respuesta original", exc)
            return response
        if not restarted:
            logger.warning("degen-recovery: restart fallo; devuelvo respuesta original")
            return response
        try:
            retry = self._post_chat_with_recovery(body, timeout=timeout)
        except RuntimeError as exc:
            logger.warning("degen-recovery: retry fallo (%s); devuelvo respuesta original", exc)
            return response
        try:
            ch2 = ((retry or {}).get("choices") or [{}])[0]
            msg2 = ch2.get("message") or {}
            if _degenerate_unused_reply(msg2.get("content"), msg2.get("tool_calls")):
                logger.warning("degen-recovery: reply SIGUE degenerado tras restart (no reintento de nuevo)")
        except Exception:
            pass
        return retry

    def _post_chat_with_recovery(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        """Wrapper de _post_chat que recupera de:
          - Connection reset (server reloadeando: poll /health, 1 retry)
          - Unsupported option (server build sin features OpenAI extras: retry sin esas keys)

        Maximo 1 reintento por categoria; si falla tras retry, propaga.
        """
        try:
            return self._post_chat(body, timeout=timeout)
        except RuntimeError as exc:
            # Caso 0: PROXY 500 del router. Hay DOS subcausas que se ven igual
            # desde el cliente pero requieren tratamiento opuesto:
            #
            #   A) child CARGANDO (race normal). El router-mode de llama.cpp
            #      proxya el chat al child ANTES de que su /health termine de
            #      arrancar (especialmente tras un swap text<->vision con
            #      --models-max 1 — el primer chat tras el swap llega mientras
            #      el child cold-start). El server NO esta zombie: en 2-10s
            #      el child esta listo y el retry tal cual funciona.
            #
            #   B) child MUERTO (zombie de verdad, #13085: OOM CUDA en 4GB o
            #      crash bajo carga). El front sigue vivo respondiendo 500
            #      pero el child esta caido. Aqui SI hay que reiniciar el
            #      managed server.
            #
            # Reiniciar en AMBOS casos es un error: el (A) comun escala a
            # restart innecesario y durante el restart vuelve a haber otra
            # carga lazy -> otro race -> el segundo intento tambien falla con
            # "llm_proxy_zombie_after_restart" (thrash text<->vision con
            # --models-max 1 dispara restarts en cascada).
            #
            # Un soft-retry (esperar al child mientras carga, hasta ~12s con
            # poll de /health) distingue A de B pero convierte cada crash en
            # un congelamiento perceptible, especialmente con un bucle de
            # reintentos (hasta ~90s total).
            #
            # Diseño actual minimal: 1 restart + 1 reintento. Si el child
            # re-crashea en el reintento, propaga error claro y se puede
            # reintentar manualmente; total de pausa ~3-5s.
            if _is_proxy_zombie_error(exc):
                logger.warning(
                    "llm proxy-zombie (router child died, HTTP 500); "
                    "restarting managed server and retrying once: %s", exc)
                if _try_restart_managed_server():
                    try:
                        return self._post_chat(body, timeout=timeout)
                    except RuntimeError as retry_exc:
                        raise RuntimeError(
                            f"llm_proxy_zombie_after_restart: {retry_exc}"
                        ) from retry_exc
                raise RuntimeError(
                    f"llm_proxy_zombie_no_recovery: server restart did not "
                    f"recover. Original: {exc}"
                ) from exc

            # Caso 1: connection reset -> server reloading. Esperar /health
            # y reintentar UNA vez. Limit total wait a min(15s, timeout/2).
            if _is_recoverable_connection_error(exc):
                wait_budget = min(15.0, timeout / 2.0)
                deadline = time.monotonic() + wait_budget
                logger.info(
                    "llm connection reset (server probably reloading); "
                    "polling /health up to %.1fs before retry: %s",
                    wait_budget, exc,
                )
                healthy = False
                while time.monotonic() < deadline:
                    # H4: exigir /health AND /slots (no solo /health, que miente
                    # bajo carga). El bootstrap ya lo hace; el recovery también
                    # ahora, para no reintentar el chat contra un slot no-listo.
                    if self.health(timeout_s=1.0) and self._probe_slots_alive(timeout_s=0.5):
                        healthy = True
                        break
                    time.sleep(0.5)
                if healthy:
                    logger.info("llm server healthy again; retrying chat once")
                    try:
                        return self._post_chat(body, timeout=timeout)
                    except RuntimeError as retry_exc:
                        # Si tambien falla en el retry: no insistir mas
                        # (evita esconder bugs reales del server).
                        if _is_recoverable_connection_error(retry_exc):
                            raise RuntimeError(
                                f"llm_connection_reset_after_retry: {retry_exc}"
                            ) from retry_exc
                        # Cae al manejo de unsupported_option si aplica
                        if _looks_like_unsupported_option_error(str(retry_exc)):
                            return self._post_chat_fallback(body, timeout=timeout)
                        raise
                # Health nunca volvio en wait_budget: propagar
                raise RuntimeError(
                    f"llm_connection_reset_no_recovery: server did not become "
                    f"healthy within {wait_budget:.1f}s. Original: {exc}"
                ) from exc

            # Caso 2: unsupported option (build sin extras OpenAI) -> retry sin esas keys.
            if _looks_like_unsupported_option_error(str(exc)):
                return self._post_chat_fallback(body, timeout=timeout)

            raise

    def _post_chat_fallback(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        """Retry sin los campos OpenAI-extra que algunos builds rechazan."""
        fallback = dict(body)
        fallback.pop("chat_template_kwargs", None)
        fallback.pop("reasoning_format", None)
        fallback.pop("parse_tool_calls", None)
        fallback.pop("parallel_tool_calls", None)
        return self._post_chat(fallback, timeout=timeout)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        thinking_budget: int | None = None,
        model: str | None = None,
        greedy: bool = False,
        sampling: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Streaming chat completion (SSE) against llama-server.

        Yields dicts of two shapes:
          - {"type": "delta", "content_delta": "...", "tool_call_delta": {...}|None}
            Emitted as tokens arrive. tool_call_delta is non-null when the
            stream is building up a tool_call (llama-server typically sends
            id/name/arguments in pieces).
          - {"type": "final", "finish_reason": "stop|tool_calls|length|...",
             "content": "<accumulated text>", "tool_calls": [<list>]}
            Emitted once at the end. tool_calls is the accumulated array
            with id/function.name/function.arguments fully assembled.

        El TTS consume "delta" para sentence-chunking en cuanto el LLM
        empieza a emitir. agent.py todavia usa chat() no-stream.
        """
        thinking = self.config.enable_thinking if enable_thinking is None else enable_thinking
        ctk: dict[str, Any] = {"enable_thinking": thinking}
        if thinking_budget is not None:
            ctk["thinking_budget"] = int(thinking_budget)
        # Mirror chat(): greedy (temp=0) for the action decision, or per-mode
        # sampling overrides, so a STREAMED pass samples identically to the
        # blocking one (e.g. info turns use temp=0.6, not the config default).
        import os as _os_s
        _greedy_on = greedy and (
            _os_s.environ.get("GEMMA4_GREEDY_TOOLCALL", "1").strip().lower()
            not in {"0", "false", "no", "off"})
        _samp = sampling or {}
        if _os_s.environ.get("GEMMA4_MODE_SAMPLING", "1").strip().lower() in {"0", "false", "no", "off"}:
            _samp = {}

        def _pick_s(key: str, cfg_default: Any) -> Any:
            v = _samp.get(key)
            return cfg_default if v is None else v

        body: dict[str, Any] = {
            # In router mode the agent passes the per-turn router preset name
            # ("<profile>-text" / "<profile>-vision"); else the configured model.
            # Without this the stream sends "gemma-4" and the router 400's, so
            # the model name must be threaded through here.
            "model": model or self.config.model,
            "stream": True,
            "messages": messages,
            "temperature": 0.0 if _greedy_on else _pick_s("temperature", self.config.temperature),
            "top_p": 1.0 if _greedy_on else _pick_s("top_p", self.config.top_p),
            "top_k": 1 if _greedy_on else _pick_s("top_k", self.config.top_k),
            "repeat_penalty": self.config.repeat_penalty,
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": ctk,
        }
        if self.config.min_p is not None and not _greedy_on:
            body["min_p"] = self.config.min_p
        if self.config.seed is not None and int(self.config.seed) >= 0:
            body["seed"] = int(self.config.seed)
        if self.config.reasoning_format:
            body["reasoning_format"] = self.config.reasoning_format
        if tools:
            body["tools"] = tools
            # String form — this build wants OpenAI-style strings, not objects.
            body["tool_choice"] = "auto"
            body["parse_tool_calls"] = self.config.parse_tool_calls
            body["parallel_tool_calls"] = (
                self.config.parallel_tool_calls if parallel_tool_calls is None else parallel_tool_calls
            )

        effective_timeout = float(timeout_s) if timeout_s is not None else self.config.request_timeout_s
        yield from self._stream_chat(body, timeout=effective_timeout)

    def _stream_chat(self, body: dict[str, Any], *, timeout: float) -> Iterator[dict[str, Any]]:
        req = urllib.request.Request(
            self.config.chat_url,
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(sse=True),
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llm_http_error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
                raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc
            raise RuntimeError(f"llm_connection_error: {exc}") from exc

        # SSE parser: cada "linea data: {...}" es un frame. Lineas vacias separan.
        # Acumulamos content + tool_call fragments hasta finish_reason.
        accumulated_content = ""
        # tool_calls indexados por index (llama-server permite multiples)
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        final_finish: str | None = None

        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].lstrip()
                if data == "[DONE]":
                    break
                try:
                    frame = json.loads(data)
                except (ValueError, TypeError):
                    continue
                choices = frame.get("choices") or []
                if not choices:
                    continue
                ch0 = choices[0]
                delta = ch0.get("delta") or {}
                finish_reason = ch0.get("finish_reason")

                content_piece = delta.get("content")
                tc_pieces = delta.get("tool_calls") or []

                tc_for_yield: dict[str, Any] | None = None
                for tc in tc_pieces:
                    idx = int(tc.get("index", 0))
                    slot = tool_calls_acc.setdefault(idx, {
                        "id": None, "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    if tc.get("type"):
                        slot["type"] = tc["type"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]
                    tc_for_yield = slot

                if content_piece is None and tc_for_yield is None and finish_reason is None:
                    continue
                if content_piece:
                    accumulated_content += content_piece
                if content_piece or tc_for_yield:
                    yield {
                        "type": "delta",
                        "content_delta": content_piece or "",
                        "tool_call_delta": tc_for_yield,
                    }
                if finish_reason:
                    final_finish = finish_reason
                    break
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"llm_stream_interrupted: {exc}") from exc
        finally:
            try:
                resp.close()
            except OSError:
                pass

        # Frame final con el resumen acumulado. Normalizamos arguments de
        # cada tool_call (issue #21384: string con braces literales se
        # serializa como JSON string en vez de array, mitigado por
        # normalize_tool_call_arguments).
        raw_tool_calls = [tool_calls_acc[k] for k in sorted(tool_calls_acc.keys())]
        # KV corrupto tambien en el path de streaming: el turno actual ya se
        # consumio (cae al empty-reply fallback como antes), pero el restart
        # acá sana los turnos SIGUIENTES en vez de dejar el server envenenado.
        if (_degenerate_unused_reply(accumulated_content, raw_tool_calls)
                and os.environ.get("GEMMA4_DEGEN_RECOVERY", "1").strip().lower()
                not in {"0", "false", "no", "off"}):
            logger.warning(
                "llm stream degenerado (solo <unusedN>, KV corrupto); "
                "reiniciando server gestionado para sanar turnos siguientes")
            try:
                _try_restart_managed_server()
            except Exception as exc:  # noqa: BLE001
                logger.warning("degen-recovery (stream): restart lanzo %s", exc)
        yield {
            "type": "final",
            "finish_reason": final_finish or "stop",
            "content": accumulated_content,
            "tool_calls": normalize_tool_calls_list(raw_tool_calls),
        }

    def _post_chat(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        req = urllib.request.Request(
            self.config.chat_url,
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llm_http_error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            # urllib raises URLError on socket timeout; surface a friendlier message.
            reason = getattr(exc, "reason", None)
            if "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
                raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc
            raise RuntimeError(f"llm_connection_error: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc


def normalize_tool_call_arguments(raw: Any) -> dict[str, Any]:
    """Normaliza `tool_call.function.arguments` a dict.

    Issue #21384 (llama.cpp + Gemma 4): cuando los args contienen `{` o `}`
    literales (paths con `${var}`, regex con sets, JSON anidado), el parser
    serializa el array como string JSON en vez de array. El cliente debe
    aceptar ambos casos.

    Recibe: dict, str (JSON), list (raro), None.
    Devuelve: dict siempre. Si el parsing falla en todos los caminos
    razonables, devuelve {"_raw": str(raw), "_parse_error": "..."}.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        # Caso muy raro pero documentado: el server devuelve un array
        # cuando el modelo emite un AST nested. Lo envolvemos.
        return {"_args_list": raw}
    if isinstance(raw, (int, float, bool)):
        return {"_value": raw}
    if not isinstance(raw, str):
        return {"_raw": str(raw), "_parse_error": "unsupported_type"}

    s = raw.strip()
    if not s:
        return {}

    # Path feliz: el string es JSON valido.
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"_args_list": parsed}
    if isinstance(parsed, str):
        # Path #21384 / doble-stringificado: el server entrego un string
        # JSON cuyo contenido es a su vez JSON. Re-parsear una vez.
        try:
            inner = json.loads(parsed)
        except (ValueError, TypeError):
            inner = None
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            return {"_args_list": inner}
        # Si tras re-parsear no llegamos a dict/list, devolvemos el string
        # primario como _value para no perder informacion.
        return {"_value": parsed}
    if parsed is not None:
        # Escalar JSON-valido distinto de string (numero, bool, null).
        return {"_value": parsed}

    # Path defensivo final: devolver raw para que el caller decida. NO
    # bloqueamos; el agente puede recuperarse pidiendo al LLM que reformule.
    return {"_raw": s, "_parse_error": "not_a_json_object"}


def normalize_tool_calls_list(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """Aplica normalize_tool_call_arguments a cada tool_call de una lista.

    Preserva id/type/function.name; solo robustifica function.arguments.
    Si una entry no respeta el shape OpenAI, la deja pasar sin tocar.
    """
    out: list[dict[str, Any]] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            out.append(tc)
            continue
        fn = tc.get("function")
        if not isinstance(fn, dict):
            out.append(tc)
            continue
        normalized = dict(tc)
        normalized_fn = dict(fn)
        normalized_fn["arguments"] = normalize_tool_call_arguments(fn.get("arguments"))
        normalized["function"] = normalized_fn
        out.append(normalized)
    return out


def _normalize_response_tool_calls(response: dict[str, Any]) -> dict[str, Any]:
    """Recorre choices[*].message.tool_calls y normaliza arguments.

    No mutamos el objeto original; devolvemos una copia ligera con la
    sustitucion. Si la estructura no coincide con OpenAI, devolvemos
    response tal cual.
    """
    if not isinstance(response, dict):
        return response
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return response
    new_choices = []
    changed = False
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        msg = choice.get("message")
        if not isinstance(msg, dict):
            new_choices.append(choice)
            continue
        tc_list = msg.get("tool_calls")
        if not isinstance(tc_list, list) or not tc_list:
            new_choices.append(choice)
            continue
        new_msg = dict(msg)
        new_msg["tool_calls"] = normalize_tool_calls_list(tc_list)
        new_choice = dict(choice)
        new_choice["message"] = new_msg
        new_choices.append(new_choice)
        changed = True
    if not changed:
        return response
    out = dict(response)
    out["choices"] = new_choices
    return out


def _looks_like_unsupported_option_error(message: str) -> bool:
    low = message.casefold()
    return "llm_http_error 400" in low and any(
        token in low
        for token in (
            "unknown",
            "unsupported",
            "invalid",
            "chat_template_kwargs",
            "reasoning_format",
            "parse_tool_calls",
            "parallel_tool_calls",
        )
    )
