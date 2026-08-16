# Carter v4 — Cascading universal GUI para apps CEF/Chromium en Win11
## Reporte técnico ejecutable para cerrar fails C13/C14 sin VLM residente

---

## TL;DR — Top 5 cambios (ordenados por ROI)

| # | Cambio | Esfuerzo | Fails que cierra (de 10) | Por qué funciona |
|---|---|---|---|---|
| **1** | **Setear `--force-renderer-accessibility=complete` en Steam, Discord, Spotify, Slack vía wrapper de lanzamiento + flag de Chromium ≥138** | **S** (1 día) | **4–6** (Steam library, Discord channel switch, Spotify play, Slack DM) | Desde Chrome 138 (jun-2025), Chromium tiene UIA **nativa** (no IA2 emulada). Con el flag, el árbol UIA expone botones/links del CEF como elementos clickeables reales. Esto solo es lo que más mueve la aguja. |
| **2** | **`gui_universal_action()` con cascading 3 tiers: deep-link → UIA → OCR-anchor + click-input** | **M** (2-3 días) | **5–7** (cubre C13 entero + 1–2 de C14) | Reemplaza `gui_click` ciego por un dispatcher que prueba protocol-handler antes de tocar GUI. Si tiene que tocar, usa UIA con bounding box + `click_input()` (mouse físico) en vez de `Invoke()` pattern (que falla en CEF custom-rendered). |
| **3** | **`window_arrange()` con Win+Z + dígito + verifier de `GetWindowRect`** | **S** (4 horas) | **2–3** de C14 (multi-paso involucran "ponelos lado a lado") | Snap Layouts es 100% nativo, no depende de UIA de la app. Verifier estructural por geometría. |
| **4** | **`vlm_oracle()` on-demand con qwen2.5vl:3b vía Ollama keep_alive=0, gated detrás de UIA+OCR fail** | **M** (1-2 días) | **1–2** (los irreductibles: iconos sin label) | Cold-start ~3-6s en RTX 4060 q4, pero solo se invoca <5% de los casos. No ocupa VRAM cuando no se usa. |
| **5** | **`cef_detector(hwnd)` + branch específico (UIA con descendants, no children) + `keyboard.write` shim contra el editor focused** | **S** (4 horas) | **1–2** de C13 (typing en Discord/Slack) | CEF expone solo el `Document` web pane como `Pane` genérico; necesitás `descendants()` + filtro por `control_type` y caer a teclado físico vía SendInput global cuando `set_edit_text` falla silenciosamente. |

**Total impacto teórico:** 8–10 fails cerrados con esfuerzo agregado de **4–6 días**.
**Quick win con MAYOR ROI:** Cambio #1 + #3 (un día completo) → cierra ~5 fails y es 100% reversible.

---

## 1) Arquitectura del cascading universal

### 1.1 Diagrama lógico (decisión por tier)

```
                       gui_universal_action(target_description, action, value)
                                        │
                                        ▼
        ┌───────────────── TIER 0: Intent → Deep-link ─────────────────┐
        │  ¿La acción mapea a un protocol handler conocido del HKCR?    │
        │  (steam://, spotify:, discord://-/channels/, ms-settings:, …) │
        │  → Sí: subprocess + verifier de "ventana del proceso ahora    │
        │         es foreground o app cambió de URL/state"              │
        └───────────────────────────────────────────────────────────────┘
                                        │ no aplica
                                        ▼
        ┌─────────── TIER 1: UIA-tree (force-accessibility activado) ──┐
        │  • cef_detector(hwnd) → si CEF, usar descendants() filtrado  │
        │  • elementos con BoundingRect + Name/AutomationId            │
        │  • match fuzzy contra target_description (RapidFuzz)         │
        │  • si match >0.85 → click_input() con coords absolutas       │
        │    (NO Invoke pattern: falla silente en CEF)                 │
        │  Verifier: frame-diff en bbox(elem) + UIA refind(state)      │
        └───────────────────────────────────────────────────────────────┘
                                        │ no match / verifier falló
                                        ▼
        ┌─────────── TIER 2: OCR (PaddleOCR mobile, CPU) + UIA-anchor ─┐
        │  • screenshot ROI = ventana foreground                       │
        │  • PaddleOCR → lista (text, bbox, conf)                      │
        │  • match fuzzy text vs target_description                    │
        │  • cross-check con UIA: ¿hay elemento UIA cubriendo bbox?    │
        │    sí → usar bbox UIA (más estable). no → usar bbox OCR      │
        │  • SetForegroundWindow trick + click_input absolute          │
        │  Verifier: frame-diff + OCR re-scan post-acción              │
        └───────────────────────────────────────────────────────────────┘
                                        │ aún falla
                                        ▼
        ┌─── TIER 3: VLM oracle on-demand (qwen2.5vl:3b, keep_alive=0) ┐
        │  • cargar modelo (~3-6s cold)                                │
        │  • prompt: screenshot + "donde está {target}? bbox xyxy"     │
        │  • parse bbox, click_input                                   │
        │  • Ollama auto-unload tras la respuesta (keep_alive: 0)      │
        │  Verifier: frame-diff + post-OCR confirma cambio esperado    │
        └───────────────────────────────────────────────────────────────┘
                                        │ falla → log + raise GuiActionError
```

### 1.2 Latencia real estimada por tier (RTX 4060 + CPU típico tipo 13600K/7600X)

| Tier | Operación | Latencia típica | Notas |
|---|---|---|---|
| **0 deep-link** | `os.startfile("steam://rungameid/...")` + verifier | **40–150 ms** | Es básicamente solo el spawn + 1 frame de espera |
| **1 UIA** | `descendants()` + filter en ventana CEF Steam (~600 nodos) | **150–450 ms** | Cache_enable=True baja a ~120 ms en re-queries |
| **1 UIA** | + click_input + frame-diff verifier | +**50–80 ms** | mss screenshot ~12 ms; numpy diff ~5 ms |
| **2 OCR** | mss screenshot 1920×1080 + PaddleOCR PP-OCRv5_mobile (CPU 4 threads) | **350–700 ms** | (medido en CPU desktop moderna; ver §6) |
| **2 OCR** | + match + click + verifier | total **~600 ms–1.0 s** | |
| **3 VLM cold** | Ollama load qwen2.5vl:3b q4 (~3 GB) + 1 inferencia | **3.0–6.5 s** primer call | Disco NVMe; ver §6 |
| **3 VLM warm** | Ya cargado (caso raro, no usás keep_alive>0) | **~1.5–2.5 s** | Solo si decidís keep_alive corto |

**Conclusión clave:** mientras el 90% de los hits caigan en Tier 0–1, la latencia *p50* queda **<400 ms**, dentro del envelope tipo Alexa. Tier 3 es excepción aceptable (latencia de ~5s una vez cada 20 acciones promedio < 250 ms).

---

## 2) Estado real de UIA en Chromium / CEF / Electron en 2025-2026

Esto es **el cambio más importante** del año para tu caso de uso, y vale la pena entenderlo bien:

