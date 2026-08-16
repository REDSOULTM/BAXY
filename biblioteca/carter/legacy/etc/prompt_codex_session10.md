# Carter v2 — Sesión 10: Probe exhaustivo post-S9 (todas las tools)

## Contexto

Carter es un asistente de Windows con LLM (Qwen3-8B vía Ollama) que ejecuta herramientas reales.
La sesión 9 añadió ~63 tools nuevas. Esta sesión verifica con LLM real que **cada tool funciona
correctamente** — incluyendo las 53 ya existentes y todas las nuevas.

El resultado de esta sesión es un JSON de errores documentados que la sesión 11 usará para hacer fixes.

**Repo:** `Carter_v2/`
**Rama activa:** `rebuild/v2-from-scratch`

---

## Objetivo

Ampliar `probe_all_tools.py` para cubrir TODAS las tools post-S9.
Ejecutarlo completo con LLM real. Guardar resultados en `probe_session10_results.json`.
**No arreglar bugs aquí** — solo documentarlos con precisión.

---

## Estructura del probe existente

El probe ya tiene infraestructura completa. Solo hay que añadir casos nuevos.

```python
# Patrón de cada test en la lista TESTS:
{
    "id": "PDF-1",           # ID único: NAMESPACE-N
    "ns": "pdf",             # namespace
    "cat": "pdf",            # categoría para agrupación
    "input": "...",          # prompt en lenguaje natural al LLM
    "expect_tools": ["pdf_read_text"],   # tools que debe llamar
    "check": lambda r: _has_tool(r, "pdf_read_text") and _reply_not_empty(r),
    "desc": "Descripción corta del test",
    "skip": lambda: not _has_pdf_support(),  # opcional
}
```

Helpers disponibles sin cambios:
- `_has_tool(result, *names)` — verifica que el LLM llamó esas tools
- `_reply_has(*words)` — verifica que la respuesta contiene alguna palabra
- `_reply_not_empty(result)` — respuesta no vacía
- `_has_any_tool(result, names)` — al menos una de las tools fue llamada
- `_used_any_tool(result)` — se usó alguna tool

---

## Detección de condiciones (añadir al probe)

```python
def _has_pdf_support() -> bool:
    try:
        import pypdf
        return True
    except ImportError:
        return False

def _has_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None

def _has_whisper() -> bool:
    try:
        import whisper
        return True
    except ImportError:
        return False

def _has_outlook() -> bool:
    try:
        import win32com.client
        win32com.client.Dispatch("Outlook.Application")
        return True
    except Exception:
        return False

def _has_sounddevice() -> bool:
    try:
        import sounddevice
        return True
    except ImportError:
        return False

def _has_node() -> bool:
    import shutil
    return shutil.which("node") is not None

def _has_sqlite_test_db() -> bool:
    from pathlib import Path
    return (Path.home() / "carter_test.db").exists() or True  # always ok, sqlite3 built-in

def _has_pandas() -> bool:
    try:
        import pandas
        return True
    except ImportError:
        return False
```

---

## Casos de test a añadir — uno por bloque de S9

### BLOQUE PDF

```python
# PDF-1: Leer texto de PDF real
{
    "id": "PDF-1", "ns": "pdf", "cat": "pdf",
    "input": "Extrae el texto del primer PDF que encuentres en mi carpeta Documentos",
    "expect_tools": ["pdf_read_text"],
    "check": lambda r: _has_any_tool(r, ["pdf_read_text", "filesystem_search_files"]) and _reply_not_empty(r),
    "desc": "Leer texto de PDF",
    "skip": lambda: not _has_pdf_support(),
},
# PDF-2: Merge
{
    "id": "PDF-2", "ns": "pdf", "cat": "pdf",
    "input": "¿Puedes fusionar dos PDFs en uno? Describe qué herramienta usarías",
    "expect_tools": ["pdf_merge"],
    "check": lambda r: _has_tool(r, "pdf_merge") or _reply_has("pdf_merge", "merge", "fusionar"),
    "desc": "Tool pdf_merge conocida por el LLM",
    "skip": lambda: not _has_pdf_support(),
},
# PDF-3: Convertir DOCX a PDF
{
    "id": "PDF-3", "ns": "pdf", "cat": "pdf",
    "input": "Convierte el archivo informe.docx a PDF",
    "expect_tools": ["pdf_from_docx"],
    "check": lambda r: _has_any_tool(r, ["pdf_from_docx", "office_pdf_export"]) and _reply_not_empty(r),
    "desc": "Convertir DOCX a PDF",
    "skip": lambda: not _has_pdf_support(),
},
```

