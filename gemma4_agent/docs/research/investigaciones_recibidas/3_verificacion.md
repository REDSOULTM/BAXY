# Verificación de efecto y recuperación robusta para un agente de voz local con Gemma 4 E4B-it (Q4_K_M, llama.cpp b9090, Windows)

## TL;DR
- **Punto 1 (verificación):** abandona OCR como vía principal y usa el árbol UIA (Microsoft UI Automation) con un cliente persistente y `CacheRequest`. Para WhatsApp Desktop 2025-2026, que ya es un wrapper WebView2 sobre web.whatsapp.com, los `ListItem` del panel de chat exponen el nombre del contacto y los estados "Sent/Delivered/Read" en la propiedad `Name`. Es el camino más fiable, más barato (decenas de ms con caché) y más general que OCR del header.
- **Punto 2 (recuperación):** un modelo 4B local NO puede auto-corregirse con confiabilidad sin señal externa (Huang et al. 2024; Kamoi et al. 2024). La política correcta es una **máquina de estados externa** (no el LLM) que use el `VerifierOutcome` como única fuente de verdad, con retries acotados por **clase de error** (no global), una sola **replan asistida por LLM** con error_trace inyectado, y escalada al usuario cuando se rompe el invariante. Reflexion-style introspection es contraproducente en este tamaño.
- **Puntos 3-5:** comunicar "unknown" con lenguaje calibrado breve ("Lo lancé pero no confirmé si abrió"), reparar precondiciones (instalado, daemon vivo, ventana focusable) ANTES de actuar de forma idempotente, y aplicar verificación **escalonada por riesgo**: siempre para acciones irreversibles (mensajes, fs delete, terminal), nunca para acciones triviales reversibles (subir volumen 5%).

---

## Punto 1 — Verificación robusta del efecto real en Windows

### (a) Diagnóstico

"El tool devolvió ok" no es verificación de efecto. `subprocess.Popen("steam.exe")` retorna éxito en el instante en que el proceso arranca, no cuando la ventana es visible; `keyboard.send("vol up")` retorna éxito aunque otra app capture el hotkey; `pyautogui.click` en una ventana no enfocada va al lugar incorrecto. La verificación tiene tres niveles:

1. **Proceso/recurso:** ¿existe el PID? ¿el archivo se creó?
2. **UI presentable:** ¿hay una HWND visible, no minimizada, no colgada, y enfocada?
3. **Estado semántico:** ¿es el chat correcto? ¿el volumen es 60%? ¿el mensaje muestra el tick de enviado?

La OCR del header de WhatsApp confunde dos cosas: detectar la *presencia* del header (visión) vs leer su *contenido* (texto). UIA hace ambas en un paso y de forma determinista — siempre que el árbol de accesibilidad esté poblado.

### Hallazgo clave sobre WhatsApp Desktop (2025-2026)

