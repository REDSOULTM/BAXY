# CARTER OS — Investigación 8/8: Automatización GUI confiable en Windows para un LLM local 4B (Gemma 4 E4B-it Q4_K_M) sin OCR/visión por turno

## TL;DR

- **Adoptar UI Automation (UIA) como capa primaria y reservar OCR/visión sólo como fallback** es la única arquitectura viable bajo vram4: el árbol de accesibilidad es texto barato (sub-segundo si se acota `searchDepth` y se filtran controles invisibles), mientras que cargar `mmproj` para visión consume VRAM que un 4B Q4_K_M en 4–6 GB compartidos no puede ceder por turno. Microsoft UFO² ya valida empíricamente esta jerarquía: UIA es "a semantically rich and high-precision interface for enumerating on-screen controls" y la visión sólo entra para controles custom.
- **El 4B no debe decidir clicks individuales; debe invocar macros deterministas parametrizadas** (`send_whatsapp(contact, text)`, `spotify_play(query)`, `open_app_and_focus(name)`) que internamente hacen focus → buscar elemento UIA por `AutomationId`/`Name`/`ControlType` → invocar pattern (`InvokePattern`, `ValuePattern`, `TogglePattern`) → verificar estado UIA → reintentar. Esto encaja con el latency budget de 4–5 s y es lo único que un modelo de 4B ejecuta de forma confiable: Aisera (Bhushan Jadhav, "SLM Agents: Why Small Language Models are the Future of AI", 18-sept-2025) lo plantea de forma textual: *"SLMs fine-tuned on narrow schemas often emit cleaner, more constrained outputs, reducing brittle post-processing and retries"*.
- **Stack concreto recomendado para CARTER OS**: `uiautomation` (yinkaisheng) v2.0.29 como motor principal por su API delgada sobre `UIAutomationCore.dll` y control fino de `searchDepth`/`SetGlobalSearchTimeout`; `pywinauto` `backend="uia"` sólo para macros legacy ya escritas; **descartar FlaUI-Python** (`flaui-uiautomation-wrapper` está marcado como Inactive en Snyk y arrastra PythonNet/.NET) y descartar **WinAppDriver** (proyecto en estado reducido de mantenimiento). Verificación post-acción **siempre** vía UIA (`GetTogglePattern().ToggleState`, `IsEnabled`, `Name` cambiado), **nunca** vía re-OCR.

## Hallazgos clave

### Por qué UIA gana a OCR/coordenadas en vram4

1. **Costo cognitivo**: el LLM recibe una lista plana de elementos `[id, role, name, automation_id, enabled, bbox]` en texto. Un 4B Q4_K_M razona mejor sobre 20–80 líneas de texto estructurado que sobre un screenshot que requeriría inyectar `mmproj` (típicamente 400–800 MB extra de VRAM para un projector multimodal de Gemma) que no caben en el slice de 4–6 GB.
2. **Costo de cómputo**: enumerar la vista de control de UIA con profundidad acotada (`searchDepth=2..4`) cuesta del orden de 50–300 ms en apps normales; OCR de pantalla completa con Tesseract ronda 1–3 s por turno y requiere captura+preprocesado. Para CARTER OS con presupuesto 4–5 s end-to-end, OCR consume ya la mitad del budget.
3. **Robustez**: `AutomationId` es estable entre versiones de la app, las coordenadas no. Microsoft Research UFO² (arXiv 2504.14603, abr-2025) confirma: *"When available, UIA offers a semantically rich and high-precision interface for enumerating on-screen controls"*.
4. **Limitación honesta**: UIA falla con DirectUI/CustomControl (algunas apps Electron mal etiquetadas, juegos, instaladores). Ahí entra el fallback OCR/visión lazy que ya existe en CARTER OS.

### El verdadero patrón: macros deterministas, planner ligero

El error costoso es exponer `click(x,y)` y `type(text)` como tools de bajo nivel al 4B. En su lugar, exponer **verbos de dominio** que internamente son código Python determinista:

```python
@tool
def send_whatsapp(contact: str, text: str) -> dict: ...
@tool
def spotify_play(query: str) -> dict: ...
@tool
def netflix_search_and_play(title: str) -> dict: ...
@tool
def app_focus(app_name: str) -> dict: ...
```

Microsoft UFO² lo formaliza con su "Puppeteer interface" y reporta verbatim: *"Speculative multi-action execution consolidates multiple steps into a single LLM call, lowering inference cost by up to 51.5% without compromising reliability"* (arXiv 2504.14603, Zhang et al., Microsoft, abr-2025). El docs de UFO² ilustra el ahorro: *"Task: 'Fill form fields A1–A10 with sequential numbers' — Traditional CUA: 10 LLM calls (1 per field) → ~30 seconds. UFO² Speculative: 1 LLM call predicts all 10 actions → ~8 seconds"* (microsoft.github.io/UFO/ufo2/overview/). Para un 4B local con latencia 4–5 s por turno, esta consolidación es la diferencia entre una tarea de 3 s y una de 30 s.

