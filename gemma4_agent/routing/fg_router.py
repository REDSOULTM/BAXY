# -*- coding: utf-8 -*-
"""FunctionGemma (run9) como router de tool-calling de Baxy.

Pieza del split: FunctionGemma-270M SOLO elige tool+args (o `no_tool` para abstenerse);
NO conversa (eso lo sigue haciendo el E2B). Reemplaza la emisión de tool-calls del E2B
cuando GEMMA4_FG_ROUTER está activo.

Flujo (router jerárquico, reusa el encoder MiniLM-FT de Baxy):
  query --[encoder FT]--> top-F familias compuestas (suggest_tools_scored)
        --> hijos individuales (tool_categories.json)
        --[encoder FT, coseno]--> top-K hijos  (+ no_tool SIEMPRE)
        --[FunctionGemma :8082]--> call:NOMBRE{args}  (o no_tool)
        --[bridge]--> (tool COMPUESTO de Baxy, {action, **args})  para ToolRegistry.execute

CONTRATO (coincide con el training run9 — NO cambiar):
  - cliente a 127.0.0.1:8082 (NO localhost: en Windows IPv6 suma ~2s de timeout. Medido.)
  - developer role + user query + tools=slim-subset; greedy; stop=["<end_function_call>"]
  - parseo re.DOTALL (valores multilínea).
Fuente: FunctionGemma/INTEGRATION_HANDOFF.md (2026-06-17).
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

_HERE = Path(__file__).resolve().parent
_DATA = _HERE.parent / "data" / "fg"
_SLIM = _DATA / "tool_schemas_slim.json"
_CATS = _DATA / "tool_categories.json"
_ACTION_MAP = _DATA / "tool_action_map.json"
_EMB_CACHE = _DATA / "fg_tool_emb.npy"
_KVA_GATE = _DATA / "kva_gate.json"  # gate conocimiento-vs-acción (corre ANTES de FG)
# GGUF de FunctionGemma (run9). El server se botea contra este archivo (ver ensure_fg_server).
_FG_GGUF = _HERE.parent.parent / "models" / "FunctionGemma" / "functiongemma-ft-270m-it-Q8_0.gguf"

# ⚡ 127.0.0.1, NO localhost (IPv6 timeout ~2s en Windows; medido fg_bench.py).
FG_SERVER = os.environ.get("GEMMA4_FG_SERVER", "http://127.0.0.1:8082/v1/chat/completions")
_DEV = "You are a model that can do function calling with the following functions"

# Gate acción-vs-conversación (umbral del pico top-1 del encoder FT).
# FunctionGemma (270M) es excelente eligiendo tool+args pero MAL abstenedor: con un
# subset "tentador" elige una tool aunque el turno sea chitchat (eager invocation;
# SimpleToolHalluBench arXiv 2510.22977, When2Call arXiv 2504.18851). El no_tool inyectado
# en el subset NO basta cuando el subset está dominado por una familia (medido en vivo).
# Solución MEDIDA (regla #3.5, batería 24 casos es/en/fr/pt): NO llamamos a FunctionGemma
# salvo que el turno sea accionable, y eso se decide con DOS señales independientes en OR:
#   (a) pico del encoder FT: top-1 de familia ≥ FG_ACT_PEAK. Separación medida: chitchat
#       top-1 ≤ 0.485, acción ≥ 0.565 (es/en/fr/pt) -> umbral 0.52 con margen a ambos lados.
#   (b) el E2B emitió un tool-call. El E2B es abstenedor PERFECTO en chitchat (7/7 medido)
#       pero PIERDE acciones no-españolas (sesgo medido); el pico (a) las rescata.
# Chitchat requiere que fallen AMBAS (encoder<0.52 Y E2B abstuvo) -> no pasa. Es clasificación
# por embeddings multilingües con fallback seguro (permitido por CLAUDE.md), no keywords.
# 2026-06-18: re-medido para el encoder reentrenado (router_encoder_ft, retrain con +149 now-playing/status).
# El retrain corrió el espacio de scores: la acción del clúster nuevo subió (top1 p50 0.487->0.581).
# 0.50 (NO 0.44): VERIFICADO en vivo end-to-end. A 0.44 entraban más acciones del borde a FunctionGemma,
# pero "qué suena" (encoder media 0.49) llegaba a FG y FG-270M elegía audio.mute (MUTEA la música = regresión,
# error de FG no del encoder). A 0.50 "qué suena" vuelve a no_tool (inofensivo) y se conservan TODAS las
# ganancias (qué canción es esta / qué música / qué estoy escuchando -> media; batería -> system; monitores
# -> device_settings). El end-to-end de las queries cortas/inglesas depende de reentrenar FG (techo del run).
# Anterior (encoder viejo): 0.52. Override: GEMMA4_FG_PEAK.
FG_ACT_PEAK = float(os.environ.get("GEMMA4_FG_PEAK", "0.50"))
# Piso de actionabilidad para PREGUNTAS (forma interrogativa): un status-question sobre
# una familia de acción ("cuánto disco me queda", "qué día es hoy") es accionable aunque
# el encoder no llegue al peak (proper nouns / fraseo ambiguo bajan el score a ~0.42-0.49).
# La FORMA (pregunta) es la señal que el score crudo no captura. Seguro porque: el
# conocimiento ya lo corta el KVA gate ANTES, y un eventual write mal-elegido lo ataja la
# read-guard. Solo aplica a interrogativas -> no abre la puerta al eager-invocation de chitchat.
FG_ACT_FLOOR = float(os.environ.get("GEMMA4_FG_ACT_FLOOR", "0.40"))

_R: "_FGRouter | None" = None
_FG_PROC: "subprocess.Popen | None" = None


def _parse_host_port(url: str) -> tuple[str, int]:
    """Extrae (host, port) de la URL del server FunctionGemma."""
    m = re.search(r"https?://([^:/]+):(\d+)", url)
    return (m.group(1), int(m.group(2))) if m else ("127.0.0.1", 8082)


def _port_in_use(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _stop_fg() -> None:
    """atexit: termina el server que botéamos (en Windows el child NO muere con
    el padre — sin esto queda orphan ocupando :8082 y VRAM). Best-effort."""
    global _FG_PROC
    p = _FG_PROC
    _FG_PROC = None
    if p is None or p.poll() is not None:
        return
    try:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    except Exception:
        pass


def ensure_fg_server(timeout_s: float = 90.0) -> bool:
    """Garantiza que el server de FunctionGemma escuche en :8082 (contrato handoff §2).

    Idempotente: si el puerto ya está en uso (server externo o ya booteado) NO hace
    nada y devuelve True. Si no, lo lanza con el GGUF run9 y espera health. Best-effort:
    nunca lanza — si falla, devuelve False y fg_emit caerá a su manejo de error (el
    caller conserva la decisión del E2B). Cumple CLAUDE.md regla #5 (el código garantiza
    sus precondiciones, sin pasarle setup al usuario). Desactivable con GEMMA4_FG_AUTOBOOT=0.
    """
    global _FG_PROC
    host, port = _parse_host_port(FG_SERVER)
    if _port_in_use(host, port):
        return True
    if os.environ.get("GEMMA4_FG_AUTOBOOT", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    if not _FG_GGUF.is_file():
        return False
    try:
        from ..infra.config import AgentConfig
        exe = AgentConfig.from_env().llama_server_exe
    except Exception:
        exe = Path(r"C:\llamacpp-cuda\bin\llama-server.exe")
    if not Path(exe).is_file():
        return False
    # FunctionGemma corre en CPU por DEFAULT (split arch: el LLM de habla es el ÚNICO en
    # GPU; en un target de 4GB la GPU es para el E2B). MEDIDO: en CPU el 270M decide en
    # ~70-150ms — sobra para el budget de voz (4-5s). GOTCHA MEDIDO: con el build CUDA de
    # llama-server, `-ngl 0` NO basta — igual reserva ~0.9GB de compute buffer en la GPU;
    # hay que OCULTAR la GPU (CUDA_VISIBLE_DEVICES=-1) para 0 VRAM. GEMMA4_FG_GPU=1 lo
    # pone en GPU (-ngl 99, contrato handoff §2) si sobra VRAM y se quiere algo más rápido.
    fg_gpu = os.environ.get("GEMMA4_FG_GPU", "0").strip().lower() in {"1", "true", "yes", "on"}
    cmd = [str(Path(exe).resolve()), "-m", str(_FG_GGUF.resolve()),
           "--host", host, "--port", str(port),
           "--jinja", "-ngl", ("99" if fg_gpu else "0"), "-c", "4096", "--no-webui"]
    env = os.environ.copy()
    if not fg_gpu:
        env["CUDA_VISIBLE_DEVICES"] = "-1"  # CPU real: oculta la GPU -> 0 VRAM (medido)
    try:
        _FG_PROC = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    except Exception:
        return False
    atexit.register(_stop_fg)
    # Esperar a que el MODELO esté listo (/health==200), no solo a que el puerto abra:
    # el puerto abre antes de cargar el GGUF y un _ask temprano daría 503.
    health = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _FG_PROC.poll() is not None:  # murió en el arranque
            return False
        try:
            if urllib.request.urlopen(health, timeout=2).getcode() == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


class _KVAGate:
    """Gate CONOCIMIENTO-vs-ACCIÓN: regresión logística calibrada sobre el embedding del MISMO
    encoder MiniLM-L12-FT del router. Corre ANTES de FunctionGemma; si la query es CONOCIMIENTO
    con alta confianza (P(conocimiento) ≥ threshold) → no_tool, sin invocar FG. Cascada con
    deferral: ante la duda DEFIERE a FG (que abstiene ~96%). threshold 0.87 = cost-optimal
    (preserva acción ≥99%). Sub-ms (un dot product de 384d). Artefacto data/fg/kva_gate.json
    (regenerable con FunctionGemma/build_kva_gate.py). Ver FunctionGemma/KVA_GATE_HANDOFF.md."""

    def __init__(self, path: Path) -> None:
        d = json.loads(path.read_text(encoding="utf-8"))
        self.coef = np.asarray(d["coef"], dtype=np.float32)   # coef de clase 1 (ACCIÓN)
        self.intercept = float(d["intercept"])
        self.thr = float(d["threshold_p_knowledge"])

    def p_knowledge(self, emb_normalized: np.ndarray) -> float:
        # P(acción)=sigmoid(logit); P(conocimiento)=1-P(acción)=sigmoid(-logit)
        logit = float(np.dot(self.coef, np.asarray(emb_normalized, dtype=np.float32)) + self.intercept)
        return 1.0 / (1.0 + np.exp(logit))

    def is_knowledge(self, emb_normalized: np.ndarray) -> bool:
        return self.p_knowledge(emb_normalized) >= self.thr


class _FGRouter:
    def __init__(self) -> None:
        ensure_fg_server()  # contrato: si el router existe, el server :8082 está garantizado
        from . import semantic_router as sr
        self.sr = sr
        sr.embed("warmup")  # carga el encoder FT (lazy)

        self.tools = json.loads(_SLIM.read_text(encoding="utf-8"))
        self.by_name = {t["function"]["name"]: t for t in self.tools}
        self.names = [t["function"]["name"] for t in self.tools]
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.cats = json.loads(_CATS.read_text(encoding="utf-8"))

        # Gate conocimiento-vs-acción (opcional; ausente -> sin gate, fallback seguro).
        self.kva: "_KVAGate | None" = None
        try:
            if _KVA_GATE.is_file():
                self.kva = _KVAGate(_KVA_GATE)
        except Exception:
            self.kva = None

        # bridge individual -> (compuesto, action). tool_action_map = {compuesto::action: individual}
        amap = json.loads(_ACTION_MAP.read_text(encoding="utf-8"))
        self.rev: dict[str, tuple[str, str]] = {}
        for k, indiv in amap.items():
            comp, _, act = k.partition("::")
            self.rev[indiv] = (comp, act)

        self._emb = self._tool_embeddings()

    def _tool_embeddings(self) -> np.ndarray:
        texts = [f"{t['function']['name']}: {t['function']['description']}" for t in self.tools]
        sig = hashlib.md5(("FT||" + "||".join(texts)).encode()).hexdigest()
        try:
            data = np.load(_EMB_CACHE, allow_pickle=True).item()
            if data.get("sig") == sig:
                return np.asarray(data["emb"], dtype=np.float32)
        except Exception:
            pass
        emb = np.stack([_norm(np.asarray(self.sr.embed(t), dtype=np.float32)) for t in texts])
        try:
            np.save(_EMB_CACHE, {"sig": sig, "emb": emb})
        except Exception:
            pass
        return emb

    def subset(self, query: str, fam_k: int = 3, tool_k: int = 10) -> list[dict[str, Any]]:
        """Stage1 familias -> hijos -> Stage2 top-K coseno (+ no_tool siempre)."""
        fams = [f for f, _ in self.sr.suggest_tools_scored(query, k=fam_k)]
        cand: list[str] = []
        for fam in fams:
            cand.extend(self.cats.get(fam, []))
        cand = [n for n in cand if n in self.idx]
        if not cand:
            cand = list(self.names)
        qv = _norm(np.asarray(self.sr.embed(query), dtype=np.float32))
        rows = [self.idx[n] for n in cand]
        sims = self._emb[rows] @ qv
        order = np.argsort(-sims)[:tool_k]
        ranked = [cand[i] for i in order]
        # FIX no_tool: SIEMPRE en el subset, si no el chitchat fuerza una tool (eager invocation).
        if "no_tool" in self.idx and "no_tool" not in ranked:
            ranked.append("no_tool")
        return [self.by_name[n] for n in ranked]

    def to_baxy(self, indiv: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Traduce un tool individual de FunctionGemma a un call de Baxy (compuesto o standalone)."""
        if indiv in self.rev:
            comp, act = self.rev[indiv]
            return comp, {"action": act, **(args or {})}
        # standalone (computer_use, skill_load, file_process): es un tool de Baxy directo.
        return indiv, dict(args or {})


