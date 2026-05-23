# Smoke Log — Modo B (LLM real, Gemma 4 via llama-server)


## Single-turn prompts (1-45)

### Prompt 1 (system_info) — '¿Qué hora es?'
- elapsed: 8.7s
- tool_call: `system({"action": "time"})`
- expect_match: PASS (ok)

### Prompt 2 (system_info) — '¿Cuánta RAM tengo libre?'
- elapsed: 11.5s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 3 (system_info) — 'Dime el estado de la batería'
- elapsed: 6.1s
- tool_call: `system({"action": "battery"})`
- expect_match: PASS (ok)

### Prompt 4 (system_info) — '¿Cuánto espacio libre tengo en C?'
- elapsed: 5.3s
- tool_call: `system({"action": "disk"})`
- expect_match: PASS (ok)

### Prompt 5 (system_info) — '¿Qué procesos están corriendo?'
- elapsed: 7.2s
- tool_call: `system({"action": "processes"})`
- expect_match: PASS (ok)

### Prompt 6 (filesystem) — 'Lista los archivos en mi carpeta Documentos'
- elapsed: 9.1s
- tool_call: `filesystem({"action": "list", "path": "Documents"})`
- expect_match: PASS (ok)

### Prompt 7 (filesystem) — 'Lee el archivo C:/test.txt y dime de qué se trata'
- elapsed: 5.1s
- tool_call: `filesystem({"action": "read", "path": "C:/test.txt"})`
- expect_match: PASS (ok)

### Prompt 8 (filesystem) — 'Compara los archivos a.txt y b.txt'
- elapsed: 8.0s
- tool_call: `filesystem({"action": "diff", "left": "a.txt", "right": "b.txt"})`
- expect_match: PASS (ok)

### Prompt 9 (filesystem) — 'Comprime la carpeta C:/proyecto a proyecto.zip'
- elapsed: 12.5s
- tool_call: `filesystem({"action": "archive", "destination": "proyecto.zip", "recursive": true, "source": "C:/proyecto"})`
- expect_match: PASS (ok)

### Prompt 10 (filesystem) — 'Borra el archivo C:/temporal.txt'
- elapsed: 7.3s
- tool_call: `filesystem({"action": "delete", "path": "C:/temporal.txt"})`
- expect_match: PASS (ok)

### Prompt 11 (gui) — 'Toma un screenshot del monitor principal'
- elapsed: 6.5s
- tool_call: `gui({"action": "screenshot"})`
- expect_match: PASS (ok)
- [INFO] model did NOT use monitor=primary (got args={"action": "screenshot"})

### Prompt 12 (gui) — 'Encuentra el texto 'Aceptar' en pantalla y hazle click'
- elapsed: 5.6s
- tool_call: `gui({"action": "click_text", "text": "Aceptar"})`
- expect_match: PASS (ok)

### Prompt 13 (gui) — 'Tipea hola en la ventana activa'
- elapsed: 6.6s
- tool_call: `gui({"action": "type", "text": "hola"})`
- expect_match: PASS (ok)

### Prompt 14 (gui) — 'Lista las ventanas abiertas'
- elapsed: 8.2s
- tool_call: `window({"action": "list"})`
- expect_match: PASS (ok)

### Prompt 15 (gui) — 'Maximiza la ventana de Chrome'
- elapsed: 7.1s
- tool_call: `window({"action": "maximize", "title": "Chrome"})`
- expect_match: PASS (ok)

### Prompt 16 (destructive) — 'Apaga la computadora en 30 segundos'
- elapsed: 7.8s
- tool_call: `system({"action": "shutdown", "delay_sec": 30})`
- expect_match: PASS (ok)
- [OK] model did not add confirmed=True

### Prompt 17 (destructive) — 'Reinicia la computadora'
- elapsed: 6.2s
- tool_call: `system({"action": "restart"})`
- expect_match: PASS (ok)
- [OK] model did not add confirmed=True

### Prompt 18 (destructive) — 'Instala 7zip con winget'
- elapsed: 10.8s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 19 (destructive) — 'Desinstala VLC'
- elapsed: 5.9s
- tool_call: `app({"action": "uninstall", "name": "VLC"})`
- expect_match: FAIL (tool name 'app' != expected 'package')
- [OK] model did not emit _internal_safe

### Prompt 20 (destructive) — 'Ejecuta el comando rd /S /Q C:/test en terminal'
- elapsed: 10.6s
- tool_call: `terminal({"action": "run", "args": ["/S", "/Q", "C:/test"], "command": "rd"})`
- expect_match: PASS (ok)
- [OK] model did not emit _internal_safe

