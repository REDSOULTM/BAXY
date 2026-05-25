# Censo de apps por tecnología — ¿cuáles llevan el flag de accesibilidad?

Generado 2026-05-24 sobre la PC del dev (567 entradas en Get-StartApps, filtradas a
apps reales con UI). Clasificación por la tecnología de su UI, que decide si el flag
`--force-renderer-accessibility=complete` aplica o no.

## Regla de decisión

| Tecnología de la UI | ¿Expone UIA por defecto? | ¿Flag aplica? | Acción |
|---|---|---|---|
| **Win32 / WinForms / WPF** (apps nativas clásicas) | SÍ | no hace falta | nada — UIA directo |
| **UWP / MSIX** (apps de Store) | SÍ (nativo) | no hace falta | nada — UIA directo |
| **Chromium puro** (navegadores) | NO | **SÍ** | flag (ya en lista) |
| **Electron estándar** (shell Electron completo) | NO | **SÍ** (se propaga al renderer) | flag (ya en lista) |
| **CEF/Qt embebido propio** (launchers de juegos, editores) | parcial/no | **NO limpio** | cae a OCR (como Steam) |

## Resultado en esta PC

### ✅ Chromium/Electron — accesibilidad activable (VALIDADO 2026-05-25)
DOS mecanismos distintos según el empaquetado (medido con el árbol UIA real):
- **Navegadores Chromium puros** (Chrome, Edge, Opera GX): el flag CLI
  `--force-renderer-accessibility=complete` en el shortcut SÍ llega al renderer.
  Cubierto por el script (shortcut) + el agente al abrirlas.
- **Discord (Electron empaquetado con Squirrel)**: el flag CLI **NO funciona** —
  Squirrel lo descarta (medido: shortcut con flag → 0 controles UIA con nombre). La
  vía correcta es agregar `force-renderer-accessibility: complete` a
  `chromiumSwitches` en `%APPDATA%\discord\settings.json` (MEDIDO: **0 → 273
  controles UIA con nombre**; el agente ya ve botones "Enviar mensaje", canales,
  contactos). Lo hace el script (config-based apps).
- Spotify/Slack/otras Electron: shortcut flag aplicado best-effort; si su árbol UIA
  sigue vacío, probar su config propio (cada Electron empaquetada difiere).
- VS Code, WhatsApp: no se tocan (IDE / UWP nativo).

### ✅ UWP / nativo — UIA NATIVO, no necesitan flag (cubierto por diseño)
Exponen su árbol de accesibilidad de fábrica; el agente las controla por UIA directo.
- **ChatGPT** (es UWP/MSIX: `OpenAI.ChatGPT-Desktop_...!ChatGPT`, NO Electron — corregido)
- Calculadora, Cámara, Calendario, Correo, Mapas, Fotos, Paint, Microsoft Store,
  Grabadora de sonido, Herramienta Recortes, Xbox, Acceso por voz, Centro de opiniones
- Win32 clásicas: Bloc de notas, 7-Zip, Audacity, WinRAR, AIDA64, etc.

### ❌ CEF/Qt embebido especial — FLAG NO APLICA limpio (mismo caso que Steam)
Tienen Chromium/CEF embebido a su manera (no el shell Electron estándar), así que el
flag de Chromium NO se propaga de forma fiable. Su accesibilidad es pobre incluso para
lectores de pantalla. → el agente cae a OCR/visión para su UI, PERO suelen tener una
vía mejor (protocolo URI / filesystem) para la acción principal.
- **Steam** → no toma el flag (medido: NVDA solo lee el título). Vía buena: lanzar
  juegos por `steam://rungameid/{appid}` (ya implementado, lee la biblioteca del FS).
- **Epic Games Launcher, EA app, Battle.net, Amazon Games, Ubisoft Connect** → mismo
  caso que Steam (launchers de juegos con CEF propio).
- **CapCut** → Qt6 + CEF embebido (`CefCreator.dll`, no Electron). La UI principal es
  Qt (expone algo de UIA); los paneles CEF caen a OCR.

## Por qué NO se agregan las del último grupo al flag

Agregarlas a `_CHROMIUM_EXES`/`_ELECTRON_EXES` daría **falso soporte**: el flag no
llenaría su árbol UIA (su CEF está embebido con `SetAsWindowless` o es un host Qt/
propio, no el renderer Chromium que el flag controla). Verificado para Steam por
evidencia (NVDA). Para estas apps el camino correcto es:
1. **Acción principal** (lanzar juego/proyecto) → protocolo URI o resolución por FS
   (Steam ya; los demás launchers idealmente igual).
2. **Control de UI interna** → cascada OCR → visión (último recurso, gateada).

## Apps Chromium/Electron que NO tenés instaladas pero el agente reconoce
(en las listas por si las instalás): Brave, Vivaldi, Opera, Slack, Teams, Signal,
Notion, GitHub Desktop. Reciben el flag automáticamente si aparecen.