def _parse_call(text: str) -> tuple[str | None, dict[str, Any]]:
    """call:NOMBRE{k:<escape>v<escape>,...}. re.S por valores multilínea (vCard/ICS)."""
    nm = re.search(r"call:([a-zA-Z0-9_]+)", text or "")
    if not nm:
        return None, {}
    args = dict(re.findall(r"([a-zA-Z0-9_]+):<escape>(.*?)<escape>", text, re.S))
    return nm.group(1), args


def _tool_name(t: dict[str, Any]) -> str | None:
    return t.get("function", {}).get("name") or t.get("name")


def _tool_props(t: dict[str, Any] | None) -> dict[str, Any]:
    if not t:
        return {}
    fn = t.get("function", t)
    return (fn.get("parameters") or {}).get("properties") or {}


def _call_fg(query: str, subset: list[dict[str, Any]], timeout_s: float) -> tuple[str | None, dict[str, Any]]:
    body = json.dumps({
        "messages": [{"role": "developer", "content": _DEV}, {"role": "user", "content": query}],
        "tools": subset, "temperature": 0.0, "max_tokens": 160, "stop": ["<end_function_call>"],
    }).encode("utf-8")
    req = urllib.request.Request(FG_SERVER, data=body, headers={"Content-Type": "application/json"})
    m = json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())["choices"][0]["message"]
    name, args = _parse_call(m.get("content") or "")
    if not name and m.get("tool_calls"):  # fallback: server devolvió tool_calls estructurado
        tc = m["tool_calls"][0]["function"]
        name = tc.get("name")
        a = tc.get("arguments") or {}
        if isinstance(a, str):
            try:
                a = json.loads(a)
            except Exception:
                a = {}
        args = a
    return name, args


