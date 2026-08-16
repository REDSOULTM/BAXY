# Carter v2 — Sesión 9: Nuevas capabilities (Email, PDF, Audio/Video, Red, Sistema, Archivos)

## Contexto del proyecto

Carter es un asistente de Windows con LLM (Qwen3-8B vía Ollama) que ejecuta herramientas reales.
Arquitectura: el LLM hace tool-calling → `AgentEngine` despacha a `CapabilityRegistry` → cada
`Capability` ejecuta la acción y devuelve `CapabilityResult`.

**Repo:** `Carter_v2/`
**Rama activa:** `rebuild/v2-from-scratch`

### Estructura de carpetas relevante

```
Carter_v2/
  src/carter_v2/
    capabilities/         ← aquí viven todas las capabilities
      base.py             ← clase base Capability
      filesystem.py       ← ejemplo de capability existente
      network.py          ← ejemplo existente
      notifications.py    ← ejemplo existente
      terminal.py         ← ejemplo existente con allowlist de seguridad
    adapters/
      tools.py            ← definiciones ToolDefinition + ToolParameter + descripciones compactas
    main.py               ← _build_registry() registra todas las capabilities
    types.py              ← CapabilityRequest, CapabilityResult, VerifiedFact, Evidence
  tests/
    test_capabilities.py  ← tests existentes (referencia de estilo)
  probe_all_tools.py      ← probe live con LLM real (añadir casos nuevos aquí)
```

---

## Patrones obligatorios — seguir exactamente

### 1. Capability nueva (archivo propio en `capabilities/`)

```python
from __future__ import annotations
from ..types import CapabilityRequest, CapabilityResult
from .base import Capability

class XyzCapability(Capability):
    namespace = "xyz"

    def supports(self, action: str) -> bool:
        return action in {"action_a", "action_b"}

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        p = request.params
        if request.action == "action_a":
            return _action_a(str(p.get("param") or ""))
        raise ValueError(f"Unsupported action: {request.action}")

def _action_a(param: str) -> CapabilityResult:
    try:
        # implementación
        return CapabilityResult(True, "Mensaje corto.", data={"key": "value"})
    except Exception as exc:
        return CapabilityResult(False, f"Error: {exc}", errors=[str(exc)])
```

### 2. Registrar en `main.py` dentro de `_build_registry()`

```python
from .capabilities.xyz import XyzCapability
registry.register(XyzCapability())
```

### 3. Registrar ToolDefinitions en `adapters/tools.py`

Cada tool necesita:
- Entrada en la lista `_TOOL_DEFINITIONS` con `ToolDefinition(name=..., capability=..., action=..., description=..., parameters=[...])`
- Entrada en `_COMPACT_TOOL_DESCRIPTIONS` dict: `"tool_name": "Descripción compacta ≤12 palabras."`
- El nombre de la tool en `_DIRECT_ACTION_TOOLS` si es acción directa (no requiere confirmación)

**NO agregar** a `_COMPACT_DEPRECATED_TOOL_NAMES` (eso las ocultaría al LLM).

### 4. `CapabilityResult` fields

```python
CapabilityResult(
    ok=True,
    message="Texto corto que el LLM lee directamente",
    data={"key": "value"},           # datos estructurados
    errors=[],                        # lista de strings si ok=False
    next_step_hint="sugerencia",      # opcional, guía al LLM cuando falla
)
```

### 5. Usar `_subprocess.run_with_kill` para subprocesos con timeout

```python
from ._subprocess import run_with_kill
rc, stdout, stderr = run_with_kill(["cmd", "/d", "/c", "comando"], timeout=30)
```

### 6. Tests — `pytest`, un archivo por capability nueva en `tests/`

```python
import pytest
from carter_v2.capabilities.xyz import XyzCapability
from carter_v2.types import CapabilityRequest

@pytest.fixture
def cap():
    return XyzCapability()

def test_action_a_ok(cap):
    r = cap.execute(CapabilityRequest(capability="xyz", action="action_a", params={"param": "valor"}))
    assert r.ok
    assert "key" in r.data
```

---

## Tareas — implementar TODO lo siguiente

### BLOQUE 1 — PDF (nueva capability `pdf.py`)

