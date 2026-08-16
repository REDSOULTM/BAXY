# Tareas por hacer

Backlog pendiente para continuar la paridad/superioridad de Carter frente a OpenClaw. No ejecutar ahora; dejar como referencia para próximos ciclos.

## 1. Documentar integraciones externas

Crear una guía práctica para configurar los gateways ya implementados.

Archivo sugerido:
- `Carter_v2/docs/integraciones.md`

Debe cubrir:
- Slack:
  - Variables: `CARTER_SLACK_GATEWAY`, `CARTER_SLACK_SIGNING_SECRET`, `CARTER_SLACK_BOT_TOKEN`, `CARTER_SLACK_HOST`, `CARTER_SLACK_PORT`.
  - Endpoints: `/slack/events`, `/slack/command`.
  - Uso con ngrok o Cloudflare Tunnel.
- Discord:
  - Variables: `CARTER_DISCORD_GATEWAY`, `CARTER_DISCORD_PUBLIC_KEY`, `CARTER_DISCORD_APPLICATION_ID`, `CARTER_DISCORD_HOST`, `CARTER_DISCORD_PORT`.
  - Endpoint: `/discord/interactions`.
  - Dependencia opcional: `pip install pynacl` para validar firmas Ed25519.
- Telegram:
  - Variables: `CARTER_TELEGRAM_BOT_TOKEN`, `CARTER_TELEGRAM_ALLOWED_IDS`.
- HTTP local:
  - Variables: `CARTER_HTTP_GATEWAY`, `CARTER_HTTP_HOST`, `CARTER_HTTP_PORT`.
  - Endpoint: `POST /message`.
- Extension Relay:
  - Variables: `CARTER_EXTENSION_RELAY`, `CARTER_EXTENSION_RELAY_HOST`, `CARTER_EXTENSION_RELAY_PORT`, `CARTER_EXTENSION_RELAY_DIR`.
  - Cómo cargar la extensión unpacked en Chrome/Edge.

## 2. CLI para arrancar/parar gateways

Agregar comandos administrativos para manejar interfaces sin depender de variables de entorno manuales.

Archivos a modificar:
- `Carter_v2/src/carter_v2/cli.py`
- `Carter_v2/src/carter_v2/interfaces/slack.py`
- `Carter_v2/src/carter_v2/interfaces/discord.py`
- `Carter_v2/src/carter_v2/interfaces/extension_relay.py`

Comandos deseados:
- `python -m carter_v2.cli admin gateways status`
- `python -m carter_v2.cli admin gateways slack start`
- `python -m carter_v2.cli admin gateways discord start`
- `python -m carter_v2.cli admin gateways extension-relay start --launch`
- `python -m carter_v2.cli admin gateways stop`

Nota técnica:
- Para procesos persistentes reales, probablemente conviene crear un supervisor local simple o integrarlo con tareas programadas de Windows.
- Evitar depender de Node/TypeScript.

## 3. UI local de administración

Crear una UI web local, servida por Carter, para administrar estado sin usar solo slash commands o herramientas LLM.

Archivos sugeridos:
- `Carter_v2/src/carter_v2/interfaces/admin_ui.py`
- `Carter_v2/src/carter_v2/interfaces/admin_static/`
- `Carter_v2/src/carter_v2/main.py`

Pantallas mínimas:
- Skills:
  - listar
  - leer
  - validar
  - refrescar
- Memory:
  - buscar
  - ver `MEMORY.md`
  - ejecutar `memory_dream_preview`
  - ejecutar `memory_dream`
- Heartbeat:
  - leer `HEARTBEAT.md`
  - editar
  - añadir task
  - wake manual
- Queue:
  - ver `pending/running/done/error`
  - reintentar job
  - ver payload/respuesta
- Gateways:
  - estado de HTTP, Telegram, Slack, Discord, Extension Relay

Restricciones:
- Python stdlib primero.
- Si se usa frontend, mantenerlo como HTML/CSS/JS estático servido por Carter.
- Escuchar solo en `127.0.0.1` por defecto.

## 4. Endurecer seguridad de canales

Antes de usar Slack/Discord fuera de una red local:
- Requerir firma válida por defecto.
- Rechazar requests sin firma salvo modo desarrollo explícito.
- Añadir allowlist de Slack teams/channels/users.
- Añadir allowlist de Discord guilds/channels/users.
- Registrar auditoría por job en `jobs.sqlite3` y `.runs.jsonl`.
- Revisar interacción con `CARTER_REQUIRE_APPROVAL=1`, porque aprobación CLI bloquea canales desatendidos.

Archivos relevantes:
- `Carter_v2/src/carter_v2/interfaces/slack.py`
- `Carter_v2/src/carter_v2/interfaces/discord.py`
- `Carter_v2/src/carter_v2/session/policy.py`

## 5. Extension Relay: completar modo operativo

El relay mínimo ya existe. Pendientes:
- Añadir instalación guiada desde CLI.
- Detectar clientes conectados y mostrar instrucciones si no hay ninguno.
- Agregar operaciones relay:
  - `navigate`
  - `click`
  - `fill`
  - screenshot vía `chrome.tabs.captureVisibleTab` si se mueve lógica al background worker.
- Separar permisos de lectura y escritura.
- Añadir token local opcional para evitar que cualquier página pueda hablar con el relay.

Archivos relevantes:
- `Carter_v2/src/carter_v2/interfaces/extension_relay.py`
- `Carter_v2/src/carter_v2/capabilities/web.py`
- `Carter_v2/src/carter_v2/adapters/tools.py`