### BLOQUE EMAIL

```python
# EMAIL-1: Enviar email
{
    "id": "EMAIL-1", "ns": "email", "cat": "email",
    "input": "Envía un email a test@example.com con asunto 'Prueba' y cuerpo 'Hola'",
    "expect_tools": ["email_send"],
    "check": lambda r: _has_tool(r, "email_send"),
    "desc": "Routing a email_send",
},
# EMAIL-2: Leer bandeja
{
    "id": "EMAIL-2", "ns": "email", "cat": "email",
    "input": "Muéstrame mis últimos 5 emails",
    "expect_tools": ["email_read_inbox"],
    "check": lambda r: _has_tool(r, "email_read_inbox"),
    "desc": "Routing a email_read_inbox",
},
# EMAIL-3: Sin backend configurado — mensaje claro
{
    "id": "EMAIL-3", "ns": "email", "cat": "email",
    "input": "¿Puedo enviar emails con Carter sin Outlook?",
    "expect_tools": [],
    "check": lambda r: _reply_has("smtp", "SMTP", "configurar", "configure", "CARTER_EMAIL"),
    "desc": "Sin backend — hint de configuración",
},
```

### BLOQUE CALENDARIO

```python
# CAL-1: Listar eventos
{
    "id": "CAL-1", "ns": "calendar", "cat": "calendar",
    "input": "¿Qué eventos tengo esta semana?",
    "expect_tools": ["calendar_list_events"],
    "check": lambda r: _has_tool(r, "calendar_list_events"),
    "desc": "Routing a calendar_list_events",
},
# CAL-2: Crear evento
{
    "id": "CAL-2", "ns": "calendar", "cat": "calendar",
    "input": "Crea una reunión mañana a las 3pm llamada 'Revisión de proyecto'",
    "expect_tools": ["calendar_create_event"],
    "check": lambda r: _has_tool(r, "calendar_create_event"),
    "desc": "Routing a calendar_create_event",
},
```

### BLOQUE AUDIO/VIDEO

```python
# MED-1: Transcribir audio
{
    "id": "MEDF-1", "ns": "media_files", "cat": "media_files",
    "input": "Transcribe el archivo audio.mp3 de mi escritorio",
    "expect_tools": ["media_audio_transcribe"],
    "check": lambda r: _has_tool(r, "media_audio_transcribe"),
    "desc": "Routing a media_audio_transcribe",
    "skip": lambda: not _has_whisper(),
},
# MED-2: Convertir video
{
    "id": "MEDF-2", "ns": "media_files", "cat": "media_files",
    "input": "Convierte el video video.mp4 a MP3",
    "expect_tools": ["media_video_extract_audio"],
    "check": lambda r: _has_any_tool(r, ["media_video_extract_audio", "media_video_convert"]),
    "desc": "Extraer audio de video",
    "skip": lambda: not _has_ffmpeg(),
},
# MED-3: Grabar audio
{
    "id": "MEDF-3", "ns": "media_files", "cat": "media_files",
    "input": "Graba 5 segundos de audio del micrófono y guárdalo como grabacion.wav",
    "expect_tools": ["media_audio_record"],
    "check": lambda r: _has_tool(r, "media_audio_record"),
    "desc": "Routing a media_audio_record",
    "skip": lambda: not _has_sounddevice(),
},
# MED-4: Redimensionar imagen
{
    "id": "MEDF-4", "ns": "media_files", "cat": "media_files",
    "input": "Redimensiona la imagen foto.jpg a 800x600 píxeles",
    "expect_tools": ["media_image_resize"],
    "check": lambda r: _has_tool(r, "media_image_resize"),
    "desc": "Routing a media_image_resize",
},
```

### BLOQUE FILESYSTEM (nuevas acciones)

