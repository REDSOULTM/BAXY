# Herencia D — los adaptadores por aplicación, fichero por fichero

Qué hay que sustituir por capacidad genérica. **Aquí no se construye nada**: el
goal 07 lo hace. Esto es la lista exacta, medida el 2026-08-16 sobre `main`.

## El tamaño del problema

| Término | Menciones en `src/` | Ficheros |
|---|---:|---:|
| Steam | 204 | 9 |
| Spotify | 139 | 11 |
| Notepad | 76 | 12 |
| YouTube | 51 | 6 |
| Calculator | 38 | 6 |
| mpv | 31 | 3 |
| Edge | 20 | 3 |
| Discord | 7 | 4 |
| Chrome | 6 | 2 |

Y **un solo fichero .cs toca UI Automation** (`WindowsDeviceControlAdapter.cs`);
el resto de UIA vive en tres scripts PowerShell. Ésa es la desproporción que
define el trabajo: 11.918 líneas de adaptadores externos y prácticamente ninguna
capacidad genérica de operar una ventana ajena.

## Lo que no es sólo deuda de implementación: el contrato tipado

El nombre de la aplicación está **dentro del catálogo tipado**, no sólo en los
adaptadores. Sustituir los adaptadores sin tocar esto deja el problema intacto:

| `src/Baxy.Kernel/Operations/ProductCatalog.cs` | Qué fija |
|---|---|
| línea 672, 684 | `provider` con valores `["spotify"]` |
| línea 1240 | `service` con valores `["netflix", "prime_video", "youtube"]` |
| línea 1251 | `service` con valores `["netflix"]` |
| línea 842 | `channel` con valores `["discord", "whatsapp"]` |
| línea 560 | `provider` con valores `["any", "epic", "steam"]` |
| 11 `game.*` | verificadores `*.steam.*` en el propio identificador de efecto |
| línea 41 | `app.open` documenta `windows.notepad` y `windows.calculator` como casos aparte |

## Los ficheros a sustituir

### Sustitución completa — existen sólo para una aplicación

| Fichero | Líneas | Operaciones que sirve | Con qué se sustituye |
|---|---:|---|---|
| `src/Baxy.Providers.Windows/External/SteamLocalAdapter.cs` | 925 | `game.catalog.list`, `game.install.cancel`, `game.install.cancel.active`, `game.install.commit`, `game.install.named`, `game.install.prepare`, `game.install.status`, `game.launch`, `game.purchase.commit`, `game.purchase.prepare` | `app.open` + cascada UIA→OCR→visión encadenada |
| `src/Baxy.Providers.Windows/External/SpotifyDesktopAdapter.cs` | 212 | `media.control`, `media.play.exact`, `media.play.query` | sesión de medios de Windows (ya existe) + cascada |
| `src/Baxy.Providers.Windows/External/YouTubeMpvAdapter.cs` | 298 | `media.play.youtube` | navegador genérico + cascada |
| `src/Baxy.Providers.Windows/External/WindowsGameInstallationAdapter.cs` | 247 | `game.installed.named` | `filesystem.*` + catálogo de aplicaciones instaladas |
| `src/Baxy.Providers.Windows/External/SpotifyDesktopAutomation.ps1` | 275 | automatización UIA de Spotify | la cascada genérica |
| `src/Baxy.Providers.Windows/External/SpotifyMediaControl.ps1` | 188 | control de medios de Spotify | sesión de medios de Windows |
| `src/Baxy.Providers.Windows/Applications/WindowsCalculatorOpenProvider.cs` | 134 | caso especial de `app.open` | `app.open` genérico |
| `src/Baxy.Providers.Windows/Applications/NotepadIdentityPolicy.cs` | 175 | identidad de ventana de Notepad | verificación de ventana genérica |

**Subtotal: 2.454 líneas que desaparecen** y con ellas 15 entradas de catálogo,
si la cascada las cubre.

### Sustitución parcial — la capacidad es genérica, el nombre no

| Fichero | Líneas | Qué hay que quitarle |
|---|---:|---|
| `src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs` | 1.418 | rutas fijas de `youtube.com`, `netflix.com`, `primevideo.com`, `amazon.com` y `msedge.exe`; `streaming.play.named` es Netflix disfrazado de genérico |
| `src/Baxy.Providers.Windows/External/DesktopMessagingAdapter.cs` | 999 | canales fijos `discord`/`whatsapp` en `message.send` |
| `src/Baxy.Providers.Windows/External/NamedBrowserAdapter.cs` | 122 | `opera.exe`, `launcher.exe` |
| `src/Baxy.Providers.Windows/External/WindowsMediaSessionAdapter.cs` | 687 | 39 menciones de Spotify sobre una API que ya es genérica (SMTC) |
| `src/Baxy.Providers.Windows/Applications/WindowsApplicationLauncher.cs` | 704 | 14 menciones de Notepad |
| `src/Baxy.Providers.Windows/Applications/WindowsApplicationPlatform.cs` | 594 | 10 menciones de Notepad |
| `src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs` | 1.080 | 6 de Notepad, 6 de Calculator |
| `src/Baxy.App/NaturalApplicationRequestParser.cs` | — | lista de apps conocidas en el parser de lenguaje |
| `src/Baxy.App/NaturalNoteRequestParser.cs` | — | 11 menciones de Notepad |
| `src/baxy_mind/data/catalog_operation_aliases.v1.json` | — | 14 alias de Steam, 6 de Spotify, 6 de Notepad, 4 de YouTube |

### Lo que se conserva y es la base de la cascada

| Fichero | Líneas | Por qué |
|---|---:|---|
| `src/Baxy.Providers.Windows/External/CaptureVisionAdapter.cs` | 452 | `ocr.read` y `vision.describe`; ya invoca `tesseract.exe`. **Es el escalón OCR de la cascada, y existe.** |
| `src/Baxy.Providers.Windows/External/WindowsVisibleControlAdapter.cs` | 82 | `input.visible.click`; es el `Click X` genérico, hoy delegado a `DesktopClickVisible.ps1` |
| `src/Baxy.Providers.Windows/External/WindowsDesktopInteractionAdapter.cs` | 168 | teclado, ratón, portapapeles genéricos |
| `src/Baxy.Providers.Windows/External/DesktopClickVisible.ps1` | 100 | UIA real, sin nombre de app |
| `src/Baxy.Providers.Windows/External/DesktopSelectAll.ps1` | 264 | UIA real, sin nombre de app |
| `src/Baxy.Providers.Windows/External/WindowsDeviceControlAdapter.cs` | 1.182 | wifi, bluetooth, periféricos, ajustes; genérico de Windows |

## El dato que decide el orden de trabajo del goal 07

El escalón **OCR ya existe y funciona** (`CaptureVisionAdapter` → `tesseract.exe`),
y el escalón **UIA existe en tres scripts PowerShell** sin nombre de aplicación.
Lo que falta no es la cascada entera: es **el escalón UIA en código, la política
de cascada que decide cuándo baja de UIA a OCR a visión, y el modelo de visión**.

Traducido a la ley 1: aquí no se empieza de cero, se sube un escalón.