## 6. Cola persistente: worker de recuperación al arranque

La cola SQLite ya persiste jobs. Falta robustecer recuperación:
- Reprocesar jobs `pending` de Slack/Discord al arrancar aunque no entre un nuevo request.
- Agregar comando `admin queue drain --source slack|discord`.
- Agregar límite de reintentos.
- Guardar `attempt_count`, `last_error`, `next_attempt_ts`.
- Evitar loops infinitos en jobs que fallan siempre.

Archivos relevantes:
- `Carter_v2/src/carter_v2/session/store.py`
- `Carter_v2/src/carter_v2/interfaces/slack.py`
- `Carter_v2/src/carter_v2/interfaces/discord.py`
- `Carter_v2/src/carter_v2/cli.py`

## 7. Pruebas futuras

Agregar tests de integración sin tocar APIs externas reales:
- Slack Events API url verification.
- Slack slash command con `response_url` mockeada.
- Discord PING e interaction deferred response.
- Extension Relay poll/result end-to-end con HTTP local.
- CLI admin para gateways.
- Queue retry con límite de intentos.

Comando base:

```powershell
$env:PYTHONPATH='src'; pytest -q
```

---

## 8. Telegram: chunking, /status y media

El polling ya funciona. Pendientes:

- Partir mensajes largos en chunks de ≤4096 caracteres (límite Telegram).
- Soportar `/status` como comando Telegram que responde con el estado de la sesión actual.
- Enviar imágenes/screenshots capturados por Carter directamente al chat.
- Allowlist de IDs de usuario via `CARTER_TELEGRAM_ALLOWED_IDS` (ya existe la variable, verificar que se aplica correctamente en el polling loop).

Archivos relevantes:
- `Carter_v2/src/carter_v2/interfaces/telegram.py`

---

## 9. Aprobación de tools vía Telegram

El sistema de approval ya existe para CLI (`CARTER_REQUIRE_APPROVAL=1`) pero bloquea la ejecución esperando `input()`, lo que rompe canales desatendidos como Telegram.

Pendiente:
- Añadir callback de aprobación asíncrono: cuando una tool requiere aprobación, Carter envía un mensaje Telegram con botones inline (Sí / No).
- Registrar la respuesta y continuar o abortar el turn.
- Conectar con `set_approval_callback()` en `session/policy.py`.

Archivos relevantes:
- `Carter_v2/src/carter_v2/session/policy.py`
- `Carter_v2/src/carter_v2/interfaces/telegram.py`
- `Carter_v2/src/carter_v2/main.py`

---

## 10. Skill hot-reload por filesystem watcher

Actualmente las skills se recargan solo cuando se llama `refresh_file_skills()` explícitamente (en arranque o via `skill_refresh`). Si el usuario edita un SKILL.md en disco, Carter no lo detecta hasta el siguiente arranque.

Pendiente:
- Añadir un watcher ligero (usando `watchdog` o polling manual cada N segundos en el hilo del ProactiveMonitor) que detecte cambios en los directorios de skills.
- Llamar `skills.refresh_file_skills()` automáticamente cuando detecte cambios.
- Notificar al usuario via `AlertQueue` que una skill fue recargada.

Archivos relevantes:
- `Carter_v2/src/carter_v2/session/proactive.py`
- `Carter_v2/src/carter_v2/session/skills.py`

---

## 11. qwen3:14b: modo thinking para planning complejo

Actualmente `think=False` en todos los turnos de tool-calling (necesario para evitar `content=""` vacío). Pero para tareas de planificación compleja sin tools (razonamiento puro), el modelo podría beneficiarse de thinking activado.

Pendiente:
- Detectar cuándo un turno no va a usar tools (consultas complejas, planificación, razonamiento).
- Activar `think=True` solo en esos turnos.
- Ya existe `_THINKING_HINT` en `agent.py` pero no se usa sistemáticamente.
- Evaluar si `qwen3:14b` con thinking mejora la calidad de respuestas en esos casos.

Archivos relevantes:
- `Carter_v2/src/carter_v2/turn/agent.py` (ver `_THINKING_HINT` y `_is_qwen3()`)

---

## 12. Durabilidad del lane queue: recuperación ante crash

Si Carter se cierra abruptamente mientras ejecuta un turno (Ctrl+C duro, BSOD, etc.), el job en curso se pierde silenciosamente. La `PersistentJobQueue` SQLite ya persiste jobs de Slack/Discord, pero el `SessionLaneQueue` in-memory no tiene recuperación.

Pendiente:
- Registrar el turn en curso en `jobs.sqlite3` antes de ejecutarlo.
- Al arrancar, detectar jobs `running` huérfanos y marcarlos como `error` o reintentarlos.
- Añadir `attempt_count` y `last_error` a la tabla `jobs`.

Archivos relevantes:
- `Carter_v2/src/carter_v2/session/store.py`

---

## 13. CDP: allocador de puertos por perfil

Actualmente los perfiles Chromium CDP usan puertos fijos configurados manualmente. Si dos perfiles intentan usar el mismo puerto, falla silenciosamente.

Pendiente:
- Implementar un allocador de puertos: asignar un puerto estable y único por nombre de perfil (ej. hash del nombre mod rango).
- Persistir la asignación en un JSON simple en `~/.carter/cdp_ports.json`.
- Detectar conflictos y reasignar automáticamente.

Archivos relevantes:
- `Carter_v2/src/carter_v2/capabilities/web.py`
- `Carter_v2/src/carter_v2/adapters/tools.py` (ver `web_profile_use`)

