# Carter Agent

Agente local desde cero para Gemma 4 en Windows. Usa `llama-server`
OpenAI-compatible, tools reales, memoria explicita y entradas multimodales.

## Ejecutar

```powershell
& "C:\llamacpp-cuda\bin\llama-server.exe" `
    -m "models\E4B\gemma-4-E4B-it-Q6_K.gguf" `
    --mmproj "models\E4B\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384 `
    --parallel 1 --ctx-checkpoints 1 --flash-attn on

python -m gemma4_agent.support.chat
```

El agente tambien puede levantar el servidor:

```powershell
python -m gemma4_agent.support.chat --start-server
```

Tambien hay un launcher local inspirado en Jarvis, sin auth/web/voz/camara:

```powershell
python -m gemma4_agent.infra.launcher
python -m gemma4_agent.infra.launcher chat
python -m gemma4_agent.infra.launcher status
python -m gemma4_agent.infra.launcher smoke
python -m gemma4_agent.infra.launcher shortcut
```

El launcher permite abrir el chat con `--start-server`, ver diagnostico local,
ejecutar smoke tests, iniciar solo `llama-server`, abrir carpetas de runtime y
crear un `.cmd` en el escritorio.

El tamano de contexto del ejemplo se controla con `GEMMA4_AGENT_CONTEXT`.
Para 6-16 GB VRAM, `16384` es el perfil diario razonable. Usa 32768/65536/128000
solo cuando la VRAM y la latencia lo permitan.

## Multimodal

```powershell
python -m gemma4_agent.support.chat --image .\foto.png
python -m gemma4_agent.support.chat --audio .\audio.wav
```

Dentro del chat:

```text
/image C:\ruta\captura.png
/audio C:\ruta\voz.wav
/progress
```

Las screenshots tomadas con `gui_screenshot` se reinyectan como imagen en el
siguiente turno para que Gemma 4 pueda razonar visualmente.

El chat muestra una barra de progreso mientras Gemma piensa y ejecuta tools:
modo elegido, pasos planeados, turno actual y tool activa. Se puede apagar con
`python -m gemma4_agent.support.chat --no-progress` o alternar dentro del chat con
`/progress`.

## Memoria

La memoria vive en `gemma4_agent/data/memory.json`. El estado operativo vive en
`gemma4_agent/data/state.json` y guarda recursos abiertos, checkpoints y notas
tecnicas de rollback/cleanup. El prompt instruye al modelo a usar
`memory(action="save")` solo cuando el usuario lo pide explicitamente.

Ejemplos:

```text
recorda que prefiero respuestas cortas
que recordas de mi?
olvida mi preferencia de respuestas cortas
```

## Tools compuestas incluidas

- `system`: hora, procesos, CPU/RAM/GPU, disco, bateria, brillo, power.
- `audio`: volumen, mute, dispositivos.
- `app`: buscar/abrir/cerrar/desinstalar apps dinamicas.
- `steam`: biblioteca, tienda dentro del cliente, juegos instalados, buscar en biblioteca, abrir pagina de tienda por AppID, lanzar/buscar/instalar.
- `window`: listar, activa, foco, cerrar, minimizar/maximizar/restaurar, mover.
- `gui`: screenshot, click, doble click, right click, type, hotkeys, scroll, drag.
- `vision`: OCR local con Tesseract y puente a vision nativa Gemma 4 via screenshot reinyectado.
- `browser`: abrir/navegar, buscar, YouTube play, pausa media, titulo activo.
- `web`: buscar, leer paginas e investigar con fuentes extraidas.
- `uia`: Windows UI Automation para arbol, buscar, click, foco y set_value.
- `filesystem`: list/read/write/search/delete/copy/move/rename/mkdir/diff/archive/open.
- `package`: winget list/search/install/uninstall.
- `clipboard`: read/write.
- `terminal`: run.
- `memory`: save/recall/list/delete.
- `verify`: app_opened/file_exists/window_exists/clipboard_contains.
- `state`: recursos abiertos, cleanup plan/cleanup, checkpoints y rollback.
- `input`: idioma/layout de teclado de Windows.
- `env`: variables de entorno process/user/machine.
- `registry`: query/export/import/add/delete/backup con backup antes de mutar.
- `download`: descarga, SHA256 y Authenticode.
- `email`: status/draft/send via Microsoft Graph si hay token.
- `reminder`: recordatorios locales en state o Graph si hay auth.
- `browser_real`: Playwright headless para leer/clickear paginas con precision.
- `knowledge`: RAG local SQLite/FTS5 para documentos de texto.
- `office`: PowerPoint/Word/Excel local via python-pptx/python-docx/openpyxl cuando esten instalados.
- `audio_device`: dispositivos de audio predeterminados/routing con helper local como SoundVolumeView.
- `notification`: timers, alarmas, recordatorios y notificaciones locales con Scheduled Tasks.
- `routine`: automatizaciones locales reutilizables y `run_now` con steps de tools.
- `media`: musica/video/local files sobre YouTube, media keys y archivos locales.
- `source_manager`: fuentes/citas/snapshots locales para investigacion.
- `dependency`: diagnostico de dependencias locales y hints de instalacion.
- `contacts`: contactos locales.
- `notes_tasks`: notas, listas y tareas locales.
- `local_calendar`: eventos offline e ICS export.
- `habit_tracker`: habitos y logs locales.
- `local_search`: busqueda local por nombre/contenido pequeno.
- `printer_scanner`: impresoras, default y colas.
- `desktop_layout`: snapshots de ventanas/monitores.
- `backup_sync`: backups ZIP locales registrados en state.
- `safety`: confirmaciones pendientes para acciones riesgosas cuando se activa.

Este prototipo no tiene capa de confirmacion de seguridad por pedido del
usuario. Por defecto `GEMMA4_AGENT_SAFETY=false`, asi las tools ejecutan
directamente lo solicitado, pero las acciones que tocan estado del PC intentan
dejar evidencia tecnica, checkpoint o cleanup cuando es razonable.

La safety layer ya existe y se puede activar:

```powershell
$env:GEMMA4_AGENT_SAFETY = "true"
```

Con safety activa, acciones como borrar, instalar/desinstalar, cerrar apps,
registro, variables persistentes o comandos riesgosos devuelven
`needs_confirmation` y quedan pendientes en `state.json`. Luego se confirma con
`safety(action="confirm", confirmation_id="...")`.

## Resolucion dinamica de apps

`app(action="open", name="Steam")` no usa una tabla fija de aliases. El resolver busca en:

- ejecutables disponibles por `PATH`
- accesos directos del Start Menu y escritorio
- `Get-StartApps` para apps UWP/Store
- registro de programas instalados
- bibliotecas Steam (`appmanifest_*.acf`)
- manifiestos de Epic Games
- busqueda profunda por `.exe` en carpetas comunes si los indices rapidos no encuentran nada

Tambien existe `app(action="search", query="...")` para inspeccionar candidatos antes de abrirlos.

## Misiones compuestas

El agente puede encadenar tools. Ejemplo:

```text
abre Steam, ve a mi biblioteca y busca Doom Eternal ahi dentro,
luego ve a Opera y busca Doom en Google
```

Secuencia esperada:

```text
steam(action="search_library", query="Doom Eternal")
browser(action="search", browser="Opera", engine="google", query="Doom")
```

Para Steam store:

```text
steam(action="store_page", query="Marvel Rivals")
```

Eso resuelve un AppID cuando puede y abre `steam://store/<appid>` en el cliente
de Steam. Si no resuelve AppID, abre la busqueda de tienda dentro del cliente y
marca el resultado como no verificado.