### Métricas relevantes de la literatura 2025

| Sistema | Modelo | Benchmark | Resultado | Modalidad |
|---|---|---|---|---|
| UFO² (Microsoft, abr-2025) | GPT-4o + UIA híbrido | WindowsAgentArena | 27,9% SR vs 20,8% de OpenAI Operator (+7,1 pp absoluto); −51,5% inference cost | UIA + OmniParser-v2 fallback |
| UFO² con o1 | o1 + UIA híbrido | OSWorld-W | 32,7% SR vs 14,3% Operator | UIA + visión |
| Fara-7B (Microsoft Research blog, nov-2025) | 7B nativo | WebVoyager | 73,5% (vs SoM GPT-4o 65,1% y OpenAI computer-use 70,9%) | Visión pura (no-UIA) |
| UI-TARS-1.5-7B | 7B nativo | WebVoyager | 66,4% (Tabla 9 paper Fara-7B); ~41 pasos por tarea vs ~16 de Fara-7B | Visión pura |
| Agent S2 (Simular, abr-2025) | Mixture-of-Grounding | OSWorld 50-step | 34,5% (supera al CUA Operator previo de 32,6%) | Visión pura |
| OSCAR (2024-2025) | LMM + A11y tree Windows API | OSWorld | Multi-app | A11y + screenshots |

**Lectura para CARTER OS**: los modelos *nativos* tipo Fara-7B/UI-TARS necesitan visión y son 7B (no caben en vram4 junto con voice + Gemma 4B). En cambio el patrón **UFO²-style con UIA como primary path** es replicable con un 4B porque el LLM ve texto, no píxeles.

## Detalle por punto

---

### Punto 1 (ALTA PRIORIDAD) — UIA como camino primario vs OCR/coordenadas

**Diagnóstico.** Para apps nativas (Win32, WinForms, WPF, UWP/WinUI), el árbol UIA expone `ControlType`, `Name`, `AutomationId`, `ClassName`, `BoundingRectangle`, `IsEnabled`, `IsOffscreen` y un conjunto de **patterns** (`InvokePattern`, `ValuePattern`, `TogglePattern`, `SelectionItemPattern`, `ExpandCollapsePattern`, `ScrollPattern`, `RangeValuePattern`, `WindowPattern`). Esto es **información estructurada que un 4B puede consumir como JSON** y elegir por nombre, sin necesidad de visión. La librería oficial de referencia en Python es `uiautomation` de yinkaisheng (wrapper sobre `UIAutomationCore.dll` vía `comtypes`); alternativa con DSL más alto nivel es `pywinauto` con `backend="uia"`.

**Cómo exponerlo al 4B (patrón "snapshot textual de UI").** Antes de cada turno donde se necesite interacción GUI, el ejecutor llama a un *snapshot* que devuelve sólo los elementos **interactuables** (filtrando `ControlType in {Button, Edit, ComboBox, ListItem, MenuItem, TabItem, Hyperlink, CheckBox, RadioButton}` y `IsEnabled=True`, `IsOffscreen=False`). Se le da al LLM como una lista corta enumerada:

```
[0] Button "Enviar"   automation_id=send_btn      enabled=true
[1] Edit   "Mensaje"  automation_id=msg_input     enabled=true
[2] Button "Adjuntar" automation_id=attach        enabled=true
[3] ListItem "Pedro Pérez" enabled=true
...
```

El 4B sólo responde `{"action":"invoke","id":0}` o `{"action":"set_value","id":1,"text":"hola"}`. Esto reduce el espacio de decisión de millones de coordenadas a ~20–50 IDs.

**Costo/latencia de enumerar el árbol.** Crítico para vram4:

