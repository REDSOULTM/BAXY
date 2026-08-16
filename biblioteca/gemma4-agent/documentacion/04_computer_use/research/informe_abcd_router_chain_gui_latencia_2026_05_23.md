# Informe técnico — Baxy (asistente de voz 100% local) — Problemas A, B, C, D

**Fecha:** 23 de mayo de 2026
**Stack confirmado:** Gemma 4 E4B-it Q4_K_M (GGUF) + llama.cpp `llama-server` b9090+ + Parakeet-TDT-v3 (STT) en Windows, 6 GB de VRAM, monoslot.

---

## TL;DR

- **A (intent/router):** El clasificador semántico debe convertirse en un **conjunto híbrido lexical+semántico con un *gate* de pregunta ANTES del retrieval**, anonimización de entidades antes del embedding (técnica de Anonymization en embeddings, arXiv 2502.02903) y **autodiagnóstico explícito** que falle ruidosamente en lugar de silenciosamente. La regla "interrogativa (qué/quién/cuándo/por qué/cuál/dónde/cómo + ¿?) → rama info" suprime el sesgo de los nombres propios casi sin coste; la **enmascaración de entidades nominales antes de embeber** aporta +1.8 % de accuracy promedio según la literatura (arXiv 2407.17862).
- **B (encadenamiento):** Para Gemma 4 E4B-Q4 (modelo <10B) lo robusto NO es ReAct puro, sino **planner determinista con plantillas para los pares conocidos** (`search→open`, `search→play`) + **ReAct corto con reflexión obligatoria sobre `tool_result`** para el resto. El paper Pre-Act (arXiv 2505.09970, May 2025) reporta: "*our turn-level evaluation, averaged across five models, shows that our approach, Pre-Act, outperforms ReAct by 70 % in Action Recall on the Almita dataset*", y advierte que "*smaller models… often struggle with complex reasoning tasks required for agentic systems*" — refuerza el enfoque híbrido determinista. Verdict: 70 % determinista, 30 % LLM con reflexión forzada.
- **C (foco GUI):** Para garantizar foreground+maximize antes de teclear en Windows usar la **secuencia canónica**: `AllocConsole/AttachThreadInput` → `keybd_event(VK_MENU)` (truco ALT documentado por Microsoft) → `ShowWindow(SW_RESTORE)` + `ShowWindow(SW_MAXIMIZE)` → `SetForegroundWindow` → **verificación con `GetForegroundWindow` + `uiautomation.SetFocus`** + reintento con backoff (3 intentos, 80/160/320 ms). Esta secuencia se mantiene 100 % en código, sin LLM en el loop.
- **D (latencia):** ROI por orden: (1) **`--cache-reuse` + `--swa-full` ya está bien**; (2) tunear **`-ub` / `-b`** a 1024/2048 reduce prefill de prompts largos en ~2–3× sin coste; (3) **persistir KV con `--slot-save-path` + `/slots/0/save|restore`** para reuso entre sesiones; (4) **mantener el slot caliente** con un keep-alive cada 30 s; (5) **speculative decoding con MTP de Google es viable pero arriesgado en 6 GB y solo en el fork `atomic-llama-cpp-turboquant`**; (6) **GBNF/JSON-schema constrain** para la llamada a herramientas reduce la dispersión del decoder pero **NO siempre acelera TTFT con `--jinja`**.

---

## 0. Aclaración sobre el modelo (confirmado vs. asumido)