## Modos de uso

Por defecto `GEMMA4_AGENT_MODE=auto`. El router elige:

- `fast_action`: preguntas simples y acciones cortas, sin thinking.
- `deep_action`: misiones compuestas en orden, con thinking privado.
- `vision_action`: imagen/screenshot -> razonamiento visual -> UIA/GUI -> verificacion.
- `audio_mode`: entrada de audio, sin inventar si la transcripcion no es clara.
- `research`: investigacion con `web(...)`, fuentes y thinking privado.

Tambien se puede forzar:

```powershell
python -m gemma4_agent.support.chat --mode research
$env:GEMMA4_AGENT_MODE = "deep_action"
```

El historial limpia campos/tags de reasoning antes de guardarlos. Esto permite
activar thinking en tareas profundas sin contaminar los turnos siguientes.

## Verificacion y honestidad

Todas las tools devuelven campos normalizados:

```json
{
  "status": "done | attempted | needs_verification | failed",
  "verified": true,
  "evidence": "..."
}
```

`ok=true` significa que la tool pudo ejecutarse, no necesariamente que el
objetivo del usuario quedo completado. Para GUI, navegador y media el agente
debe verificar con `uia`, `gui`, `vision`, `window`, `verify` o `web` antes de
afirmar que termino.

Para investigar en internet se usa `web(action="research", query="...")`.
`browser(action="search")` solo abre resultados visibles en el navegador.
Para control real de paginas se usa `browser_real(...)`, basado en Playwright
headless y sesiones persistentes por `session_id`; si Playwright o Chromium no
estan disponibles, devuelve `needs_user/needs_dependency` en vez de fingir.
Tambien puede conectarse por CDP a un navegador iniciado con remote debugging:
`browser_real(action="connect_cdp", endpoint="http://127.0.0.1:9222")`.
El proveedor de busqueda vive detras de `GEMMA4_WEB_SEARCH_PROVIDER`; por ahora
el backend implementado es `duckduckgo_html`.