def _ask(query: str, subset: list[dict[str, Any]], timeout_s: float = 20.0) -> tuple[str | None, dict[str, Any]]:
    name, args = _call_fg(query, subset, timeout_s)
    # FG-270M DROPEA args cuando el subset es grande y está dominado por una familia de
    # tools similares (MEDIDO 2026-06-17: "abre Steam" con 11 tools steam/app/launch ->
    # app_open{} VACÍO -> el tool falla sin target; con [app_open,no_tool] -> name:Steam).
    # Si el tool elegido ACEPTA args pero vino vacío, re-preguntamos ENFOCADO (ese tool +
    # no_tool): FG deja de competir entre tools hermanos y completa el arg. No hardcodea
    # nada — es el mismo FG con un subset mínimo. Si el tool no toma args (steam_open{},
    # get_volume{}) el reintento queda vacío también (inocuo).
    if name and name != "no_tool" and not args:
        chosen = next((t for t in subset if _tool_name(t) == name), None)
        if _tool_props(chosen):
            minimal = [chosen] + [t for t in subset if _tool_name(t) == "no_tool"]
            if len(minimal) < len(subset):  # solo si de verdad achicamos
                n2, a2 = _call_fg(query, minimal, timeout_s)
                if n2 == name and a2:
                    args = a2
    return name, args