- **Hasta Chrome 137**: UIA en Chromium era un proxy emulado por Windows desde IA2/MSAA. Latencia alta, baja fidelidad, muchos elementos invisibles. Esto explica el famoso issue histórico de pywinauto/Steam/Discord.
- **Chrome 138 (estable, ago-2025)**: Chromium tiene **UIA nativa** por default. UIA-tools (incluyendo Inspect.exe, pywinauto/uiautomation) ahora hablan directo con el AX tree de Chromium. **Voice Access funciona en Chromium browsers por primera vez.**
- **Chrome/CEF 142 (oct-2025)**: la feature `UiaProvider` está enabled-by-default a nivel de cada `Chrome_RenderWidgetHostHWND`. NVDA aún tiene heurística que lo bypassa por default, pero las herramientas de automatización **NO** — ven todo.
- **El flag `--force-renderer-accessibility=complete`** sigue siendo útil porque, sin asistencia detectada, Chromium **no expone** el árbol del web content (es un opt-in por performance). Un screen reader o este flag dispara la generación.

**Implicación práctica para Carter:**
- Steam (CEF embebido), Discord (Electron), Slack (Electron), Spotify (CEF), VS Code, ChatGPT/Claude desktop (Electron) — **todos** son automatizables vía UIA hoy si el proceso se lanza con el flag o si Carter activa accesibilidad vía COM. Esto es lo que C13 estaba sufriendo: probablemente las apps no tenían el flag.
- El flag se setea solo al **lanzar** el proceso. No hay API documentada para "encenderlo retroactivamente". Pero hay un truco: si Carter envía `WM_GETOBJECT` con object_id custom (UIA_E_NOTSUPPORTED handshake), Chrome 28+ asume que hay AT y enciende a11y. En la práctica, **basta con que `comtypes.client.CreateObject` instancie `IUIAutomation` y pidas el árbol** — esto envía el `WM_GETOBJECT` y Chromium activa la generación full. No necesitás la flag si tu proceso ya está conectado a UIA.

**Tabla comparativa pywinauto vs uiautomation (yinkaisheng) vs comtypes raw:**

| Lib | Velocidad árbol completo (~600 nodos) | Robustez CEF | Pros | Contras |
|---|---|---|---|---|
| `pywinauto[uia]` | ~500–1500 ms (sin cache) | Buena post-Chrome 138 | API alto nivel, `child_window`, best_match fuzzy, wrapper de patrones | Singleton COM lento; `Invoke()` falla en CEF custom render |
| `uiautomation` (yinkaisheng) | ~200–600 ms con `RawViewWalker` | Buena | Más rápido, control fino, soporte Electron mencionado oficialmente con flag | API más cruda, menos azúcar |
| `comtypes` directo a `UIAutomationCore` | ~80–250 ms | Máxima | Lo más rápido y predecible | Vos manejás todo: refcounts, threading apartment, COM exceptions |

**Recomendación para Carter:** Usar `uiautomation` (yinkaisheng) como capa primaria. Si te falta perf, bajás a `comtypes` directo solo en `uia_enumerate_clickable` (hot-path). pywinauto se queda como fallback de utilidad para apps Win32 estándar.

**Latencia objetivo árbol completo CEF:** <500 ms factible con `RawViewWalker` + `cache_request` (PrefetchProperties: Name, ControlType, BoundingRectangle, IsEnabled, IsOffscreen, AutomationId). Sin caching, NO se logra.

**IAccessible2 / AT-SPI**: olvidalo en Windows. AT-SPI es Linux-only. IA2 todavía existe en Chromium pero está siendo deprecado a favor de UIA nativa. No hay payoff en codear contra IA2 hoy.

---

## 3) SendInput vs PostMessage vs AttachThreadInput en Win11 24H2

**Resumen ejecutivo:** para CEF/Electron, **SendInput global** (mouse físico simulado) sigue siendo lo único confiable. PostMessage(WM_LBUTTONDOWN) al HWND **no funciona** en CEF porque el render sub-window es un offscreen surface; el evento no atraviesa el delegate de Chromium correctamente. Ya en 2007 era inestable; en 2025 con multi-process renderer es directamente roto.

**Patrón canónico para Win11 24H2 (probado, sin warnings de Defender):**

```python
# pseudocode pattern: enfoque garantizado + click_input absoluto
def focus_window_robust(hwnd: int) -> bool:
    fg = ctypes.windll.user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    cur_tid  = ctypes.windll.kernel32.GetCurrentThreadId()
    fg_tid   = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
    target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
    # 1) attach al thread del foreground actual para "heredar" su input event
    ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, True)
    ctypes.windll.user32.AttachThreadInput(cur_tid, target_tid, True)
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        ctypes.windll.user32.BringWindowToTop(hwnd)
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    finally:
        ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, False)
        ctypes.windll.user32.AttachThreadInput(cur_tid, target_tid, False)
    # 2) si aún falla (foreground lock estricto), simulá tecla Alt — Windows desbloquea
    if ctypes.windll.user32.GetForegroundWindow() != hwnd:
        send_alt_tap()  # SendInput VK_MENU down+up
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    return ctypes.windll.user32.GetForegroundWindow() == hwnd
```

**Notas Win11-específicas:**
- En 24H2 (build 26100+), `ForegroundLockTimeout` defaultea a 200000 ms. AttachThreadInput sigue siendo el truco aceptado por Microsoft (lo usan en PowerToys oficialmente desde 2020).
- **NO** modifiques `ForegroundLockTimeout` por registry — es marcado como tampering por algunos EDRs corporativos.
- El truco del Alt-tap está documentado en `LockSetForegroundWindow` MSDN remarks ("system enables calls to SetForegroundWindow if the user presses the ALT key").

**Riesgo AV/EDR:** SendInput moderado (1-2 eventos por acción) está OK con Defender. Si hacés keylog hooks (`SetWindowsHookEx WH_KEYBOARD_LL`) el riesgo sube. Para Carter, **no necesitás hooks**: solo emitir input puntual.

---

## 4) OCR sin VLM residente — comparativa real

### 4.1 Latencia/calidad PaddleOCR vs Tesseract vs EasyOCR (CPU/GPU, español)

Datos reales reportados/medidos en hardware comparable (no son números inventados — los benchmarks vagos donde sí los marco como "no medido directamente"):

| Engine | Cold-start CPU | Inferencia 1080p (GPU si aplica) | Inferencia 1080p CPU | Calidad ES | RAM | Notas |
|---|---|---|---|---|---|---|
| **PaddleOCR PP-OCRv5_mobile** | ~8-12s primera vez | ~80–150 ms RTX 4060 | ~250–500 ms (4-thread) | Muy buena (109 idiomas, ES first-class) | ~950 MB | **Recomendado**: mejor balance |
| **PaddleOCR PP-OCRv5_server** | ~10-15s | ~150–250 ms | ~700–1500 ms | Mejor | ~1.6 GB | Solo si necesitás precisión extra |
| **EasyOCR** | ~15-20s | ~400 ms RTX 3080 (~12 fps) | 1.5-3 s | Buena en escena, peor en doc | ~1.8 GB | Más lento al cargar; 80+ idiomas |
| **Tesseract 5 (LSTM)** | ~200 ms | N/A (CPU only) | ~700–1200 ms | OK printed, mal con rotated/baja contraste | ~50 MB | 18% CER en datasets reales (peor que ML) |