```python
# FSX-1: Comprimir ZIP
{
    "id": "FSX-1", "ns": "filesystem_ext", "cat": "filesystem",
    "input": "Comprime la carpeta Documentos en un archivo backup.zip",
    "expect_tools": ["filesystem_zip"],
    "check": lambda r: _has_tool(r, "filesystem_zip"),
    "desc": "Routing a filesystem_zip",
},
# FSX-2: Descomprimir
{
    "id": "FSX-2", "ns": "filesystem_ext", "cat": "filesystem",
    "input": "Descomprime el archivo datos.zip en la carpeta temporal",
    "expect_tools": ["filesystem_unzip"],
    "check": lambda r: _has_tool(r, "filesystem_unzip"),
    "desc": "Routing a filesystem_unzip",
},
# FSX-3: Añadir texto a archivo
{
    "id": "FSX-3", "ns": "filesystem_ext", "cat": "filesystem",
    "input": "Añade la línea 'Nueva entrada' al final del archivo log.txt",
    "expect_tools": ["filesystem_append_text"],
    "check": lambda r: _has_tool(r, "filesystem_append_text"),
    "desc": "Routing a filesystem_append_text",
},
# FSX-4: Renombrar
{
    "id": "FSX-4", "ns": "filesystem_ext", "cat": "filesystem",
    "input": "Renombra el archivo viejo.txt a nuevo.txt",
    "expect_tools": ["filesystem_rename"],
    "check": lambda r: _has_any_tool(r, ["filesystem_rename", "filesystem_move"]),
    "desc": "Routing a filesystem_rename",
},
# FSX-5: Tamaño de carpeta
{
    "id": "FSX-5", "ns": "filesystem_ext", "cat": "filesystem",
    "input": "¿Cuánto ocupa la carpeta Descargas?",
    "expect_tools": ["filesystem_get_size"],
    "check": lambda r: _has_any_tool(r, ["filesystem_get_size", "filesystem_get_stat"]) and _reply_not_empty(r),
    "desc": "Tamaño de directorio",
},
```

### BLOQUE RED (nuevas acciones)

```python
# NETX-1: Ping
{
    "id": "NETX-1", "ns": "network_ext", "cat": "network",
    "input": "Haz ping a google.com y dime la latencia",
    "expect_tools": ["network_ping"],
    "check": lambda r: _has_tool(r, "network_ping") and _reply_not_empty(r),
    "desc": "Ping a host",
},
# NETX-2: IP pública
{
    "id": "NETX-2", "ns": "network_ext", "cat": "network",
    "input": "¿Cuál es mi IP pública?",
    "expect_tools": ["network_get_public_ip"],
    "check": lambda r: _has_tool(r, "network_get_public_ip") and _reply_not_empty(r),
    "desc": "IP pública",
},
# NETX-3: Port check
{
    "id": "NETX-3", "ns": "network_ext", "cat": "network",
    "input": "¿Está abierto el puerto 443 de google.com?",
    "expect_tools": ["network_port_check"],
    "check": lambda r: _has_tool(r, "network_port_check") and _reply_not_empty(r),
    "desc": "Verificar puerto TCP",
},
# NETX-4: DNS lookup
{
    "id": "NETX-4", "ns": "network_ext", "cat": "network",
    "input": "¿Cuál es la IP de github.com?",
    "expect_tools": ["network_dns_lookup"],
    "check": lambda r: _has_any_tool(r, ["network_dns_lookup", "network_get_public_ip"]) and _reply_not_empty(r),
    "desc": "DNS lookup",
},
```

### BLOQUE SISTEMA (nuevas acciones)