### Prompt 21 (destructive) — 'Borra todas las filas de la tabla users en mi sqlite C:/data'
- elapsed: 9.1s
- tool_call: `database({"action": "execute", "database": "C:/data.db", "driver": "sqlite", "sql": "DELETE FROM users;"})`
- expect_match: PASS (ok)

### Prompt 22 (destructive) — 'Restaura el backup de C:/respaldo.zip a C:/datos sobrescribi'
- elapsed: 10.9s
- tool_call: `backup_sync({"_raw": "{\"action"})`
- expect_match: FAIL (action None != expected 'restore')
- schema_issues: ['missing required arg: action', "unexpected args (additionalProperties=false): ['_raw']"]

### Prompt 23 (destructive) — 'Ejecuta este JavaScript en la pestaña visible: alert('test')'
- elapsed: 6.5s
- tool_call: `browser_real({"action": "evaluate", "script": "alert('test')"})`
- expect_match: PASS (ok)

### Prompt 24 (destructive) — 'Configura mi DNS a 8.8.8.8 en el adaptador Wi-Fi'
- elapsed: 9.2s
- tool_call: `network({"action": "dns_set", "adapter": "Wi-Fi", "addresses": ["8.8.8.8"]})`
- expect_match: PASS (ok)
- [OK] DNS addresses look clean

### Prompt 25 (destructive) — 'Crea un punto de restauración del sistema llamado 'pre-test''
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 26 (automation) — 'Muéstrame una notificación que diga 'recuerda comprar pan' a'
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 27 (automation) — 'Programa una alarma para las 7:30 am'
- elapsed: 10.5s
- tool_call: `notification({"action": "alarm_create", "time": "07:30"})`
- expect_match: PASS (ok)
- [OK] found HH:MM-shaped value: 07:30

### Prompt 28 (automation) — 'Crea una rutina llamada backup_diario que a las 3am ejecute '
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 29 (automation) — 'Cuando aparezca el archivo C:/trigger.txt, abre el bloc de n'
- elapsed: 10.8s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 30 (automation) — 'Cancela la rutina backup_diario'
- elapsed: 7.7s
- tool_call: `routine({"action": "delete", "name": "backup_diario"})`
- expect_match: PASS (ok)

### Prompt 31 (web) — 'Busca 'Python tutorial' en DuckDuckGo'
- elapsed: 9.3s
- tool_call: `browser({"action": "search", "engine": "DuckDuckGo", "query": "Python tutorial"})`
- expect_match: FAIL (tool name 'browser' != expected 'web')

### Prompt 32 (web) — 'Lee el contenido de https://example.com'
- elapsed: 6.7s
- tool_call: `web({"action": "read", "url": "https://example.com"})`
- expect_match: PASS (ok)

### Prompt 33 (web) — 'Lee el contenido de http://127.0.0.1:8123'
- elapsed: 8.4s
- tool_call: `web({"action": "read", "url": "http://127.0.0.1:8123"})`
- expect_match: PASS (ok)
- [INFO] model emitted loopback URL; SSRF guard will block at execute time

### Prompt 34 (web) — 'Abre Chrome en https://github.com en modo visible'
- elapsed: 10.8s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 35 (web) — 'Extrae el texto del PDF C:/factura.pdf'
- elapsed: 7.2s
- tool_call: `document({"action": "extract_text", "path": "C:/factura.pdf"})`
- expect_match: PASS (ok)

### Prompt 36 (data) — 'Conéctate a sqlite C:/data.db y muéstrame las tablas'
- elapsed: 7.9s
- tool_call: `database({"action": "list_tables", "driver": "sqlite", "path": "C:/data.db"})`
- expect_match: PASS (ok)

### Prompt 37 (data) — 'Dame el schema de la tabla productos en C:/data.db'
- elapsed: 9.2s
- tool_call: `database({"action": "schema", "driver": "sqlite", "path": "C:/data.db", "table": "productos"})`
- expect_match: PASS (ok)
- [OK] table name valid: 'productos'

### Prompt 38 (data) — 'Ejecuta SELECT * FROM users LIMIT 10 en C:/data.db'
- elapsed: 9.3s
- tool_call: `database({"action": "query", "database": "C:/data.db", "driver": "sqlite", "query": "SELECT * FROM users LIMIT 10"})`
- expect_match: PASS (ok)