**Capability:** `PdfCapability`, namespace `"pdf"`

| Action | Params | Descripción |
|--------|--------|-------------|
| `read_text` | `path: str`, `max_pages: int = 0` (0=todos) | Extraer texto de un PDF usando `pypdf`. Devolver texto en `data["text"]` y nº páginas en `data["pages"]`. |
| `merge` | `paths: list[str]`, `output: str` | Unir varios PDFs en uno. Usar `pypdf.PdfWriter`. |
| `split` | `path: str`, `output_dir: str`, `pages_per_file: int = 1` | Dividir en archivos por grupo de páginas. |
| `from_docx` | `path: str`, `output: str` | Convertir DOCX → PDF usando LibreOffice headless: `soffice --headless --convert-to pdf --outdir <dir> <file>`. Fallback: intentar con Word COM si LibreOffice no está. |
| `to_images` | `path: str`, `output_dir: str`, `dpi: int = 150` | Convertir cada página a PNG usando `pdf2image` (wrapper de pdftoppm/poppler). Si no está disponible, devolver `ok=False` con `next_step_hint`. |

**Tools en `tools.py`:**
- `pdf_read_text` — "Extract text from a PDF file."
- `pdf_merge` — "Merge multiple PDF files into one."
- `pdf_split` — "Split a PDF into separate files by page range."
- `pdf_from_docx` — "Convert a Word .docx file to PDF."
- `pdf_to_images` — "Convert PDF pages to PNG images."

**Dependencias:** `pypdf` (ya puede estar instalado), `pdf2image` (opcional).
Usar `try/import` para dependencias opcionales y devolver `next_step_hint` si faltan.

---

### BLOQUE 2 — Email (nueva capability `email.py`)

**Capability:** `EmailCapability`, namespace `"email"`

Estrategia de backends (intentar en orden):
1. **Outlook COM** — si Outlook está instalado: `win32com.client.Dispatch("Outlook.Application")`
2. **SMTP/IMAP** — configurado en env vars: `CARTER_EMAIL_SMTP_HOST`, `CARTER_EMAIL_SMTP_PORT`, `CARTER_EMAIL_SMTP_USER`, `CARTER_EMAIL_SMTP_PASS`, `CARTER_EMAIL_IMAP_HOST`

| Action | Params | Descripción |
|--------|--------|-------------|
| `send` | `to: str`, `subject: str`, `body: str`, `cc: str = ""`, `attachments: list[str] = []` | Enviar email. Intentar Outlook COM primero, luego SMTP. |
| `read_inbox` | `max_count: int = 10`, `unread_only: bool = False` | Leer bandeja de entrada. Devolver lista de `{id, from, subject, date, preview}`. |
| `read_message` | `message_id: str` | Leer cuerpo completo de un email por ID. |
| `reply` | `message_id: str`, `body: str` | Responder a un email existente. |
| `list_folders` | — | Listar carpetas del buzón. |

Si ningún backend está configurado, devolver `ok=False` con `next_step_hint` explicando cómo configurar.

**Tools:** `email_send`, `email_read_inbox`, `email_read_message`, `email_reply`, `email_list_folders`

---

### BLOQUE 3 — Calendario (nueva capability `calendar.py`)

**Capability:** `CalendarCapability`, namespace `"calendar"`

Backends (igual que email, en orden): Outlook COM → Google Calendar API (si `CARTER_GOOGLE_CREDENTIALS` existe).

| Action | Params | Descripción |
|--------|--------|-------------|
| `list_events` | `days_ahead: int = 7`, `max_count: int = 20` | Listar eventos próximos. Devolver `{id, title, start, end, location, description}`. |
| `create_event` | `title: str`, `start: str` (ISO), `end: str` (ISO), `location: str = ""`, `description: str = ""`, `attendees: list[str] = []` | Crear evento. |
| `delete_event` | `event_id: str` | Eliminar evento por ID. |
| `update_event` | `event_id: str`, `title: str = ""`, `start: str = ""`, `end: str = ""` | Modificar evento existente. |

**Tools:** `calendar_list_events`, `calendar_create_event`, `calendar_delete_event`, `calendar_update_event`

---

### BLOQUE 4 — Audio/Video (nueva capability `media_files.py`)