```python
# SYSX-1: Apps instaladas
{
    "id": "SYSX-1", "ns": "system_ext", "cat": "system",
    "input": "¿Qué aplicaciones tengo instaladas que contienen 'Adobe'?",
    "expect_tools": ["system_list_installed_apps"],
    "check": lambda r: _has_tool(r, "system_list_installed_apps") and _reply_not_empty(r),
    "desc": "Listar apps instaladas filtradas",
},
# SYSX-2: Apps de inicio
{
    "id": "SYSX-2", "ns": "system_ext", "cat": "system",
    "input": "¿Qué programas arrancan con Windows?",
    "expect_tools": ["system_get_startup_apps"],
    "check": lambda r: _has_tool(r, "system_get_startup_apps") and _reply_not_empty(r),
    "desc": "Apps de inicio de Windows",
},
# SYSX-3: Variable de entorno
{
    "id": "SYSX-3", "ns": "system_ext", "cat": "system",
    "input": "¿Cuál es el valor de la variable de entorno PATH?",
    "expect_tools": ["system_env_get"],
    "check": lambda r: _has_any_tool(r, ["system_env_get", "terminal_run_powershell"]) and _reply_not_empty(r),
    "desc": "Leer variable de entorno",
},
# SYSX-4: Servicios en ejecución
{
    "id": "SYSX-4", "ns": "system_ext", "cat": "system",
    "input": "Lista los servicios de Windows que están corriendo ahora",
    "expect_tools": ["system_get_running_services"],
    "check": lambda r: _has_any_tool(r, ["system_get_running_services", "terminal_run_powershell"]) and _reply_not_empty(r),
    "desc": "Servicios de Windows en ejecución",
},
# SYSX-5: Registro de Windows (lectura)
{
    "id": "SYSX-5", "ns": "system_ext", "cat": "system",
    "input": "Lee el valor ProductName del registro en HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
    "expect_tools": ["system_registry_read"],
    "check": lambda r: _has_any_tool(r, ["system_registry_read", "terminal_run_powershell"]) and _reply_not_empty(r),
    "desc": "Leer registro de Windows",
},
```

### BLOQUE VENTANAS (nuevas acciones)

```python
# WINX-1: Mover ventana
{
    "id": "WINX-1", "ns": "window_ext", "cat": "window",
    "input": "Mueve la ventana del Bloc de notas a la posición 100, 100",
    "expect_tools": ["window_move"],
    "check": lambda r: _has_tool(r, "window_move"),
    "desc": "Mover ventana a coordenadas",
},
# WINX-2: Redimensionar ventana
{
    "id": "WINX-2", "ns": "window_ext", "cat": "window",
    "input": "Cambia el tamaño de la ventana de Chrome a 1280x720",
    "expect_tools": ["window_resize"],
    "check": lambda r: _has_tool(r, "window_resize"),
    "desc": "Redimensionar ventana",
},
# WINX-3: Pin on top
{
    "id": "WINX-3", "ns": "window_ext", "cat": "window",
    "input": "Pon la ventana de la calculadora siempre encima de todo",
    "expect_tools": ["window_pin_on_top"],
    "check": lambda r: _has_tool(r, "window_pin_on_top"),
    "desc": "Always on top",
},
```

### BLOQUE CÓDIGO

```python
# CODE-1: Ejecutar Python
{
    "id": "CODE-1", "ns": "code", "cat": "code",
    "input": "Ejecuta este código Python: print(2 + 2)",
    "expect_tools": ["code_run_python"],
    "check": lambda r: _has_any_tool(r, ["code_run_python", "terminal_run_powershell"]) and _reply_has("4"),
    "desc": "Ejecutar código Python simple",
},
# CODE-2: Git status
{
    "id": "CODE-2", "ns": "code", "cat": "code",
    "input": "¿Cuál es el estado del repositorio git en C:/Users?",
    "expect_tools": ["code_git_status"],
    "check": lambda r: _has_any_tool(r, ["code_git_status", "terminal_git_run", "terminal_run_command"]) and _reply_not_empty(r),
    "desc": "Git status via code capability",
},
# CODE-3: Ejecutar Node
{
    "id": "CODE-3", "ns": "code", "cat": "code",
    "input": "Ejecuta este JavaScript: console.log('hola mundo')",
    "expect_tools": ["code_run_node"],
    "check": lambda r: _has_any_tool(r, ["code_run_node", "terminal_run_command"]) and _reply_not_empty(r),
    "desc": "Ejecutar JavaScript con Node",
    "skip": lambda: not _has_node(),
},
```

### BLOQUE BASE DE DATOS