def _missing_value_fields(fg_tool: str, args: dict[str, Any] | None, cap: int = 3) -> list[str]:
    """Campos de VALOR del slim-schema de `fg_tool` que FunctionGemma dejó VACÍOS.

    Los args sin 'action' del slim-schema (data/fg/tool_schemas_slim.json) son los valores que el
    tool necesita (name/level/query/provider/url/...). FG-270M a veces dropea uno o VARIOS con
    subsets grandes (MEDIDO: "abre Steam"->app.open sin name; "pon X en spotify"->play sin query NI
    provider — perdía la plataforma). Devuelve los que faltan (hasta `cap`, en orden de schema) para
    que el LLM de habla los complete desde el texto del usuario; el speech-LLM devuelve None por
    campo si no está en el texto, así que pedir de más es seguro. NO es lista hardcoded: del schema.
    Lista vacía si el tool no toma valores (steam.store, system.time) o si ya viene completo.
    """
    schema = _R.by_name.get(fg_tool) if _R is not None else None
    value_props = [p for p in _tool_props(schema) if p != "action"]
    a = args or {}
    return [p for p in value_props if not a.get(p)][:cap]


# Marcadores de FORMA INTERROGATIVA (palabra-WH inicial, accent-folded). Igual que
# _IMPERATIVE_VERBS desambigua el IDIOMA por la forma verbal, esto desambigua la
# INTENCIÓN por la forma de la oración: una PREGUNTA sobre media ("qué suena") es LEER,
# una ORDEN ("poné música") es REPRODUCIR. Mide la FORMA gramatical, NO contenido.
_INTERROGATIVE_FIRST = frozenset({
    "que", "cual", "cuales", "como", "quien", "quienes", "cuanto", "cuanta",
    "cuantos", "cuantas", "donde",                                  # es (incl. plurales)
    "what", "which", "who", "how", "where", "whose", "whats",       # en
    "quel", "quelle", "quels", "quelles", "qui", "comment",         # fr
    "wie", "welche", "welcher", "wer", "wann", "wieviel",           # de
    "che", "cosa", "chi", "quale", "quali",                         # it
    "qual", "quais", "quem",                                        # pt
})