**Capability:** `MediaFilesCapability`, namespace `"media_files"`

Usar FFmpeg (via subprocess) para todas las operaciones de video/audio. Usar `pydub` o `sounddevice` para grabación.

| Action | Params | Descripción |
|--------|--------|-------------|
| `audio_play` | `path: str` | Reproducir archivo de audio (usar `winsound.PlaySound` para WAV, o `playsound` para otros formatos). |
| `audio_record` | `output: str`, `duration_seconds: int = 10` | Grabar desde micrófono usando `sounddevice` + `scipy.io.wavfile`. |
| `audio_transcribe` | `path: str`, `language: str = ""` | Transcribir audio a texto usando `openai-whisper` si está instalado, sino intentar Azure Speech o devolver error con hint. |
| `video_convert` | `input: str`, `output: str`, `codec: str = ""` | Convertir video usando FFmpeg: `ffmpeg -i input -c:v libx264 output`. |
| `video_extract_audio` | `input: str`, `output: str` | Extraer pista de audio: `ffmpeg -i input -vn -acodec libmp3lame output.mp3`. |
| `video_trim` | `input: str`, `output: str`, `start: str`, `end: str` | Recortar video: `ffmpeg -i input -ss start -to end -c copy output`. |
| `image_resize` | `input: str`, `output: str`, `width: int`, `height: int = 0` | Redimensionar imagen usando Pillow. Si height=0, mantener proporción. |
| `image_convert` | `input: str`, `output: str` | Convertir formato de imagen (Pillow). |
| `audio_tts_to_file` | `text: str`, `output: str` | TTS a archivo MP3/WAV usando pyttsx3 o gTTS. |

Para FFmpeg, verificar que `ffmpeg` esté en PATH antes de ejecutar. Si no está, devolver `next_step_hint="install ffmpeg and add to PATH"`.

**Tools:** `media_audio_play`, `media_audio_record`, `media_audio_transcribe`, `media_video_convert`, `media_video_extract_audio`, `media_video_trim`, `media_image_resize`, `media_image_convert`, `media_audio_tts_file`

---

### BLOQUE 5 — Archivos: operaciones faltantes (extender `filesystem.py`)

Agregar a `FileSystemCapability.supports()` y `execute()`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `append_text` | `path: str`, `content: str` | Añadir texto al final del archivo sin sobreescribir. |
| `rename` | `path: str`, `new_name: str` | Renombrar archivo/carpeta (solo nombre, no mover). |
| `zip` | `paths: list[str]`, `output: str` | Comprimir lista de archivos/carpetas en un ZIP usando `zipfile`. |
| `unzip` | `path: str`, `output_dir: str` | Descomprimir un ZIP en un directorio destino. |
| `read_lines` | `path: str`, `start_line: int = 1`, `end_line: int = 0` | Leer rango de líneas de un archivo. |
| `get_size` | `path: str` | Tamaño total de archivo o directorio (recursivo si es dir). Devolver en bytes y formato human-readable. |

**Tools nuevas en `tools.py`:**
- `filesystem_append_text`, `filesystem_rename`, `filesystem_zip`, `filesystem_unzip`, `filesystem_read_lines`, `filesystem_get_size`

---

### BLOQUE 6 — Red: operaciones faltantes (extender `network.py`)

Agregar a `NetworkCapability`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `ping` | `host: str`, `count: int = 4` | Ping a host: `ping -n count host` (Windows). Parsear RTT promedio. |
| `get_public_ip` | — | Obtener IP pública via `https://api.ipify.org` (requests). |
| `port_check` | `host: str`, `port: int`, `timeout: int = 3` | Verificar si puerto TCP está abierto usando `socket.connect_ex`. |
| `dns_lookup` | `host: str` | Resolver DNS: devolver IPs. Usar `socket.getaddrinfo`. |
| `speed_test` | — | Test de velocidad usando `speedtest-cli` si está instalado, sino `next_step_hint`. |
| `traceroute` | `host: str` | Ejecutar `tracert host` y parsear resultado. |

**Tools:** `network_ping`, `network_get_public_ip`, `network_port_check`, `network_dns_lookup`, `network_speed_test`, `network_traceroute`

---