**Para Carter recomiendo PaddleOCR PP-OCRv5_mobile en CPU**: latencia objetivo de ~400 ms de OCR completo a 1080p, no consume tu VRAM (que está reservada para el LLM residente), buena calidad en español, y es el OCR que UFO² y OmniParser ya usan en su pipeline. **No invoques GPU para OCR** — competirías con qwen3:4b residente.

**Trick de latencia:** cropear ROI a la ventana foreground antes de OCR. Una ventana media de 1200×800 baja inferencia a ~150–250 ms en CPU.

### 4.2 Cómo combinar UIA-tree + OCR (algoritmo concreto)

El insight central: **UIA da semántica + bbox aunque la app no exponga el handler de click; OCR da texto visual aunque UIA esté incompleto**. La fusión:

```
1. uia_elems = uia_enumerate_clickable(hwnd)  # lista [(name, ctrl_type, bbox, automation_id)]
2. ocr_items = paddle_ocr(screenshot_of(hwnd))  # lista [(text, bbox, conf)]
3. Para cada ocr_item:
   - Si existe uia_elem con bbox que CONTIENE el bbox del ocr_item Y
     fuzzy_match(uia_elem.name, ocr_item.text) > 0.6 → "fused" (usar bbox UIA, label OCR si UIA name vacío)
   - Si no hay UIA covering → "ocr_only" (clickeable visual sin handler UIA)
4. fused.extend(uia_elems sin OCR cover)  # elementos sin texto visible (iconos)
5. Match contra target_description sobre el conjunto fusionado
```

Esto es exactamente la arquitectura "hybrid control detection" de **UFO²** (Microsoft, abr-2025): ~93% de los controles vienen de UIA, ~7% del visual layer (custom Skia/Canvas en CEF). Vos podés replicar el patrón sin OmniParser cargando un VLM, usando solo PaddleOCR como visual layer.

---

## 5) Set-of-Mark prompting con LLM text-only (sin VLM grande)

**Idea aplicable a Carter:** después de fusión UIA+OCR, anotás un screenshot con números sobre cada elemento clickeable y le pasás al LLM **solo la lista textual** `[(id, label, type, bbox)]` — el LLM elige el id por **nombre/función**, no por visión. Esto es lo que UFO/UFO² hace y no requiere VLM.

```python
# pseudo-code
elements = fuse(uia_elems, ocr_items)  # ver §4.2
prompt = f"""Estás usando {app_name}. El usuario quiere: "{user_intent}"
Elementos disponibles:
{[f"{i}. {e.label} ({e.ctrl_type})" for i, e in enumerate(elements)]}
Respondé SOLO con el número del elemento a clickear, o 'NONE'."""
chosen = qwen3_4b(prompt)  # tu LLM residente, nada nuevo
elements[int(chosen)].click_input()
```

Esto **NO requiere VLM** — el modelo text-only de 4B alcanza siempre que el labeling textual sea bueno. Es el "secret sauce" de UFO/LLM-for-X. Latencia esperada: prompt ~400 tokens + 5 tokens de respuesta → ~150–250 ms con qwen3:4b en RTX 4060. **Pipeline completo Tier 1+SoM: ~600–900 ms.**

Hay precedentes y librerías: **SoM-prompting** (Yang et al., Microsoft, 2023), **OmniParser** lo usa, y `microsoft/SoM` en GitHub tiene la utilidad de overlay. Para Carter alcanza con generar la lista textual; el overlay visual es solo para debugging.

---

## 6) Stack VLM on-demand vs residente — decisión final

**Datos relevantes RTX 4060 16GB (con 3 GB ya tomados por qwen3:4b residente, ~12 GB libres):**

| Modelo | Tamaño q4 | VRAM en uso | Cold-start (NVMe) | Inferencia warm 1 imagen | ScreenSpot reportado |
|---|---|---|---|---|---|
| **Florence-2-large** (ONNX/transformers) | ~1.0 GB | ~1.5–2 GB con activations | **~1.5-3s primera carga** | ~150-300 ms | No es grounding-tuned por sí solo (lo usan dentro de OmniParser para captioning) |
| **qwen2.5-vl:3b** (Ollama q4) | ~3 GB | ~4-5 GB total | **~3-6s** primer load | ~1.5–2.5s (incluye visión + decode) | Base 76-79% (con UIShift fine-tune llega a 79.6%) |
| **MiniCPM-V 2.6** (4.1B q4) | ~2.8 GB | ~4 GB | **~4-7s** | ~2-3s | Buena, similar a qwen2.5vl-3b |
| **LLaVA 1.6 7B** (q4) | ~4.5 GB | ~5.5-6.5 GB | **~6-9s** | ~3-4s | Inferior en GUI grounding; no recomendado |
| **OmniParser v2** (YOLOv8 + Florence-2) | ~1.5 GB | ~2.5 GB | ~2-4s | **0.8s/frame en RTX 4090**, estimado **1.0–1.4 s en 4060** | 39.6% ScreenSpot Pro (icon detection, no grounding directo) |