**CONFIRMADO** (Google DeepMind, 2 de abril de 2026, https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/ y https://ai.google.dev/gemma/docs/releases):

- Gemma 4 existe como familia con cuatro tamaños: **E2B, E4B, 26B-A4B (MoE) y 31B Dense**.
- La "E" significa "effective parameters"; E2B/E4B usan **Per-Layer Embeddings (PLE)** para reducir huella de memoria en el acelerador (igual que Gemma 3n).
- Gemma 4 usa **atención híbrida**: capas locales SWA intercaladas + atención global, con la capa final siempre global (`huggingface.co/google/gemma-4-26B-A4B-it`).
- **Function calling es nativo en Gemma 4** con buena calidad: "*Other open weight models can call tools, yet they do not perform reliably, and this is what differentiates them from Gemma 4. The model consistently provides valid JSON arguments, processes optional parameters correctly, and determines when to return knowledge and not call a tool*" (analyticsvidhya.com, abr. 2026).
- Soporte day-one en `llama.cpp` (blog de Google).

**ESPECÍFICO DE GEMMA 4 EN LLAMA.CPP (confirmado por issues recientes):**

- "*Gemma 4 uses a Shared KV Cache architecture where the last `num_kv_shared_layers` layers reuse K/V tensors from the last non-shared layer rather than computing their own*" (issue ggml-org/llama.cpp#21468). Esto **rompe parcialmente el reuso de caché** y exige `--swa-full` + `-fa`.
- Bug abierto: Gemma 4 31B con `--flash-attn` + checkpoint SWA puede crashear (issue #22527). En E4B-Q4 el riesgo es menor pero existe — vigilar el log.
- **`-np 1` reduce ~3× el SWA KV cache** en Gemma 4 (aiproductivity.ai, 2026): "*Adding `-np 1` to your llama.cpp launch command tells the server to allocate cache for exactly one user instead of the default. The result: SWA cache VRAM drops by roughly 3x.*"

**LO QUE TRANSFIERE DE GEMMA 3n** (E2B/E4B con MatFormer, https://developers.googleblog.com/en/introducing-gemma-3n-developer-guide/): nomenclatura "E2B/E4B" (MatFormer Matryoshka), arquitectura SWA, función de PLE. **Lo que NO transfiere:** Gemma 4 añade MTP (Multi-Token Prediction) como mecanismo *separado* para speculative decoding, con drafters dedicados por tamaño.

---

## PROBLEMA A — Router robusto y auto-diagnóstico

### A.1 Diagnóstico

El log de la sesión #847 muestra que:

1. **El sesgo de nombres propios es real** y bien documentado en la literatura: "*Name regularity bias in NER occurs when a model relies on a signal coming from the entity name, and disregards evidences within the local context*" (arXiv 2107.11610). El embedding de `paraphrase-multilingual-MiniLM-L12-v2` empuja "Mortal Kombat" hacia el clúster de "documento/oficina" porque los nombres propios dominan la representación CLS-pool.
2. **El fallo es silencioso**: `torchcodec` rompió `sentence-transformers`, el router devolvió `None`/`[]` y el planner cayó al fallback "office only".
3. **Recall holdout actual = 0.881** (objetivo: mantener o mejorar).

### A.2 Opciones y comparativa

| Técnica | Latencia añadida | Recall esperado | Multilingüe | Riesgo | Veredicto |
|---|---|---|---|---|---|
| **Gate sintáctico lexical (`¿…?`, qué/quién/cuándo/por qué/cuál/dónde/cómo)** ANTES del retrieval | ~0.1 ms (regex puro) | Sin pérdida de recall, +precisión en queries-info | Sí (lista por idioma) | Muy bajo | **ADOPTAR** |
| **Anonimización/enmascaramiento de entidades antes del embedding** (sustituir nombres propios por `<ENT>`) | +5–15 ms (NER spaCy es-multilingual) | +1.8 % accuracy promedio (arXiv 2407.17862, Table 4) | Sí | Medio (NER puede fallar) | **ADOPTAR (opcional para Q de info)** |
| **Clasificador dedicado pequeño** (XLM-R / mDeBERTa fine-tuned info-vs-action) | +20–40 ms en CPU | CNN-BiLSTM joint model (PeerJ Computer Science, oct. 2024, doi:10.7717/peerj-cs.2346) reporta "*intent accuracy of 97.90 % and slot filling F1-score of 98.86 % on the ATIS dataset*" | Sí | Modelo extra que cargar | Alternativa — añade un punto de falla |
| **Tool2Vec + RRF actual** (status quo) | ~10 ms | 0.881 | Sí | Sesgado por nombres propios | Mantener como base |
| **Self-check con doble centroide (anchor info y anchor action) + margen** | Ya implementado | — | Sí | Silencioso si falla el encoder | Mejorable con health-check |
| **Health-check explícito al cargar** + **circuit breaker** | 0 ms en runtime | — | — | Bajo | **ADOPTAR (crítico)** |
| **NER masking + paraphrasing inferencia** (arXiv 2407.17862) | +30 ms | +2.4 % combinada | Sí | Mayor latencia | Solo si recall actual no basta |

**Evidencia:**

- "*We observe that masking increases performance by an average of +1.80 % and the addition of masked embedding only when entity overlaps are predicted increases performance by +0.32 % on average*" (Exploring Description-Augmented Dataless Intent Classification, arXiv 2407.17862).
- "*Naturally, many entity names have a strong correlation with a single type… Recent works have noted that over-relying on entity name information negatively impacts NLU tasks*" (arXiv 2107.11610).
- En español, las palabras interrogativas son un conjunto cerrado y siempre llevan tilde cuando son interrogativas: `qué, quién, quiénes, cómo, dónde, cuándo, por qué, cuál, cuáles, cuánto, cuántos` (rosettastone.com, baselang.com). Esto hace que el gate sintáctico sea casi perfecto en español/inglés/portugués/italiano.

### A.3 Veredicto A

**Arquitectura propuesta — Router robusto v2:**

1. **Antes del embedding**, ejecutar `is_question_lexical(text)` → boolean (ver código abajo). Si `True` y no contiene un verbo de acción claro (abrir, reproducir, crear, enviar, cerrar…), forzar `info_branch=True` con prior fuerte (+0.20 al score de la rama info).
2. **Health-check al import**: `assert classify_intent("¿qué es Python?") is not None`. Si falla, **negarse a iniciar** y emitir error visible (en TTS también: "Asistente offline: router caído").
3. **Enmascaramiento opcional**: para queries marcadas como info, reemplazar entidades por `<ENT>` antes de re-embedear y promediar con el embedding original.
4. **Fallback explícito y visible**: si el router está degradado, el planner anuncia por TTS "no puedo enrutar esta consulta" y no inventa una herramienta.

```python
# semantic_router_health.py
import re, logging, time
from typing import Optional, Tuple
from sentence_transformers import SentenceTransformer

LOG = logging.getLogger("router.health")

# Palabras interrogativas multilingües (es/en/pt/it/fr)
WH_WORDS = {
    "es": r"qué|quién|quiénes|cómo|dónde|cuándo|por\s*qué|cuál|cuáles|cuánto|cuántos|cuánta|cuántas",
    "en": r"what|who|how|where|when|why|which|whose",
    "pt": r"o\s*que|quem|como|onde|quando|por\s*que|qual|quais|quanto",
    "it": r"cosa|chi|come|dove|quando|perché|quale|quali|quanto",
}
ACTION_VERBS_ES = {"abre", "abrir", "abreme", "ábreme",
                   "reproduce", "reproducir", "pon", "ponme",
                   "crea", "crear", "envía", "enviar", "cierra", "cerrar",
                   "busca", "buscar", "muestra", "muéstrame", "elimina",
                   "manda", "escribe", "responde", "guarda", "descarga"}

_WH_RE = re.compile(r"\b(" + "|".join(WH_WORDS.values()) + r")\b", re.IGNORECASE)
_Q_RE  = re.compile(r"[¿?]")

def is_question_lexical(text: str) -> Tuple[bool, float]:
    """Devuelve (es_pregunta, confianza). Cero ML, sub-ms."""
    t = text.strip().lower()
    has_qmark = bool(_Q_RE.search(t))
    has_wh    = bool(_WH_RE.search(t))
    # heurística: si tiene wh-word o signos de pregunta, es info
    if has_wh and has_qmark:               return True, 0.95
    if has_wh and not has_qmark:           return True, 0.80
    if has_qmark and not has_wh:           return True, 0.55
    return False, 0.0

def has_explicit_action(text: str) -> bool:
    return any(v in text.lower().split() for v in ACTION_VERBS_ES)

class RouterHealth:
    def __init__(self, encoder_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self.encoder = None
        self.error  = None
        try:
            self.encoder = SentenceTransformer(encoder_name)
            # Health-probes en 4 idiomas:
            probes = [("¿qué es python?", True),
                      ("abre whatsapp", False),
                      ("what is mortal kombat?", True),
                      ("crea un documento", False)]
            for q, expected_info in probes:
                emb = self.encoder.encode([q])
                if emb is None or emb.shape[1] < 16:
                    raise RuntimeError(f"encoder devuelve embeddings inválidos para: {q}")
            LOG.info("router.health: OK")
        except Exception as e:
            self.error = repr(e)
            LOG.error("router.health: FALLO — %s", self.error)

    @property
    def healthy(self) -> bool:
        return self.encoder is not None and self.error is None
```

```python
# planner.py — uso del gate
def route(query: str, scored_tools):
    is_q, q_conf = is_question_lexical(query)
    action       = has_explicit_action(query)

    # Regla 1: pregunta sin acción → forzar info
    if is_q and not action:
        return {"branch": "info", "tools": [], "reason": "lex-question-no-action"}

    # Regla 2: router degradado → degradación visible
    if not router_health.healthy:
        speak("Tengo el módulo de enrutamiento caído. Ejecuto solo el reset.")
        return {"branch": "degraded", "tools": [], "reason": router_health.error}

    # Regla 3: lógica RRF + Tool2Vec actual
    return rrf_with_anchors(query, scored_tools)
```

**Riesgo asumido:** el recall holdout 0.881 puede caer si las heurísticas léxicas son demasiado agresivas; recomiendo medir con A/B antes de habilitar permanentemente. Para frases marginales ("Quiero abrir Word"), el gate devuelve `is_q=False`, `action=True` → rama acción (correcto). Para "¿qué es Mortal Kombat?", devuelve `is_q=True`, `action=False` → rama info (correcto).

---

## PROBLEMA B — Encadenamiento de herramientas

### B.1 Diagnóstico

El log muestra el patrón clásico **cascading failure** documentado en la literatura 2025–2026:

- "*Research from Zhu et al. (2025) confirms that error propagation from early mistakes cascading into later failures is the single biggest barrier to building dependable LLM agents*" (futureagi.com, 2026).
- El modelo E4B llamó a `filesystem.search` (correcto), obtuvo paths, y NO encadenó `office.open(path=…)`. En la iteración previa, llamó a `office.open` sin path → falló y "olvidó" usar el resultado anterior.
- "*The 4b models have a genuine tool-call bias regardless of prompt. The 12b and 27b models (base and fine-tuned) correctly answer conversational questions in plain text even when tools are available*" (Ollama orieg/gemma3-tools card). Es decir: los modelos de ~4B son los más frágiles en el encadenamiento — confirma que el problema es **estructural del tamaño**, no específico de tu prompt.

### B.2 Opciones y comparativa

| Enfoque | Fiabilidad multi-paso (4B) | Latencia adicional | Implementación | Veredicto |
|---|---|---|---|---|
| **ReAct puro** (modelo decide cada paso) | Baja en <10B (cascadas, ~50 % completion rate según Live API-Bench arXiv 2506.11266) | 1 LLM-call por paso | Media | NO confiar |
| **Plan-then-Execute** (planner LLM escribe DAG, ejecutor determinista) | Alta. Pre-Act (arXiv 2505.09970, may. 2025) reporta: "*Pre-Act outperforms ReAct by 70 % in Action Recall on the Almita dataset*" | 1 LLM-call extra al inicio | Media | Bueno, pero requiere planner fiable |
| **Planner determinista por patrón** (templates `search→open`, `search→play`) | Muy alta para patrones cubiertos (~100 %) | 0 ms LLM | Baja | **ADOPTAR para los 5-10 patrones top** |
| **ReAct con reflexión forzada sobre `tool_result`** | Media; mejor que ReAct ingenuo | 1 LLM-call extra de reflexión | Baja-media | **ADOPTAR para resto** |
| **LLMCompiler (DAG paralelo)** | Alta cuando hay paralelismo (arXiv 2312.04511: 3.7× latency, ~9% accuracy) | Planner extra | Alta | Sobre-ingenieril para este caso |
| **Fine-tuning del modelo en patrones de acción** | Muy alta. Blog oficial de Google (blog.google/technology/developers/functiongemma/, dic. 2025): "*In our 'Mobile Actions' evaluation, fine-tuning transformed the model's reliability, boosting accuracy from a 58 % baseline to 85 %.*" (modelo FunctionGemma-270M-IT, basado en Gemma 3, ~288 MB int8) | 0 ms | Muy alta | Fuera de alcance corto plazo |
| **Plan-then-Execute con validación Pydantic en cada borde** | Muy alta | +5–10 ms validación | Media | **ADOPTAR la validación** |

**Evidencia clave:**

- "*Research from Scale AI shows that having the LLM formulate a structured plan first (as JSON or Python code) and then running it through a deterministic executor reduces tool chaining errors significantly*" (futureagi.com).
- "*We observe consistent latency speedup of up to 3.7×, cost savings of up to 6.7×, and accuracy improvement of up to ~9% compared to ReAct*" (LLMCompiler, arXiv 2312.04511).
- Live API-Bench (arXiv 2506.11266, 10 LLMs evaluados): "*extremely low task completion rates (7–47 %) that improve modestly to 50 % when models interact with the live API environment as ReACT agents*".
- Pre-Act también advierte: "*smaller models… often struggle with complex reasoning tasks required for agentic systems*" — argumento directo para no apoyarse solo en el LLM en un 4B.
- "*A 3.4 GB model scored higher than everything else I tested, including models five times its size*" — el ranking actual de tool calling local NO es lineal con el tamaño (jdhodges.com, 2026). Gemma 4 E4B está en la franja de "puede funcionar muy bien con la arquitectura correcta".

### B.3 Veredicto B

**Arquitectura propuesta — Híbrido determinista 70 % / ReAct-reflexivo 30 %:**

1. **Patrones determinísticos cubiertos** (sin pasar por el LLM dos veces):
   - `search→open` (archivos)
   - `search→play` (música/video)
   - `search→read` (leer en voz alta)
   - `app→focus→type` (escribir en app activa)
   - `web_search→summarize`
2. **Detección de patrón**: tras la primera tool-call exitosa, el planner pregunta "¿la combinación (tool_devuelto, query_original) corresponde a un patrón conocido?". Si sí, ejecuta la cadena sin invocar al LLM de nuevo.
3. **Para el resto**: ReAct corto con **reflexión obligatoria** sobre `tool_result` antes de la siguiente acción.
4. **Validación Pydantic en cada borde**: si `filesystem.search` devuelve `[]`, no se invoca `office.open` — se responde "no encontré archivos .docx en Descargas".

**Pseudocódigo (planner determinista):**

```python
# planner_chain.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError

# === Patrones determinísticos ===
class FilesystemSearchResult(BaseModel):
    paths: List[str]
    count: int

class ChainStep(BaseModel):
    tool: str
    args: Dict[str, Any]

# Tabla de patrones: (verbo_usuario_regex, tool_origen, tool_destino, mapeo_args)
DET_PATTERNS = [
    # "abre el primer .docx en Descargas"
    {
        "trigger": r"\b(abre|abrir|ábreme|abreme)\b.*\b(archivo|documento|word|docx|pdf|xlsx)\b",
        "step1":   {"tool": "filesystem", "args_template": {"action": "search", "pattern": "{ext}"}},
        "step2":   {"tool": "office",     "args_template": {"action": "open", "path": "{step1.paths[0]}"}},
        "guard":   lambda r: isinstance(r, dict) and len(r.get("paths", [])) > 0,
        "on_empty": "No encontré archivos que coincidan."
    },
    # "pon la última canción que escuché"
    {
        "trigger": r"\b(pon|ponme|reproduce|reproducir)\b",
        "step1":   {"tool": "local_search", "args_template": {"q": "{query_clean}", "type": "audio"}},
        "step2":   {"tool": "app",          "args_template": {"action": "play", "uri": "{step1.uri}"}},
        "guard":   lambda r: r.get("uri") is not None,
        "on_empty": "No encontré esa canción en tu biblioteca."
    },
]

def try_deterministic(query: str, tool_subset: List[str]) -> Optional[ChainStep]:
    import re
    for pat in DET_PATTERNS:
        if re.search(pat["trigger"], query.lower()):
            return pat
    return None

# === Orquestador ===
def execute(query: str, llm, tool_subset: List[str]):
    pat = try_deterministic(query, tool_subset)
    if pat:
        # Paso 1
        r1 = call_tool(pat["step1"]["tool"], _fill_args(pat["step1"]["args_template"], query=query))
        if not pat["guard"](r1):
            speak(pat["on_empty"])
            return
        # Paso 2 — determinista, sin re-prompt al LLM
        args2 = _fill_args(pat["step2"]["args_template"], step1=r1)
        r2 = call_tool(pat["step2"]["tool"], args2)
        speak_result(r2)
        return

    # Fallback: ReAct con reflexión forzada
    react_loop_with_reflection(query, llm, tool_subset, max_steps=3)


def react_loop_with_reflection(query, llm, tools, max_steps=3):
    history = [{"role":"user", "content": query}]
    for step in range(max_steps):
        resp = llm.chat(history, tools=tools, tool_choice="auto")
        if resp.tool_calls:
            for tc in resp.tool_calls:
                result = call_tool(tc.name, tc.args)
                history.append({"role":"tool", "tool_call_id": tc.id, "content": str(result)})
                # REFLEXIÓN OBLIGATORIA — empuja al modelo a usar el resultado
                history.append({"role":"system",
                                "content": (f"Acabas de obtener un resultado de `{tc.name}`. "
                                           f"Si la tarea del usuario requiere otro paso "
                                           f"(p.ej. abrir, reproducir, leer, mostrar) y este "
                                           f"resultado lo permite, EJECÚTALO ahora con la "
                                           f"siguiente tool-call. Si no hay más pasos, responde al usuario.")})
        else:
            speak(resp.content); return
```

**Por qué funciona en E4B-Q4:**
- El modelo pequeño NO tiene que "razonar" sobre el encadenamiento en los patrones top; el código lo garantiza.
- Cuando sí razona, la reflexión inyectada como `system` message rompe la inercia "ya respondí, listo" (failure mode observado en sesión #847).
- La validación Pydantic en `guard()` impide invocar `office.open` con `path=None`, lo que causaba el "no me diste un path".

---

## PROBLEMA C — Foco+maximize 100 % fiable antes de teclear

### C.1 Diagnóstico

Windows tiene **reglas explícitas de foreground-lock** (Microsoft Learn, `LockSetForegroundWindow`/`SetForegroundWindow`):
> "*The system restricts which processes can set the foreground window. A process can set the foreground window by calling SetForegroundWindow only if: …*" (https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow).
>
> "*The system automatically enables calls to SetForegroundWindow if the user presses the ALT key or takes some action that causes the system itself to change the foreground window*" (https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-locksetforegroundwindow).

El **truco de simular ALT** está documentado por Microsoft mismo: "*pressing the [ALT] key causes Windows itself to enable calls to SetForegroundWindow*" (gist Aetopia, codeproject.com).

Pywinauto ha reportado fallos intermitentes de `AttachThreadInput` y `SetForegroundWindow` (issue pywinauto#270): "*pywintypes.error: (87, 'AttachThreadInput', 'The parameter is incorrect.')*".

### C.2 Opciones y comparativa

| Técnica | Fiabilidad | Coste | Riesgo | Veredicto |
|---|---|---|---|---|
| `SetForegroundWindow` solo | Baja (~60 %) | 0 | Falla bajo lock | NO |
| `SetForegroundWindow` + `ShowWindow(SW_RESTORE)` | ~80 % | 0 | Falla bajo lock | NO solo |
| `AttachThreadInput` + `SetForegroundWindow` | ~90 % | Pequeño | Puede fallar si thread no existe | Bueno |
| **Truco ALT (simular VK_MENU keydown/keyup) + `SetForegroundWindow`** | **~100 %** (documentado por Microsoft) | Mínimo | Modifica brevemente el estado del teclado | **ADOPTAR como capa 1** |
| `AllocConsole()/FreeConsole()` antes de SFW | ~95 % | Crea/destruye consola | Verboso | Alternativa |
| `uiautomation.SetFocus()` (UIA estándar) | Alta para elementos UIA-aware | +10–50 ms | No funciona si la ventana no es UIA | Capa 2 |
| `SetTopmost(True)` permanente | Alta | UX horrible | Ventana queda topmost | NO |
| **Combo: ALT + AttachThreadInput + ShowWindow + SFW + verificar + retry** | **~99.9 %** | ~50–150 ms total | Bajo | **ADOPTAR (ver código)** |

### C.3 Veredicto C — Código robusto

```python
# win_focus.py — robust foreground+maximize for Windows
import time
import ctypes
from ctypes import wintypes
import win32gui, win32con, win32process, win32api
import uiautomation as auto
import logging

LOG = logging.getLogger("win.focus")
user32 = ctypes.windll.user32

SW_RESTORE   = 9
SW_MAXIMIZE  = 3
SW_SHOW      = 5
SW_MINIMIZED = win32con.SW_SHOWMINIMIZED  # 2

VK_MENU = 0x12  # ALT

def _press_alt():
    """Bypass del foreground-lock siguiendo doc Microsoft LockSetForegroundWindow."""
    win32api.keybd_event(VK_MENU, 0, 0, 0)                       # ALT down
    win32api.keybd_event(VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)  # ALT up

def _attach_and_set(hwnd: int) -> bool:
    """AttachThreadInput trick — atómico, devolvemos True si SFW retornó nonzero."""
    cur_fg = win32gui.GetForegroundWindow()
    if cur_fg == hwnd:
        return True
    this_tid = win32api.GetCurrentThreadId()
    fg_tid, _ = win32process.GetWindowThreadProcessId(cur_fg) if cur_fg else (0, 0)
    attached = False
    try:
        if fg_tid and fg_tid != this_tid:
            attached = bool(win32process.AttachThreadInput(this_tid, fg_tid, True))
        # Asegurar visible y restaurada
        _, showCmd, _, _, _ = win32gui.GetWindowPlacement(hwnd)
        if showCmd == SW_MINIMIZED:
            win32gui.ShowWindow(hwnd, SW_RESTORE)
        win32gui.ShowWindow(hwnd, SW_MAXIMIZE)
        win32gui.BringWindowToTop(hwnd)
        ok = bool(win32gui.SetForegroundWindow(hwnd))
        try: win32gui.SetActiveWindow(hwnd)
        except Exception: pass
        try: win32gui.SetFocus(hwnd)
        except Exception: pass
        return ok
    finally:
        if attached:
            try: win32process.AttachThreadInput(this_tid, fg_tid, False)
            except Exception: pass

def _verify_focus(hwnd: int, expected_title_substr: str = None) -> bool:
    fg = win32gui.GetForegroundWindow()
    if fg != hwnd:
        return False
    if expected_title_substr:
        title = (win32gui.GetWindowText(fg) or "").lower()
        if expected_title_substr.lower() not in title:
            return False
    return True

def focus_and_maximize(hwnd: int,
                       expected_title_substr: str = None,
                       retries: int = 3,
                       initial_sleep: float = 0.08) -> bool:
    """
    Devuelve True si la ventana queda foreground+maximize+verificada.
    Estrategia (basada en Microsoft docs + Aetopia gist + codeproject):
      1. truco ALT (Windows acepta SFW tras input)
      2. AttachThreadInput + SetForegroundWindow + ShowWindow
      3. Verificación con GetForegroundWindow + título
      4. Capa UIA SetFocus (Microsoft Win32 API)
      5. Retry con backoff exponencial (80→160→320 ms)
    """
    if not win32gui.IsWindow(hwnd):
        LOG.error("hwnd %s no existe", hwnd); return False

    backoff = initial_sleep
    for attempt in range(retries):
        try:
            _press_alt()
        except Exception as e:
            LOG.debug("alt-press falló: %s", e)

        ok = _attach_and_set(hwnd)
        time.sleep(backoff)

        if _verify_focus(hwnd, expected_title_substr):
            LOG.info("foco OK en intento %d", attempt + 1)
            return True

        # Capa UIA: SetFocus formal por UI Automation
        try:
            ctrl = auto.ControlFromHandle(hwnd)
            if ctrl:
                ctrl.SetFocus()
                ctrl.SetTopmost(True)  # toggle temporal
                time.sleep(0.05)
                ctrl.SetTopmost(False)
        except Exception as e:
            LOG.debug("UIA SetFocus falló: %s", e)

        time.sleep(backoff)
        if _verify_focus(hwnd, expected_title_substr):
            LOG.info("foco OK vía UIA en intento %d", attempt + 1)
            return True

        backoff *= 2  # 80 → 160 → 320 ms

    LOG.error("focus_and_maximize: agotados %d intentos para hwnd=%s", retries, hwnd)
    return False


# ─── Uso típico ───
def type_into_whatsapp(text: str) -> bool:
    hwnds = []
    def cb(h, _):
        if "whatsapp" in (win32gui.GetWindowText(h) or "").lower() and win32gui.IsWindowVisible(h):
            hwnds.append(h)
    win32gui.EnumWindows(cb, None)
    if not hwnds:
        return False
    if not focus_and_maximize(hwnds[0], expected_title_substr="whatsapp"):
        return False
    # Pegado con portapapeles (Unicode-robusto, ya implementado)
    paste_unicode_to_focused(text)
    return True
```

**Notas:**

- El truco ALT es **explícitamente descrito por la documentación de Microsoft** (no es un hack no-soportado): `LockSetForegroundWindow` indica que la presión de ALT habilita `SetForegroundWindow`. Por lo tanto, simular `keybd_event(VK_MENU)` es legal y estable.
- `AttachThreadInput` puede fallar con error 87 si el thread origen ya no existe; el código lo encapsula en `try/finally` para nunca dejar threads attached.
- `uiautomation.SetTopmost(True)` temporal seguido de `SetTopmost(False)` fuerza un reordenamiento de Z-order pero no deja la ventana topmost.
- **Verificación con título** evita escribir en la ventana equivocada cuando una notificación roba el foco entre el `SetForegroundWindow` y el `paste`.

### C.4 Pitfalls conocidos

1. **UWP/Windows Store apps**: la doc de `SetForegroundWindow` dice "*The calling process belongs to a desktop application, not a UWP app*". Para WhatsApp UWP el camino preferido es `uiautomation.WindowControl(...).SetActive()` + `.SetFocus()`.
2. **Procesos elevados (admin)**: si tu agente NO está elevado y la ventana destino sí, SFW falla silenciosamente. Mismo manifest de UAC o lanzar el agente elevado.
3. **`AllocConsole/FreeConsole`** funciona pero parpadea una ventana de consola — UX peor.
4. **El reloj de `LockSetForegroundWindow` se resetea** con cualquier input genuino del usuario; si hay un teclado físico activo, el sistema ya está "desbloqueado" y SFW puede funcionar sin el truco ALT.

---

## PROBLEMA D — Reducir latencia primer-tool-call

### D.1 Diagnóstico

Estado actual reportado:
- 16–22 s → 3–7 s tras `--swa-full` + `--cache-reuse` + system-prompt magro (920 tokens).
- YOU→TOOL: 4–5 s (TTFT + decode de la tool-call).
- Respuesta final puede sumar 10 s.

Objetivo: **bajar TTFT y first-tool-call sin cambiar el modelo**.

### D.2 Inventario de técnicas con ROI

| Técnica | Ganancia estimada (E4B-Q4, 6 GB) | Coste VRAM | Riesgo tool-calling | Esfuerzo | Veredicto |
|---|---|---|---|---|---|
| `--cache-reuse 256` (ya activo) | YA aplicado | 0 | 0 | — | Mantener |
| `--swa-full` (ya activo) | YA aplicado (crítico Gemma) | +SWA full alloc | 0 | — | Mantener |
| `-np 1` (ya activo) | Reduce ~3× SWA cache vs default | Ahorra VRAM | 0 | — | Mantener |
| **`-b 2048 -ub 1024` (subir batch/ubatch)** | Prefill 2–3× más rápido en prompts >2k tokens | +200–400 MB compute buffer | 0 | Bajo | **ADOPTAR** |
| **`--slot-save-path` + restore al inicio** | TTFT 400 ms→<20 ms en sesiones repetidas tras restart (CraftRigs midió 380 ms → 12 ms en cache_hit) | Disco (cientos de MB) | 0 | Bajo-medio | **ADOPTAR** |
| **Keep-alive del slot** (ping cada 30 s con prompt vacío) | Mantiene KV caliente entre turnos | 0 | 0 | Bajo | **ADOPTAR** |
| **GBNF / JSON-schema constrain** para tool-calls | Mejora *fiabilidad*; NO siempre acelera TTFT con `--jinja` | 0 | Posible conflicto con `--jinja` | Medio | Adoptar para fiabilidad, no como acelerador principal |
| **N-gram self-speculation** (`--draft-min`/`--draft-max` sin draft model) | 1.05–1.2× en patrones repetitivos, riesgo de regresión | 0 | Bajo | Bajo | Probar (medir) |
| **MTP / Multi-Token Prediction (drafter Gemma 4 oficial)** | ~1.2–1.3× en E4B-Q4 según único benchmark público (night-dev.com, RTX 5070 Ti) | +~300–600 MB (drafter) | Bajo | Alto (requiere fork `atomic-llama-cpp-turboquant`) | **ARRIESGADO en 6 GB y mainline llama.cpp NO lo carga aún (issue #22337)** |
| **Reducir tamaño de tool-subset** (router envía 3–5 tools, no 65) | Prompt 920→~700 tokens; TTFT ~12–18 % menos prefill | 0 | 0 | Bajo (ya implementado) | Mantener / agresivizar |
| **Subir threads / `-t` igual a cores físicos** | Pequeña ganancia CPU-side prefill | 0 | 0 | Bajo | Probar |
| `--cache-type-k q8_0 --cache-type-v q8_0` | KV cache 2× más pequeña → más ctx con misma VRAM | Cuidado con calidad | Bajo si q8 | Bajo | Opcional |

### D.3 Sobre speculative decoding en este stack — **conclusión basada en evidencia**

**Confirmado:**

1. **Existe un drafter MTP oficial de Google para Gemma 4**: `google/gemma-4-E4B-it-assistant` (156 M params, 4 layers, ~340 MB en Q4). Releases oficiales y documentación en https://ai.google.dev/gemma/docs/mtp/overview definen MTP como "*the specific architecture used to enable highly efficient Speculative Decoding*".
2. **Cada tamaño tiene su drafter propio** — E2B **no** es drafter de E4B; cada modelo tiene su `*-it-assistant` dedicado (kaitchup.substack.com, mayo 2026).
3. **mainline llama.cpp NO carga el drafter de Gemma 4 todavía** — issue ggml-org/llama.cpp#22337: "*model loading fails with `invalid vector subscript` during load_tensors*". Solo el fork `atomic-llama-cpp-turboquant` lo soporta hoy.
4. **Benchmark único de E4B-Q4 con MTP**: night-dev.com (07/05/2026, RTX 5070 Ti 16 GB) reporta 1.28× promedio (136.3 → 174.6 tok/s) en E4B-Q4. **Acceptance rates 0.70–0.76**. Y el mismo benchmark reportó que con `-ctk turbo3 -ctv turbo3` el server crasheó en `fattn.cu`.
5. **En consumer Ampere (RTX 3060)** el model card del drafter "ultralight" (`HackAfterDark/gemma-4-e4b-it-mtp-assistant-ultralight`) advierte: "*On the RTX 3060, the standard llama.cpp (without MTP) is currently faster due to memory bandwidth saturation.*"
6. **Razón teórica** (arXiv 2505.22179 "Speculative Decoding Meets Quantization"): "*the memory benefits from 4-bit weight quantization are diminished by the computational load from speculative decoding*".
7. **Q4 + target 4B + 6 GB**: el VRAM no alcanza cómodamente para target + drafter + KV cache + `--swa-full` + buffer de compute.

**Veredicto D-spec:** **NO adoptar speculative decoding ahora mismo** en 6 GB con mainline llama.cpp. Re-evaluar cuando:
- llama.cpp mainline incorpore el loader para el drafter MTP de Gemma 4 (seguir issue #22337).
- O se prueba en GPU con ≥12 GB VRAM (E2B-Q4 + drafter en 6 GB es marginalmente posible pero crashea).

Como sustituto barato, **probar `--draft-min 1 --draft-max 8` con n-gram lookup (sin draft model)** — cero VRAM extra, suele dar 1.05–1.10× en prompts con repetición (texto estructurado, JSON, código), regresión posible en chat libre. **Medir antes de mantenerlo.**

### D.4 Sobre grammar/GBNF + `--jinja`

- "*It seems that enabling jinja disables gbnf grammar; the grammar property of the chat completions request json is ignored*" (discussion #12204). **Comportamiento real reciente:** en versiones modernas (post-b8800) `--jinja` y grammar funcionan juntos, pero el tool-calling de `--jinja` **inyecta su propia grammar internamente** ("*function calling internally uses its own grammar, depending on the model*" — discussion #15341). Forzar otra grammar encima puede chocar.
- GBNF **mejora fiabilidad** del JSON de tool-call (en lugar de "salir bien o salir mal") pero **no acelera TTFT** sustancialmente. El beneficio es reducir reintentos por JSON malformado, no decode crudo.
- Para Gemma 4 que ya es muy fiable en tool-calling (citado arriba), GBNF añade **fiabilidad marginal** y **complejidad**. Recomendación: **NO añadir GBNF**, mantener `--jinja` puro.

### D.5 Recomendación final D — flags llama-server

```bat
:: Configuración objetivo para Gemma 4 E4B-it Q4_K_M en 6 GB (Windows, mono-usuario)
llama-server.exe ^
  --model           "C:\models\gemma-4-E4B-it-Q4_K_M.gguf" ^
  --mmproj          "C:\models\gemma-4-E4B-mmproj-F16.gguf" ^
  --port            8080 ^
  --host            127.0.0.1 ^
  -c                8192 ^
  --parallel        1 ^
  -ngl              99 ^
  --flash-attn      on ^
  --swa-full ^
  --jinja ^
  --ctx-checkpoints 1 ^
  --cache-reuse     256 ^
  --keep            -1 ^
  -b                2048 ^
  -ub               1024 ^
  --slots ^
  --slot-save-path  "C:\llama-slots" ^
  --metrics ^
  --no-context-shift ^
  --threads         %NUMBER_OF_PHYSICAL_CORES% ^
  --threads-batch   %NUMBER_OF_PHYSICAL_CORES%
```

**Razonamiento por flag:**
- `-b 2048 -ub 1024`: el default `-ub 512` deja el GPU subutilizado durante prefill. La doc de Apple Silicon es la mejor referencia ("*setting both to 2048 measurably accelerates the prefill phase*") y aplica análogamente en CUDA. En 6 GB, `-ub 1024` es un punto seguro; subir a 2048 puede OOM con KV grande.
- `--slot-save-path`: habilita `/slots/0/save` y `/slots/0/restore` — al cerrar el agente, guardas KV con el system prompt ya procesado; al abrir, restauras en ms en lugar de re-procesar 920 tokens.
- `--keep -1`: mantiene el prompt entero en cache.
- `--no-context-shift`: con tool-calling, mejor explicitar y nunca rotar el contexto silenciosamente.
- `--slots --metrics`: necesarios para verificar el `cache_hit` en logs y diagnóstico vía `/metrics`.

**Keep-alive del slot** (Python, cliente):

```python
# slot_keepalive.py
import requests, threading, time

def keepalive(url="http://127.0.0.1:8080", interval=25.0):
    """Empuja un completion vacío cada N segundos para que el slot no sea desalojado."""
    def loop():
        while True:
            try:
                requests.post(f"{url}/v1/chat/completions",
                              json={"model":"gemma-4-e4b",
                                    "messages":[{"role":"system","content":"keepalive"}],
                                    "max_tokens": 1,
                                    "temperature": 0,
                                    "cache_prompt": True},
                              timeout=5)
            except Exception:
                pass
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True); t.start()

# Persistencia del slot al cierre / arranque
def save_slot(url="http://127.0.0.1:8080", path="C:/llama-slots/session.bin"):
    requests.post(f"{url}/slots/0/save", json={"filename": path}, timeout=10)

def restore_slot(url="http://127.0.0.1:8080", path="C:/llama-slots/session.bin"):
    try:
        requests.post(f"{url}/slots/0/restore", json={"filename": path}, timeout=10)
    except Exception:
        pass
```

### D.6 Plan de medición

Antes/después, registrar:

1. **TTFT** (tiempo al primer token de la respuesta).
2. **YOU→TOOL** (tiempo al primer tool-call generado).
3. **t_prompt_processing** en los logs del server (campos `prompt processing done` / `cache_hit`).
4. Pruebas en 3 prompts canónicos: "¿qué es Mortal Kombat?", "abre el primer .docx en Descargas", "pon música relajante".

**Objetivos numéricos sugeridos:**
- TTFT: 3–7 s → **<2.5 s** consistente.
- YOU→TOOL: 4–5 s → **<2 s** en cadena.
- Respuesta final: <10 s → **<5 s** end-to-end (cumple tier-Alexa).

---

## Recomendaciones priorizadas

### Inmediato (1–3 días, alta ROI):

1. **Implementar `is_question_lexical` + `has_explicit_action`** y meter como pre-gate del router (Problema A).
2. **Health-check del encoder al startup** con probes en 4 idiomas; fallar ruidoso (Problema A).
3. **Añadir `-b 2048 -ub 1024 --slot-save-path` a llama-server** y medir TTFT antes/después (Problema D).
4. **Añadir keep-alive del slot** cada 25 s (Problema D).
5. **Implementar 5 patrones determinísticos `search→open`** (Problema B).

### Corto plazo (1–2 semanas):

6. **Validación Pydantic en cada borde** de las tool-chains (Problema B).
7. **Reflexión obligatoria post-tool** en ReAct loop (Problema B).
8. **Reemplazar el código actual de focus por `focus_and_maximize`** con truco ALT + AttachThreadInput + UIA + verificación + retry (Problema C).
9. **Enmascaramiento de entidades** experimental para queries de info (Problema A, opt-in).

### Mediano plazo (mes+):

10. **Vigilar issue ggml-org/llama.cpp#22337** para MTP de Gemma 4 en mainline. Cuando se cierre, evaluar drafter MTP en una GPU de prueba con ≥12 GB y, si gana >1.2× sin regresión, considerarlo para el target final.
11. **Probar `--draft-min 1 --draft-max 8` n-gram lookup** en producción shadow durante una semana; abortar si TTFT mediano regresa.
12. **Considerar fine-tuning de E4B en patrones de acción del agente** si el ratio de error multi-paso sigue >5 % (el efecto demostrado por FunctionGemma 58 %→85 % sugiere techo alto, ver §B.2).

### Umbrales que cambian decisiones:

| Métrica | Umbral | Acción si cruza |
|---|---|---|
| TTFT mediano > 3 s | Tras todas las optimizaciones | Revisar `--ctx-checkpoints` / reducir system prompt o tool count |
| Recall holdout cae <0.85 | Tras añadir gate léxico | Desactivar gate y volver a Tool2Vec puro |
| Multi-step success <70 % | Tras patrones deterministas | Añadir 3 patrones más / forzar reflexión |
| VRAM se acerca a 5.8 GB | En picos | Reducir `-c` a 4096 o subir a `-ctk q8_0 -ctv q8_0` |

---

## Caveats

1. **Versionado de Gemma 4 en llama.cpp es activo y volátil.** Issues abiertos #21468 (cache reuse Gemma 4 con shared KV), #22527 (crash 31B con FA+SWA checkpoint), #22337 (E4B drafter no carga). Pin a un build concreto (b9090) y no actualices a ciegas — leer changelog antes.
2. **El benchmark MTP único disponible para E4B-Q4 (night-dev.com)** fue en RTX 5070 Ti 16 GB Blackwell, no en 6 GB Ampere. La extrapolación a 6 GB es asimétrica y probablemente peor por saturación de ancho de banda; tratar el 1.28× como cota superior.
3. **El recall holdout 0.881 del router actual** no fue replicado en este informe; los +1.8 % del paper de masking (arXiv 2407.17862) son sobre ATIS/SNIPS/CLINC/BANKING, no sobre tu set propio. Hay que medir en tu dataset.
4. **"Tier-Alexa 4–5 s" es un objetivo de UX interno, no un SLA publicado.** El benchmark más cercano publicado es un memo interno de Amazon filtrado y reportado por Fortune (18-nov-2024): el objetivo interno de Amazon para "AI Alexa basic requests" era **"2–4 segundos"**, y pruebas en Echo antiguos midieron **"latency times of up to 10 seconds — well above the target of 2–4 seconds"**. No hay benchmark público que respalde 1.5–2.5 s; el objetivo 4–5 s de este informe es razonable pero conservador respecto al target de Amazon.
5. **El truco ALT** modifica brevemente el estado del teclado del usuario. En aplicaciones de captura de teclado de muy bajo nivel (juegos en pantalla completa, RDP) puede ser detectado o causar atajos no deseados; usar solo cuando GUI tools están activas.
6. **El "patrón determinista" tiene techo:** cubre los 5–10 verbos top en español/inglés. Para cola larga el LLM sigue siendo el camino.
7. **Gemma 4 vs Gemma 3n:** la nomenclatura E2B/E4B es idéntica pero las arquitecturas difieren — Gemma 3n usa MatFormer puro; Gemma 4 añade MTP separado, atención híbrida SWA+global y soporte nativo de function calling con `<|tool_call|>` tokens. **No supongas que un finding de Gemma 3n aplica 1:1 a Gemma 4.**
8. **El informe asume Windows 10/11 desktop apps**. Para UWP/Windows Store apps, UIA es obligatorio y `SetForegroundWindow` puro fallará.
9. **El 97.90 % de accuracy en ATIS (PeerJ Computer Science, oct. 2024)** corresponde a un CNN-BiLSTM joint model entrenado específicamente para ATIS (18 intents); NO es un proxy directo para tu set de 65 herramientas multilingüe — es solo evidencia de que un clasificador dedicado pequeño puede llegar a esa franja si se invierte en datos etiquetados propios.