### BLOQUE 7 — Sistema: operaciones faltantes (extender `system.py`)

Agregar a `SystemCapability`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `list_installed_apps` | `filter: str = ""` | Lista de apps instaladas (winreg `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`). Filtrar por nombre si se pasa `filter`. |
| `get_startup_apps` | — | Apps que arrancan con Windows (registro + carpeta Startup). |
| `env_get` | `name: str` | Leer variable de entorno. |
| `env_set` | `name: str`, `value: str`, `persist: bool = False` | Escribir variable de entorno (proceso actual). Si `persist=True`, usar winreg para hacerlo permanente. |
| `registry_read` | `hive: str`, `key: str`, `value_name: str` | Leer valor del registro. Hives: HKLM, HKCU, HKCR, HKU, HKCC. |
| `registry_write` | `hive: str`, `key: str`, `value_name: str`, `value: str`, `value_type: str = "REG_SZ"` | Escribir valor en registro. |
| `get_running_services` | `filter: str = ""` | Listar servicios de Windows en ejecución (PowerShell `Get-Service`). |
| `clipboard_history` | — | Obtener historial de portapapeles de Windows 10+ vía PowerShell. |

**Tools:** `system_list_installed_apps`, `system_get_startup_apps`, `system_env_get`, `system_env_set`, `system_registry_read`, `system_registry_write`, `system_get_running_services`, `system_clipboard_history`

---

### BLOQUE 8 — Ventanas: operaciones faltantes (extender `window.py`)

Agregar a `WindowCapability`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `resize` | `title: str`, `width: int`, `height: int` | Cambiar tamaño de ventana por título (pywin32 `win32gui.MoveWindow`). |
| `move` | `title: str`, `x: int`, `y: int` | Mover ventana a posición. |
| `get_text` | `title: str` | Leer texto visible de una ventana (pywin32 `win32gui.GetWindowText` + UIA si disponible). |
| `screenshot` | `title: str`, `output: str = ""` | Captura solo de la ventana especificada (PIL/win32gui). Si output vacío, guardar en temp. |
| `pin_on_top` | `title: str`, `enabled: bool = True` | Activar/desactivar "always on top" (`win32con.HWND_TOPMOST`). |

**Tools:** `window_resize`, `window_move`, `window_get_text`, `window_screenshot`, `window_pin_on_top`

---

### BLOQUE 9 — Office: operaciones faltantes (extender `office.py`)

Agregar a `OfficeCOMCapability`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `word_find_replace` | `path: str`, `find: str`, `replace: str`, `match_case: bool = False` | Buscar y reemplazar texto en documento Word abierto o abriendo el archivo. |
| `excel_create_chart` | `path: str`, `sheet: str`, `data_range: str`, `chart_type: str = "bar"`, `title: str = ""` | Crear gráfico en Excel (COM: `xlChart`). Types: "bar", "line", "pie", "scatter". |
| `pdf_export` | `path: str`, `output: str = ""` | Exportar cualquier documento Office (Word/Excel/PPT) a PDF usando COM `ExportAsFixedFormat`. |
| `excel_run_macro` | `path: str`, `macro_name: str` | Ejecutar macro de Excel vía COM `Application.Run`. |

**Tools:** `office_word_find_replace`, `office_excel_create_chart`, `office_pdf_export`, `office_excel_run_macro`

---

### BLOQUE 10 — Código: nueva capability `code.py`

**Capability:** `CodeCapability`, namespace `"code"`

| Action | Params | Descripción |
|--------|--------|-------------|
| `run_python` | `script: str`, `timeout: int = 30` | Ejecutar código Python en subproceso aislado (`python -c script`). Capturar stdout/stderr. |
| `run_node` | `script: str`, `timeout: int = 30` | Ejecutar JavaScript con Node.js. Verificar que `node` está en PATH. |
| `lint_python` | `path: str` | Ejecutar `flake8 path` o `ruff check path`. Devolver lista de errores. |
| `format_python` | `path: str` | Ejecutar `black path` o `ruff format path`. |
| `git_status` | `repo_path: str = "."` | Estado del repositorio git (wrapper semántico). |
| `git_diff` | `repo_path: str = "."`, `file: str = ""` | Diff del repositorio o de un archivo específico. |
| `git_log` | `repo_path: str = "."`, `max_count: int = 10` | Log de commits recientes. |
| `git_clone` | `url: str`, `dest: str = ""` | Clonar repositorio. |
| `git_push` | `repo_path: str = "."`, `remote: str = "origin"`, `branch: str = ""` | Push al remoto. |
| `git_pull` | `repo_path: str = "."` | Pull del remoto. |