Meta migró WhatsApp Desktop de UWP/WinUI nativo a un **wrapper WebView2 alrededor de web.whatsapp.com** (paquete Store 2.2584.3.0, confirmado por Jamie Teh —NVDA core dev— en su blog jantrid.net del 20 dic 2025: *"WhatsApp have discontinued the UWP app and replaced it with an app that effectively just wraps the WhatsApp web app"*; NVDA issue #19655 de febrero 2026 lo confirma como regresión de accesibilidad). Esto significa:

- La ventana superior es `ClassName="Chrome_WidgetWin_1"`, con un hijo `Chrome_RenderWidgetHostHWND`.
- Chromium **no expone su árbol UIA hasta que un cliente AT lo despierta** enviando `WM_GETOBJECT` al `Chrome_RenderWidgetHostHWND` (lo hacen pywinauto/uiautomation automáticamente al usar `ElementFromHandle`).
- Una vez despertado, los elementos del DOM/ARIA aparecen como `ListItem`s con `ControlType=ListItem`, `Name=<nombre del contacto + último mensaje + estado>`. El header del chat activo es un heading/button cuyo `Name` contiene el nombre del contacto.
- Los ticks (Sent/Delivered/Read) NO requieren OCR: están en el `Name` del `ListItem` del último mensaje. La add-on **WhatsApp-Enhancer para NVDA** (GPL-2.0, github.com/starkrush123/WhatsApp-Enhancer) explícitamente lo confirma: *"removing the instruction text while preserving important status updates like 'Read', 'Delivered', 'unread', or 'reactions'"*.
- **AutomationId es generalmente vacío** en contenido web; hay que buscar por `Name` + `ControlType`.

### (b) Comparativa de técnicas — Windows + voz + 4B local

| Técnica | Detección de efecto | Latencia añadida (típica) | Riesgo de falso-OK / falso-FAIL | Veredicto |
|---|---|---|---|---|
| Tool returned OK (status quo) | Bajísima — sólo "se lanzó" | 0 ms | Falso-OK altísimo (el caso del bug) | Insuficiente como única verificación |
| `EnumWindows` + `GetForegroundWindow` + título regex (win32gui) | Media — confirma HWND visible y foreground | **<5 ms** (Win32 puro) | Falso-OK si hay otra instancia; falso-FAIL si el título tarda en aparecer | **Excelente como primer escalón para "app abierta"** |
| `WaitForInputIdle` (con timeout) | Alta — confirma que la app procesó su primer mensaje | 50-500 ms (bloqueante hasta input idle) | Falso-FAIL si la app es lenta arrancando | Útil tras `CreateProcess`, antes de UIA |
| `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` | Alta — evento push, no polling | ~0 ms (asíncrono) | Falso-OK si otra app robó el foreground; requiere thread con message loop | Ideal para detectar foco real tras `SetForegroundWindow` |
| UIA tree walk — pywinauto backend="uia" | Alta — propiedades semánticas | **6× más lento que win32**; `top_window()` puede tardar **30 s** en frío (issue #1102); ~95 s para 15 clicks vs 16 s en win32 (issue #256) | Bajo falso-OK; alto riesgo de timeout | **NO recomendado** salvo con WrapperObject cacheado |
| UIA tree walk — `uiautomation` (yinkaisheng) | Alta | **decenas de ms** con `searchDepth=1` + elemento cacheado; cientos de ms a segundos en frío | Bajo; el más equilibrado en Python | **Recomendado** para verifiers Python |
| UIA + FlaUI (.NET, `CacheRequest`) | Alta | Sub-300 ms consistente con caché | Bajo | El más rápido, pero requiere bindings .NET |
| OCR del header (Tesseract/PaddleOCR) | Media-alta | 150-500 ms por crop | Falso-OK por glifos similares; falla con render dinámico | Sólo como fallback cuando Chromium no expone UIA |
| Template matching de píxeles | Media | 20-100 ms | Frágil ante DPI/temas/zoom | Sólo para iconos estables (mute icon) |
| `pycaw IAudioEndpointVolume.GetMasterVolumeLevelScalar()` | Altísima — lee el estado real del kernel audio | **<5 ms** | Casi nulo | **Ideal para verify_audio** |
| Filesystem `Path.exists()` / `stat.st_mtime` | Altísima | <1 ms | Nulo | **Ideal para verify_filesystem** |
| Subprocess return code + stdout regex | Alta para CLI | depende del comando | Falso-OK si el comando reporta éxito pero no hizo nada | Combinar con verificación de side-effect |

### Qué medir (instrumentar SIEMPRE)

- `t_verify_ms` por verifier, p50/p95/p99.
- Distribución `verified` / `failed` / `unknown` por tool.
- Tasa de **falso-OK** detectado post-hoc (auditoría manual de 100 sesiones / mes).
- Latencia desde "tool fin" hasta "verifier dice algo".
- Tasa de "Chromium activation cold-start" (primera llamada UIA tras lanzar WhatsApp).

### (c) Fuentes (2025-2026)
- Microsoft Learn — *UI Automation Specification* y *UI Automation Tree Overview*.
- WindowsForum (2025), "WhatsApp Windows switches to WebView2 web wrapper, native UI replaced" (paquete 2.2584.3.0).
- Jamie Teh (NVDA core dev), jantrid.net, 20 dic 2025: "WhatsApp Messenger Web Accessibility Fixes".
- NVDA issues #19236, #19276, #19655 (2026) — comportamiento de Chromium/WebView2 con UIA.
- Descolada UIA-v2 wiki — pitfalls Chromium/Electron y `activateChromiumAccessibility`.
- pywinauto issues #256, #842, #1102 — performance UIA backend.
- yinkaisheng/Python-UIAutomation-for-Windows — librería Python recomendada (Apache-2.0).
- pycaw (PyPI 20251023) — control de audio real vía Core Audio.
- starkrush123/WhatsApp-Enhancer (NVDA add-on v1.1.1, feb 2026) — referencia de extracción de status strings vía accesibilidad.
- Microsoft Remote Operations (`Microsoft-UI-UIAutomation`) — batching cross-process para minimizar latencia.

### (d) Veredicto
**Viable y recomendado:** sustituir OCR del header por traversal UIA con un cliente persistente en proceso (no spawnear pywinauto cada vez), cacheando el `WindowControl` raíz de WhatsApp y haciendo find por `Name`/`ControlType=ListItem` con `searchDepth` acotado. **Sub-300 ms es alcanzable** con `uiautomation` + caché; **inalcanzable** con pywinauto en cada llamada. Para `verify_audio` usar pycaw directo (lectura del estado real, no del comando). Para `verify_filesystem` usar `Path` + `stat`. Para `verify_app` combinar `EnumWindows` (rápido) + UIA (rico, sólo si el primero pasa).

### (e) Código concreto

```python
# uia_verifier.py — cliente UIA persistente, sub-300ms con caché
import uiautomation as auto
import win32gui, win32con
import ctypes, ctypes.wintypes as wt
import time
from dataclasses import dataclass
from typing import Optional, Literal

# --- 1) Verificador rápido de ventana (Win32 puro, <5 ms) ---
def find_window_by_substr(substr: str, must_be_visible=True) -> Optional[int]:
    substr_low = substr.lower()
    found = []
    def cb(hwnd, _):
        if must_be_visible and not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if substr_low in title.lower():
            found.append(hwnd)
        return True
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None

def is_foreground(hwnd: int) -> bool:
    return win32gui.GetForegroundWindow() == hwnd

def is_hung(hwnd: int, timeout_ms: int = 200) -> bool:
    # SendMessageTimeout con SMTO_ABORTIFHUNG detecta apps colgadas
    SMTO_ABORTIFHUNG = 0x0002
    result = wt.DWORD()
    r = ctypes.windll.user32.SendMessageTimeoutW(
        hwnd, win32con.WM_NULL, 0, 0,
        SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result))
    return r == 0

# --- 2) Cliente UIA persistente (vive en el proceso del agente) ---
class UiaClient:
    """Mantén UNA instancia. NO instanciar por llamada (overhead COM ~100ms)."""
    def __init__(self):
        auto.uiautomation.InitializeUIAutomationInThread = True
        self._root = auto.GetRootControl()
        self._cache = {}  # hwnd -> WindowControl

    def window_for(self, hwnd: int) -> auto.WindowControl:
        if hwnd in self._cache:
            return self._cache[hwnd]
        w = auto.ControlFromHandle(hwnd)  # despierta Chromium si aplica
        self._cache[hwnd] = w
        return w

    def find_named_listitem(self, hwnd: int, name_substr: str,
                            max_depth=8, timeout_s=0.25) -> Optional[auto.Control]:
        w = self.window_for(hwnd)
        deadline = time.time() + timeout_s
        name_low = name_substr.lower()
        while time.time() < deadline:
            it = w.ListItemControl(searchDepth=max_depth,
                                   Compare=lambda c, d: name_low in (c.Name or '').lower())
            if it.Exists(maxSearchSeconds=0.05, searchIntervalSeconds=0.02):
                return it
        return None

UIA = UiaClient()  # singleton del agente

# --- 3) Verificadores específicos ---
@dataclass
class VerifierOutcome:
    state: Literal['verified', 'failed', 'unknown']
    detail: str
    elapsed_ms: float

def verify_app_opened(name: str, timeout_s: float = 3.0) -> VerifierOutcome:
    t0 = time.perf_counter()
    deadline = t0 + timeout_s
    while time.perf_counter() < deadline:
        hwnd = find_window_by_substr(name)
        if hwnd and not is_hung(hwnd):
            return VerifierOutcome('verified',
                f'hwnd={hwnd} title="{win32gui.GetWindowText(hwnd)}"',
                (time.perf_counter()-t0)*1000)
        time.sleep(0.05)
    return VerifierOutcome('unknown',
        f'no window with "{name}" appeared in {timeout_s}s',
        (time.perf_counter()-t0)*1000)

def verify_window_focused(hwnd: int) -> VerifierOutcome:
    t0 = time.perf_counter()
    ok = is_foreground(hwnd) and win32gui.IsWindowVisible(hwnd) and not is_hung(hwnd)
    return VerifierOutcome('verified' if ok else 'failed',
        f'foreground={is_foreground(hwnd)} visible={win32gui.IsWindowVisible(hwnd)}',
        (time.perf_counter()-t0)*1000)

# --- 4) WhatsApp: verificar header (contacto) y estado enviado por UIA ---
WA_STATUS_WORDS = {
    'en': ('sent','delivered','read'),
    'es': ('enviado','entregado','leído','leido'),
    'de': ('gesendet','zugestellt','gelesen'),
    'pt': ('enviada','entregue','lida'),
    'fr': ('envoyé','envoye','remis','lu'),
}

def verify_whatsapp_chat_header(expected_contact: str) -> VerifierOutcome:
    t0 = time.perf_counter()
    hwnd = find_window_by_substr('WhatsApp')
    if not hwnd:
        return VerifierOutcome('failed', 'WhatsApp window not found',
                               (time.perf_counter()-t0)*1000)
    # En WebView2 el header del chat activo es heading/button cuyo Name contiene el contacto
    w = UIA.window_for(hwnd)
    hdr = w.HeaderItemControl(searchDepth=12,
        Compare=lambda c,d: expected_contact.lower() in (c.Name or '').lower())
    if not hdr.Exists(0.2, 0.05):
        hdr = w.TextControl(searchDepth=12,
            Compare=lambda c,d: expected_contact.lower() == (c.Name or '').strip().lower())
    elapsed = (time.perf_counter()-t0)*1000
    if hdr.Exists(0.05):
        return VerifierOutcome('verified', f'header={hdr.Name}', elapsed)
    return VerifierOutcome('failed',
        f'header for "{expected_contact}" not visible', elapsed)

def verify_whatsapp_message_sent(text_substr: str, lang='es',
                                  timeout_s=4.0) -> VerifierOutcome:
    t0 = time.perf_counter()
    deadline = t0 + timeout_s
    hwnd = find_window_by_substr('WhatsApp')
    if not hwnd:
        return VerifierOutcome('failed', 'no WhatsApp window',
                               (time.perf_counter()-t0)*1000)
    w = UIA.window_for(hwnd)
    status_words = WA_STATUS_WORDS.get(lang, WA_STATUS_WORDS['en'])
    while time.perf_counter() < deadline:
        last = w.ListItemControl(foundIndex=-1, searchDepth=16)
        if last.Exists(0.05):
            n = (last.Name or '').lower()
            if text_substr.lower() in n and any(s in n for s in status_words):
                return VerifierOutcome('verified',
                    f'last_msg_name="{last.Name[:120]}"',
                    (time.perf_counter()-t0)*1000)
        time.sleep(0.08)
    return VerifierOutcome('unknown',
        f'no status word seen near "{text_substr}"',
        (time.perf_counter()-t0)*1000)

# --- 5) Audio (pycaw — estado real) ---
def verify_volume(expected_scalar: float, tol=0.02) -> VerifierOutcome:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER
    t0 = time.perf_counter()
    devs = AudioUtilities.GetSpeakers()
    iface = devs.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    vol = cast(iface, POINTER(IAudioEndpointVolume))
    actual = vol.GetMasterVolumeLevelScalar()
    elapsed = (time.perf_counter()-t0)*1000
    if abs(actual - expected_scalar) <= tol:
        return VerifierOutcome('verified', f'vol={actual:.2f}', elapsed)
    return VerifierOutcome('failed',
        f'expected={expected_scalar:.2f} actual={actual:.2f}', elapsed)
```

**Qué medir aquí:** latencia de cada verifier por tool (p50/p95), tasa de timeouts UIA en frío vs con caché, comparar tasa de "verified" antes/después de migrar de OCR a UIA, y "cold-start hits" tras lanzar WhatsApp (donde Chromium tarda en activar el árbol).

---

## Punto 2 — Política de recuperación para un LLM 4B local

### (a) Diagnóstico

La literatura 2024-2025 es contundente: **modelos pequeños no pueden auto-corregir su razonamiento sin señal externa**. Citas verbatim clave:

- Huang et al. (ICLR 2024, "Large Language Models Cannot Self-Correct Reasoning Yet"): *"our findings indicate that LLMs struggle to self-correct their reasoning in this setting. In most instances, the performance after self-correction degrades"*.
- Kamoi et al. (TACL 2024, MIT Press): *"no prior work demonstrates successful self-correction with feedback from prompted LLMs, except for studies in tasks that are exceptionally suited for self-correction"; "self-correction works well in tasks that can use reliable external feedback"*.
- Cho et al., EMNLP 2025 Findings (arXiv:2505.23060, POSTECH), "Self-Correcting Code Generation Using Small Language Models": *"smaller models struggle to exhibit reflective revision behavior across both self-correction paradigms"*.
- inventrium.net (2025), benchmark de ReAct: *"The benchmark revealed that out of 513 retries, 466 were wasted—triggered by errors that no retry could fix. The biggest culprit? The agent trying to call tools that don't exist"* — el contador de retries global no distingue clases de error y se agota con hallucinations irrecuperables.

Reflexion-style reflection puro (modelo critica su propia salida) **es contraproducente con Gemma 4B**: tiende a "rewrites unnecessary" y a degradar respuestas correctas (overshoot rate >10% en CyberCorrect, arxiv 2605.17305, 2026).

**Conclusión:** no le pidas al 4B que se introspecte. Dale **señales externas tipadas** (el `VerifierOutcome`) y una **máquina de estados externa** que decide qué hacer.

### (b) Comparativa de patrones de recuperación

| Patrón | Funciona con 4B local | Latencia añadida | Riesgo de bucle / mentira | Veredicto |
|---|---|---|---|---|
| Reflexion puro (auto-crítica del LLM) | **No** | 1 llamada extra (~3-8 s con Gemma 4B Q4_K_M) | Alto: degrada respuestas correctas; overshoot | Evitar |
| Self-Refine prompting | No fiable | idem | Alto en sub-10B | Evitar |
| Retry-bruto con misma entrada | Sólo para errores transitorios | 1 ejecución | Bucle inmediato si el error es lógico | Sólo para `TRANSIENT` clasificado |
| Retry con argumentos corregidos **por código** (no por LLM) | **Sí** | µs | Bajo | **Recomendado** para errores tipados (path normalize, focus refresh) |
| Replan con LLM y error_trace inyectado (1 sola vez) | Sí, si limitado a 1 | 1 llamada | Medio si no se acota | **Ya implementado — mantener acotado** |
| Process Reward Model externo (PRM) | Sobra para este tamaño | añade modelo extra | Bajo | No vale la pena |
| Verifier externo determinista (estado actual del proyecto) | **Sí** | la del verifier | Bajo | **Es el approach correcto** |
| Escalada al usuario (clarification) | Sí | latencia humana | Nulo | Esencial como último escalón |
| Detección de loop por hash de (tool, args, error) | Sí | µs | Nulo | **Crítico** — ya implementado, reforzar con err_class |

### Política recomendada — máquina de estados externa

Clasificar cada error/outcome en una de **6 clases tipadas** y aplicar una acción diferente por clase (no un contador global):

| Clase | Ejemplo | Acción | Reintentos máx | Escalada |
|---|---|---|---|---|
| `TRANSIENT` | timeout HTTP, COM error 0x800401E3 | retry con backoff exponencial + jitter (base 250 ms, factor 2, cap 3 s) | 2 | tras 2 |
| `PRECONDITION_MISSING` | app no instalada, daemon abajo | ejecutar `repair_precondition()` (ver Punto 4), luego reintentar | 1 | tras reparar fallido |
| `ARG_INVALID` | path mal formado, contacto no existe | normalizar args por código; si tras normalizar sigue fallando → ask user | 1 | inmediata si no se puede normalizar |
| `VERIFIER_UNKNOWN` | tool ok pero verifier dice "unknown" | re-verify tras 200 ms; si sigue unknown → reportar honestamente | 1 re-verify | sólo si la acción es high-risk |
| `VERIFIER_FAILED` | tool ok pero la acción NO tuvo efecto | 1 replan LLM con error_trace; si replan vuelve a fallar → escalar | 1 replan | inmediata si la acción es destructiva |
| `TOOL_NOT_FOUND` / `MALFORMED_CALL` | el modelo alucinó un tool | NO reintentar (waste). Inyectar lista de tools válidos y reanudar | 0 | tras 1 alucinación seguida |

**Principios clave:**

1. **El LLM nunca se pregunta a sí mismo "¿lo hice bien?"** — quien responde es el verifier (señal externa).
2. **El presupuesto de retries es por clase, no global** — un loop infinito de `TOOL_NOT_FOUND` no debe agotar el budget para `TRANSIENT` real (lección del estudio inventrium.net 2025: 466/513 retries desperdiciados por tool hallucinations contabilizados igual que errores recuperables).
3. **Una sola llamada de replan** (ya implementado), con el `error_trace` como contexto adicional y los args anteriores tachados.
4. **Loop detector** sobre `hash(tool_name, normalized_args, error_class)` con ventana corta (3 últimas acciones). Ya está; reforzar para que el hash incluya `error_class`.
5. **Escalada al usuario es una respuesta legítima**, no un fallo. La frase debe ser específica ("No pude abrir Steam: el proceso no aparece tras 3 segundos. ¿Lo intento otra vez o lo dejamos?").

### (c) Fuentes (2024-2026)
- Huang et al. (ICLR 2024, arXiv:2310.01798) "LLMs Cannot Self-Correct Reasoning Yet".
- Kamoi et al. (TACL 2024, MIT Press) "When Can LLMs Actually Correct Their Own Mistakes?".
- Cho et al. (EMNLP 2025 Findings, arXiv:2505.23060) "Self-Correcting Code Generation Using Small Language Models".
- CyberCorrect (arxiv 2605.17305, 2026) — overshoot en self-correction; CyberCorrect reduce overshoot al 8.2% vs >10% de Self-Refine/Reflexion.
- inventrium.net (2025) "Your ReAct AI Agent Is Wasting 90% of Retries".
- Fastio (2026) "AI Agent Retry Patterns" (exponential backoff + jitter + escalada humana).
- Matrixtrak (2025) "Agents loop forever" — stop rules y budgets.
- Zylos Research (2026) "Agent Self-Correction: From Reflexion to Process Reward Models".
- SCoRe (ICLR 2025, training language models to self-correct) — confirma que las ganancias requieren fine-tuning con datos pareados, no prompting.

### (d) Veredicto
**Lo que ya hay (verifiers + replan acotado + loop detector + honesty guard) es exactamente el approach correcto** según la literatura 2024-2026 para modelos sub-10B. Las únicas mejoras estructurales recomendadas son:

1. **Tipificar errores** en las 6 clases anteriores en lugar de un contador global de "tool failures".
2. **Presupuesto por clase**, no global.
3. **Replan input estructurado** (un JSON de `error_trace` con campos `tool`, `args`, `expected`, `actual`, `class`) en lugar de prosa libre — Gemma 4B sigue mejor estructura que texto plano.
4. **Asegurar que el LLM nunca ve la pregunta "¿está hecho?"** — sólo ve "el verifier dice X, plantea el siguiente paso o termina".

### (e) Código concreto

```python
# recovery.py — máquina de estados externa
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import time, hashlib, random, json

class ErrClass(str, Enum):
    TRANSIENT = "transient"
    PRECONDITION = "precondition_missing"
    ARG_INVALID = "arg_invalid"
    VERIFIER_UNKNOWN = "verifier_unknown"
    VERIFIER_FAILED = "verifier_failed"
    TOOL_NOT_FOUND = "tool_not_found"
    HARD = "hard_fail"

RETRY_BUDGET = {
    ErrClass.TRANSIENT:        2,
    ErrClass.PRECONDITION:     1,
    ErrClass.ARG_INVALID:      1,
    ErrClass.VERIFIER_UNKNOWN: 1,
    ErrClass.VERIFIER_FAILED:  1,   # 1 replan
    ErrClass.TOOL_NOT_FOUND:   0,
    ErrClass.HARD:             0,
}

@dataclass
class Attempt:
    tool: str
    args: dict
    outcome: str         # 'verified' | 'failed' | 'unknown'
    err_class: ErrClass | None
    err_msg: str = ""

@dataclass
class RecoveryState:
    attempts: list[Attempt] = field(default_factory=list)
    spent: dict = field(default_factory=lambda: defaultdict(int))

    def hash_action(self, tool, args, err_class):
        norm = json.dumps({"t":tool,"a":args,"e":str(err_class)}, sort_keys=True)
        return hashlib.sha1(norm.encode()).hexdigest()[:12]

    def is_loop(self, tool, args, err_class, window=3) -> bool:
        h = self.hash_action(tool, args, err_class)
        recent = [self.hash_action(a.tool, a.args, a.err_class)
                  for a in self.attempts[-window:]]
        return recent.count(h) >= 2

def classify(tool_result, verifier_outcome) -> ErrClass | None:
    if tool_result.exception is not None:
        msg = str(tool_result.exception).lower()
        if any(k in msg for k in ('timeout','timed out','temporarily','com error 0x8001')):
            return ErrClass.TRANSIENT
        if any(k in msg for k in ('not installed','not found in path','no such file','daemon')):
            return ErrClass.PRECONDITION
        if any(k in msg for k in ('invalid','must be','unsupported','no contact')):
            return ErrClass.ARG_INVALID
        return ErrClass.HARD
    if verifier_outcome.state == 'failed':
        return ErrClass.VERIFIER_FAILED
    if verifier_outcome.state == 'unknown':
        return ErrClass.VERIFIER_UNKNOWN
    return None

def backoff_sleep(attempt_n: int):
    delay = min(0.25 * (2 ** attempt_n), 3.0)
    delay += random.uniform(0, 0.1)
    time.sleep(delay)

ACTION_HIGH_RISK_TOOLS = {
    'send_whatsapp_message','fs_delete','fs_move','run_terminal',
    'send_email','create_event','post_web'
}

def decide_next(state: RecoveryState, err: ErrClass, tool: str) -> str:
    """Returns: 'retry' | 'repair_then_retry' | 'replan_once' | 'ask_user' | 'give_up'"""
    if state.spent[err] >= RETRY_BUDGET[err]:
        return 'ask_user' if tool in ACTION_HIGH_RISK_TOOLS else 'give_up'
    if err == ErrClass.PRECONDITION:
        return 'repair_then_retry'
    if err == ErrClass.VERIFIER_FAILED:
        return 'replan_once'
    if err == ErrClass.TOOL_NOT_FOUND:
        return 'ask_user'
    if err == ErrClass.ARG_INVALID:
        return 'replan_once'
    return 'retry'

def build_replan_payload(state: RecoveryState, user_goal: str) -> dict:
    """Estructura JSON; Gemma 4B sigue mejor estructura que prosa."""
    last = state.attempts[-1]
    return {
        "user_goal": user_goal,
        "last_attempt": {
            "tool": last.tool,
            "args": last.args,
            "outcome": last.outcome,
            "error_class": str(last.err_class),
            "error": last.err_msg[:300],
        },
        "instruction": (
            "The previous tool call did NOT achieve its effect. "
            "Choose ONE next action from the allowed tool list. "
            "Do NOT claim the action is done. "
            "If you do not know how to fix it, return tool=ask_user with a "
            "single concrete question."
        ),
        "honesty_constraint": "Never say 'done'. The verifier decides."
    }

def run_action_with_recovery(planner, executor, verifier, user_goal: str,
                             tool: str, args: dict, max_steps=5):
    state = RecoveryState()
    for step in range(max_steps):
        tool_result = executor.run(tool, args)
        v = verifier.verify(tool, args, tool_result)
        err = classify(tool_result, v)
        if err is None:
            state.attempts.append(Attempt(tool, args, v.state, None))
            return ('verified', v, state)

        attempt = Attempt(tool, args, v.state, err, str(tool_result.exception or ''))
        state.attempts.append(attempt)

        if state.is_loop(tool, args, err):
            return ('loop_detected', v, state)

        action = decide_next(state, err, tool)
        state.spent[err] += 1

        if action == 'retry':
            backoff_sleep(state.spent[err]); continue
        if action == 'repair_then_retry':
            if not repair_precondition(tool, args):
                return ('repair_failed', v, state)
            continue
        if action == 'replan_once':
            payload = build_replan_payload(state, user_goal)
            new_plan = planner.replan(payload)         # 1 sola llamada LLM
            tool, args = new_plan['tool'], new_plan['args']
            continue
        if action == 'ask_user':
            return ('ask_user', v, state)
        if action == 'give_up':
            return ('give_up', v, state)
    return ('budget_exhausted', None, state)
```

**Qué medir:** distribución de `ErrClass` por tool, tasa de éxito tras `replan_once`, tasa de bucles detectados, frecuencia de `ask_user` (un valor demasiado alto erosiona confianza; demasiado bajo significa que el agente está alucinando hechos).

---

## Punto 3 — Comunicar "unknown" sin sobre-hedging

### (a) Diagnóstico
El estado `unknown` (la acción se ejecutó pero el verifier no pudo confirmar el efecto) es el más delicado por voz. Decirlo *siempre* erosiona la fluidez; no decirlo es mentir. UXmatters (nov 2025) cita a Nielsen Norman Group, 2024: *"63% of users are more likely to rely on AI systems that display confidence levels or explain their reasoning than on those that give black-box answers"*. Pero StudioNorth/HBR (marzo 2026) advierten que *"calibrated AI sounds honest, not hesitant"* — hedging vacío daña tanto como el silencio.

### (b) Comparativa de microcopy por estado

| Estado | Acción | Microcopy reversible (subir volumen) | Microcopy alto riesgo (mensaje, fs) |
|---|---|---|---|
| `verified` | Confirmar breve | "Hecho." | "Enviado a Mamá." |
| `unknown` (low risk) | Reportar sin alarmar | "Listo." (+ honesty footer cubre) | n/a — no aplica |
| `unknown` (high risk) | Decir literalmente que no se confirmó | n/a | "Lo lancé pero no pude confirmar que se envió. ¿Reviso?" |
| `failed` | Decir qué pasó + opción concreta | "No subió el volumen, está mute. ¿Lo desmuteo?" | "No se envió: WhatsApp no respondió. ¿Reintento?" |

### Reglas de microcopy calibrado (2025-2026)

1. **Un solo intent por turno** (Microcopy Voice Checkout 2025: *"One intent per turn... avoid compound prompts"*).
2. **Echo con propósito**: repetir SÓLO lo que reduce riesgo (destinatario y primeras palabras del mensaje, no la frase entera).
3. **Verbo en pasado SOLO si verified**. Si unknown: verbo en pasado del *acto del agente* ("lo intenté", "lo lancé"), no del *efecto* ("se envió").
4. **No agregar "creo que" ni "quizás"** — son hedges vacíos. Mejor: nombrar lo que se hizo y lo que no se pudo verificar.
5. **Si una sesión tuvo `unknown` en ≥1 paso, el honesty footer es obligatorio** y debe nombrar el paso (esto ya existe — mantener).

### (c) Fuentes
- UXmatters (nov 2025) "Design Psychology of Trust in AI" — citando Nielsen Norman Group 2024.
- Smashing Magazine (sep 2025) "Psychology of Trust in AI: A Guide to Measuring and Designing for User Confidence".
- StudioNorth / HBR (marzo 2026) "When AI speaks, authority comes with it" — calibrated AI voice authority.
- InfoWorld (2025) "Building enterprise voice AI agents: a UX approach" (*"41% admit to yelling at their voice assistant when things go wrong"*).
- Influencers-Time (2025) microcopy voice checkout.
- CHI '23 (arxiv 2303.00164) "Mixed-Methods Approach to User Trust after Voice Assistant Failures".

### (d) Veredicto
**Adoptar microcopy diferenciado por riesgo** (no por estado solo). El estado `unknown` para acciones reversibles puede acortarse a un acknowledgment neutro ("Listo") siempre que el honesty footer cubra la sesión; para acciones high-risk debe verbalizarse en la misma frase ("no pude confirmar").

### (e) Código concreto

```python
# voice_microcopy.py
HIGH_RISK = {'send_whatsapp_message','fs_delete','fs_move','run_terminal',
             'send_email','create_event','post_web'}

def reply_for(tool: str, outcome, args: dict, lang='es') -> str:
    risky = tool in HIGH_RISK
    if outcome.state == 'verified':
        if tool == 'send_whatsapp_message':
            return f"Enviado a {args.get('contact','')}."
        if tool == 'open_app':
            return f"Abierto {args.get('name','')}."
        if tool == 'set_volume':
            return "Hecho."
        return "Hecho."
    if outcome.state == 'unknown':
        if risky:
            return ("Lo intenté, pero no pude confirmar que tuviera efecto. "
                    "¿Reviso?")
        return "Listo."   # low risk: ack neutro, el footer cubre
    # failed
    detail = outcome.detail.split(';')[0]
    if tool == 'send_whatsapp_message':
        return f"No se envió. {detail}. ¿Reintento?"
    if tool == 'open_app':
        return f"No se abrió {args.get('name','')}. {detail}. ¿Reintento?"
    return f"No pude hacerlo. {detail}."

def honesty_footer(session_attempts) -> str | None:
    unverified = [a for a in session_attempts if a.outcome == 'unknown']
    if not unverified:
        return None
    if len(unverified) == 1:
        a = unverified[0]
        return f"(Aviso: no confirmé el paso «{a.tool}».)"
    return f"(Aviso: {len(unverified)} pasos quedaron sin confirmar.)"
```

**Qué medir:** longitud media de reply en sílabas, frecuencia de footer, tasa de "no entendí lo que hiciste" (proxy de over-hedging), tasa de re-pregunta del usuario tras `unknown` (proxy de under-hedging).

---

## Punto 4 — Auto-reparación de precondiciones

### (a) Diagnóstico
El mandato del proyecto es: **el código garantiza precondiciones antes de actuar**, no después de fallar. La literatura coincide (InferAct, arxiv 2407.11843; VeriGuard, arxiv 2510.05156, 2025; AGENT-C, arxiv 2512.23738, 2025): la verificación pre-acción reduce fallos irreversibles más que el post-mortem. Precondiciones típicas:

- **App instalada y accesible**: `where steam.exe`, `winget list --id …`, registro `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\…`.
- **Servicio/daemon corriendo**: `sc query` o `psutil.process_iter` por nombre.
- **Ventana focusable**: existe HWND, no minimizada, no colgada (`SendMessageTimeout SMTO_ABORTIFHUNG`).
- **Permisos**: token elevado para acciones admin; UAC.
- **Conectividad** para web tools.
- **Pareja correcta de tools**: si vas a mandar WhatsApp, primero asegurar que el chat del contacto está abierto Y enfocado.

### (b) Comparativa

| Precondición | Detección | Reparación idempotente | Latencia |
|---|---|---|---|
| App instalada | `shutil.which`, `winget list`, registry walk | `winget install` (con consentimiento) o avisar | <50 ms detección |
| Proceso vivo | `psutil.process_iter(['name'])` | `subprocess.Popen` + `WaitForInputIdle` | <30 ms |
| Ventana enfocable | `EnumWindows` + `IsHungAppWindow` | `ShowWindow(SW_RESTORE)` + `SetForegroundWindow` (con AttachThreadInput) | <10 ms |
| WhatsApp logueado | UIA: presencia del panel "Chats" vs pantalla QR | avisar al usuario (no se puede auto-loguear) | 50-200 ms |
| Audio device default | pycaw `GetDefaultEndpoint` | n/a (pedir al usuario) | <5 ms |
| Network | socket connect 1.1.1.1:443 timeout 200ms | esperar / informar | 50-200 ms |
| Permisos admin | `ctypes.windll.shell32.IsUserAnAdmin()` | re-launch con `runas` + consentimiento explícito | <1 ms |

### (c) Fuentes
- InferAct (arxiv 2407.11843) — preemptive evaluation de acciones críticas.
- VeriGuard (arxiv 2510.05156, 2025) — verified code generation for agent safety.
- AGENT-C (arxiv 2512.23738, 2025) — runtime enforcement de propiedades temporales.
- Vellum "ultimate LLM agent build guide" (2025) — idempotencia, contratos.
- Towards AI / Oborskyi (nov 2025) — "Uncertainty Architecture": *"store the generated message, and treat retries as idempotent by business key"*.
- pywin32 docs (`WaitForInputIdle`, `SetWinEventHook`); pycaw 20251023.

### (d) Veredicto
**Implementar un módulo `preconditions.py` invocado ANTES** de cada tool, con un mapping `tool → [precondiciones]` declarativo. Cada precondición tiene `check()` y `repair()` idempotente. Repair sólo modifica estado si `check()` falla. Si `repair()` no puede, devuelve `RepairOutcome.needs_user` y el agente pregunta antes de tocar nada.

### (e) Código concreto

```python
# preconditions.py
from dataclasses import dataclass
from typing import Callable, Literal
import psutil, shutil, ctypes
import win32gui, win32con, win32api, subprocess, socket

@dataclass
class RepairOutcome:
    state: Literal['ok','repaired','failed','needs_user']
    detail: str = ""

@dataclass
class Precondition:
    name: str
    check: Callable[[dict], bool]
    repair: Callable[[dict], RepairOutcome]

def _proc_running(name: str) -> bool:
    name = name.lower()
    return any(p.info['name'] and p.info['name'].lower()==name
               for p in psutil.process_iter(['name']))

def _launch_and_wait(exe: str, args=(), timeout_s=5) -> RepairOutcome:
    try:
        p = subprocess.Popen([exe, *args])
    except Exception as e:
        return RepairOutcome('failed', f'launch failed: {e}')
    h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, p.pid)
    if h:
        r = ctypes.windll.user32.WaitForInputIdle(h, int(timeout_s*1000))
        ctypes.windll.kernel32.CloseHandle(h)
        if r == 0:
            return RepairOutcome('repaired', f'pid={p.pid} idle')
    return RepairOutcome('failed', 'did not reach idle')

def _focus_hwnd(hwnd: int) -> bool:
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    fg = win32gui.GetForegroundWindow()
    t_fg = win32api.GetCurrentThreadId()
    try:
        target_thread, _ = win32api.GetWindowThreadProcessId(fg) if fg else (0, 0)
        win32api.AttachThreadInput(t_fg, target_thread, True)
        win32gui.SetForegroundWindow(hwnd)
    finally:
        try: win32api.AttachThreadInput(t_fg, target_thread, False)
        except: pass
    return win32gui.GetForegroundWindow() == hwnd

# --- catálogo declarativo ---
PRECONDS = {
    'open_app': [
        Precondition(
            name='installed',
            check=lambda args: shutil.which(args['exe']) is not None
                               or _registry_has_app(args['name']),
            repair=lambda args: RepairOutcome('needs_user',
                f"'{args['name']}' no está instalado. ¿Lo instalo con winget?"),
        ),
    ],
    'send_whatsapp_message': [
        Precondition(
            name='whatsapp_running',
            check=lambda args: _proc_running('WhatsApp.exe'),
            repair=lambda args: _launch_and_wait(
                shutil.which('WhatsApp.exe') or
                r'%LOCALAPPDATA%\WhatsApp\WhatsApp.exe'),
        ),
        Precondition(
            name='whatsapp_logged_in',
            check=lambda args: _whatsapp_logged_in_via_uia(),
            repair=lambda args: RepairOutcome('needs_user',
                "WhatsApp pide login (QR). Necesito tu intervención."),
        ),
        Precondition(
            name='contact_visible_and_focused',
            check=lambda args: _verify_chat_header_uia(args['contact']),
            repair=lambda args: _open_chat_with_contact(args['contact']),
        ),
    ],
    'run_terminal': [
        Precondition(
            name='shell_exists',
            check=lambda args: shutil.which(args.get('shell','powershell.exe')) is not None,
            repair=lambda args: RepairOutcome('failed', 'shell no encontrado'),
        ),
    ],
    'web_get': [
        Precondition(
            name='network',
            check=lambda args: _has_network(),
            repair=lambda args: RepairOutcome('needs_user', 'sin conexión'),
        ),
    ],
}

def _has_network(timeout=0.3) -> bool:
    try:
        s = socket.create_connection(('1.1.1.1', 443), timeout=timeout)
        s.close(); return True
    except OSError:
        return False

def ensure_preconditions(tool: str, args: dict) -> RepairOutcome:
    for pc in PRECONDS.get(tool, []):
        if pc.check(args):
            continue
        out = pc.repair(args)
        if out.state in ('failed','needs_user'):
            return RepairOutcome(out.state,
                f"precond «{pc.name}» no satisfecha: {out.detail}")
        if not pc.check(args):
            return RepairOutcome('failed',
                f"repair de «{pc.name}» no surtió efecto")
    return RepairOutcome('ok')

def repair_precondition(tool, args):  # usado por recovery.py
    return ensure_preconditions(tool, args).state in ('ok','repaired')
```

**Qué medir:** tasa de "fail evitado por precondición" (acciones que NO se intentaron porque la precond falló), tiempo medio de `ensure_preconditions`, % de `needs_user` por tool.

---

## Punto 5 — Coste de verificación vs latencia (política escalonada por riesgo)

### (a) Diagnóstico
Verificar cada acción añade latencia y, según SmartSnap (arxiv 2512.22322, 2026): *"passive verification design leads directly to two critical drawbacks: (1) it incurs prohibitively high verification costs (in both API fees and latency), and (2) it places a heavy load on the VLMs, increasing the risk of hallucinations and false positive judgments"*. La solución es **selective verification**.

Evidencia cuantitativa reciente: **TrustBench** (Sharma et al., ASU/UCLA, arxiv 2603.09157, 2026) reporta verbatim: *"Across multiple agentic tasks, TrustBench reduced harmful actions by 87%. Domain-specific plugins outperformed generic verification, achieving 35% greater harm reduction. With sub-200ms latency, TrustBench enables practical real-time trust verification for autonomous agents"*. **Critical Step Optimization** (Mukai Li et al., Tencent AI Lab, arxiv 2602.03412, feb 2026): *"CSO achieves 37% and 26% relative improvement over the SFT baseline... while requiring supervision at only 16% of trajectory steps"* — el 84% restante puede dejarse sin supervisión sin pérdida.

### (b) Tabla de riesgo por tool del agente

| Tool | Reversible | Daño máximo | Política recomendada | Latencia objetivo del verifier |
|---|---|---|---|---|
| `set_volume(+5%)` | sí | molestia menor | NO verificar; sólo footer si verifier ligero gratuito | n/a |
| `set_volume(absolute=X)` | sí | molestia | verificar con pycaw (<5 ms) | <10 ms |
| `mute / unmute` | sí | molestia | verificar pycaw | <10 ms |
| `media_play / pause / next` | sí | nulo | NO verificar | n/a |
| `open_app` | sí | nulo | verificar (EnumWindows + WaitForInputIdle) | <500 ms (timeout) |
| `focus_window` | sí | nulo | verificar GetForegroundWindow | <5 ms |
| `gui_click(coords)` | mayormente sí | medio (clic equivocado) | verificar cambio de UIA estado tras 200 ms | <300 ms |
| `fs_create / fs_read` | sí | bajo | verificar Path.exists / stat | <2 ms |
| `fs_move / fs_rename` | reversible si registramos | medio | **verificar SIEMPRE** + log undo | <10 ms |
| `fs_delete` | NO | alto | **verificar SIEMPRE + confirmación previa por voz** | <50 ms |
| `run_terminal` | depende | alto | **verificar return code + stdout regex** | varía |
| `send_whatsapp_message` | NO | alto (mensaje al chat equivocado) | **verificar SIEMPRE header del chat + tick de enviado** | <400 ms |
| `web_get` (read-only) | sí | nulo | verificar HTTP 200 | la del request |
| `web_post / web_submit` | NO | alto | **verificar SIEMPRE** | varía |
| `create_event / send_email` | semi | alto | **verificar SIEMPRE** | varía |

### Reglas de selección
1. Si la acción es **irreversible o de comunicación a terceros** → verificación obligatoria, sin excepción.
2. Si la acción es **reversible y de bajo daño** → verificación opcional, sólo si el verifier es gratuito (<10 ms).
3. **Risk-tier por tool, no por sesión** — el mismo tool puede caer en distintos niveles según args (`fs_delete /tmp/foo.txt` vs `fs_delete C:\Users\me\Documents`).
4. **Coste de no verificar = honesty footer obligatorio**: si la acción fue alto riesgo y no verificada, el reply debe decirlo.

### (c) Fuentes
- SmartSnap (arxiv 2512.22322, 2026) — proactive self-verification, paradigma shift de verificación pasiva.
- TrustBench (Sharma et al., arxiv 2603.09157, 2026) — sub-200 ms, 87% reducción de acciones dañinas, 35% adicional con plugins por dominio.
- Critical Step Optimization (Li et al., Tencent AI Lab, arxiv 2602.03412, feb 2026) — 16% de pasos supervisados rinden 37%/26% de mejora.
- "Agentic AI and Hallucinations" (arxiv 2507.19183, 2025) — coste de verificación como palanca económica.
- "Criticality and Safety Margins for RL" (arxiv 2409.18289) — supervisar el 5% de decisiones previene el 47% de errores en Atari Beamrider.

### (d) Veredicto
**Adoptar una tabla declarativa `tool → risk_tier → verifier_policy`** evaluada al planificar, no al ejecutar. Esto da: (1) latencia mínima en acciones triviales, (2) garantías duras en acciones críticas, (3) presupuesto de verificación predecible. Para acciones reversibles ligeras, **omitir verificación es una decisión válida y explícita**, no negligencia.

### (e) Código concreto

```python
# verify_policy.py
from enum import Enum
from dataclasses import dataclass

class Risk(str, Enum):
    TRIVIAL = "trivial"      # reversible, daño nulo
    LOW = "low"              # reversible, daño bajo
    MEDIUM = "medium"        # reversible con coste
    HIGH = "high"            # irreversible o comunicación externa

@dataclass
class VerifyPolicy:
    risk: Risk
    must_verify: bool
    require_user_confirmation: bool
    verify_timeout_ms: int

def policy_for(tool: str, args: dict) -> VerifyPolicy:
    if tool == 'set_volume':
        delta = args.get('delta_pct', 0)
        if abs(delta) <= 10:
            return VerifyPolicy(Risk.TRIVIAL, False, False, 0)
        return VerifyPolicy(Risk.LOW, True, False, 10)
    if tool in ('media_play','media_pause','media_next'):
        return VerifyPolicy(Risk.TRIVIAL, False, False, 0)
    if tool == 'open_app':
        return VerifyPolicy(Risk.LOW, True, False, 1500)
    if tool == 'fs_delete':
        return VerifyPolicy(Risk.HIGH, True, True, 100)
    if tool == 'send_whatsapp_message':
        return VerifyPolicy(Risk.HIGH, True, False, 400)
    if tool == 'run_terminal':
        return VerifyPolicy(Risk.HIGH, True, True, 5000)
    if tool == 'gui_click':
        return VerifyPolicy(Risk.MEDIUM, True, False, 300)
    if tool == 'web_get':
        return VerifyPolicy(Risk.LOW, True, False, 200)
    if tool in ('web_post','send_email','create_event'):
        return VerifyPolicy(Risk.HIGH, True, False, 1000)
    return VerifyPolicy(Risk.MEDIUM, True, False, 500)
```

**Qué medir:** latencia media añadida por verificación (total y por tier), tasa de "skipped verification" (debería ser solo TRIVIAL), tasa de daño post-hoc por tier (debería ser 0 en HIGH).

---

## Recomendaciones (decisiones accionables)

**Fase A — inmediato (semana 1):**
1. Migrar `verify_window` y `verify_whatsapp_*` de OCR a `uiautomation` (yinkaisheng) con cliente singleton y caché de `WindowControl`. Mantener OCR como fallback sólo si el árbol UIA vuelve vacío tras 200 ms (Chromium cold-start).
2. Sustituir el contador global de retries por la tabla `ErrClass → budget` (6 clases).
3. Reforzar el hash del loop detector incluyendo `err_class` además de `(tool, args)`.
4. Adoptar `policy_for(tool, args)` antes de cada ejecución; respetar `must_verify` y `require_user_confirmation`.

**Fase B — corto plazo (semanas 2-3):**
5. Implementar `preconditions.py` con catálogo declarativo por tool. Empezar por `send_whatsapp_message` (el caso del bug) y `open_app`.
6. Migrar `verify_audio` a `pycaw.GetMasterVolumeLevelScalar()` (lectura del estado real).
7. Cambiar el formato del input del replan a JSON estructurado (Gemma 4B sigue mejor estructura que prosa).
8. Instrumentar las métricas listadas en cada sección.

**Fase C — medio plazo (mes 2):**
9. Telemetría: dashboard con p50/p95 de latencia por verifier, distribución de `ErrClass`, tasa de `unknown` y de honesty footers.
10. Auditoría de 100 sesiones aleatorias: medir falso-OK real.
11. Considerar binding a FlaUI vía pythonnet sólo si la telemetría muestra que sub-300 ms con `uiautomation` no se alcanza.

**Umbrales que cambiarían estas recomendaciones:**
- Si la tasa de falso-OK <1% tras Fase A → no hace falta Fase C (#11).
- Si la latencia p95 de `verify_whatsapp_chat_header` >500 ms tras Fase A → migrar a FlaUI o a CDP (DevTools Protocol vía WebView2).
- Si `ask_user` >15% de sesiones → re-examinar `policy_for` (verificación demasiado agresiva) o mejorar prompt/datos.
- Si los usuarios reportan "no entiendo lo que hiciste" → reducir hedging en microcopy (subir umbral de risk para activar footer).

---

## Caveats

1. **WhatsApp Desktop cambió a WebView2 en finales de 2025**. Es probable que Meta vuelva a cambiar — mantener la verificación con `Name`+`ControlType` y NO hardcodear AutomationIds; añadir tests de smoke al pipeline.
2. **Localización de "Sent/Delivered/Read"**: el verifier de WhatsApp depende del idioma del sistema. La tabla `WA_STATUS_WORDS` cubre en/es/de/pt/fr; ampliar según telemetría.
3. **Las medidas de latencia citadas son órdenes de magnitud**, no benchmarks formales — no existe un benchmark público que compare FlaUI vs uiautomation vs pywinauto con números reproducibles a 2026 (issue FlaUI #188 lo pidió y no obtuvo datos). Los 30 s de pywinauto vienen del issue #1102; los 95 s vs 16 s vienen del #256.
4. **Gemma 4 tool-calling tiene bugs conocidos** en algunas combinaciones llama.cpp/Ollama (PR llama.cpp #21326, #21343; issue #22786). La política de recuperación debe asumir tool-calls malformados (clase `MALFORMED_CALL`/`TOOL_NOT_FOUND`) como caso normal y devolver al modelo la lista válida en lugar de reintentar.
5. **El budget de 1 replan LLM ya implementado es la cifra correcta** para Gemma 4B según la literatura — más replans no mejoran y aumentan el overshoot (CyberCorrect 2026).
6. **No usar Reflexion ni Self-Refine puros** con este modelo (Huang 2024, Kamoi 2024, Cho et al. EMNLP 2025). El proyecto ya hace lo correcto (señal externa); reforzar esa arquitectura, no introspección.
7. **Algunas técnicas de runtime enforcement de la literatura (VeriGuard, AGENT-C, AgentSpec) requieren especificaciones formales** — son overkill para un asistente personal. El approach declarativo (`preconditions.py` + `policy_for`) captura la mayoría del beneficio con una fracción de la complejidad.
8. **Las cifras de TrustBench (87%, sub-200 ms) y CSO (16% de pasos, 37%/26% de mejora) son de benchmarks de investigación**, no de despliegues idénticos al tuyo — úsalas como evidencia de viabilidad cualitativa, no como objetivo numérico literal.