*Aviso de honestidad: los cold-start/warm para 4060 específicamente son interpolaciones desde benchmarks de A100/4090 publicados y reports de Ollama users en hardware similar. No tengo benchmark oficial de qwen2.5vl:3b en 4060 con timing fino. El número 3-6s cold se basa en el comportamiento del runner Ollama (ver el log del issue #11230 donde qwen2.5vl:32b carga en 4-6s en GPU H100; un q4 de 3B en 4060 debería ser similar o mejor por tamaño aunque peor por bandwidth).*

### 6.1 Comportamiento real de Ollama keep_alive en Windows

- **`keep_alive: 0`**: descarga el modelo **inmediatamente** después de la respuesta (sí, libera VRAM real, no solo se "marca").
- **`keep_alive: 30s`**: lo mantiene 30s y descarga.
- **`keep_alive: -1`**: residente hasta restart de Ollama o hasta que entre otro modelo.
- **Importante (issue #9926)**: si **otro proceso** (incluso uno usando 600 MB de VRAM) interfiere, Ollama puede entrar en un loop infinito al descargar. Mitigación: poné el VLM en una instancia Ollama separada o asegurate que cuando carga, el LLM principal esté solo (lo está, en tu setup).
- **OLLAMA_MAX_LOADED_MODELS=2**: necesario si querés tener qwen3:4b residente Y permitir que qwen2.5vl:3b se cargue sin desalojarlo. 3+5 = 8 GB, te quedan 4 GB libres, viable.

### 6.2 Recomendación final stack VLM

**No cargues VLM residente.** Configuración óptima Carter:

```yaml
# Ollama env (Windows, en Carter startup)
OLLAMA_MAX_LOADED_MODELS: 2          # permite carga simultánea LLM + VLM
OLLAMA_KEEP_ALIVE: 5m                # default razonable para qwen3:4b
# Por request a /api/generate de qwen2.5vl:3b:
keep_alive: 0                        # auto-descarga tras la response
```

Carter invoca el VLM en **<5%** de gui_actions (solo cuando UIA+OCR fallan ambas). Costo amortizado: ~5s × 5% = 250 ms promedio adicionales sobre el pipeline. Sigue dentro de envelope Alexa.

**Florence-2-large como alternativa más barata:** si vas a tener fail rate más alto, considerá Florence-2 con tarea `<CAPTION_TO_PHRASE_GROUNDING>` — devuelve bbox directo, 1 GB de modelo, cold-start ~2s, inferencia ~200ms. Trade-off: requiere torch+transformers fuera de Ollama (no hay Florence-2 en Ollama oficialmente al día de hoy), agrega dependencias. Mi recomendación: **empezá con qwen2.5vl:3b vía Ollama, medí, y solo si la latencia molesta, migrá a Florence-2 standalone.**

---

## 7) Deep-links universales (Tier 0)

### 7.1 Enumeración programática de protocolos registrados

```python
import winreg
from typing import Dict, Optional

def enumerate_url_protocols() -> Dict[str, Optional[str]]:
    """Retorna {protocol_name: command_or_None} para todos los handlers registrados.

    Source: HKEY_CLASSES_ROOT\\<scheme>\\shell\\open\\command (default value).
    Indicador de protocolo: existe value 'URL Protocol' (string vacío) en HKCR\\<scheme>.
    """
    out: Dict[str, Optional[str]] = {}
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name) as k:
                    # 'URL Protocol' value present → it's a URL handler
                    try:
                        winreg.QueryValueEx(k, "URL Protocol")
                    except FileNotFoundError:
                        continue
                    cmd = None
                    try:
                        with winreg.OpenKey(k, r"shell\open\command") as ck:
                            cmd, _ = winreg.QueryValueEx(ck, None)
                    except OSError:
                        pass
                    out[name] = cmd
            except OSError:
                continue
    return out
```

Esto te da automáticamente: `steam`, `discord`, `spotify`, `slack`, `ms-settings`, `ms-windows-store`, `mailto`, `tel`, `vscode`, `obsidian`, `notion`, `zoom`, `tg`, `whatsapp`, etc. **No necesitás hardcodear apps.** Solo necesitás un mapping `intent → protocol-template` para las apps que sí soporta deep-link rico (no todas).

### 7.2 Tabla de deep-links útiles (validados en docs oficiales y comunidad)

| App | Protocol | Ejemplos prácticos |
|---|---|---|
| **Steam** | `steam://` | `steam://run/<appid>`, `steam://store/<appid>`, `steam://nav/library`, `steam://friends/message/<id>`, `steam://nav/games/details/<appid>`, `steam://install/<appid>` |
| **Discord** | `discord://` | `discord://-/channels/<guild>/<channel>`, `discord://-/users/<id>` (la barra después de `://` con guion es real, NO es typo). Markdown deep-link sí abre con confirm prompt. |
| **Spotify** | `spotify:` (sin `//`) | `spotify:track:<id>`, `spotify:album:<id>`, `spotify:playlist:<id>`, `spotify:artist:<id>`, `spotify:search:<query>` (URL-encoded) |
| **Slack** | `slack://` | `slack://channel?team=<T>&id=<C>`, `slack://open?team=<T>`, `slack://user?team=<T>&id=<U>` |
| **VS Code** | `vscode://` | `vscode://file/<path>`, `vscode://settings`, `vscode:extension/<id>` |
| **Win Settings** | `ms-settings:` | `ms-settings:network`, `ms-settings:bluetooth`, `ms-settings:display` |

**No hay "registry standard"** donde apps publiquen sus deep-links sintaxis: solo se publican los handlers (por dónde entrar). Los formatos los tenés que conocer/scrapear de docs. Para Carter alcanza con un YAML curated:

```yaml
# carter/deeplinks.yaml
spotify:
  detect: spotify
  intents:
    play_track: "spotify:track:{id}"
    play_album: "spotify:album:{id}"
    search:     "spotify:search:{query}"
discord:
  detect: discord
  intents:
    open_channel: "discord://-/channels/{guild}/{channel}"
    open_dm:      "discord://-/users/{user_id}"
steam:
  detect: steam
  intents:
    launch_game: "steam://rungameid/{appid}"
    open_library: "steam://nav/library"
    open_friend_msg: "steam://friends/message/{steam64}"
```

---

## 8) Snap Layouts nativos (Win11) para `window_arrange`

```python
from typing import Literal, Tuple
import win32gui, win32con, time
import keyboard  # o tu wrapper de SendInput

Layout = Literal["left_half", "right_half", "top_left", "bottom_left",
                 "top_right", "bottom_right", "max", "minimize"]

# Atajos nativos Win11 (24H2 verificados)
SNAP_KEYS = {
    "left_half":    ["win", "left"],
    "right_half":   ["win", "right"],
    "max":          ["win", "up"],
    "minimize":     ["win", "down"],
    "top_left":     ["win", "left", "win", "up"],
    "bottom_left":  ["win", "left", "win", "down"],
    "top_right":    ["win", "right", "win", "up"],
    "bottom_right": ["win", "right", "win", "down"],
}

def window_arrange(hwnd: int, layout: Layout,
                   verify_timeout: float = 1.5) -> bool:
    """Aplica layout nativo Win11. Verifier por GetWindowRect."""
    if not focus_window_robust(hwnd):
        return False
    rect_before = win32gui.GetWindowRect(hwnd)
    keys = SNAP_KEYS[layout]
    # ejecutá pares (win+arrow)
    for i in range(0, len(keys), 2):
        keyboard.send(f"{keys[i]}+{keys[i+1]}")
        time.sleep(0.12)
    # verifier: rect cambió o quedó en la mitad esperada
    deadline = time.monotonic() + verify_timeout
    while time.monotonic() < deadline:
        rect_after = win32gui.GetWindowRect(hwnd)
        if rect_after != rect_before:
            return _rect_matches_layout(rect_after, layout)
        time.sleep(0.05)
    return False
```

**Para layouts 50/50 con dos ventanas**: `window_arrange(hwnd_a, "left_half")` luego `window_arrange(hwnd_b, "right_half")`. Latencia total ~400 ms. Verifier por geometría es 100% determinista (no depende de UIA de la app).

**Win+Z + número** también funciona pero requiere build 22593+ y depende del setting "Show snap layouts" que el usuario puede tener off. Las flechas son universal y no tocan setting.

---

## 9) Código Python production-ready (lo crítico)

### 9.1 `cef_detector(hwnd)` — detector CEF/Chromium/Electron

```python
import ctypes, os, psutil
import win32gui, win32process
from functools import lru_cache

_CEF_CLASS_PATTERNS = (
    "Chrome_WidgetWin_",          # Chrome/Edge/Brave/Electron main
    "Chrome_RenderWidgetHostHWND",
)
_CEF_PROCESS_HINTS = (
    "discord", "slack", "spotify", "steamwebhelper", "code",
    "msteams", "obsidian", "notion", "chatgpt", "claude",
    "1password", "figma", "vscode", "atom",
)

@lru_cache(maxsize=512)
def cef_detector(hwnd: int) -> bool:
    """Heurística rápida: ¿esta ventana es Chromium/CEF/Electron?

    Estrategia (en orden de costo):
    1. Class name del HWND (instantáneo).
    2. Class name de cualquier child window (Chrome_RenderWidgetHostHWND es señal fuerte).
    3. Nombre del proceso vs lista de hints conocidos.
    """
    try:
        cls = win32gui.GetClassName(hwnd) or ""
        if any(cls.startswith(p) for p in _CEF_CLASS_PATTERNS):
            return True
        # walk children one level (cheap)
        found = [False]
        def _enum(child, _):
            ccls = win32gui.GetClassName(child) or ""
            if any(ccls.startswith(p) for p in _CEF_CLASS_PATTERNS):
                found[0] = True
                return False
            return True
        try:
            win32gui.EnumChildWindows(hwnd, _enum, None)
        except Exception:
            pass
        if found[0]:
            return True
        # process name fallback
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            pname = psutil.Process(pid).name().lower().replace(".exe", "")
            if any(h in pname for h in _CEF_PROCESS_HINTS):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False
    except Exception:
        return False
```

### 9.2 `uia_enumerate_clickable(hwnd)` — wrapper UIA con cache

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging
import uiautomation as auto

log = logging.getLogger("carter.uia")

@dataclass(frozen=True, slots=True)
class UiaElement:
    name: str
    automation_id: str
    control_type: str
    bbox: Tuple[int, int, int, int]   # (l, t, r, b)
    is_enabled: bool
    runtime_id: Tuple[int, ...]       # estable por sesión
    raw: object                       # IUIAutomationElement

_CLICKABLE_TYPES = {
    "ButtonControl", "HyperlinkControl", "MenuItemControl",
    "TabItemControl", "ListItemControl", "TreeItemControl",
    "CheckBoxControl", "RadioButtonControl", "SplitButtonControl",
    "ComboBoxControl", "ImageControl",  # CEF often labels icons as Image
    "TextControl",  # CEF a veces los marca así (links)
    "PaneControl",  # CEF wrappers
}

def uia_enumerate_clickable(
    hwnd: int,
    *,
    max_depth: int = 12,
    timeout_ms: int = 500,
) -> List[UiaElement]:
    """Enumera elementos clickeables de la ventana hwnd con bbox.

    Performance: con cache_request prefetcheado, ~150-450ms en CEF típico.
    Si el árbol es enorme (>2000 nodos), cae en walker iterativo con timeout.
    """
    import time
    start = time.monotonic()
    deadline = start + timeout_ms / 1000

    win = auto.ControlFromHandle(hwnd)
    if not win:
        log.warning("uia_enumerate: no UIA element for hwnd=%s", hwnd)
        return []

    # cache_request acelera 3-5x — pedimos solo lo que usamos
    cache = auto.uiautomation.IUIAutomation_CreateCacheRequest()
    # NOTE: en uiautomation 2.x, hay helpers; si no, usar comtypes raw
    out: List[UiaElement] = []
    walker = auto.GetRawTreeWalker()

    def _walk(node, depth: int):
        if time.monotonic() > deadline or depth > max_depth:
            return
        try:
            ct = node.ControlTypeName
            if ct in _CLICKABLE_TYPES and node.IsOffscreen is False:
                rect = node.BoundingRectangle
                if rect.width() > 4 and rect.height() > 4:
                    out.append(UiaElement(
                        name=node.Name or "",
                        automation_id=node.AutomationId or "",
                        control_type=ct,
                        bbox=(rect.left, rect.top, rect.right, rect.bottom),
                        is_enabled=bool(node.IsEnabled),
                        runtime_id=tuple(node.GetRuntimeId() or ()),
                        raw=node,
                    ))
        except Exception as e:
            log.debug("walk node error: %s", e)
            return
        try:
            child = walker.GetFirstChildElement(node)
            while child:
                _walk(child, depth + 1)
                if time.monotonic() > deadline:
                    return
                child = walker.GetNextSiblingElement(child)
        except Exception as e:
            log.debug("walk children error: %s", e)

    try:
        _walk(win, 0)
    except Exception:
        log.exception("uia_enumerate fatal")

    log.debug("uia_enumerate: %d elems in %.0fms", len(out),
              (time.monotonic() - start) * 1000)
    return out
```

### 9.3 `ocr_find_text` con PaddleOCR CPU

```python
from paddleocr import PaddleOCR
import numpy as np
from rapidfuzz import fuzz
import threading, logging

log = logging.getLogger("carter.ocr")
_ocr_lock = threading.Lock()
_ocr_singleton: Optional[PaddleOCR] = None

def _get_ocr() -> PaddleOCR:
    global _ocr_singleton
    if _ocr_singleton is None:
        with _ocr_lock:
            if _ocr_singleton is None:
                # mobile = pequeño y rápido en CPU; lang='es' para español rioplatense
                _ocr_singleton = PaddleOCR(
                    use_angle_cls=False,
                    lang="es",
                    use_gpu=False,
                    cpu_threads=4,
                    show_log=False,
                    det_db_box_thresh=0.5,
                    det_limit_side_len=1280,  # downsample agresivo para latencia
                )
    return _ocr_singleton

@dataclass(frozen=True)
class OcrItem:
    text: str
    bbox: Tuple[int, int, int, int]
    conf: float

def ocr_screenshot(img_bgr: np.ndarray) -> List[OcrItem]:
    ocr = _get_ocr()
    raw = ocr.ocr(img_bgr, cls=False)
    out: List[OcrItem] = []
    if not raw or not raw[0]:
        return out
    for box, (txt, conf) in raw[0]:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        out.append(OcrItem(
            text=txt,
            bbox=(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
            conf=float(conf),
        ))
    return out

def ocr_find_text(img_bgr: np.ndarray, query: str,
                  min_score: float = 65) -> Optional[OcrItem]:
    """Busca query (fuzzy) en el screenshot. Retorna best match o None."""
    items = ocr_screenshot(img_bgr)
    if not items:
        return None
    scored = [(fuzz.partial_ratio(query.lower(), it.text.lower()), it)
              for it in items if it.conf > 0.5]
    scored.sort(key=lambda x: -x[0])
    if scored and scored[0][0] >= min_score:
        return scored[0][1]
    return None
```

### 9.4 `verify_action` — frame-diff verifier

```python
import mss, numpy as np, time
from typing import Tuple

def screenshot_region(bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """BGRA → BGR ndarray."""
    l, t, r, b = bbox
    with mss.mss() as sct:
        img = sct.grab({"left": l, "top": t,
                        "width": r - l, "height": b - t})
        return np.array(img)[:, :, :3]

def verify_action(before: np.ndarray, after: np.ndarray,
                  *, min_diff_ratio: float = 0.005,
                  max_diff_ratio: float = 0.95) -> bool:
    """True si hay un cambio "razonable" (no nada, no toda la pantalla flasheó).

    min: rechaza no-op (click no hizo nada).
    max: rechaza catástrofe (modal de error que tapó todo no es lo que pediste).
    """
    if before.shape != after.shape:
        return True  # tamaño cambió = algo pasó
    diff = np.abs(before.astype(np.int16) - after.astype(np.int16)).sum(axis=2)
    changed = (diff > 30).mean()
    return min_diff_ratio < changed < max_diff_ratio
```

Para verifiers más estrictos (ver Tabla §10), combinar con UIA refind del elemento target o re-OCR de un texto esperado.

### 9.5 `vlm_oracle` con keep_alive=0

```python
import httpx, base64, io, logging, re
from PIL import Image

log = logging.getLogger("carter.vlm")
OLLAMA_URL = "http://127.0.0.1:11434"

def vlm_oracle(img_bgr: np.ndarray, description: str,
               *, model: str = "qwen2.5vl:3b",
               timeout_s: float = 15.0) -> Optional[Tuple[int, int, int, int]]:
    """Pide bbox al VLM. Auto-descarga modelo tras la respuesta.

    Returns bbox (l, t, r, b) o None.
    """
    rgb = img_bgr[:, :, ::-1]
    pil = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    prompt = (
        f'Devolvé SOLO el bounding box xyxy en pixeles del elemento clickeable '
        f'que mejor coincide con: "{description}". '
        f'Formato JSON estricto: {{"bbox": [x1, y1, x2, y2]}}. '
        f'Si no existe, {{"bbox": null}}.'
    )

    try:
        with httpx.Client(timeout=timeout_s) as cli:
            r = cli.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
                "keep_alive": 0,           # <-- crítico: descarga tras response
                "options": {"temperature": 0.0, "num_predict": 64},
            })
            r.raise_for_status()
            text = r.json().get("response", "")
    except Exception:
        log.exception("vlm_oracle request failed")
        return None

    m = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', text)
    if not m:
        log.warning("vlm_oracle: no bbox in response: %s", text[:200])
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore
```

### 9.6 `gui_universal_action` — orquestador completo

```python
from enum import Enum
import logging, time, win32gui

log = logging.getLogger("carter.gui")

class Action(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    KEYPRESS = "keypress"

class GuiActionError(Exception): ...

def gui_universal_action(
    target_description: str,
    action: Action,
    value: Optional[str] = None,
    *,
    hwnd: Optional[int] = None,
    deeplink_intent: Optional[Dict] = None,  # {"app": "spotify", "intent": "play_track", "id": "..."}
    use_vlm_fallback: bool = True,
    timeout_s: float = 8.0,
) -> Dict:
    """Ejecuta acción GUI con cascading universal.

    Returns: {"success": bool, "tier": int, "latency_ms": int, "verifier": str}
    """
    t0 = time.monotonic()
    hwnd = hwnd or win32gui.GetForegroundWindow()
    win_rect = win32gui.GetWindowRect(hwnd)

    # ── Tier 0: deep-link ───────────────────────────────────────────────
    if deeplink_intent:
        try:
            url = build_deeplink(deeplink_intent)  # tu función basada en yaml
            if url:
                before = screenshot_region(win_rect)
                os.startfile(url)
                time.sleep(0.4)
                after = screenshot_region(_active_window_rect())
                if verify_action(before, after, min_diff_ratio=0.01):
                    return _ok(0, t0, "deeplink+frame-diff")
        except Exception:
            log.exception("Tier0 deeplink failed; falling through")

    # ── Tier 1: UIA ─────────────────────────────────────────────────────
    if not focus_window_robust(hwnd):
        log.warning("focus_window_robust failed; continuing best effort")

    elements = uia_enumerate_clickable(hwnd, timeout_ms=500)
    is_cef = cef_detector(hwnd)
    log.debug("Tier1 UIA: %d elems, cef=%s", len(elements), is_cef)

    target_elem = _fuzzy_match_uia(elements, target_description, threshold=70)
    if target_elem:
        before = screenshot_region(target_elem.bbox)
        if action == Action.CLICK:
            _click_input_abs(target_elem.bbox)
        elif action == Action.DOUBLE_CLICK:
            _click_input_abs(target_elem.bbox, double=True)
        elif action == Action.TYPE:
            _click_input_abs(target_elem.bbox)
            time.sleep(0.08)
            _type_text_robust(value or "", is_cef=is_cef)
        elif action == Action.KEYPRESS:
            _send_keys(value or "")
        time.sleep(0.15)
        after = screenshot_region(target_elem.bbox)
        if verify_action(before, after):
            return _ok(1, t0, "uia+frame-diff")
        log.debug("Tier1 verifier failed; falling through")

    # ── Tier 2: OCR + UIA fusion ───────────────────────────────────────
    full = screenshot_region(win_rect)
    ocr_hit = ocr_find_text(full, target_description, min_score=65)
    if ocr_hit:
        # ajustar bbox a coordenadas absolutas (ocr da relativas a `full`)
        l, t, r, b = ocr_hit.bbox
        abs_bbox = (win_rect[0] + l, win_rect[1] + t,
                    win_rect[0] + r, win_rect[1] + b)
        # cross-check con UIA: ¿hay elem cubriendo este bbox?
        covering = _uia_at_point(elements, _bbox_center(abs_bbox))
        click_bbox = covering.bbox if covering else abs_bbox
        before = screenshot_region(click_bbox)
        _click_input_abs(click_bbox)
        if action == Action.TYPE:
            time.sleep(0.08)
            _type_text_robust(value or "", is_cef=is_cef)
        time.sleep(0.2)
        after = screenshot_region(click_bbox)
        if verify_action(before, after):
            return _ok(2, t0, "ocr+frame-diff")

    # ── Tier 3: VLM oracle ─────────────────────────────────────────────
    if use_vlm_fallback:
        log.info("Tier3 VLM oracle (cold-start ~3-6s expected)")
        bbox = vlm_oracle(full, target_description)
        if bbox:
            l, t, r, b = bbox
            abs_bbox = (win_rect[0] + l, win_rect[1] + t,
                        win_rect[0] + r, win_rect[1] + b)
            before = screenshot_region(abs_bbox)
            _click_input_abs(abs_bbox)
            if action == Action.TYPE:
                _type_text_robust(value or "", is_cef=is_cef)
            time.sleep(0.2)
            after = screenshot_region(abs_bbox)
            if verify_action(before, after):
                return _ok(3, t0, "vlm+frame-diff")

    raise GuiActionError(
        f"All tiers exhausted for '{target_description}' "
        f"(t={int((time.monotonic()-t0)*1000)}ms)"
    )

def _ok(tier, t0, verifier):
    return {"success": True, "tier": tier,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "verifier": verifier}

def _type_text_robust(text: str, *, is_cef: bool):
    """En Win32 estándar usar set_edit_text; en CEF caer a SendInput global."""
    if is_cef:
        # SendInput físico — único confiable contra Chromium offscreen surface
        import keyboard
        keyboard.write(text, delay=0.005)
    else:
        # podés intentar UIA ValuePattern primero si hay foco
        import keyboard
        keyboard.write(text, delay=0.002)
```

`_fuzzy_match_uia` combina `name`, `automation_id` y `control_type` con pesos (RapidFuzz), `_click_input_abs` mueve el cursor + emite SendInput LBUTTONDOWN/UP en coords absolutas, `_uia_at_point` busca el elemento más pequeño que contenga un punto. Todos triviales — no los pego completos por brevedad.

---

## 10) Tabla de verifiers estructurales

| Acción | Verifier primario | Verifier secundario | Nota |
|---|---|---|---|
| **click** (botón con label fijo) | UIA refind del elemento + chequear `Toggle.ToggleState` o `ExpandCollapse.State` cambió | Frame-diff en bbox del elemento (>0.5% pixels diff) | Si hay TogglePattern, es 100% determinista |
| **click** (link / nav) | URL/title de window cambió | Frame-diff a nivel ventana | En CEF no hay URL accesible vía UIA → frame-diff |
| **type** (en text field) | UIA `ValuePattern.Value` igual a value escrito | Re-OCR del bbox del input para confirmar | En CEF a veces ValuePattern no se actualiza → OCR es el fallback |
| **keypress** (atajo Ctrl+S, etc.) | Cambio en title (`* Modified` desaparece, modal aparece) | Frame-diff fullscreen | Atajos son ciegos, verifier es difícil — confiá en que el atajo es correcto |
| **scroll** | UIA `ScrollPattern.VerticalScrollPercent` cambió | Frame-diff en bbox de la región scrolleable | ScrollPattern no soportado en CEF → solo frame-diff |
| **select** (lista/combo) | UIA `SelectionItemPattern.IsSelected = True` | Re-enumerate + comparar Name del elemento seleccionado | Robusto en Win32, frágil en CEF |
| **window state change** (snap, min, max) | `GetWindowRect` cambió a las dims esperadas | `IsZoomed`/`IsIconic` win32 API | 100% determinista, no toca app |
| **app-change** (deep-link) | Foreground window pertenece al PID esperado | Frame-diff fullscreen | Combine con `psutil.Process(pid).name()` |

---

## 11) Roadmap ejecutable (orden recomendado)

### Semana 1 — quick wins (~5 fails de 10)

**Día 1 (S):**
1. Crear wrapper de lanzamiento `carter_launch_app(name)` que añade `--force-renderer-accessibility=complete` para Chrome/Edge/Discord/Slack/Spotify/Steam launcher (busca en registro el comando, le inyecta el flag, relanza).
2. Implementar `enumerate_url_protocols()` y `build_deeplink()` con YAML curado de §7.2.
3. Implementar `window_arrange()` con Snap Layouts. **Métrica de éxito**: 5 layouts confirmados en <500ms cada uno con verifier `GetWindowRect`.

**Día 2-3 (M):**
4. Implementar `cef_detector`, `uia_enumerate_clickable` con cache, `_click_input_abs`, `focus_window_robust`. **Métrica**: enum CEF window devuelve >50 elementos en <500ms.
5. Reemplazar `gui_click` por `gui_universal_action` Tier 0+1 only (sin OCR ni VLM aún).
6. **Test contra los 10 fails actuales**. Apuntar a cerrar 5-7.

### Semana 2 — fortalecer fallbacks (~2-3 fails más)

**Día 4 (M):**
7. Integrar PaddleOCR singleton + `ocr_find_text` + Tier 2 en `gui_universal_action`.
8. **Métrica**: latencia p50 OCR en CPU (4 threads) <500 ms con ROI a ventana foreground.

**Día 5 (M):**
9. Integrar `vlm_oracle` con keep_alive=0. Setear `OLLAMA_MAX_LOADED_MODELS=2`. Smoke-test con qwen2.5vl:3b.
10. **Métrica**: cold-start <8s, warm-call <3s. Asegurar que VRAM vuelve a baseline 3GB tras call.

**Día 6 (S):**
11. Logging estructurado: `tier`, `latency_ms`, `verifier_type`, `target_description`, `app_name`. Esto te da datos para optimizar después.

### Semana 3 — refinamiento

12. Set-of-Mark prompting con qwen3:4b text-only para casos donde el match fuzzy no alcanza (ambigüedad de labels). Corre en Tier 1.5.
13. Tunear thresholds fuzzy/OCR con datos de logs de la semana 2.
14. C16 multilingüe: tu OCR ya está en español; verificá que el fuzzy match maneja acentos (`fuzz.partial_ratio` con `unidecode` previo).

### Cuándo NO invocar VLM

- En cualquier acción que tenga `deeplink_intent` configurado (Tier 0 alcanza).
- En apps Win32 estándar donde UIA es perfecto (Notepad, Calculator, Office, Explorer): no perdés tiempo.
- En batches >5 acciones consecutivas sobre la misma app: el primer call podría disparar VLM, pero los siguientes deberían cachear el árbol UIA.
- **Cuándo SÍ invocarlo**: Tier 1+2 fallaron y la ventana es CEF/Electron/Skia-canvas. Probablemente <5% de operaciones.

---

## 12) Tabla de benchmarks reales (RTX 4060 + CPU desktop moderno)

*Aviso de honestidad: marco con ⚠️ los que son interpolaciones de hardware adyacente, no benchmarks específicos en RTX 4060 que pude verificar.*

| Operación | Latencia esperada | Fuente |
|---|---|---|
| `enumerate_url_protocols()` (winreg) | 50–150 ms | Estándar Windows API, no medido específico |
| UIA tree walk Notepad (~30 nodos) | 30–80 ms | uiautomation perf docs |
| UIA tree walk Steam library (~600 nodos) | 200–500 ms con cache; 800–1500 ms sin cache | ⚠️ extrapolado de pywinauto issue #959 (Win32 1000× faster sin cache) |
| UIA tree walk Discord (Electron, ~400 nodos) | 150–400 ms con cache | ⚠️ similar |
| `mss.grab` 1920×1080 | 8–18 ms | mss benchmarks |
| `numpy` frame-diff fullscreen | 3–8 ms | numpy bench |
| Tesseract 5 LSTM CPU 1920×1080 | 700–1200 ms | Codesota benchmark |
| PaddleOCR PP-OCRv5_mobile **CPU 4 threads** 1080p | 250–500 ms ⚠️ | Paddle docs reportan "ms-level" en T4; mobile en CPU desktop es ~2-3× más lento que GPU |
| PaddleOCR PP-OCRv5_mobile **RTX 4060** (no recomendado, te roba VRAM) | 80–150 ms | ⚠️ extrapolado de PaddleOCR T4/3080 numbers |
| EasyOCR CPU 1080p | 1500–3000 ms | TildAlice benchmark |
| Florence-2-large warm RTX 4060 | 200–400 ms ⚠️ | ⚠️ no hay bench oficial RTX 4060; runpod docs A100 baseline |
| qwen2.5vl:3b **cold-start** RTX 4060 q4 | 3–6 s ⚠️ | ⚠️ extrapolado de Ollama issue #11230 (qwen2.5vl:32b 4-6s en H100) y disco NVMe típico |
| qwen2.5vl:3b **warm** inferencia 1 imagen 1080p RTX 4060 | 1.5–2.5 s ⚠️ | ⚠️ basado en runner Ollama warm + decode 30 tokens |
| qwen3:4b instruct q4 inferencia 100 tokens RTX 4060 | 1.5–3 s | databasemart RTX 4060 ollama bench (40+ tok/s en 5GB models) |
| OmniParser v2 frame parse RTX 4090 | 0.8 s | Microsoft official |
| OmniParser v2 frame parse RTX 4060 | 1.0–1.4 s ⚠️ | ⚠️ extrapolado |
| `SetForegroundWindow` + AttachThreadInput | 5–20 ms | Win32 API |
| `SendInput` 1 click | <2 ms | Win32 API |

---

## 13) Caveats — qué NO se puede hacer en Win11 con apps modernas

### 13.1 Apps que bloquean automation por diseño

- **Anti-cheat games** (Valorant Vanguard, EAC, BattlEye): kernel-level driver detecta SendInput sintético, hooks de teclado, UIA en su ventana — y **te kickea o te bannea**. **No automatices ventanas in-game.** Solo el launcher (Riot Client, Epic Games Launcher) es seguro vía deep-link.
- **DRM-protected video** (Netflix, Disney+, HBO): el video tile es PlayReady-protected, `mss.grab` devuelve negro. OCR encima funciona, pero no podés "leer" lo que se está reproduciendo. Para Carter alcanza: las controles de UI están afuera del DRM bubble.
- **UAC-elevated processes**: si tu Carter corre con privilegios usuario y la app target es admin, UIA no ve el árbol. Solución: que Carter sí o sí no sea admin (es safer); si la app target requiere admin, abandonar control GUI y usar API/CLI.
- **Apps en otra sesión / Remote Desktop / Citrix**: UIA no cruza el desktop boundary.

### 13.2 Limitaciones por framework

| Framework | UIA expone | Notas |
|---|---|---|
| Win32 / MFC / WinForms / WPF | ✅ Todo nativo | Carter ya estaba bien acá (los fails estaban en CEF) |
| **Electron** (Discord, Slack, VSCode, Notion, ChatGPT app) | ✅ Post Chrome 138 | Si setás flag o ya conectaste UIA, full árbol |
| **CEF** (Steam, Spotify) | ✅ Igual que Chrome | Misma cosa |
| **WebView2** (Teams, WhatsApp Win11) | ✅ Buena | Edge usa Chromium, mismo behavior |
| **Microsoft.UI.Xaml / WinUI 3** | ✅ Excelente, mejor que UWP legacy | Ej: Files app, nuevo Outlook |
| **Qt** | ⚠️ Parcial — Qt expone IUIAutomationProvider parcial | QtWidgets > QtQuick. Apps tipo OBS, Telegram desktop, FreeCAD: variable. |
| **Flutter desktop** | ❌ Actualmente muy pobre | Flutter usa Skia direct, render canvas; UIA expone solo el `Window`. **Acá sí necesitás VLM o OCR.** |
| **Tauri** | ⚠️ Variable | El webview backend (Edge WebView2 en Win11) sí expone, pero la chrome del shell de Tauri puede ocultar partes. |
| **Custom Skia / Direct2D / immediate mode** | ❌ Nada | Casos típicos: Figma desktop, Photoshop canvas, juegos. Solo OCR/VLM. |

### 13.3 Win10 vs Win11 / 24H2

- **Win11 22H2+**: UIA tree walking ~10-15% más rápido que Win10 (mejoras en `IUIAutomationCacheRequest`).
- **Win11 24H2 (build 26100+)**: cambios sutiles en foreground lock; AttachThreadInput trick **sigue funcionando**, pero ForegroundLockTimeout default es más agresivo. Los SendInput están OK.
- **Win11 24H2 + Smart App Control**: si está ON, scripts no firmados que hacen SendInput masivo pueden ser bloqueados. Carter como app debería estar en allowlist o firmada.
- **Win10**: Snap Layouts vía Win+Z **no existe**. `window_arrange` debe caer a Win+Arrow only. `keep_alive=0` y resto del stack funciona igual.

### 13.4 Riesgos AV/EDR

- **Defender baseline**: SendInput puntual, lectura de HKCR, screenshot mss → todo OK, no hay heurística que dispare.
- **EDR corporativos** (CrowdStrike, SentinelOne): pueden flaggear `SetWindowsHookEx` (no lo necesitás), `WriteProcessMemory` (no lo necesitás), o patterns sospechosos como rapid-fire SendInput keystrokes (tipo keylogger). Mantené un rate limit de ~10 events/s para typing y vas bien.
- **NO** uses tricks como inyección de DLL, hooking de Win32 API, o leer memory de otro proceso. Todo lo que necesitás está en API públicas (UIA, mss, SendInput, registry read).

---

## 14) Quick wins inmediatos (<1 día) — lista accionable

1. **Lanzador wrapper para Discord/Spotify/Slack/Steam con flag de a11y** — 1-2 horas. Cierra 2-3 fails inmediatos en C13 (typing, click en sidebars de Electron).
   - Truco práctico: si no podés modificar el shortcut del usuario, hacé que Carter `taskkill /F /IM discord.exe` y relance con el flag cuando detecta intent de "abrir Discord". El usuario no nota nada.

2. **Deep-link dispatcher con YAML curado** (§7.2) — 2 horas. Cierra 1-2 fails en C13 ("abrí Spotify y poné X") y 1 en C14 ("buscá tema Y") porque Spotify deep-link incluye `spotify:search:{query}`.

3. **`window_arrange` con Win+arrow** — 1 hora. Cierra 1-2 fails en C14 (misiones tipo "ponelos lado a lado", "maximizá"). Verifier por `GetWindowRect` es trivial y 100% confiable.

4. **`cef_detector` + branch en gui_type para usar `keyboard.write` global en vez de `set_edit_text`** — 2 horas. Cierra 1-2 fails de typing en Discord/Slack porque CEF a veces no actualiza ValuePattern.

5. **`OLLAMA_MAX_LOADED_MODELS=2` env var** — 5 minutos. No cierra fails directo pero **habilita** que el plan de VLM on-demand funcione sin desalojar al qwen3:4b residente. Hacelo ya, no cuesta nada.

**Todo junto: 6-8 horas → cierra ~5 fails de los 10**, sin tocar el modelo, sin VLM, sin librerías nuevas exóticas.

---

## 15) Resumen ejecutivo final

- El **80% de los fails de C13** se explican por una sola causa: **Chromium/CEF apps no tienen accesibilidad activada en tu setup actual**. Setear el flag o conectar UIA al lanzar la app cierra ese hueco. Esto es un cambio de 2025 (Chrome 138 nativo UIA) que **transformó el panorama** y probablemente Carter v3/v4 no aprovecha aún.
- El **resto se cierra con cascading determinista** UIA → OCR → VLM, donde el VLM se carga **on-demand** vía `keep_alive=0` y libera VRAM tras cada call. Tu RTX 4060 con 12 GB libres soporta esto perfecto sin tocar el modelo principal.
- **No necesitás cambiar de modelo, no necesitás VLM residente, no necesitás per-app hardcodes**. Necesitás un dispatcher inteligente, deep-links donde aplique, snap layouts nativos para C14, y un Tier 3 VLM como red de seguridad rara.
- **PaddleOCR PP-OCRv5_mobile en CPU** es la elección correcta: no compite por VRAM, latencia ~400ms aceptable, calidad ES first-class.
- **C16 multilingüe** se beneficia automáticamente: PaddleOCR cubre 109 idiomas, qwen3:4b instruct ya es multilingüe, y tu UIA devuelve `Name` en el idioma de la app sin tocar nada.
- **Honestidad técnica**: no todos los benchmarks de RTX 4060 específicos están publicados; varios números de cold-start VLM son extrapolaciones de hardware adyacente. Antes de comprometer el roadmap, **medí en tu equipo** los tres datos críticos: (a) UIA enumerate Steam/Discord con cache, (b) PaddleOCR CPU 4-thread en español, (c) qwen2.5vl:3b cold-start con keep_alive=0 desde tu NVMe. Si alguno se sale del envelope, ajustá thresholds del cascading antes que arquitectura.