## RAG local

`knowledge` usa SQLite FTS5 local. No usa embeddings cloud.

```text
knowledge(action="ingest", path="docs/Contrato.md")
knowledge(action="search", query="condiciones del contrato")
```

Soporta texto plano (`.txt`, `.md`, `.json`, `.csv`, `.log`, `.py`, `.ps1`,
`.yaml`, `.yml`). Para PDF/DOCX todavia conviene extraer texto primero.

`app(action="close")` intenta cerrar primero ventanas que coincidan con el
nombre visible y despues procesos resueltos desde accesos directos, registro o
rutas instaladas. Si no cierra nada, devuelve `ok=false`; ya no marca como
exito un `taskkill` que no encontro el proceso.

## Opciones de llama-server

El cliente envia parametros compatibles con llama.cpp para Gemma 4:

- `GEMMA4_AGENT_PARSE_TOOL_CALLS=true` por defecto.
- `GEMMA4_AGENT_PARALLEL_TOOL_CALLS=false` por defecto para mantener acciones de PC en orden.
- `GEMMA4_AGENT_ENABLE_THINKING=false` sigue siendo el default global, pero el router puede activar thinking por turno en `deep_action`, `vision_action` y `research`.
- `GEMMA4_AGENT_REASONING_FORMAT` vacio por defecto; solo se envia si lo defines.
- `GEMMA4_AGENT_MIN_P` es opcional. Si no lo defines no se envia, para quedar alineado con los parametros oficiales principales de Gemma 4 (`temperature=1.0`, `top_p=0.95`, `top_k=64`).
- `GEMMA4_AGENT_CONTEXT=16384` controla el `-c` usado por `--start-server`.

Las schemas de tools compuestas incluyen `enum` en `action` para reducir
llamadas ambiguas o acciones inventadas por el modelo, y
`additionalProperties=false` para desalentar argumentos fuera del contrato.
Ademas hay validacion runtime: si Gemma manda una accion fuera del enum o
argumentos desconocidos, la tool no se ejecuta y recibe un error estructurado.
Si una version vieja de `llama-server` rechaza opciones nuevas del request, el
cliente reintenta automaticamente sin esas opciones especificas.

## Trazas y evaluacion

Cada turno genera una linea JSONL en `gemma4_agent/data/traces.jsonl` con:

- modo elegido
- resumen del input sin volcar base64 completo
- respuestas del LLM
- tool calls/resultados
- final o error
- `mission_status`: PASS, PARTIAL, FAILED, UNVERIFIED o NEEDS_USER
- plan deterministico del turno, con pasos esperados y tools sugeridas

Esto permite crear evaluaciones offline sin abrir apps ni controlar el PC.
Se puede desactivar con:

```powershell
$env:GEMMA4_AGENT_TRACING = "false"
```

La ruta se puede cambiar con `GEMMA4_AGENT_TRACE_PATH`.
