# Prompt de investigación 8/8 — Automatización GUI/desktop fiable (clicks, UIA, visión) en Windows desde un 4B (vram4)

Copiá esto a Claude (research/web). Tema ESPECÍFICO: que el asistente opere apps
de escritorio (clickear, escribir, navegar UI) de forma FIABLE en Windows, guiado
por un 4B, sin OCR/visión caros que rompan la latencia. Fuentes 2025-2026.

## RESTRICCIÓN DURA: TODO en vram4 = Gemma 4 E4B-it Q4_K_M
Default vram4 (4B cuantizado, voz local, GPU compartida 4-6 GB, latencia 4-5 s).
La visión (mmproj) es LAZY — solo se carga en turnos con imagen y compite por la
VRAM. Las soluciones GUI no pueden depender de visión pesada por turno ni de un
modelo más grande. Lo que no entre en vram4 → NO-VIABLE + alternativa.

## 1. El problema
Muchas acciones útiles requieren manipular UIs sin API (mandar WhatsApp, navegar
streaming, configurar apps). Hoy se hace con: deeplinks, foco de ventana,
keypress/type, y a veces OCR (locate_text/click_text) o CDP para navegadores. Es
frágil: clicks a coordenadas que cambian, OCR lento, UI que se mueve. Un 4B no
"ve" la pantalla salvo que le inyectemos visión (cara).

## 2. Lo que YA tenemos (no recomendar)
- gui tool: click/type/keypress/scroll/locate_text/click_text (OCR Tesseract)/
  locate_image/wait_for. win_focus.py (foco+maximize robusto ALT+AttachThreadInput
  +UIA). gui_type por clipboard-paste (Unicode-safe).
- browser_real (CDP/Playwright) para web: click_text, fill, extract, tabs.
- Verificadores por tool (verify_gui/window/app) + verificación de chat por OCR.
- Streaming: selectores data-uia/data-testid para Netflix/Disney/etc.
- Visión lazy (mmproj on-demand) para turnos con imagen.

## 3. Lo que quiero investigado
1. **UI Automation (UIA) como camino primario vs OCR/coordenadas**: para apps
   Windows nativas/UWP, ¿conviene leer el árbol de accesibilidad (UIA: nombres,
   roles, AutomationId) y actuar sobre ELEMENTOS en vez de píxeles? Es más fiable
   y barato que OCR. ¿Cómo exponerlo al 4B (lista de elementos clickeables como
   texto) para que elija sin "ver"? Costo/latencia de enumerar el árbol UIA.
2. **Reducir dependencia de visión cara**: la visión (mmproj) compite por VRAM en
   vram4. ¿Cómo resolver la mayoría de tareas GUI con UIA + texto (accesibilidad)
   y reservar la visión solo para lo que de verdad necesita píxeles? Política.
3. **Robustez ante UIs que cambian**: selectores/coordenadas se rompen cuando la
   app actualiza. ¿Estrategias resilientes (buscar por texto/rol/AutomationId con
   fallbacks, re-localizar antes de clickear, reintentos)? Para apps comunes
   (WhatsApp, Spotify, navegadores).
4. **El LLM como planificador de pasos GUI vs ejecutor determinista**: ¿el 4B debe
   decidir cada click (poco fiable) o invocar "macros" deterministas parametrizadas
   (ej. send_whatsapp(contact, text) que internamente hace foco+search+verify+
   type+send)? ¿Cuánto encapsular en código vs dejar al LLM? (cruza con T1
   tool-calling pero acá enfocá la CAPA de automatización GUI).
5. **Frameworks/patrones de desktop automation 2025-2026** viables OSS local
   Windows (pywinauto, UIA directo, FlaUI-equivalentes en Python, Computer-Use
   patterns adaptados a SLM). Qué adoptar sin meter dependencias pesadas.
6. **Verificación post-acción de GUI** (cruza con tema 3): confirmar que el click
   tuvo efecto vía UIA (estado del elemento) en vez de re-OCR. Más barato/fiable.

## 4. Formato
Por punto: diagnóstico, tabla (fiabilidad, latencia, VRAM, robustez a cambios de
UI, complejidad), fuentes recientes (UIA, desktop automation, computer-use en
SLMs), veredicto VIABLE vram4+Windows, código/pseudocódigo (cómo encajar con el
gui tool y win_focus existentes). Priorizá 1 y 4 (UIA primario + macros
deterministas — el camino más fiable y barato para un 4B).