- `Control.descendants()` sin acotar puede tardar **>1 minuto** en apps grandes como iTunes/Chrome — issue documentado de pywinauto (#359, #1018: *"`print_control_identifiers()` takes more than a minute"*).
- La diferencia win32 vs UIA en pywinauto es ~5–10× (issue #256: 16 s en win32 vs 1 min 35 s en uia para el mismo script de Calculator). Las release notes oficiales de pywinauto 0.6.0 son explícitas: *"Despite code coverage is ~95% consider it as beta quality. Performance is slower than for 'win32'"*.
- **Mitigación obligatoria**: usar `searchDepth=1..3`, prefiltrar por `ControlType`, cachear `RuntimeId`, y usar `WalkControl(root, maxDepth=2)` de `uiautomation` (yinkaisheng) que recorre una sola vez. En `uiautomation` los defaults son `SEARCH_INTERVAL = 0.5 s`, `TIME_OUT_SECOND = 10` y `searchDepth = 0xFFFFFFFF` (efectivamente ilimitado) — los tres deben bajarse explícitamente en el código de CARTER OS (p. ej. 0.1 s / 3 s / `searchDepth=4`).

**Tabla comparativa.**

| Enfoque | Confiabilidad | Latencia/turno | VRAM | Robustez a cambios UI | Complejidad |
|---|---|---|---|---|---|
| UIA por `AutomationId` | Muy alta | 50–300 ms | 0 | Muy alta | Media |
| UIA por `Name`/`ControlType` | Alta | 80–400 ms | 0 | Alta (i18n sensible) | Baja |
| OCR `click_text` (Tesseract) | Media | 800–2500 ms | 0 (CPU) | Baja (depende de fuente/escala) | Baja |
| `locate_image` template | Media-baja | 200–600 ms | 0 | Muy baja (rompe en updates) | Baja |
| Coordenadas absolutas | Muy baja | 10 ms | 0 | Nula | Trivial |
| Visión multimodal (mmproj) | Alta | 2–6 s + carga | +400–900 MB | Alta | Alta |

**Veredicto vram4: VIABLE — UIA primario es el único camino sostenible.** La lazy-visión queda exclusivamente para apps no-UIA (juegos, instaladores raros, contenido renderizado en canvas).

**Código de referencia — snapshot UIA serializable para el 4B:**

```python
# carter_os/gui/uia_snapshot.py
import uiautomation as auto

auto.uiautomation.SetGlobalSearchTimeout(3)         # bajar de 10 a 3 s
INTERACTABLE = {
    auto.ControlType.ButtonControl, auto.ControlType.EditControl,
    auto.ControlType.ComboBoxControl, auto.ControlType.ListItemControl,
    auto.ControlType.MenuItemControl, auto.ControlType.TabItemControl,
    auto.ControlType.HyperlinkControl, auto.ControlType.CheckBoxControl,
    auto.ControlType.RadioButtonControl, auto.ControlType.TreeItemControl,
}

def snapshot_window(window: auto.Control, max_depth: int = 4, limit: int = 60):
    """Devuelve lista de dicts livianos para inyectar como texto al LLM."""
    out = []
    for ctrl, depth in auto.WalkControl(window, includeTop=False, maxDepth=max_depth):
        if ctrl.ControlType not in INTERACTABLE:
            continue
        try:
            if ctrl.IsOffscreen or not ctrl.IsEnabled:
                continue
        except Exception:
            continue
        out.append({
            "idx": len(out),
            "role": ctrl.ControlTypeName,         # "Button", "Edit"...
            "name": (ctrl.Name or "")[:60],
            "auto_id": ctrl.AutomationId or "",
            "class": ctrl.ClassName or "",
            "bbox": [ctrl.BoundingRectangle.left, ctrl.BoundingRectangle.top,
                     ctrl.BoundingRectangle.right, ctrl.BoundingRectangle.bottom],
            "_ref": ctrl,                         # NO se serializa al LLM
        })
        if len(out) >= limit:
            break
    return out

def to_llm_text(snap):
    """Versión texto compacta — ~30 tokens por elemento."""
    lines = []
    for e in snap:
        lines.append(f"[{e['idx']}] {e['role']} \"{e['name']}\" id={e['auto_id']}")
    return "\n".join(lines)
```

---

### Punto 4 (ALTA PRIORIDAD) — LLM como PLANNER vs macros deterministas

**Diagnóstico.** Un 4B Q4_K_M no es confiable eligiendo el click "correcto" turno a turno en una secuencia larga: cualquier benchmark 2025 (OSWorld, WindowsAgentArena) muestra que incluso GPT-4o queda por debajo de 40% en tareas de 10+ pasos. Sin embargo, el 4B sí es confiable **eligiendo qué macro invocar** y rellenando sus argumentos — esto es esencialmente *function-calling*, y Aisera (Bhushan Jadhav, "SLM Agents: Why Small Language Models are the Future of AI", 18-sept-2025, aisera.com/blog/small-language-model-agents) lo resume textualmente: *"SLMs fine-tuned on narrow schemas often emit cleaner, more constrained outputs, reducing brittle post-processing and retries"*.

**Arquitectura recomendada para CARTER OS.** Tres capas:

1. **Capa LLM (planner ligero)**: el 4B sólo decide *intent + macro + args*. Salida típica:
   ```json
   {"tool": "send_whatsapp", "args": {"contact": "Carla", "text": "voy en 10"}}
   ```
2. **Capa de macros deterministas (executor)**: código Python puro que implementa el procedimiento robusto. Incluye focus, búsqueda UIA, fallback OCR, retries, verificación.
3. **Capa verifier**: tras cada macro, comprobación UIA del estado esperado (mensaje nuevo en el chat, app en foreground, valor seteado).

**¿Cuánto encapsular en código vs dejar al LLM?** Regla operativa:

- Si una tarea se puede expresar en ≤ 8 pasos UIA con árboles de decisión finitos → **encapsular** (e.g. `send_whatsapp`, `spotify_play`, `open_app`, `set_brightness`).
- Si requiere navegación abierta con texto libre → **planner LLM ciclando sobre snapshots UIA** con un loop ReAct corto (máx 5 iteraciones, presupuesto 25 s).
- Si requiere lectura visual (imagen embebida, gráfico, contenido en canvas) → **promover a vision lazy** sólo para ese turno.

**Tabla — Planner vs Executor para un 4B en vram4.**

| Estrategia | Confiabilidad | Latencia | VRAM | Robustez a cambios UI | Complejidad |
|---|---|---|---|---|---|
| 4B decide cada click sobre coordenadas | 5–15% | Alta (5–10 turnos × 4 s) | mmproj on | Muy baja | Baja en código, alta en prompts |
| 4B decide cada click sobre snapshot UIA | 30–55% | 3–6 turnos × 4 s | 0 | Media | Media |
| **4B invoca macro determinista** | **85–98%** (tarea cubierta) | **1 turno + ~1 s exec** | **0** | **Alta** | **Alta en código, baja en prompts** |
| 4B híbrido: macro + fallback planner | 90–99% | 1–3 turnos × 4 s | 0 (vision lazy) | Muy alta | Alta |

**Veredicto vram4: VIABLE — el patrón macro determinista es OBLIGATORIO con 4B.**

**Código de referencia — macro `send_whatsapp` con UIA + retries + verificación:**

```python
# carter_os/macros/whatsapp.py
import time
import uiautomation as auto
from carter_os.gui.win_focus import focus_and_maximize     # ya existe en stack
from carter_os.gui.uia_snapshot import snapshot_window

WHATSAPP_CLASS = "Chrome_WidgetWin_1"  # WhatsApp Desktop (Electron)
WHATSAPP_TITLE_RE = r"^WhatsApp"

def _find_whatsapp_window(timeout=6):
    end = time.time() + timeout
    while time.time() < end:
        win = auto.WindowControl(searchDepth=1, RegexName=WHATSAPP_TITLE_RE)
        if win.Exists(0.5, 0.2):
            return win
        time.sleep(0.3)
    raise RuntimeError("WhatsApp Desktop no encontrado")

def send_whatsapp(contact: str, text: str, max_retries: int = 2) -> dict:
    """Macro determinista: focus -> abrir buscador -> seleccionar contacto -> escribir -> enviar -> verificar."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            win = _find_whatsapp_window()
            focus_and_maximize(win.NativeWindowHandle)     # win_focus.py existente

            # 1. Caja de búsqueda (AutomationId estable en WA Desktop reciente)
            search = win.EditControl(searchDepth=10, Name="Cuadro de texto de búsqueda")
            if not search.Exists(1, 0.2):
                # Fallback: Ctrl+F abre búsqueda
                auto.SendKeys("{Ctrl}f", waitTime=0.05)
                search = win.EditControl(searchDepth=10)
            search.GetValuePattern().SetValue(contact)
            time.sleep(0.4)

            # 2. Seleccionar primer resultado de la lista
            list_ctrl = win.ListControl(searchDepth=10)
            list_ctrl.Exists(2, 0.2)
            first = list_ctrl.ListItemControl(foundIndex=1)
            first.Click(simulateMove=False)
            time.sleep(0.3)

            # 3. Caja de mensaje
            msg = win.EditControl(searchDepth=10, Name="Escribe un mensaje")
            if not msg.Exists(2, 0.2):
                msg = win.EditControl(foundIndex=-1)       # último Edit (msg compose)
            msg.SendKeys(text, waitTime=0.005)
            auto.SendKeys("{Enter}", waitTime=0.05)

            # 4. VERIFICACIÓN UIA: el último ListItem del panel de conversación
            #    debe contener `text`. NO usamos OCR aquí.
            time.sleep(0.4)
            conv = win.ListControl(searchDepth=12, AutomationId="conv-panel")  \
                   if win.ListControl(AutomationId="conv-panel").Exists(0.5,0.1) \
                   else win.ListControl(foundIndex=-1)
            last_items = list(auto.WalkControl(conv, includeTop=False, maxDepth=3))
            ok = any(text[:20] in (c.Name or "") for c, _ in last_items[-10:])
            if ok:
                return {"status": "ok", "verified": True, "attempt": attempt}
            last_err = "Mensaje enviado pero no verificado en panel"
        except Exception as e:
            last_err = repr(e)
            time.sleep(0.6 * (attempt + 1))
    return {"status": "error", "error": last_err}
```

Observaciones clave de este patrón:
- **Re-localización antes de cada click** (no se reutilizan `Control` cacheados a través de retries).
- **Fallback por shortcut de teclado** cuando UIA no encuentra el elemento (Ctrl+F).
- **Verificación textual sobre UIA** (`Name` del último item de la lista de conversación) en vez de OCR.
- **Reintentos con backoff** controlado.

---

### Punto 2 — Política para decidir cuándo usar visión

**Diagnóstico.** Visión (`mmproj` de Gemma) compite con el modelo base por VRAM. En vram4 (4–6 GB compartidos), cargar el projector multimodal puede empujar al OOM si el modelo principal ya está cargado en GPU. Por tanto: **no se carga mmproj salvo política explícita**.

**Política propuesta (árbol de decisión en el Router):**

```
¿La tarea requiere leer texto/imagen NO expuesto en UIA?
  ├─ NO  → UIA-only path (90% de tareas)
  └─ SÍ  → ¿hay alternativa textual (clipboard, API nativa, archivo)?
            ├─ SÍ → usar esa
            └─ NO → ¿el contenido es estable >10 s y vale la latencia?
                     ├─ SÍ → cargar mmproj LAZY, screenshot, descargar mmproj
                     └─ NO → fallback OCR (Tesseract) sobre región acotada
```

**Heurísticas concretas para CARTER OS:**

- **UIA cubre**: WhatsApp Desktop, Spotify Desktop, Edge/Chrome (con `--force-renderer-accessibility`), Outlook, File Explorer, Notepad, Office, Settings, Calculator, Teams, Discord (parcial).
- **Requiere visión o OCR**: Netflix UWP (los thumbnails de películas no exponen texto en UIA), juegos, instaladores con DirectUI, captchas, gráficos.
- **Apps mixtas (UIA + visión puntual)**: Spotify para identificar carátula de álbum; Netflix para confirmar que un título empezó a reproducirse.

**Tabla.**

| Caso | Camino recomendado | VRAM | Latencia |
|---|---|---|---|
| Click en botón nombrado | UIA `InvokePattern` | 0 | <200 ms |
| Leer un valor de input | UIA `ValuePattern.Value` | 0 | <100 ms |
| Confirmar app en foreground | `GetForegroundWindow` + UIA `Name` | 0 | <50 ms |
| Texto en canvas/imagen | OCR región acotada | 0 | 0,8–2 s |
| Identificar contenido visual | mmproj lazy | +400–900 MB | 3–6 s |

**Veredicto vram4: VIABLE — gating por política, mmproj solo on-demand.**

---

### Punto 3 — Robustez ante cambios de UI

**Diagnóstico.** Las UIs cambian: AutomationIds renombrados, textos i18n, layout reordenado, Electron apps cuyo DOM se reestructura. Estrategias por orden de preferencia:

1. **Selector compuesto con fallbacks ordenados** (similar a Playwright `getByRole`/`getByLabel`):
   ```python
   def find_send_button(win):
       candidates = [
           lambda: win.ButtonControl(AutomationId="send_btn"),
           lambda: win.ButtonControl(Name="Enviar"),
           lambda: win.ButtonControl(Name="Send"),
           lambda: win.ButtonControl(ClassName="SendButton"),
       ]
       for c in candidates:
           ctrl = c()
           if ctrl.Exists(0.5, 0.2):
               return ctrl
       raise LookupError("send button no encontrado")
   ```

2. **Re-localización antes de cada acción** (no cachear `Control` entre pasos): el `Control` de `uiautomation` revalida automáticamente vía `Control.Refind()` cuando el IUIAutomationElement subyacente caduca.

3. **Retries con backoff** (ya documentados en `pywinauto.timings.wait_until_passes` y replicables en `uiautomation`): `(0,2 s, 0,5 s, 1 s, 2 s)`.

4. **Wait explícito en lugar de `sleep`**: `Control.Exists(timeout, searchInterval)` o esperar a un cambio de estado (`wait_until(lambda: btn.IsEnabled)`).

5. **Aislar selectores en un módulo `selectors.py` por app** — cuando una app rompa el AutomationId, se cambia en un solo lugar.

6. **Telemetría de fallos**: registrar cada `ElementNotFoundError` con `app_name`, `version`, `selector_intentado` para detectar drift y rotar selectores.

7. **Filtro semántico** (patrón UFO²): si el LLM tiene un plan de paso ("haz click en Enviar"), se filtra el snapshot UIA por similitud de embedding antes de mostrárselo. El `config_dev.yaml` oficial de UFO² documenta los valores: `CONTROL_FILTER_TOP_K_PLAN=2`, `CONTROL_FILTER_TOP_K_SEMANTIC=15`, `CONTROL_FILTER_TOP_K_ICON=15`, modelo de embeddings `all-MiniLM-L6-v2` (CPU, ~80 MB) y modelo de iconos `clip-ViT-B-32`. Para CARTER OS, basta con el filtro semántico CPU.

**Tabla por app.**

| App | Selector primario | Selector fallback | Verificación |
|---|---|---|---|
| WhatsApp Desktop | `EditControl(Name="Escribe un mensaje")` | último `EditControl` del árbol | último `ListItem` contiene texto |
| Spotify | `EditControl(AutomationId="search-input")` | Ctrl+L luego `EditControl` con foco | `Name` de track actual cambia |
| Edge/Chrome | `EditControl(Name="Barra de direcciones")` | `Ctrl+L` + tipear | URL del tab vía CDP `Page.url` |
| Netflix UWP | listado de tiles vía `ListItemControl` | OCR región del título seleccionado | tile seleccionado tiene foco |
| Outlook | `Name="Mensaje nuevo"` | Ctrl+N | ventana de redacción visible |

**Veredicto vram4: VIABLE.**

---

### Punto 5 — Frameworks/patrones 2025-2026 viables

**Recomendación CARTER OS:**

| Librería | Estado 2025-2026 | Recomendación CARTER OS | Razón |
|---|---|---|---|
| `uiautomation` (yinkaisheng) v2.0.29 | Mantenida, wheels en PyPI, API directa sobre `UIAutomationCore.dll` | **PRIMARIO** | API delgada, `WalkControl(maxDepth)`, `SetGlobalSearchTimeout`, sin dependencias .NET |
| `pywinauto` 0.6.8 (BSD) | Mantenido (vasily-v-ryabov), backend `uia` | **SECUNDARIO** para macros legacy | API más alta, pero pywinauto 0.6.0 release notes advierten verbatim: *"Performance is slower than for 'win32'"* |
| `flaui-uiautomation-wrapper` (Python sobre FlaUI/.NET) | **Inactive** según Snyk (sin releases >12 meses) | **NO ADOPTAR** | Arrastra PythonNet + .NET; el wrapper Python no tiene paridad estable |
| `FlaUI` (C#/.NET) | Activo en .NET | **NO ADOPTAR** | Requiere bridge .NET; coste de empaquetado vs valor cero para Python |
| `WinAppDriver` (Microsoft) | Estado de mantenimiento reducido | **NO ADOPTAR** | Stack Selenium/Appium pesado; no aporta sobre UIA directa |
| `PyAutoGUI` | Activo | **Sólo para `keypress`/`mouse_move` global** | Sin UIA; pixel-based |
| `pyUIauto` 0.1.12 (jun-2025) | Cross-platform sobre pywinauto/atomac | **No primario** (joven, GPL-3.0) | License GPL es incompatible si CARTER OS quiere permanecer en licencia permisiva |
| **Patrones UFO²/OSCAR** | Estado del arte 2025 | **ADOPTAR el patrón, no el código** | Heavy LLM (GPT-4o); pero la arquitectura HostAgent→AppAgent→Puppeteer es directamente trasladable a Planner→Router→Executor de CARTER OS |
| Patrón Fara-7B (visión pura) | Modelo 7B, on-device | **NO ADOPTAR** | 7B Q4 ~5 GB + projector visual; excede vram4. Útil sólo como referencia de techo de rendimiento si en el futuro se sube a vram8 |

**Detalle clave de UFO² aplicable a CARTER OS:** del paper arXiv 2504.14603, Tabla 5 (Average Completion Steps): con GPT-4o el modo GUI-only requiere 13,8 pasos vs 12,9 con GUI+API (−6,5%); con o1, GUI-only requiere 16,0 pasos vs 6,6 con GUI+API (−58,5%). La lección para CARTER OS es: **cada vez que se pueda reemplazar una secuencia UIA por una API nativa (xlwings, win32com, python-pptx, MediaPlayer COM, Web APIs), hacerlo**. La fusión hybrid UIA+visión de UFO² descarta 27,9% (WAA) y 56,7% (OSWorld-W) de las detecciones de OmniParser-v2 por overlap con UIA usando `IoU > 10%`: confirma que **UIA cubre la mayoría del trabajo** y la visión sólo aporta en el complemento.

**Adopción concreta sin dependencias pesadas:**

```bash
pip install uiautomation==2.0.29 comtypes pywin32
# opcional, para fallback semántico:
pip install sentence-transformers   # all-MiniLM-L6-v2 corre en CPU
```

---

### Punto 6 — Verificación post-acción vía UIA

**Diagnóstico.** Re-OCR post-click es caro (0,8–2 s) y poco confiable (Tesseract falla con fuentes pequeñas, anti-aliasing). UIA expone **patterns con estado consultable** que cuestan <50 ms.

**Patrones UIA para verificación:**

| Acción esperada | Pattern / propiedad a consultar | Confirma |
|---|---|---|
| Click en toggle/checkbox | `GetTogglePattern().ToggleState == ToggleState_On` | Estado activado |
| Selección en lista | `GetSelectionItemPattern().IsSelected` | Item seleccionado |
| Set value en input | `GetValuePattern().Value == expected` | Texto efectivamente seteado |
| Click en botón modal | `WindowControl(Name=expected_dialog).Exists()` | Diálogo apareció |
| Expand de menú | `GetExpandCollapsePattern().ExpandCollapseState` | Estado expandido |
| Slider/Volumen | `GetRangeValuePattern().Value` | Valor numérico |
| Window/foco | `GetForegroundWindow()` + comparar handle | App correcta al frente |
| Cambio de tab | `GetSelectionItemPattern().IsSelected` sobre el `TabItem` | Tab activa |
| Mensaje enviado en chat | `Name` del último `ListItem` del panel | Contenido textual aparece |
| Invocación con feedback dinámico | suscribirse a `InvokePattern.InvokedEvent` o `AutomationElement.LayoutInvalidatedEvent` | Evento UIA disparado |

**Patrón canónico verifier:**

```python
# carter_os/verify/uia_verify.py
import uiautomation as auto

def verify_toggle_on(ctrl: auto.Control) -> bool:
    try:
        return ctrl.GetTogglePattern().ToggleState == auto.ToggleState.On
    except Exception:
        return False

def verify_value(ctrl: auto.Control, expected: str, contains: bool = True) -> bool:
    try:
        v = ctrl.GetValuePattern().Value
        return (expected in v) if contains else (v == expected)
    except Exception:
        return False

def verify_window_active(name_regex: str) -> bool:
    fg = auto.GetForegroundControl()
    import re
    return bool(re.search(name_regex, fg.Name or ""))

def verify_listitem_text_appears(list_ctrl, text: str, last_n: int = 8) -> bool:
    items = list(auto.WalkControl(list_ctrl, includeTop=False, maxDepth=3))[-last_n:]
    return any(text[:24] in (c.Name or "") for c, _ in items)
```

**Tabla comparativa verificación.**

| Método | Latencia | Confiabilidad | VRAM | Notas |
|---|---|---|---|---|
| UIA pattern state | 10–60 ms | Muy alta | 0 | Sólo si el pattern está implementado |
| UIA `Name` re-lectura | 20–100 ms | Alta | 0 | Sensible a i18n |
| OCR re-screenshot | 800–2500 ms | Media | 0 (CPU) | Lento y frágil |
| Visión mmproj re-screenshot | 2–6 s | Alta | +400–900 MB | Desperdicio en este caso |
| Hash de pixels en bbox conocida | 30–80 ms | Baja-media | 0 | Útil sólo como tripwire |

**Veredicto vram4: VIABLE — verificación por UIA pattern state como default, OCR sólo como último recurso.**

## Recomendaciones (staged)

**Fase 1 — Núcleo UIA (próximas 2 semanas)**

1. Añadir `uiautomation==2.0.29` al stack. Crear `carter_os/gui/uia.py` con tres funciones públicas: `snapshot_window`, `find_by_role_and_name`, `invoke_with_verify`.
2. Reemplazar las 3–5 macros más usadas (WhatsApp, Spotify, abrir-app, focus, set-volume) por implementaciones UIA-primary. Mantener temporalmente el `gui tool` actual como fallback.
3. Configurar `SetGlobalSearchTimeout(3)` y `SEARCH_INTERVAL≈0.1 s` globalmente al import.
4. Instrumentar telemetría: cada selector lleva `app_name`, `app_version`, `selector_id`, `latency_ms`, `result`. Esto detecta drift de UI antes que falle el usuario.

**Fase 2 — Planner-como-Router de macros (semanas 3–4)**

5. Refactorizar el prompt del 4B para que **sólo emita tool-calls a macros**, nunca `click(x,y)`. El catálogo de macros se inyecta con descripciones cortas (≤200 tokens por macro) y ejemplos few-shot.
6. Añadir el verifier UIA como paso obligatorio en LangGraph (nodo `verify_after_macro`). Si falla, reintentar la macro hasta 2 veces; si sigue fallando, escalar a planner LLM ciclando sobre snapshot UIA (loop máx 5 turnos).
7. Implementar filtro semántico opcional con `all-MiniLM-L6-v2` (CPU, modelo de UFO² documentado en `config_dev.yaml`) cuando el snapshot UIA supere 40 elementos: reducir a top-15 por similitud con el "subgoal" del paso, replicando exactamente `CONTROL_FILTER_TOP_K_SEMANTIC=15`.

**Fase 3 — Política visión-lazy y resiliencia (semanas 5–6)**

8. Implementar la gate `needs_vision(intent)` en el Router. Por defecto False. Listar explícitamente intents que la activan (e.g. "describe lo que ves", "qué película está en el carrusel de Netflix").
9. Marcar mmproj como **descargable** entre turnos (release VRAM tras usar). Validar que el reload no exceda 2 s.
10. Añadir suscripción a `AutomationEventHandler` para verificación basada en eventos (`InvokedEvent`, `WindowOpenedEvent`) — más reactivo que polling.

**Fase 4 — Endurecimiento (semanas 7+)**

11. Suite de regresión: 50 tareas reales × top-10 apps × ejecución nightly. Métrica: SR ≥ 92% para macros, p95 latency ≤ 5 s.
12. Banco de selectores versionado por app/versión, con auto-detección de versión vía `GetFileVersionInfo` del .exe.
13. Evaluar el fallback de visión en una lista cerrada de apps no-UIA-friendly (Netflix UWP, instaladores). Si su uso supera el 5% del total, revisar si vale subir a vram8.

**Benchmarks que cambiarían estas recomendaciones:**

- Si Gemma 4 publica un projector visual `mmproj` < 200 MB que cargue en < 800 ms → ampliar uso de visión a más casos.
- Si UIA tree enumeration en CARTER OS sube a > 800 ms p95 → introducir caché de árbol con invalidación por `StructureChangedEvent`.
- Si verifier falla > 10% → introducir un small classifier dedicado para "did the action succeed?" (modelo de 80–300 MB que reciba diff UIA pre/post).
- Si se migra a vram8 → considerar Fara-7B (Microsoft Foundry/HuggingFace, nov-2025) como segundo cerebro para tareas web puramente visuales, dejando Gemma 4B para todo lo UIA/intent.

## Caveats

- **El proyecto `flaui-uiautomation-wrapper` figura como Inactive en Snyk**: no asumir mantenimiento. Si se necesita FlaUI, hay que ir a la versión .NET o aceptar el riesgo.
- **UIA en Chrome/Edge**: requiere `--force-renderer-accessibility` o el árbol viene incompleto. Para web mejor usar el `browser_real` (CDP/Playwright) ya existente, que es mucho más eficiente.
- **Apps Electron mal etiquetadas** (e.g. algunas versiones de WhatsApp Desktop) exponen UIA pobre. Las macros deben tener **selectores múltiples y verificación por `Name` parcial** porque los `AutomationId` cambian entre releases.
- **i18n**: la macro `send_whatsapp` mostrada usa `Name="Escribe un mensaje"` (es-ES/es-CL). Para robustez global, mantener un mapa `selector_by_locale` o usar `AutomationId` cuando exista.
- **Las cifras de UFO²** (51,5% reducción de LLM calls; +7,1 pp absoluto vs Operator en WindowsAgentArena; 9,86% de casos previamente irrecuperables convertidos en completaciones; 27,9%/56,7% de detecciones de OmniParser-v2 descartadas por overlap UIA con `IoU>10%`) provienen del paper de Microsoft Research como arXiv preprint v1 (abril 2025), todavía no peer-reviewed. Tomarlas como orden de magnitud, no como garantía exacta.
- **Fara-7B (Microsoft Research blog, nov-2025) y UI-TARS-1.5-7B** alcanzan 73,5% y 66,4% en WebVoyager respectivamente, pero ambos son **7B con visión pura** — fuera del presupuesto vram4. Sirven como referencia del techo, no como sustitutos de Gemma 4B en este stack.
- **`uiautomation` (yinkaisheng) requiere ejecutar Python como administrador** para enumerar controles de algunas apps elevadas; documentarlo claramente en el setup de CARTER OS.
- **CoInitialize en threads**: si CARTER OS llama UIA desde threads distintos al main (LangGraph nodos asíncronos), recordar que desde pywinauto 0.6.5 el modelo es MTA por defecto, pero `uiautomation` puede requerir `pythoncom.CoInitialize()` explícito en cada thread nuevo.
- **Verificación por UIA no captura todos los efectos**: si la app sólo cambia píxeles (e.g. emoji que aparece en un canvas), la verificación UIA dará falso positivo. Para esos casos, fallback OCR sobre bbox conocido, no visión mmproj.