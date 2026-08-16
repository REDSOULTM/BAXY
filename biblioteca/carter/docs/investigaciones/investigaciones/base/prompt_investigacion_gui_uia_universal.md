# Prompt de Investigación — GUI Control Universal en Windows 11 sin per-app hardcodes

## Contexto del proyecto

Carter v4 es un asistente local Jarvis-style en Windows 11. Tengo 47 tools registradas, latencia tipo Alexa, modelo `qwen3:4b-instruct-2507-q4_K_M`. Audit manual de la matrix oficial 540 dio 96.1% PASS REAL. Las **categorías más débiles** son:

- **C13 GUI/visión** (27/30): `gui_click`, `gui_type`, `gui_keypress` con frame-diff verifier funcionan bien para apps Win32 estándar pero **fallan en apps CEF/Chromium** (Steam, Discord, Spotify, Slack) — el frame-diff numpy detecta correctamente que el evento no llegó, pero no podemos resolver el problema.
- **C14 misiones multi-paso** (25/30): cuando el flow incluye `abre Steam → biblioteca → busca Batman`, no podemos navegar la UI de Steam.
- **C16 multilingüe** (29/30): regional names ("coso de notas") no se resuelven.

## Lo que NO quiero

- VLM residente (UI-TARS-2, MiniCPM-V) → consume VRAM permanente, conflict con tier 8GB.
- OmniParser con qwen2.5-vl → 3-8s/screenshot, rompe budget Alexa.
- Per-app hardcodes (no Steam-specific code, no Discord-specific code).
- Keyword lists per idioma.
- Cambiar de modelo o de Ollama.
- Soluciones que requieran que el usuario instale algo manualmente.

## Lo que SÍ tengo y funciona

- `pyautogui` + `pywin32` + `mss` + `numpy` instalados.
- `tools/gui.py` con click/type/keypress + frame-diff verifier.
- `tools/apps.py` con `Get-StartApps` resolver universal (UWP + Win32 + .lnk).
- `window_manage` tool (focus/minimize/maximize/restore por título).
- 5GB libres de VRAM (tier 16GB total) para algún modelo VLM bajo demanda si se usa **on-demand** y no residente.

## Lo que necesito que investigues a fondo

### 1. UIA (UI Automation) cascading universal

- **Estado del arte 2025-2026** sobre UIA para apps Chromium/CEF en Windows 11. ¿Funciona el flag `--force-renderer-accessibility`? ¿Cómo activarlo retroactivamente sin relanzar la app?
- `pywinauto.uia.UIA_Wrapper` vs `comtypes.client.GetModule("UIAutomationCore")` — comparativa real.
- ¿Qué patrones de UIA funcionan en Steam/Discord/Spotify? Hay reportes de issues #606 de pywinauto que dicen "no funciona" — ¿qué cambió en 2025?
- **AT-SPI / IAccessible2 fallback**: ¿son alternativas viables en Windows?
- Estrategia: **primero UIA (free, <500ms)**, si no encuentra elemento → screenshot + OCR (Tesseract/PaddleOCR CPU), si OCR no resuelve → VLM bajo demanda.

### 2. SendInput vs PostMessage vs AttachThreadInput

- ¿Cuál es la mejor estrategia 2025-2026 para apps que ignoran SendInput global (CEF en background)?
- `AttachThreadInput + mouse_event coords absolutas` es lo que la investigación previa decía. ¿Hay algo nuevo?
- `SendMessage(WM_LBUTTONDOWN)` directo al HWND: ¿funciona en CEF?
- ¿Hay forma de **enfocar la ventana garantizado** antes de SendInput? (SetForegroundWindow tiene restricciones de foreground-lock en Win11).

### 3. OCR + Vision universal sin VLM residente

- **Tesseract en español** vs **PaddleOCR** vs **EasyOCR** — comparativa de calidad y latencia en Windows 11.
- ¿Cómo combinar UIA-tree (que da elementos textuales aunque clickables fallen) con OCR (que da texto visual)?
- `Florence-2-large` (1GB) como detector de elementos clicables on-demand: ¿latencia? ¿accuracy?
- `qwen2.5-vl:3b` (3GB) cargado on-demand vía Ollama: ¿se puede cargar/descargar dinámicamente con `keep_alive=0` cuando se necesita y no consume VRAM cuando no?