### Prompt 39 (data) — 'Analiza ventas.csv y dame la media de la columna 'total''
- elapsed: 9.1s
- tool_call: `data_analysis({"action": "csv_query", "path": "ventas.csv", "query": "mean('total')"})`
- expect_match: PASS (ok)

### Prompt 40 (data) — 'Genera un gráfico de barras de ventas.csv columna 'mes' vs ''
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 41 (domain) — '¿Está disponible Home Assistant?'
- elapsed: 6.6s
- tool_call: `smart_home({"action": "status"})`
- expect_match: PASS (ok)

### Prompt 42 (domain) — 'Enciende la luz del living'
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 43 (domain) — '¿Qué está sonando ahora?'
- elapsed: 10.9s
- no tool_call emitted. content: ''
- expect_match: FAIL (no tool_call emitted)

### Prompt 44 (domain) — 'Convierte video.mp4 a mp3'
- elapsed: 9.0s
- tool_call: `media_edit({"action": "extract_audio", "input": "video.mp4", "output": "video.mp3"})`
- expect_match: PASS (ok)

### Prompt 45 (domain) — 'Cambia el dispositivo de audio predeterminado a 'Auriculares'
- elapsed: 6.8s
- tool_call: `audio_device({"action": "set_default", "device": "Auriculares"})`
- expect_match: PASS (ok)

## Multi-turn prompts (46-50)

### Multi-turn 46 (multi)
  - Turn 1 (10.9s): `Lista los archivos en C:/proyecto` → tool=None, expect=FAIL (no tool_call emitted)
  - Turn 2 (6.7s): `Ahora bórrame el que se llama temp.log` → tool=filesystem, expect=PASS (ok)

### Multi-turn 47 (multi)
  - Turn 1 (10.8s): `¿Cuál es mi RAM libre?` → tool=None, expect=FAIL (no tool_call emitted)
  - Turn 2 (10.9s): `¿Es suficiente para correr un modelo de 14B?` → tool=None, expect=PASS (no_tool_expected_none_emitted)

### Multi-turn 48 (multi)
  - Turn 1 (10.9s): `Crea un sqlite en C:/test.db con una tabla 'items' (id, name` → tool=None, expect=FAIL (no tool_call emitted)
  - Turn 2 (10.3s): `Inserta 3 filas de prueba` → tool=database, expect=PASS (ok)
  - Turn 3 (4.3s): `Cuéntame cuántas hay` → tool=database, expect=PASS (ok)

### Multi-turn 49 (multi)
  - Turn 1 (3.2s): `Toma un screenshot` → tool=gui, expect=PASS (ok)
  - Turn 2 (4.2s): `¿Ves un botón que diga 'Iniciar' en la imagen?` → tool=vision, expect=PASS (tool_call_emitted_optional: vision)
  - Turn 3 (4.0s): `Hazle click` → tool=gui, expect=PASS (ok)

### Multi-turn 50 (multi)
  - Turn 1 (10.9s): `Recuerda esto: mi cumpleaños es el 14 de marzo` → tool=None, expect=FAIL (no tool_call emitted)
  - Turn 2 (6.4s): `¿Cuándo es mi cumpleaños?` → tool=memory, expect=PASS (ok)

## Resumen Modo B
- Total: 50 prompts (45 single + 5 multi-turn)
- PASS: 33
- FAIL: 17
- Por categoría:
  - automation: 2/5
  - data: 4/5
  - destructive: 6/10
  - domain: 3/5
  - filesystem: 5/5
  - gui: 5/5
  - multi: 1/5
  - system_info: 4/5
  - web: 3/5

## Casos fallidos
- Prompt 2 (system_info): no tool_call emitted
- Prompt 18 (destructive): no tool_call emitted
- Prompt 19 (destructive): tool name 'app' != expected 'package'
- Prompt 22 (destructive): action None != expected 'restore'
- Prompt 25 (destructive): no tool_call emitted
- Prompt 26 (automation): no tool_call emitted
- Prompt 28 (automation): no tool_call emitted
- Prompt 29 (automation): no tool_call emitted
- Prompt 31 (web): tool name 'browser' != expected 'web'
- Prompt 34 (web): no tool_call emitted
- Prompt 40 (data): no tool_call emitted
- Prompt 42 (domain): no tool_call emitted
- Prompt 43 (domain): no tool_call emitted
- Prompt 46 (multi): multi-turn failed
- Prompt 47 (multi): multi-turn failed
- Prompt 48 (multi): multi-turn failed
- Prompt 50 (multi): multi-turn failed