# Preguntas SÍ/NO: no arrancan con palabra-WH sino con CÓPULA/AUXILIAR/EXISTENCIAL
# por inversión verbo-sujeto ("está corriendo X", "is X running", "hay Y abierta").
# Sin "?" (vienen de STT) caían sub-peak -> no_tool -> confab ("Spotify está corriendo"
# sin verificar). Señal de FORMA gramatical (como _INTERROGATIVE_FIRST), no keywords de
# contenido. Los IMPERATIVOS ("abrí/poné/subí") no arrancan con cópula -> intactos.
_YESNO_LEADING = frozenset({
    "esta", "estan", "estas", "estoy", "es", "son", "hay", "anda", "funciona",
    "sigue", "tengo", "tenes", "tienes", "tiene",                   # es
    "is", "are", "am", "was", "were", "do", "does", "did", "can",
    "could", "have", "has", "will", "would", "should",             # en
    "est", "sont", "ist", "sind", "sono", "estao", "estou", "sao",
    "tem", "tenho",                                                 # fr/de/it/pt
})
# "tener QUE <verbo>" es perífrasis de OBLIGACIÓN (afirmación: "tengo que apagar"),
# no una pregunta -> no debe contar como interrogativa (si no, bloquearía la acción).
_TENER_FORMS = frozenset({"tengo", "tenes", "tienes", "tiene", "tem", "tenho"})