```python
# DB-1: Crear y consultar SQLite
{
    "id": "DB-1", "ns": "database", "cat": "database",
    "input": "Crea una base de datos SQLite en el escritorio llamada prueba.db con una tabla usuarios(id, nombre)",
    "expect_tools": ["db_sqlite_create"],
    "check": lambda r: _has_any_tool(r, ["db_sqlite_create", "db_sqlite_execute"]),
    "desc": "Crear base de datos SQLite",
},
# DB-2: Query SQLite
{
    "id": "DB-2", "ns": "database", "cat": "database",
    "input": "Consulta SELECT * FROM usuarios en la base de datos prueba.db del escritorio",
    "expect_tools": ["db_sqlite_query"],
    "check": lambda r: _has_tool(r, "db_sqlite_query"),
    "desc": "Query SELECT en SQLite",
},
# DB-3: CSV a Excel
{
    "id": "DB-3", "ns": "database", "cat": "database",
    "input": "Convierte el archivo datos.csv a Excel",
    "expect_tools": ["db_csv_to_excel"],
    "check": lambda r: _has_any_tool(r, ["db_csv_to_excel", "office_excel_open"]),
    "desc": "Convertir CSV a Excel",
    "skip": lambda: not _has_pandas(),
},
```

### BLOQUE RECORDATORIOS

```python
# REM-1: Recordatorio con delay
{
    "id": "REM-1", "ns": "scheduler_remind", "cat": "scheduler",
    "input": "Recuérdame en 2 minutos que tengo una reunión",
    "expect_tools": ["scheduler_remind"],
    "check": lambda r: _has_any_tool(r, ["scheduler_remind", "scheduler_schedule_task"]) and _reply_not_empty(r),
    "desc": "Recordatorio por timer",
},
```

### BLOQUE OFFICE (nuevas acciones)

```python
# OFFX-1: Exportar a PDF
{
    "id": "OFFX-1", "ns": "office_ext", "cat": "office",
    "input": "Exporta el documento Word informe.docx a PDF",
    "expect_tools": ["office_pdf_export"],
    "check": lambda r: _has_any_tool(r, ["office_pdf_export", "pdf_from_docx"]),
    "desc": "Exportar Office a PDF",
},
# OFFX-2: Buscar y reemplazar en Word
{
    "id": "OFFX-2", "ns": "office_ext", "cat": "office",
    "input": "En el documento Word contrato.docx reemplaza 'Empresa ABC' por 'Empresa XYZ'",
    "expect_tools": ["office_word_find_replace"],
    "check": lambda r: _has_tool(r, "office_word_find_replace"),
    "desc": "Find & replace en Word",
},
```

---

## Runner — actualizar para incluir `skip` dinámico

El runner actual ya soporta `skip`. Verificar que funciona con lambdas:

```python
# En el bucle principal del runner:
skip_fn = test.get("skip")
if skip_fn and skip_fn():
    results.append({**test, "status": "SKIP", "reason": "condition not met"})
    continue
```

---

## Salida esperada

Al terminar, el probe debe:

1. Imprimir resumen por categoría:
```
PDF       3/3 PASS
EMAIL     2/3 PASS  1 FAIL
CALENDAR  2/2 PASS
...
TOTAL: XX/YY PASS  (ZZ%)
```

2. Guardar `probe_session10_results.json` con estructura:
```json
{
  "timestamp": "2026-04-20T...",
  "total": 90,
  "passed": 85,
  "failed": 4,
  "skipped": 1,
  "failures": [
    {
      "id": "EMAIL-1",
      "desc": "Routing a email_send",
      "input": "Envía un email...",
      "tools_called": ["notify_toast"],
      "reply": "...",
      "reason": "LLM llamó notify_toast en vez de email_send"
    }
  ]
}
```

3. Para cada FAIL, imprimir:
   - ID y descripción
   - Tools que el LLM realmente llamó
   - Primeras 200 chars de la respuesta
   - Categoría del fallo: `ROUTING` (LLM eligió tool equivocada) | `CRASH` (tool lanzó excepción) | `WRONG_OUTPUT` (tool corrió pero resultado incorrecto) | `NO_TOOL` (LLM no usó ninguna tool)

---

## Reglas

1. **No arreglar bugs** en esta sesión — solo documentarlos con precisión en el JSON.
2. **No modificar** capabilities existentes — solo añadir tests al probe.
3. Si una tool falla con excepción, capturarla y marcar como `CRASH` con el traceback completo.
4. Correr el probe completo una vez y guardar resultados. No re-intentar tests fallidos.
5. Al final, hacer commit con mensaje: `probe(s10): exhaustive all-tools probe post-s9`.