### 4. Set-of-Mark prompting universal

- Set-of-Mark es la técnica donde se anotan elementos numerados sobre el screenshot y el LLM elige por número.
- ¿Hay implementación open-source ligera (sin dependencia de modelos vision grandes)?
- ¿Se puede usar UIA-tree → annotate over screenshot → text-only LLM elige por número?

### 5. Tool genérica `gui_action` que abstraiga el cascading

Imaginá que Carter tiene una sola tool `gui_action(target_description: str, action: "click"|"type"|"select"|"scroll", value: str = "")`. Esa tool internamente:
1. Toma screenshot
2. Detecta UIA-tree
3. Si UIA encuentra elemento que matchea description → invoke pattern
4. Si no, OCR del screenshot, find text matching description
5. Si no, VLM bajo demanda
6. Verifier: frame-diff post-acción

**¿Es factible esto en Python/Windows 11 con las libs disponibles? ¿Cuál es la latencia esperada por tier?**

### 6. Steam, Discord, Spotify — patrones específicos que SÍ son universales

Los 3 son CEF. Pero todos exponen **deep-links** universales del SO:
- `steam://run/<appid>` `steam://store/<appid>`
- `discord://discord.com/channels/...`
- `spotify:track:...` `spotify:playlist:...`

¿Es viable que `app_open` detecte si el "app" tiene protocolo URL deep-link conocido y lo despache vía `start <protocol>:<...>` ANTES de intentar abrir la GUI?

¿Cómo enumerar protocols registrados en HKEY_CLASSES_ROOT para hacerlo universal sin hardcodear apps?

### 7. Tool window_arrange para layouts (Win+Arrow keys)

Win11 tiene Snap Layouts nativos:
- `Win + Left/Right` → split half
- `Win + Z` → snap menu
- `Win + Up/Down` → maximize/minimize

¿Es viable una tool `window_arrange(window1_title, window2_title, layout: "side-by-side")` que use atajos nativos sin per-app hacks? Latencia? Verifier?

### 8. Stack recomendado: VLM on-demand vs residente

Carter tiene 16GB VRAM total, qwen3:4b-instruct-2507 ocupa ~3GB residente. Sobran ~12GB.

Si cargo un VLM vía Ollama on-demand con `keep_alive=30s` (descarga después de 30s sin uso):
- ¿Cuánto tiempo toma el cold-start? (probable 1-3s)
- ¿Es viable usarlo solo en C13/C14 cuando UIA + OCR fallaron?
- Recomendación entre: `qwen2.5-vl:3b`, `MiniCPM-V 2.6 (4.1B)`, `Florence-2-large (1GB)`, `LLaVA 1.6 7B`.

### 9. Implementación práctica

Dame **código Python concreto** para:
1. Una tool `gui_universal_action(description, action)` que haga el cascading completo
2. Un detector de "esta app es CEF/Chromium" (verificar `--force-renderer-accessibility` flag)
3. Un wrapper de UIA cascading que devuelva lista de elementos clickeables con bounding boxes
4. OCR fallback con PaddleOCR CPU (latencia esperada)

### 10. Caveats y trade-offs honestos

- ¿Qué cosas simplemente **no se pueden** hacer en Windows 11 con apps modernas?
- ¿Hay diferencias entre Win10 y Win11 que matter?
- ¿Hay riesgos de seguridad / triggering de antivirus con SendInput masivo?

---

## Formato esperado

Quiero un **plan ejecutable** con:

1. **TL;DR** (top 5 cambios concretos para C13/C14 con esfuerzo y impacto).
2. **Código snippets** Python concretos para la tool `gui_universal_action`.
3. **Tabla de verifiers** estructurales para cada tipo de acción GUI.
4. **Roadmap**: qué probar primero, qué medir, qué cambios son seguros.
5. **Caveats**: qué no funciona y por qué.

Foco en **soluciones que cierran fails reales en C13/C14** (5 + 5 fails actualmente). Si la mejor solución requiere un VLM on-demand, decílo claramente con costo/beneficio.