def _is_interrogative(query: str) -> bool:
    """¿La query tiene FORMA de pregunta? Signo (¿/?), primer token = palabra-WH, o
    pregunta SÍ/NO (cópula/auxiliar inicial por inversión). Las ÓRDENES ("poné/play/
    abrí") no arrancan con WH ni cópula -> no matchean. FORM estructural multilingüe."""
    q = (query or "").strip().lower()
    if not q:
        return False
    if "?" in q or "¿" in q:
        return True
    import unicodedata

    def _fold(w: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c))
    toks = q.split()
    first = _fold(toks[0].strip(".,;:!¡"))
    if first in _INTERROGATIVE_FIRST:
        return True
    if first in _YESNO_LEADING:
        second = _fold(toks[1].strip(".,;:!¡")) if len(toks) > 1 else ""
        if first in _TENER_FORMS and second == "que":
            return False
        return True
    return False


# Negadores iniciales de una ORDEN ("no abras X", "don't open Y", "mejor no pongas Z").
# El encoder/FG ignoran el "no" (token chico) y rutean igual que la orden afirmativa ->
# ejecutaban lo CONTRARIO de lo pedido. FORM gramatical multilingüe (no contenido).
_NEGATORS = frozenset({"no", "dont", "not", "non", "nicht", "nao", "nunca", "never", "kein"})
# Clíticos: "no me/te/se/le..." NIEGA un sentimiento/cláusula, no la orden ("no me gusta,
# poné otra") -> NO es orden-negada. Si tras el negador viene un clítico, no gateamos.
_CLITICS = frozenset({"me", "te", "se", "le", "lo", "la", "les", "los", "las", "nos", "os"})


def _is_negated_command(query: str) -> bool:
    """¿La query NIEGA una orden? Negador en los 2 primeros tokens seguido de algo que
    NO es clítico ("no abras X" sí; "no me gusta..." no). El caller lo gatea a acciones
    MUTANTES -> nunca afecta lecturas ni no_tool. FORM gramatical, no por contenido."""
    import unicodedata
    toks = [
        "".join(c for c in unicodedata.normalize("NFKD", t.strip(".,;:!¡¿?'\"").replace("'", "").replace("’", ""))
                if not unicodedata.combining(c))
        for t in (query or "").strip().lower().split()
    ]
    for i in (0, 1):
        if i < len(toks) and toks[i] in _NEGATORS:
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            return bool(nxt) and nxt not in _CLITICS
    return False