**Tools:** `code_run_python`, `code_run_node`, `code_lint_python`, `code_format_python`, `code_git_status`, `code_git_diff`, `code_git_log`, `code_git_clone`, `code_git_push`, `code_git_pull`

---

### BLOQUE 11 — Base de datos: nueva capability `database.py`

**Capability:** `DatabaseCapability`, namespace `"database"`

| Action | Params | Descripción |
|--------|--------|-------------|
| `sqlite_query` | `db_path: str`, `sql: str`, `params: list = []` | Ejecutar SELECT en SQLite. Devolver filas como lista de dicts. |
| `sqlite_execute` | `db_path: str`, `sql: str`, `params: list = []` | Ejecutar INSERT/UPDATE/DELETE. Devolver rows affected. |
| `sqlite_create` | `db_path: str`, `schema_sql: str` | Crear base de datos y ejecutar schema. |
| `csv_query` | `path: str`, `query: str` | Query SQL sobre CSV usando `pandas` + `pandasql` o duckdb. Devolver resultados. |
| `csv_to_excel` | `path: str`, `output: str` | Convertir CSV a Excel usando pandas + openpyxl. |

**Tools:** `db_sqlite_query`, `db_sqlite_execute`, `db_sqlite_create`, `db_csv_query`, `db_csv_to_excel`

---

### BLOQUE 12 — Recordatorios (extender `scheduler.py` o nueva capability)

Agregar a `SchedulerCapability`:

| Action | Params | Descripción |
|--------|--------|-------------|
| `remind` | `message: str`, `delay_minutes: int` | Mostrar un toast de recordatorio después de N minutos. Implementar usando `threading.Timer` + `notifications.toast`. |

**Tool:** `scheduler_remind`

---

## Reglas generales para esta sesión

1. **Sin hardcode de rutas, nombres de app, o idiomas** — usar APIs del sistema o env vars.
2. **Dependencias opcionales** — si una lib no está instalada, devolver `ok=False` con `next_step_hint="pip install <lib>"`. Nunca lanzar ImportError al usuario.
3. **Seguridad** — registry_write y env_set requieren params explícitos, no shell strings. pdf_from_docx usa `shlex.quote` para paths.
4. **Timeout** — todas las operaciones externas (FFmpeg, LibreOffice, SMTP, winreg) con timeout máximo de 60s usando `run_with_kill` o `threading.Timer`.
5. **Tests** — un archivo de test por cada bloque nuevo (`tests/test_pdf.py`, `tests/test_email.py`, etc.). Mínimo 3 tests por capability. Usar `pytest.mark.skipif` para tests que requieren software externo (Outlook, FFmpeg, LibreOffice).
6. **probe_all_tools.py** — agregar al menos 1 caso por capability nueva al probe existente, usando el patrón ya establecido.
7. **Compact descriptions** — todas las tools nuevas deben tener entrada en `_COMPACT_TOOL_DESCRIPTIONS` con ≤12 palabras.
8. **main.py** — registrar todas las capabilities nuevas en `_build_registry()`.

---

## Resultado esperado

Al terminar la sesión:
- `probe_all_tools.py` corre y pasa todos los tests nuevos con LLM real
- `pytest` pasa la suite completa (sin regresiones)
- Carter puede manejar pedidos como:
  - "Envíame un email a X con el resumen de esta reunión"
  - "Extrae el texto del PDF en mi escritorio"
  - "Graba 5 segundos de audio y transcríbelo"
  - "Comprime la carpeta proyecto en un ZIP"
  - "¿Qué apps tengo instaladas que contienen 'Adobe'?"
  - "Haz ping a google.com y dime la latencia"
  - "Convierte este video MP4 a MP3"
  - "Crea un evento en el calendario para mañana a las 3pm"
  - "Ejecuta este script Python y muéstrame el output"
