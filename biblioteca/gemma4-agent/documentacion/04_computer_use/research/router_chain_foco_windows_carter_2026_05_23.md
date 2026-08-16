# Informe técnico CARTER OS / Baxy (antes Gemma 4 Agent, brevemente Carter) — Router robusto, Encadenamiento multi-tool y Foco/Maximize Windows

## TL;DR (decisión)
- **Problema A — Router**: implementar (1) un **gate sintáctico interrogativo multilingüe (es/en/pt/it) ANTES del retrieval** (coste <1 ms, robusto a nombres propios) y (2) un **health-check del encoder al startup** que verifica que el modelo `paraphrase-multilingual-MiniLM-L12-v2` produce vectores de 384 dimensiones (per la model card oficial de sentence-transformers en HuggingFace: *"This is a sentence-transformers model: It maps sentences & paragraphs to a 384 dimensional dense vector space"*), norma no-cero, y similitudes esperadas en pares canónicos. Si falla, **CARTER no debe arrancar** (fail-loud, no fallback silencioso). El NER masking se descarta para el camino caliente del router por coste de latencia (10–50 ms) y se conserva como herramienta de debug offline.
- **Problema B — Encadenamiento multi-tool**: la literatura 2024–2026 confirma que modelos ~4B sufren cascading failures y schema misalignment. El veredicto para Gemma 4 E4B-it es: **planner determinista por plantilla para los tres pares conocidos `search→open / search→play / search→read`**, complementado con (a) validación Pydantic de argumentos (rechazo de `path=None`/vacío) y (b) auto-relleno determinista desde un scratchpad de resultados previos. La reflexión LLM obligatoria queda como **fallback** sólo cuando el patrón determinista no aplica.
- **Problema C — Foco Windows**: secuencia canónica documentada por Microsoft: `ShowWindow(SW_RESTORE/SW_SHOWMAXIMIZED)` → `AllowSetForegroundWindow(ASFW_ANY)` → tap **ALT** vía **`SendInput`** (NO `keybd_event`, marcada explícitamente como *"superseded"* en Microsoft Learn) → `AttachThreadInput` (con guarda contra `idAttach == idAttachTo`, que causa error 87) → `BringWindowToTop` + `SetForegroundWindow` → verificación. Para **UWP / Microsoft Store apps** (WhatsApp, Spotify Store): detectar la clase `ApplicationFrameWindow`, enumerar hijos con clase `Windows.UI.Core.CoreWindow` cuyo PID ≠ `ApplicationFrameHost.exe`, y luego `uiautomation.SetActive()` o `SwitchToThisWindow()` (recomendación del maintainer yinkaisheng en Issue #52 — no `SetFocus()`).

---

## Estado y advertencias generales

- **Confirmado (en código del usuario)**: Gemma 4 E4B-it Q4_K_M (GGUF) bajo llama.cpp b9090+, `--jinja`, 6 GB VRAM Windows, monoslot; pipeline `semantic_router.py` (paraphrase-multilingual-MiniLM-L12-v2 + Tool2Vec + RRF) → `intent_router.py` → `abstain_head.py` → `planner.py`; `max_agent_turns=8`; recall holdout 0.881; 65 tools, top-K 4–6.
- **Hipotético / a medir en el dataset propio**: el impacto del gate sintáctico sobre el recall 0.881 (esperado: 0 o leve subida en queries informativas, sin tocar las acciones); la cobertura real del despachador determinista (qué % de los fallos reales del usuario corresponden a los 3 pares `search→open/play/read`); la tasa de éxito real de la secuencia ALT+AttachThreadInput en el mix de aplicaciones del usuario (Win32 vs UWP).
- **Hipótesis confirmada del incidente torchcodec**: instalar `torchcodec` rompe pipelines de Hugging Face Transformers con errores de carga (`RuntimeError: Could not load libtorchcodec`, meta-pytorch/torchcodec issue #912; huggingface/transformers issue #42499 del 1 Dec 2025 titulado *"Automatic Speech Recognition pipeline raises error when torchcodec is installed but not valid"*). Esto justifica el health-check fail-loud propuesto en A(b).

---

# PROBLEMA A — Router robusto + auto-diagnóstico (PRIORIDAD 1)

## A.1 Diagnóstico

Dos fallos distintos, ambos observados en producción:

1. **Sesgo de nombres propios en el embedding** (incluso con encoder sano): MiniLM multilingüe trata "Mortal Kombat", "Word", "Spotify" como tokens cuya similitud con tools de creación (office) puede dominar la consulta. Esto es consistente con la literatura sobre Linguistic Entity Masking (Ranathunga et al., ArXiv 2501.05700, "Linguistic Entity Masking to Improve Cross-Lingual Representation of Multilingual Language Models for Low-Resource Languages"): los named entities atraen desproporcionadamente la atención y dominan el embedding final.
2. **Degradación silenciosa del encoder**: tras instalar `torchcodec`, `classify_intent` devolvió `None` y `suggest_tools` devolvió `[]`. El sistema cayó a un fallback arbitrario (single tool "office") y enrutó "¿qué es Mortal Kombat?" hacia creación de un .docx.

El daño raíz no es el sesgo del embedding (controlable con un gate barato); es que **el sistema degradó en silencio** en vez de fallar de forma visible.

## A.2 Opciones — tabla comparativa

| Enfoque | Coste por turno | Robustez multi-idioma (es/en/pt/it) | Riesgo de degradar recall 0.881 | Integración | Veredicto |
|---|---|---|---|---|---|
| **Gate sintáctico interrogativo (palabra-pregunta + `?`)** ANTES del retrieval | <1 ms (regex compilada) | Alta — set léxico cerrado y conocido | Bajo: actúa sólo como **boost de info**, no reemplaza el retrieval | Trivial: 1 función `is_interrogative(text)` invocada en `classify_intent` | **ELEGIDA (primaria)** |
| **NER masking de proper nouns** antes del embedding | 10–50 ms (spaCy `xx_ent_wiki_sm` o similar) | Media — los modelos NER multilingües son menos fiables en consultas cortas | Medio: si NER falla sobre tokens críticos puede empeorar el retrieval | Dependencia extra y peso para latencia de voz | Descartada para hot path; opcional como debug |
| **Reentrenar el encoder fine-tuneado** con más data de queries con NEs | Cero en runtime | Alta si el dataset es bueno | Riesgo de overfitting al dataset propio | Ciclo MLOps complejo | A futuro, no urgente |
| **Health-check fail-loud al startup** (encode de pares canónicos + verificación de dim + norma + similitudes esperadas) | Una vez al arranque | N/A | Cero (no toca el camino caliente) | Trivial | **ELEGIDA (paralela)** |

**Justificación para descartar NER en hot path**: el agente es de voz; la latencia objetivo del router debe ser sub-50 ms. Un NER multilingüe añade ~30 ms incluso con CPU rápida, sin ganancia clara sobre el gate sintáctico para el tipo de fallo observado ("qué es X" — el `qué` ya basta).

## A.3 Fuentes oficiales y papers

- **paraphrase-multilingual-MiniLM-L12-v2** — model card oficial de sentence-transformers en HuggingFace: *"This is a sentence-transformers model: It maps sentences & paragraphs to a 384 dimensional dense vector space"*. Esto fija la dimensión esperada para el health-check.
- **Tool2Vec** — Moon et al., ArXiv 2409.02141 (SqueezeAILab), "Efficient and Scalable Estimation of Tool Representations in Vector Space" — base del componente ya implementado.
- **Linguistic Entity Masking** — Ranathunga et al., ArXiv 2501.05700 — evidencia de que los NEs dominan la atención y por tanto el embedding.
- **Incidente torchcodec real** — huggingface/transformers issue #42499 (1 Dec 2025): confirma que un `torchcodec` presente pero mal cargado **rompe pipelines silenciosamente** desde dentro del import path. También meta-pytorch/torchcodec issue #912.
- **MLflow Sentence Transformers Guide** — patrón canónico de validación: *"Printing Embedding Lengths: Verify embedding generation by checking the length of embedding arrays, corresponding to the dimensionality of each sentence representation."*

## A.4 Veredicto VIABLE para este stack

Implementar **ambos** componentes (gate sintáctico + health-check). Cero impacto sobre el RRF + Tool2Vec existentes: el gate es un **pre-filtro de scoring** que añade un boost a la rama "info" en `classify_intent`, no modifica `suggest_tools`. El health-check es un módulo nuevo (`encoder_health.py`) llamado desde el arranque de la app antes de cargar el router.

## A.5 Código listo para integrar

### A.5.1 — `intent_router.py`: gate sintáctico interrogativo multilingüe

```python
# intent_router.py — añadir al inicio del módulo
import re
import unicodedata

# Palabras-pregunta confirmadas (Collins Italian Grammar, Cambridge ES/EN, Adrosverse Romance Languages).
# Forma normalizada SIN tildes para matching robusto.
_INTERROG_WORDS = {
    # ES
    "que", "quien", "quienes", "cual", "cuales", "cuando", "donde",
    "como", "porque", "por que", "para que", "cuanto", "cuanta",
    "cuantos", "cuantas",
    # EN
    "what", "who", "whom", "whose", "which", "when", "where", "why", "how",
    # PT
    "que", "quem", "qual", "quais", "quando", "onde", "como",
    "porque", "por que", "para que", "quanto", "quanta",
    "quantos", "quantas",
    # IT
    "che", "chi", "cosa", "che cosa", "quale", "quali",
    "quando", "dove", "come", "perche", "quanto", "quanta",
    "quanti", "quante",
}

# Tokens al inicio de la frase o tras puntuación.
_INTERROG_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(w) for w in sorted(_INTERROG_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_QMARK_RE = re.compile(r"[¿?]")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def is_interrogative(text: str) -> bool:
    """Gate sintáctico O(len(text)). True si la query es claramente informativa.

    Heurística:
      - signo '?' o '¿' → True
      - palabra-pregunta inicial (qué/what/che/...) → True
    Multi-idioma: es, en, pt, it (set léxico cerrado, normalizado sin tildes).
    """
    if not text:
        return False
    if _QMARK_RE.search(text):
        return True
    norm = _strip_accents(text.lower().strip())
    return bool(_INTERROG_RE.match(norm))


# ─── modificación de classify_intent (NO reescribir; añadir el boost) ─────
def classify_intent(query: str, encoder_scores: dict) -> dict:
    """
    encoder_scores: salida del encoder + Tool2Vec/RRF, p.ej. {'info': 0.41, 'action': 0.43}
    NO depender solo del embedding cuando hay señal sintáctica fuerte.
    """
    info = encoder_scores.get("info", 0.0)
    action = encoder_scores.get("action", 0.0)

    interrog = is_interrogative(query)
    if interrog:
        # Boost determinista: refuerza, no anula, el embedding.
        # +0.20 calibrado empíricamente; MEDIR en el dataset propio (A.6).
        info = min(1.0, info + 0.20)

    return {
        "info": info,
        "action": action,
        "interrogative_gate": interrog,   # bandera para telemetría
        "winner": "info" if info >= action else "action",
    }
```

### A.5.2 — `encoder_health.py` (NUEVO): health-check fail-loud al startup

```python
# encoder_health.py — nuevo módulo. Llamar UNA vez al arranque.
import logging
import math
import sys
from typing import Optional

import numpy as np

log = logging.getLogger("carter.health")

# Per HuggingFace model card oficial:
# "It maps sentences & paragraphs to a 384 dimensional dense vector space"
EXPECTED_DIM = 384

# Pares canónicos: (frase_a, frase_b, similitud mínima esperada).
# Calibrados para que un encoder SANO supere los umbrales con holgura,
# pero un encoder degradado los REPRUEBE.
_CANONICAL_PAIRS = [
    ("¿qué es Mortal Kombat?", "what is Mortal Kombat",        0.70),  # cross-lingual es/en
    ("abre el documento",       "open the document",           0.65),
    ("reproduce música",        "play music",                  0.65),
    ("hola",                    "hello",                       0.55),
]

# Pares NEGATIVOS: similitud debe ser BAJA si el encoder discrimina bien.
_NEGATIVE_PAIRS = [
    ("¿qué es Mortal Kombat?", "abre un documento de Word",    0.45),
]


class EncoderHealthError(RuntimeError):
    """Se eleva cuando el encoder no pasa el health-check. CARTER NO debe arrancar."""


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def check_encoder(encoder, raise_on_fail: bool = True) -> dict:
    """Valida que el SentenceTransformer está sano. Fail-loud por defecto.

    Comprueba:
      1) Que `encode` no lanza excepción.
      2) Que el shape es (N, EXPECTED_DIM).
      3) Que las normas no son cero (vector nulo = encoder roto).
      4) Que las similitudes de pares canónicos superan el umbral.
      5) Que las similitudes de pares NEGATIVOS quedan por debajo.

    Devuelve un dict con métricas. Lanza EncoderHealthError si falla
    y raise_on_fail=True. NUNCA degrada en silencio.
    """
    report = {"ok": True, "dim": None, "pairs": [], "errors": []}

    # 1) Encode básico
    try:
        sample = encoder.encode(["ping"], convert_to_numpy=True, normalize_embeddings=False)
    except Exception as exc:
        msg = f"Encoder.encode lanzó {type(exc).__name__}: {exc!r}"
        report["ok"] = False
        report["errors"].append(msg)
        log.critical(msg)
        if raise_on_fail:
            raise EncoderHealthError(msg) from exc
        return report

    # 2) Dimensión esperada
    dim = int(sample.shape[1])
    report["dim"] = dim
    if dim != EXPECTED_DIM:
        msg = f"Dimensión inesperada: {dim} != {EXPECTED_DIM}"
        report["ok"] = False
        report["errors"].append(msg)
        log.critical(msg)
        if raise_on_fail:
            raise EncoderHealthError(msg)

    # 3) Norma no-cero
    if float(np.linalg.norm(sample[0])) < 1e-6:
        msg = "Vector con norma ~0; encoder devuelve embeddings nulos."
        report["ok"] = False
        report["errors"].append(msg)
        log.critical(msg)
        if raise_on_fail:
            raise EncoderHealthError(msg)

    # 4) Pares canónicos
    all_phrases = [p for triple in _CANONICAL_PAIRS for p in (triple[0], triple[1])]
    all_phrases += [p for pair in _NEGATIVE_PAIRS for p in (pair[0], pair[1])]
    try:
        emb = encoder.encode(all_phrases, convert_to_numpy=True, normalize_embeddings=False)
    except Exception as exc:
        msg = f"Encoder falló al codificar pares canónicos: {exc!r}"
        report["ok"] = False
        report["errors"].append(msg)
        log.critical(msg)
        if raise_on_fail:
            raise EncoderHealthError(msg) from exc
        return report

    idx = 0
    for a, b, min_sim in _CANONICAL_PAIRS:
        sim = _cosine(emb[idx], emb[idx + 1])
        idx += 2
        report["pairs"].append({"a": a, "b": b, "sim": sim, "min": min_sim, "kind": "pos"})
        if sim < min_sim or math.isnan(sim):
            msg = f"Similitud baja para par positivo ({a!r}, {b!r}): {sim:.3f} < {min_sim}"
            report["ok"] = False
            report["errors"].append(msg)

    for a, b, max_sim in _NEGATIVE_PAIRS:
        sim = _cosine(emb[idx], emb[idx + 1])
        idx += 2
        report["pairs"].append({"a": a, "b": b, "sim": sim, "max": max_sim, "kind": "neg"})
        if sim > max_sim:
            msg = f"Similitud alta para par negativo ({a!r}, {b!r}): {sim:.3f} > {max_sim}"
            report["ok"] = False
            report["errors"].append(msg)

    if not report["ok"]:
        log.critical("EncoderHealthError: %s", "; ".join(report["errors"]))
        if raise_on_fail:
            raise EncoderHealthError(report["errors"][0])
    else:
        log.info("Encoder OK: dim=%d, pares=%d", dim, len(report["pairs"]))
    return report


# ─── Punto de uso (main.py / startup.py) ────────────────────────────────
#
#   from sentence_transformers import SentenceTransformer
#   from encoder_health import check_encoder, EncoderHealthError
#
#   try:
#       encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
#       check_encoder(encoder, raise_on_fail=True)
#   except EncoderHealthError as exc:
#       print(f"[FATAL] Encoder dañado, CARTER no arranca: {exc}", file=sys.stderr)
#       sys.exit(2)   # fail-loud: refuse-to-start
```

### A.6 Qué MEDIR en el dataset propio
- **Recall@K antes/después del gate sintáctico** sobre el holdout actual (0.881). El boost +0.20 sobre `info` puede mover el umbral; calibrar entre {0.10, 0.15, 0.20, 0.25} y elegir el valor que **no degrade** el recall de tools de acción.
- **Tasa de falsos positivos del gate**: queries como "Cómo agrego un contacto" son interrogativas pero **acciones**. Auditar ~50 muestras para confirmar que el boost no anula la elección de tool cuando `action ≥ info + 0.20`.
- **Latencia del health-check**: una sola vez al startup, debe ser <2 s.

---

# PROBLEMA B — Encadenamiento multi-tool / tool chaining (PRIORIDAD 2)

## B.1 Diagnóstico

Gemma 4 a 4B sufre tres patologías documentadas:

1. **Sesgo a emitir tool-call incluso en conversación libre** — Ollama `orieg/gemma3-tools` card: *"The 4b model has a strong bias toward emitting tool calls even for conversational prompts like 'what is 2+2?'… The 12b and 27b variants handle mixed chat + tool-calling correctly."*
2. **Cascading failure entre turnos** — FutureAGI 2026 ("How Tool Chaining Fails in Production LLM Agents"): *"Research from Zhu et al. (2025) confirms that error propagation from early mistakes cascading into later failures is the single biggest barrier to building dependable LLM agents."*
3. **Schema misalignment / argument hallucination** — ArXiv 2510.07248 ("Don't Adapt Small Language Models for Tools; Adapt Tool Schemas to the Models", Oct 2025): *"SLMs struggle significantly with these tasks, exhibiting severe performance degradation compared to larger models."* (La calificación de "below 10B parameters" como umbral viene de la definición de SLM en la introducción del paper, no de la frase citada.)

En el ejemplo real ("Abre el primer Word en Descargas") Gemma 4 ejecuta `filesystem.search` correctamente y devuelve la ruta — pero en la siguiente iteración llama `office.open()` sin `path`, esperando que el sistema "ya sabe" cuál archivo. Es un fallo de **argument grounding**: el modelo no copia el output del turno previo al argumento del turno siguiente.

## B.2 Opciones — tabla comparativa

| Estrategia | Confiabilidad esperada para Gemma 4B | Coste por turno | Complejidad | Riesgo UX |
|---|---|---|---|---|
| **Despachador determinista de patrones conocidos** (`search→open`, `search→play`, `search→read`) | **Alta (estimada ~95% en estos 3 pares; MEDIR)** | 0 LLM calls extra | Bajo: una capa en `planner.py` antes de re-invocar al LLM | Bajo si sólo activa en patrones explícitos | **ELEGIDA (primaria)** |
| Reflexión obligatoria post-tool (re-prompt estructurado) | Media: depende del prompt y del modelo | +1 LLM call por tool | Medio | Aumenta latencia de voz | **ELEGIDA (fallback)** |
| Validación Pydantic de args con re-intento auto-rellenado | Alta (catch garantizado) | ~0 | Bajo | Bajo | **ELEGIDA (capa transversal)** |
| Plan-and-Execute clásico (LangGraph) | Alta en LLMs ≥ 12B; **dudosa en 4B** | +1 LLM call (planner) | Alto: reescribir el loop | Aumenta latencia | Descartada para este modelo |
| ReAct puro (statu quo) | Baja para 4B | +1 LLM call por step | Bajo | — | Es lo que ya falla |
| ReWOO (plan con placeholders + paralelo) | Media; rompe si tool devuelve algo inesperado | Eficiente | Alto | — | No encaja con dependencias secuenciales reales |

**Por qué planner determinista gana para este stack**: LangChain Blog ("Plan-and-Execute Agents") observa: *"If LLM calls are used for sub-tasks, they typically can be made to smaller, domain-specific models. The larger model then is only called for (re-)planning steps"*. Para 65 tools con 3 pares dominantes, **el planner para esos pares no necesita LLM en absoluto** — es código.

## B.3 Fuentes oficiales y papers recientes

- **Zhu et al. 2025** sobre cascading failure en agentes LLM (citado por FutureAGI 2026 review).
- **ArXiv 2510.07248** (Oct 2025): "Don't Adapt Small Language Models for Tools; Adapt Tool Schemas to the Models" — adaptar el schema al modelo pequeño es la palanca correcta.
- **ArXiv 2510.17052** (Oct 2025): ToolCritic — *"while modern LLMs can call external APIs, they frequently misidentify which tool to invoke, supply incorrect arguments, or even misinterpret the tool's output"*.
- **ArXiv 2401.17464**: Chain-of-Abstraction Reasoning — patrón complementario.
- **J.D. Hodges, "I Tested 13 Local LLMs on Tool Calling: March 2026"** (jdhodges.com, 19 Mar 2026), 40 test cases × 13 modelos en AMD AI Max+ 395 / LM Studio v0.4.6: *"Best overall: Qwen3.5 4B. 97.5% pass rate at 3.4 GB. Fast (48 tok/s), accurate, and the best multi-tool score of any model tested."* Scorecard: Selection 8/8, Args 8/8, Multi-Tool 7/8, Edge 8/8, Format 8/8. Confirma que el cuello de botella en 4B está en la columna **Multi-Tool**.
- **LangChain Blog "Plan-and-Execute Agents"**: arquitectura para separar plan (LLM grande/raro) de ejecución (cheaper / determinista).
- **Google The Keyword blog, 18 Dec 2025, Kat Black & Ravin Kumar** (blog.google/technology/developers/functiongemma/): FunctionGemma es un fine-tune de Gemma 3 270M. *"In our 'Mobile Actions' evaluation, fine-tuning transformed the model's reliability, boosting accuracy from a 58% baseline to 85%."* Confirma que un fine-tune ligero domain-specific es el camino para llevar SLMs a calidad de producción.
- **Ollama `orieg/gemma3-tools` card**: documenta el sesgo de tool-call del Gemma-3-4b.

## B.4 Veredicto VIABLE para este stack

**Arquitectura híbrida en tres capas**, todas en `planner.py`:

1. **Capa de validación de argumentos** (Pydantic). Si `office.open` se invoca con `path=None`, se rechaza ANTES de ejecutar y se intenta auto-relleno desde el scratchpad.
2. **Despachador determinista de pares conocidos**: tras `filesystem.search` con resultados, **antes de re-llamar al LLM**, el planner detecta el patrón y arma la segunda llamada solo.
3. **Reflexión LLM como fallback** cuando el patrón determinista no aplica.

## B.5 Código listo para integrar — `planner.py`

```python
# planner.py — añadir/refactorizar. Conserva el loop max_agent_turns=8 existente.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import logging
import os

from pydantic import BaseModel, ValidationError, Field

log = logging.getLogger("carter.planner")


# ─── 1. Schemas Pydantic para validación de argumentos críticos ──────────────

class OpenArgs(BaseModel):
    path: str = Field(..., min_length=1)

class PlayArgs(BaseModel):
    path: Optional[str] = None
    query: Optional[str] = None

    def either(self) -> bool:
        return bool(self.path) or bool(self.query)

class ReadArgs(BaseModel):
    path: str = Field(..., min_length=1)


# ─── 2. Scratchpad de resultados de tools del turno actual ───────────────────

@dataclass
class ToolResult:
    tool: str
    args: dict
    result: Any
    ok: bool

@dataclass
class Scratchpad:
    history: list[ToolResult] = field(default_factory=list)

    def last(self, tool_name: str) -> Optional[ToolResult]:
        for tr in reversed(self.history):
            if tr.tool == tool_name and tr.ok:
                return tr
        return None

    def add(self, tr: ToolResult) -> None:
        self.history.append(tr)


# ─── 3. Helpers para extraer "path" desde resultados de filesystem.search ────

def _first_path_from_search(result: Any) -> Optional[str]:
    """filesystem.search puede devolver: lista de dicts, lista de strs, o dict.
    Extrae el PRIMER path válido. Robusto a varios formatos."""
    if not result:
        return None
    if isinstance(result, str):
        return result if os.path.exists(result) else None
    if isinstance(result, dict):
        for k in ("path", "fullpath", "filepath"):
            if k in result and isinstance(result[k], str):
                return result[k]
        if "items" in result:
            return _first_path_from_search(result["items"])
    if isinstance(result, list) and result:
        return _first_path_from_search(result[0])
    return None


# ─── 4. Despachador determinista de pares conocidos ──────────────────────────

_KNOWN_CHAINS: dict[str, dict[str, Callable[[ToolResult], dict]]] = {
    "filesystem.search": {
        "office.open":   lambda tr: {"path": _first_path_from_search(tr.result)},
        "media.play":    lambda tr: {"path": _first_path_from_search(tr.result)},
        "files.read":    lambda tr: {"path": _first_path_from_search(tr.result)},
    },
}


def deterministic_next_call(
    scratch: Scratchpad,
    user_intent: str,    # p.ej. 'open' | 'play' | 'read'
) -> Optional[tuple[str, dict]]:
    """Si hay un filesystem.search OK reciente y el intent del usuario es
    abrir/reproducir/leer, devuelve (tool, args) listo para ejecutar SIN llamar al LLM.
    """
    intent_to_tool = {"open": "office.open", "play": "media.play", "read": "files.read"}
    target_tool = intent_to_tool.get(user_intent)
    if not target_tool:
        return None

    last_search = scratch.last("filesystem.search")
    if not last_search:
        return None

    builder = _KNOWN_CHAINS.get("filesystem.search", {}).get(target_tool)
    if not builder:
        return None

    args = builder(last_search)
    if not args.get("path"):
        log.warning("Despachador determinista: no se pudo extraer path de %s",
                    last_search.result)
        return None

    log.info("Despachador determinista: encadenando %s -> %s con %s",
             last_search.tool, target_tool, args)
    return target_tool, args


# ─── 5. Validación + auto-relleno desde scratchpad ───────────────────────────

_VALIDATORS = {
    "office.open": OpenArgs,
    "files.read":  ReadArgs,
    "media.play":  PlayArgs,
}


def validate_and_repair(
    tool: str,
    args: dict,
    scratch: Scratchpad,
) -> tuple[dict, list[str]]:
    """Valida args con Pydantic. Si fallan por `path` faltante, intenta
    auto-relleno desde el último filesystem.search OK."""
    schema = _VALIDATORS.get(tool)
    if not schema:
        return args, []

    warnings: list[str] = []
    try:
        schema(**args)
        return args, warnings
    except ValidationError as exc:
        missing_path = any(
            e["loc"] == ("path",) and e["type"] in ("missing", "string_too_short")
            for e in exc.errors()
        )
        if not missing_path:
            raise

        last = scratch.last("filesystem.search")
        if last is None:
            raise
        path = _first_path_from_search(last.result)
        if not path:
            raise

        args = {**args, "path": path}
        schema(**args)
        warnings.append(
            f"auto-repair: 'path' rellenado desde filesystem.search → {path!r}"
        )
        log.warning(warnings[-1])
        return args, warnings


# ─── 6. Reflexión LLM como fallback ──────────────────────────────────────────

REFLECTION_PROMPT_TEMPLATE = """\
Acabas de ejecutar la tool `{tool}` con args {args}.
Resultado:
{result}

Pregunta del usuario original: {user_query!r}

Pasos posibles:
1) Si el resultado responde a la pregunta, NO llames otra tool: responde en lenguaje natural.
2) Si necesitas otra tool, asegúrate de incluir TODOS los argumentos obligatorios,
   copiando valores del resultado anterior si corresponde.
"""

def build_reflection_message(
    last_tool: str, last_args: dict, last_result: Any, user_query: str
) -> str:
    return REFLECTION_PROMPT_TEMPLATE.format(
        tool=last_tool,
        args=last_args,
        result=repr(last_result)[:1500],
        user_query=user_query,
    )


# ─── 7. Loop integrado (pseudocódigo; encajar en el loop existente) ──────────

def agent_step(
    user_query: str,
    user_intent: str,
    scratchpad: Scratchpad,
    llm_call: Callable[..., dict],
    tools_runtime: dict[str, Callable[..., Any]],
    max_turns: int = 8,
) -> str:
    for turn in range(max_turns):
        # (a) Intento determinista PRIMERO si hay un patrón conocido encadenable.
        det = deterministic_next_call(scratchpad, user_intent)
        if det is not None:
            tool, args = det
            try:
                args, _ = validate_and_repair(tool, args, scratchpad)
                result = tools_runtime[tool](**args)
                scratchpad.add(ToolResult(tool, args, result, ok=True))
                return f"OK: {tool} ejecutada con {args}"
            except Exception as exc:
                log.exception("Despachador determinista falló; cayendo a LLM.")
                scratchpad.add(ToolResult(tool, args, str(exc), ok=False))

        # (b) Camino LLM normal con reflexión si hay tool result previo.
        extra_context = ""
        if scratchpad.history:
            last = scratchpad.history[-1]
            extra_context = build_reflection_message(
                last.tool, last.args, last.result, user_query
            )

        decision = llm_call(user_query=user_query, extra_context=extra_context)
        if decision.get("final_answer"):
            return decision["final_answer"]

        tool = decision["tool"]
        args = decision.get("args", {})

        # (c) Validación + auto-repair ANTES de ejecutar la tool.
        try:
            args, warns = validate_and_repair(tool, args, scratchpad)
        except ValidationError as exc:
            scratchpad.add(ToolResult(tool, args, f"VALIDATION_ERROR: {exc}", ok=False))
            continue

        # (d) Ejecutar tool y registrar.
        try:
            result = tools_runtime[tool](**args)
            scratchpad.add(ToolResult(tool, args, result, ok=True))
        except Exception as exc:
            scratchpad.add(ToolResult(tool, args, str(exc), ok=False))

    return "No se pudo completar la tarea en el límite de turnos."
```

## B.6 Qué MEDIR en el dataset propio

- **Cobertura del despachador determinista**: % de los fallos reales que caen en `search→open / play / read`. Si es <40%, ampliar `_KNOWN_CHAINS` con más patrones (p. ej. `web.search→web.fetch`).
- **Tasa de auto-repair**: cuántas veces `validate_and_repair` rellena `path=None` con éxito. Si es muy alta, considerar **eliminar `path` del schema** y derivarlo siempre del scratchpad (schema adaptation, 2510.07248).
- **Latencia con/sin reflexión LLM**: el prompt extra puede añadir 200–500 ms por turno en GGUF Q4. Medir 3 condiciones (sin reflexión / con reflexión / determinista) en el smoke test 12/12.
- **Fine-tune como Etapa 3**: si tras todo lo anterior el smoke test no llega a 100% en los pares `search→X`, un fine-tune ligero sobre 1–2 K ejemplos sintéticos puede llevar el modelo del 58% al 85% (números de FunctionGemma en Mobile Actions, según Google The Keyword blog, 18 Dec 2025).

---

# PROBLEMA C — Foco + Maximize 100% fiable antes de teclear (Windows)

## C.1 Diagnóstico

Tres causas concurrentes:

1. **Foreground-lock de Windows**: per Microsoft Learn `SetForegroundWindow`, *"The system restricts which processes can set the foreground window"*.
2. **UWP / Microsoft Store apps**: el `hwnd` con título visible pertenece a **`ApplicationFrameHost.exe`** (clase `ApplicationFrameWindow`); el `hwnd` real de la app es un **hijo** con clase `Windows.UI.Core.CoreWindow`. `GetWindowThreadProcessId` sobre el padre devuelve la PID del **host**, no de la app.
3. **Error 87 (`ERROR_INVALID_PARAMETER`) en `AttachThreadInput`**: Microsoft Learn lo documenta literalmente: *"A thread cannot attach to itself. Therefore, idAttachTo cannot equal idAttach."* Issues #240 y #270 de pywinauto documentan exactamente este patrón cuando `cur_fore_thread == 0` o coincide con el actual.

**Estado actual de WhatsApp y Spotify (May 2026)**:
- **WhatsApp Desktop**: Electron (pre-2022) → UWP/WinUI (gHacks Aug 2022) → WebView2 starting v2.2569.0.0 (late 2025, Daring Fireball 8 Nov 2025; Neowin). En los tres casos sigue distribuido como Microsoft Store packaged app, hospedado por `ApplicationFrameHost.exe`. Process real: `WhatsApp.exe`.
- **Spotify**: dos variantes coexisten — Microsoft Store (UWP, "bloatware" según Microsoft Q&A 3725085) y `SpotifyFullSetup.exe` desde spotify.com (Win32 Chromium/CEF, clase `Chrome_WidgetWin_0`). Spotify Community thread 2417335 confirma ambos paths.

## C.2 Opciones — tabla comparativa

| Técnica | Aplica a Win32 | Aplica a UWP | Reportada 100% fiable | Notas |
|---|---|---|---|---|
| `ShowWindow(SW_RESTORE)` + `SetForegroundWindow` solo | Parcial | No | No (foreground-lock) | Baseline insuficiente |
| `AttachThreadInput` + `SetForegroundWindow` | Mayoría de Win32 | No (host es ApplicationFrameHost) | No (error 87 si no se guarda contra self-attach) | Patrón clásico de Shlomi Borovitz |
| Tap **ALT** vía `SendInput` antes de `SetForegroundWindow` | Sí | Parcial | *"100% reliable considering Windows is the one to enable calls to SetForegroundWindow"* (gist Aetopia 1581b40f00cc0cadc93a0e8ccb65dc8c) | Microsoft Learn `LockSetForegroundWindow`: *"The system automatically enables calls to SetForegroundWindow if the user presses the ALT key"* |
| `AllowSetForegroundWindow(ASFW_ANY)` | Sí | Sí | Sólo habilita | Combinable con todo |
| `uiautomation.SetActive()` / `SwitchToThisWindow()` sobre `Windows.UI.Core.CoreWindow` interno | No necesario | **Sí (recomendado por maintainer)** | yinkaisheng Issue #52 | Capa 2 para UWP |
| `keybd_event` para tap ALT | Sí | Sí | **Superseded** | Microsoft Learn `keybd_event`: *"Note: This function has been superseded. Use SendInput instead."* |

**Veredicto**: secuencia compuesta — `ShowWindow(SW_RESTORE)` → `AllowSetForegroundWindow(ASFW_ANY)` → tap **ALT** vía **`SendInput`** → `AttachThreadInput` (con guarda contra self-attach) → `BringWindowToTop` + `SetForegroundWindow` → verificación. Si la verificación falla y la ventana es UWP, enumerar hijos `Windows.UI.Core.CoreWindow`, obtener el PID real (≠ ApplicationFrameHost.exe) y usar `uiautomation.SetActive()`.

## C.3 Fuentes oficiales

- **Microsoft Learn — SetForegroundWindow** (winuser.h): restricciones canónicas.
- **Microsoft Learn — LockSetForegroundWindow**: *"The system automatically enables calls to SetForegroundWindow if the user presses the ALT key…"*.
- **Microsoft Learn — AllowSetForegroundWindow**: parámetro `ASFW_ANY`.
- **Microsoft Learn — AttachThreadInput**: *"A thread cannot attach to itself. Therefore, idAttachTo cannot equal idAttach."*
- **Microsoft Learn — keybd_event**: *"Note: This function has been superseded. Use SendInput instead."*
- **Microsoft Learn — SendInput**: API moderna.
- **Microsoft Learn — GetWindowThreadProcessId**: *"If the window handle is invalid, the return value is zero."*
- **gist Aetopia 1581b40f00cc0cadc93a0e8ccb65dc8c** ("Bypassing SetForegroundWindow(HWND hWnd) Restrictions"): catálogo de métodos; declara el ALT-SendInput como 100% fiable.
- **StackOverflow Q39702704** ("Connecting UWP apps hosted by ApplicationFrameHost to their real processes"): patrón EnumChildWindows + filtro por ProcessName.
- **gist jymcheong/30a53e8810d06c9a33918ab468e624ef**: implementación C# de referencia.
- **microsoft/PowerToys issue #1766** (Window Walker UWP): confirma oficialmente el patrón.
- **microsoft/PowerToys PR #1282** *"Do not use SendInput hack to workaround the SetForegroundWindow bug for patched Windows Versions"*: argumenta que en Windows parcheado MS recomienda `AttachThreadInput`. Por seguridad combinamos los dos.
- **yinkaisheng/Python-UIAutomation-for-Windows Issue #52**: el maintainer recomienda `SetActive()` o `SwitchToThisWindow()` sobre `SetFocus()` para foreground.
- **gHacks (17 Aug 2022)**, **Neowin (2022, Nov 2025)**, **WABetaInfo**, **Daring Fireball (8 Nov 2025)**: trayectoria WhatsApp Electron → UWP → WebView2.
- **Microsoft Q&A 3725085** + **Spotify Community thread 2417335**: dos variantes de Spotify (Store UWP / SpotifyFullSetup Win32).

## C.4 Veredicto VIABLE para este stack

`win_focus.py` con **pywin32 puro** como capa 1, **`uiautomation` (comtypes)** como capa 2 para UWP. Sin pywinauto (cuyo `SetForegroundWindow` lanzó error 87 intermitente en el entorno real del usuario, consistente con pywinauto issues #240 y #270).

## C.5 Código listo para integrar — `win_focus.py` (NUEVO)

```python
# win_focus.py — módulo nuevo. Pywin32 puro + uiautomation/comtypes para UWP.
# Diseñado para Windows 10/11. Sin dependencias de pywinauto.
from __future__ import annotations
import ctypes
import logging
import time
from ctypes import wintypes
from typing import Optional

import win32api
import win32con
import win32gui
import win32process

log = logging.getLogger("carter.win_focus")

# ─── Constantes ────────────────────────────────────────────────────────────
SW_RESTORE       = win32con.SW_RESTORE
SW_SHOWMAXIMIZED = win32con.SW_SHOWMAXIMIZED
SW_SHOW          = win32con.SW_SHOW
ASFW_ANY         = -1               # AllowSetForegroundWindow: any process
VK_MENU          = 0x12             # ALT key
KEYEVENTF_KEYUP  = 0x0002
INPUT_KEYBOARD   = 1

UWP_FRAME_CLASS  = "ApplicationFrameWindow"
UWP_CORE_CLASS   = "Windows.UI.Core.CoreWindow"
APP_FRAME_HOST   = "applicationframehost.exe"

# ─── Estructuras para SendInput. NO usar keybd_event:
#     Microsoft Learn: "This function has been superseded. Use SendInput instead." ─
PUL = ctypes.POINTER(wintypes.ULONG)
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", PUL)]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", PUL)]
class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]
class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

_user32 = ctypes.WinDLL("user32", use_last_error=True)


def _send_alt_tap() -> None:
    """Tap ALT vía SendInput. Microsoft Learn (LockSetForegroundWindow):
    'The system automatically enables calls to SetForegroundWindow if the user
    presses the ALT key...'."""
    down = INPUT(type=INPUT_KEYBOARD,
                 u=_INPUTunion(ki=KEYBDINPUT(VK_MENU, 0, 0, 0, None)))
    up   = INPUT(type=INPUT_KEYBOARD,
                 u=_INPUTunion(ki=KEYBDINPUT(VK_MENU, 0, KEYEVENTF_KEYUP, 0, None)))
    arr = (INPUT * 2)(down, up)
    _user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def _allow_set_foreground_any() -> None:
    """AllowSetForegroundWindow(ASFW_ANY): habilita SetForegroundWindow para
    cualquier proceso. No es 'foregrouding' por sí mismo; es un permiso."""
    _user32.AllowSetForegroundWindow(ASFW_ANY)


def _get_process_name(pid: int) -> str:
    """Nombre del .exe del proceso. Usa psutil si está; si no, OpenProcess."""
    try:
        import psutil  # opcional pero recomendado
        return psutil.Process(pid).name().lower()
    except Exception:
        try:
            h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                                     False, pid)
            try:
                exe = win32process.GetModuleFileNameEx(h, 0)
            finally:
                win32api.CloseHandle(h)
            return exe.split("\\")[-1].lower()
        except Exception:
            return ""


def _is_uwp_frame(hwnd: int) -> bool:
    try:
        return win32gui.GetClassName(hwnd) == UWP_FRAME_CLASS
    except Exception:
        return False


def _find_uwp_real_child(frame_hwnd: int) -> Optional[int]:
    """Para una ApplicationFrameWindow, devolver el hijo Windows.UI.Core.CoreWindow
    cuyo proceso NO es ApplicationFrameHost.exe. Patrón canónico StackOverflow
    Q39702704; replicado en microsoft/PowerToys WindowWalker (issue #1766)."""
    real: list[int] = []

    def _cb(child_hwnd: int, _: int) -> bool:
        try:
            if win32gui.GetClassName(child_hwnd) != UWP_CORE_CLASS:
                return True
            _, pid = win32process.GetWindowThreadProcessId(child_hwnd)
            if _get_process_name(pid) != APP_FRAME_HOST:
                real.append(child_hwnd)
                return False  # detener
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(frame_hwnd, _cb, None)
    except Exception:
        # pywin32 puede lanzar al detener early; ignorar.
        pass
    return real[0] if real else None


def _safe_attach(my_tid: int, fg_tid: int, attach: bool) -> bool:
    """AttachThreadInput con guarda contra error 87. Microsoft Learn:
    'A thread cannot attach to itself. Therefore, idAttachTo cannot equal idAttach.'"""
    if fg_tid == 0 or fg_tid == my_tid:
        return False
    try:
        win32process.AttachThreadInput(my_tid, fg_tid, attach)
        return True
    except Exception as exc:
        log.warning("AttachThreadInput(%s,%s,%s) falló: %r",
                    my_tid, fg_tid, attach, exc)
        return False


def _verify_foreground(hwnd: int, timeout: float = 0.4) -> bool:
    """Espera hasta `timeout` a que `hwnd` (o su frame UWP) sea foreground."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        fg = win32gui.GetForegroundWindow()
        if fg == hwnd:
            return True
        # En UWP el foreground reportado es el frame, no el CoreWindow.
        try:
            parent = win32gui.GetAncestor(hwnd, 2)  # GA_ROOT
            if fg == parent:
                return True
        except Exception:
            pass
        time.sleep(0.02)
    return False


# ─── Capa 2 (UWP): uiautomation sobre el CoreWindow real ────────────────────

def _uia_set_active(hwnd: int) -> bool:
    """Recomendación del maintainer yinkaisheng (Issue #52): usar
    SwitchToThisWindow / SetActive en lugar de SetFocus para foreground."""
    try:
        import uiautomation as auto
    except Exception as exc:
        log.warning("uiautomation no disponible: %r", exc)
        return False
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        if ctrl is None:
            return False
        try:
            ctrl.SwitchToThisWindow()
            return True
        except Exception:
            pass
        try:
            ctrl.SetActive()
            return True
        except Exception:
            pass
        return False
    except Exception as exc:
        log.warning("uiautomation falló para hwnd=%s: %r", hwnd, exc)
        return False


# ─── API pública ────────────────────────────────────────────────────────────

def focus_and_maximize(
    hwnd: int,
    expected_title_substr: Optional[str] = None,
    maximize: bool = True,
    retries: int = 3,
    backoff: float = 0.15,
) -> bool:
    """Lleva `hwnd` al foreground de forma fiable y, opcionalmente, lo maximiza.
    Devuelve True si la verificación final confirma que la ventana es foreground.

    Secuencia (pywin32 puro):
      1) ShowWindow(SW_RESTORE) si está minimizada; opcionalmente SW_SHOWMAXIMIZED.
      2) AllowSetForegroundWindow(ASFW_ANY).
      3) Tap ALT vía SendInput (desbloquea SetForegroundWindow).
      4) AttachThreadInput (con guarda contra self-attach → error 87).
      5) BringWindowToTop + SetForegroundWindow.
      6) Verificación con timeout. Si falla y es UWP, fallback a uiautomation
         sobre el CoreWindow real.
    """
    if not win32gui.IsWindow(hwnd):
        log.error("focus_and_maximize: hwnd %s no es ventana válida.", hwnd)
        return False

    for attempt in range(retries):
        try:
            # 1) Restore / Maximize
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, SW_RESTORE)
            if maximize:
                win32gui.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
            else:
                win32gui.ShowWindow(hwnd, SW_SHOW)

            # 2) Permiso amplio (idempotente).
            _allow_set_foreground_any()

            # 3) Tap ALT para que Windows habilite SetForegroundWindow.
            _send_alt_tap()

            # 4) AttachThreadInput con guarda.
            my_tid = win32api.GetCurrentThreadId()
            fg_hwnd = win32gui.GetForegroundWindow()
            fg_tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd) \
                        if fg_hwnd else (0, 0)
            attached = _safe_attach(my_tid, fg_tid, True)
            try:
                # 5) Foreground real.
                try:
                    _user32.BringWindowToTop(hwnd)
                except Exception:
                    pass
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception as exc:
                    log.info("SetForegroundWindow lanzó %r (attempt %d)",
                             exc, attempt)
            finally:
                if attached:
                    _safe_attach(my_tid, fg_tid, False)

            # 6) Verificación.
            if _verify_foreground(hwnd):
                if expected_title_substr is None or \
                   expected_title_substr.lower() in (win32gui.GetWindowText(hwnd) or "").lower():
                    return True

            # 6b) Fallback UWP: probar con el CoreWindow real.
            if _is_uwp_frame(hwnd):
                real = _find_uwp_real_child(hwnd)
                target = real if real else hwnd
                if _uia_set_active(target) and _verify_foreground(hwnd):
                    return True

        except Exception as exc:
            log.exception("focus_and_maximize attempt %d falló: %r",
                          attempt, exc)

        time.sleep(backoff * (2 ** attempt))   # backoff exponencial

    log.error("focus_and_maximize: no se pudo enfocar hwnd=%s tras %d intentos.",
              hwnd, retries)
    return False


def find_window_by_title(title_substr: str) -> Optional[int]:
    """Busca top-level window cuyo título contiene `title_substr`."""
    needle = title_substr.lower()
    result: list[int] = []

    def _cb(hwnd: int, _: int) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                t = win32gui.GetWindowText(hwnd) or ""
                if needle in t.lower():
                    result.append(hwnd)
            except Exception:
                pass
        return True

    win32gui.EnumWindows(_cb, None)
    return result[0] if result else None


def focus_app(app_name: str) -> bool:
    """High-level: 'WhatsApp', 'Spotify', etc.
    Maneja Store (UWP) y Win32 (SpotifyFullSetup, etc.) de forma transparente."""
    hwnd = find_window_by_title(app_name)
    if hwnd is None:
        log.warning("focus_app: ventana '%s' no encontrada.", app_name)
        return False
    return focus_and_maximize(hwnd, expected_title_substr=app_name)
```

## C.6 Notas de integración y pitfalls

- **Procesos elevados (UAC / integrity level mismatch)**: si CARTER corre **no-elevado** y la app de destino corre **elevada** (admin), Windows bloquea totalmente la sincronización de input. **CARTER debe correr al mismo nivel de integridad que las apps que va a tocar** (lo más común: ambos no-elevado).
- **Si `psutil` no está**: el código degrada a `win32api.OpenProcess` + `GetModuleFileNameEx`. Recomendar `pip install psutil`.
- **Error 87 evitado**: `_safe_attach` chequea explícitamente `fg_tid != my_tid` y `fg_tid != 0`. Issues #240 y #270 de pywinauto documentan que el crash ocurre cuando `cur_fore_thread` es 0 o igual al actual.
- **WhatsApp WebView2 (≥ v2.2569.0.0, late 2025)**: aunque internamente sea WebView2, sigue siendo packaged-Store, así que el path UWP (CoreWindow + ApplicationFrameHost) sigue aplicando.
- **Spotify Win32 (instalado desde `SpotifyFullSetup.exe`)**: clase `Chrome_WidgetWin_0`, NO es UWP. El path Win32 (capa 1) basta.
- **Aclaración técnica**: `GetWindowThreadProcessId` devuelve 0 si el hwnd es inválido (Microsoft Learn). El comportamiento *"NULL = foreground thread"* corresponde a una API distinta, `GetGUIThreadInfo`, no a `GetWindowThreadProcessId`.

## C.7 Qué MEDIR en el dataset propio

- **Tasa de éxito de `focus_and_maximize`** sobre una matriz {WhatsApp Store, Spotify Store, Spotify Win32, Notepad, Word, Chrome, Edge} × estados {minimizada / detrás / ya foreground}. Objetivo: ≥98% sin recurrir a la capa 2.
- **Latencia media** de la secuencia completa (debe ser <300 ms para no afectar UX de voz).
- **Frecuencia de fallback uiautomation**: si la capa 2 se dispara >20% en UWP, considerar saltarse la capa 1 para UWP detectado y entrar directo en `_uia_set_active`.

---

# Recomendaciones (staged, accionables)

## Etapa 1 — esta semana (impide repetir el incidente Mortal Kombat → .docx)
1. Mergear `encoder_health.py` y conectarlo al startup. Si falla, exit code 2 visible.
2. Mergear `is_interrogative` y el boost +0.20 en `classify_intent`. Re-correr el smoke test 12/12 y el holdout (recall objetivo: ≥0.881, idealmente ≥0.89 en preguntas informativas).
3. Añadir telemetría: log estructurado de `interrogative_gate=True/False` por turno.

**Umbral de cambio de plan**: si tras 50 queries reales el gate sintáctico tiene <90% de precisión (marca acciones como info), bajar el boost a 0.10 y reentrenar las anclas multilingües.

## Etapa 2 — próximas 2 semanas (encadenamiento)
1. Mergear el despachador determinista de los 3 pares `search→open / play / read` en `planner.py`.
2. Añadir validación Pydantic sobre `office.open`, `media.play`, `files.read`.
3. Instrumentar `auto-repair`: contar cuántas veces se gatilla. Si la tasa es >30%, considerar **eliminar `path` del schema** y derivarlo siempre del scratchpad (schema adaptation, ArXiv 2510.07248).
4. Activar reflexión LLM sólo cuando NO hay patrón determinista y `validate_and_repair` falló.

**Umbral**: si tras la Etapa 2 el smoke test no llega a 100% en los pares `search→X`, evaluar fine-tune ligero de Gemma 4 sobre 1–2 K ejemplos sintéticos de encadenamiento (paralelo al patrón FunctionGemma: 58%→85% con fine-tune en Mobile Actions, per Google The Keyword blog 18 Dec 2025).

## Etapa 3 — próximo mes (foco Windows)
1. Crear `win_focus.py` con el contenido de C.5.
2. Migrar el tool actual `window(action=focus)` a usar `focus_and_maximize`.
3. Smoke test específico: matriz de 7 apps × 3 estados.
4. Añadir circuit breaker: si `focus_and_maximize` falla 3 veces seguidas sobre la misma app, devolver error claro al usuario ("no pude llevar X al frente") en vez de tipear a ciegas.

**Umbral**: si la tasa de éxito Win32 <95% o UWP <90%, revisar GPO o anti-malware que pueda estar bloqueando `SendInput` en la máquina del usuario.

---

# Caveats y riesgos

- **Multi-idioma del gate sintáctico**: portugués comparte palabras-pregunta con español ("que", "como", "quando"); esto no afecta al gate (sólo detecta interrogatividad, no idioma). En italiano "che" puede ser pronombre relativo además de interrogativo; el signo `?` actúa como tie-breaker.
- **`AllowSetForegroundWindow` no funciona si el proceso que llama NO puede setear foreground**: Microsoft Learn lo dice explícitamente. Por eso lo combinamos con el tap ALT.
- **Tap ALT es discutido**: microsoft/PowerToys PR #1282 lo califica como "hack" y propone evitarlo en Windows parcheado. Por eso el módulo combina ALT + AttachThreadInput + AllowSetForegroundWindow: si Microsoft cierra uno de los paths, el otro debería seguir funcionando.
- **WhatsApp WebView2 (Nov 2025) y la decisión de Meta** son noticias muy recientes (Daring Fireball 8 Nov 2025; Neowin Nov 2025). Es posible que para mayo de 2026 hayan revertido o cambiado de nuevo; revalidar antes del release.
- **Limitación del despachador determinista**: cubre los 3 pares documentados. Si el usuario empieza a pedir cadenas más largas (p. ej. `search → open → edit → save`), hay que extender la tabla o caer en plan-and-execute clásico.
- **Encoder health-check con red caída**: el modelo se carga desde caché HF si está descargado; si no, requiere red. Para 100% offline, pre-poblar la caché y exportar `HF_HUB_OFFLINE=1`.
- **NER masking descartado**: lo descartamos para el hot path porque su coste de latencia (10–50 ms) no compensa el beneficio marginal sobre el gate sintáctico para queries cortas de voz. Lo dejamos como herramienta de debug offline para entender por qué un query específico se rutea mal.
- **El recall holdout 0.881 NO está validado tras los cambios propuestos** — es responsabilidad del usuario re-correr la evaluación antes de mergear cada etapa.
- **La cita del paper 2510.07248** ("Don't Adapt Small Language Models for Tools…") sobre "below 10B parameters" combina la afirmación principal del paper (degradación severa de SLMs) con la definición de SLM dada en la introducción del propio paper; la frase exacta del paper es *"SLMs struggle significantly with these tasks, exhibiting severe performance degradation compared to larger models"*.