# Clasificación ESTRUCTURAL de acciones por su NOMBRE (no por contenido): de LECTURA
# (consultan estado) vs MUTANTES/físicas (modifican el SO / mandan input). Se usa para
# la guarda "una PREGUNTA no dispara una escritura" (generaliza el caso media de #1 a
# cualquier familia: qué ves->gui.click, qué brillo->brightness_up). Por subcadena del
# nombre de acción/tool, que el catálogo nombra consistente (status/get/list vs set/up/play).
_READ_ACTION_HINTS = ("now_playing", "status", "_list", "list_", "_get", "get_",
                      "describe", "displays", "_info", "info_", "stats", "history", "current")
# Verbos MUTANTES/físicos como TOKENS (no substrings): "now_playing"/"display_list"
# contienen 'play' pero NO son escrituras -> el match por token (split en _ y no-alfa)
# los excluye, evitando que la read-guard misfire sobre acciones de lectura.
_MUTATING_TOKENS = frozenset({
    "click", "type", "press", "scroll", "drag", "up", "down", "set", "open", "close",
    "create", "delete", "add", "start", "stop", "play", "resume", "pause", "next",
    "previous", "move", "send", "install", "uninstall", "launch", "restart", "shutdown",
    "kill", "write", "enable", "disable", "toggle", "mute", "unmute", "connect",
    "disconnect", "pair", "maximize", "minimize", "snap",
})


def _is_read_action_name(name: str) -> bool:
    n = (name or "").lower()
    return any(h in n for h in _READ_ACTION_HINTS)


def _is_mutating_action(action: str) -> bool:
    return any(t in _MUTATING_TOKENS for t in re.split(r"[^a-z0-9]+", (action or "").lower()))


def fg_emit(query: str, *, e2b_emitted: bool = False,
            fam_k: int = 3, tool_k: int = 10) -> tuple[str | None, dict[str, Any] | None, list[str]]:
    """Devuelve (baxy_tool, args, missing_fields) para `query`.
      ("no_tool", None, [])        -> abstención: turno conversacional, que responda el LLM.
      (baxy_tool, args, missing)   -> ejecutar via ToolRegistry.execute(tool, args); `missing` es la
                                      LISTA de campos de valor que FG dejó vacíos (vacía si completo).
                                      El caller puede pedirle al LLM de habla que los complete desde
                                      el texto del usuario (FG-270M a veces dropea args con subsets
                                      grandes — MEDIDO: "abre Steam"->app.open sin name; "pon X en
                                      spotify"->play sin query NI provider).
      (None, None, [])             -> FunctionGemma no resolvió (caller conserva la decisión del E2B).

    `e2b_emitted`: True si el E2B ya emitió un tool-call este turno (señal (b) del gate).
    """
    global _R
    if _R is None:
        _R = _FGRouter()

    scored = _R.sr.suggest_tools_scored(query, k=12)
    # GUARDA ESTRUCTURAL DE FORMA (va ANTES de los gates). Causa raíz del mis-route
    # "qué suena"->play/mute/no_tool: el encoder y el FG-270M confunden LEER (now_playing)
    # con REPRODUCIR (play) porque "canción/música" aparece en AMBAS intenciones; la señal
    # que las separa es la FORMA gramatical (pregunta vs orden), que los embeddings y un
    # modelo de 270M capturan mal. Si el encoder rutea a MEDIA y la query es una PREGUNTA,
    # la intención es LEER qué suena -> now_playing (sin provider: lee la sesión activa).
    # Mismo patrón sancionado que _IMPERATIVE_VERBS (mide la FORMA, no keywords de
    # contenido). Va antes del KVA gate porque éste a veces marca "qué música hay" como
    # conocimiento (no lo es: es una acción de lectura). Las ÓRDENES ("poné/pon/reproducí")
    # no arrancan con palabra-WH -> quedan intactas (siguen al flujo normal -> play).
    if scored and scored[0][0] == "media" and _is_interrogative(query):
        return "media", {"action": "now_playing"}, []

    # 1) GATE CONOCIMIENTO-vs-ACCIÓN (ANTES de FunctionGemma): si la query es CONOCIMIENTO con
    # alta confianza -> no_tool, sin invocar FG. Corta el mis-route conocimiento→acción de las
    # trampas family-dominated que FG no abstiene aunque no_tool esté en el subset ("contame de
    # Roma"→contacts, "what is a linked list"→vision, "y cuánto mide"→data_analysis). Usa el
    # embedding del MISMO encoder del router, normalizado (contrato del gate). Cascada con
    # deferral: ante la duda DEFIERE a FG. Fallback seguro: si no hay gate o falla, sigue el flujo.
    if _R.kva is not None:
        try:
            q_emb = _norm(np.asarray(_R.sr.embed(query), dtype=np.float32))
            if _R.kva.is_knowledge(q_emb):
                return "no_tool", None, []
        except Exception:
            pass

    # 2) Gate acción-vs-conversación (ver FG_ACT_PEAK). Solo consultamos a FunctionGemma
    # si el turno es accionable; si no, no_tool y que responda el E2B (ahorra latencia
    # en chitchat y evita el eager-invocation de FunctionGemma).
    top1 = scored[0][1] if scored else 0.0
    # Accionable si: (a) el encoder pica fuerte (>=peak), (b) el E2B ya emitió tool, o
    # (c) es una PREGUNTA con familia de acción decente (>=floor) — un status-question
    # cuyo score quedó sub-peak por proper-nouns/fraseo, pero la FORMA interrogativa lo
    # delata como accionable. El conocimiento ya se cortó arriba (KVA gate).
    actionable_question = _is_interrogative(query) and top1 >= FG_ACT_FLOOR
    if not (top1 >= FG_ACT_PEAK or e2b_emitted or actionable_question):
        return "no_tool", None, []

    # GUARDA DE NEGACIÓN: una ORDEN NEGADA ("no abras X", "don't open Y", "no pongas
    # música") NO debe ejecutar la acción. El encoder/FG ignoran el "no" (token chico) y
    # rutean igual que la afirmativa -> se ejecutaba lo CONTRARIO de lo pedido (medido
    # 14/16). Va ANTES de consultar FG y devuelve no_tool, así también OVERRIDEA el tool
    # que el E2B haya emitido (si FG abstiene, el caller conservaría el del E2B = bypass).
    # "no <verbo>" = no lo hagas (read o write) -> suprime cualquier acción; el clítico
    # ("no me gusta...") ya queda excluido en _is_negated_command. FORM, no contenido.
    if _is_negated_command(query):
        return "no_tool", None, []

    subset = _R.subset(query, fam_k=fam_k, tool_k=tool_k)
    name, args = _ask(query, subset)
    if not name or name == "no_tool":
        # FunctionGemma abstuvo en un turno que el gate marcó accionable: no forzamos
        # no_tool (perderíamos la acción) — devolvemos None para conservar la del E2B.
        return None, None, []
    missing = _missing_value_fields(name, args)
    comp, baxy_args = _R.to_baxy(name, args)
    # GUARDA GENERAL read-vs-write (generaliza el caso media de #1 a TODAS las familias):
    # una PREGUNTA no debe disparar una acción MUTANTE/física. Si FG eligió un write para
    # una pregunta interrogativa, preferimos la 1ra acción de LECTURA del subset (el encoder
    # ya la rankeó primero); si no hay ninguna, ABSTENEMOS (no_tool) en vez de ejecutar el
    # write -> nunca clickear / cambiar brillo / reproducir por una pregunta. Caza medido:
    # "qué ves"->gui.click, "qué brillo tengo"->brightness_up, "qué resolución"->set_resolution.
    if _is_interrogative(query) and _is_mutating_action(baxy_args.get("action", "")):
        for _t in subset:
            _tn = _t.get("function", {}).get("name", "")
            if _is_read_action_name(_tn):
                _rc, _ra = _R.to_baxy(_tn, {})
                return _rc, _ra, []
        return "no_tool", None, []
    return comp, baxy_args, missing
