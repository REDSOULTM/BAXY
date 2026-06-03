# Local Jarvis Design Notes

Objetivo: mantener el agente totalmente local y centrado en texto/tools. Del
repo Jarvis copiado solo se tomaron patrones de arquitectura, no auth, voz,
camara, orb movil ni UI de voz.

## Patrones Adoptados

- Tool catalog compacto: tools compuestas por dominio en vez de decenas de
  funciones sueltas.
- Estado operacional: recursos abiertos por el agente, checkpoints y planes de
  cleanup.
- Planner deterministico por turno: divide misiones compuestas y agrega hints
  privados al prompt para que Gemma no corte la tarea a mitad.
- Timeline/evaluacion: las trazas JSONL ahora incluyen `mission_status`.
- Dependencias explicitas: cuando falta auth o una dependencia como Playwright,
  la tool devuelve `needs_user` o `needs_dependency` en vez de simular exito.
- Browser persistente: Playwright mantiene sesiones por `session_id` y puede
  conectarse por CDP si el navegador fue arrancado con remote debugging.
- OCR local: Tesseract entrega texto y coordenadas para `vision(ocr)` y
  `gui(click_text)`.
- RAG local: SQLite FTS5 para documentos de texto, sin embeddings externos.
- Safety configurable: confirmaciones pendientes en `state.json` cuando
  `GEMMA4_AGENT_SAFETY=true`.

## Fuentes Base

- Windows language list: `Get-WinUserLanguageList` y
  `Set-WinUserLanguageList`.
  <https://learn.microsoft.com/powershell/module/international/set-winuserlanguagelist>
- Environment scopes: scopes `Process`, `User`, `Machine` de
  `[Environment]::SetEnvironmentVariable`.
  <https://learn.microsoft.com/dotnet/api/system.environment.setenvironmentvariable>
- Registry: `reg query/export/import/add/delete`; todo `add/delete` intenta
  exportar backup antes.
  <https://learn.microsoft.com/windows-server/administration/windows-commands/reg>
- Downloads: `Invoke-WebRequest`, `Get-FileHash`, `Get-AuthenticodeSignature`.
  <https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/invoke-webrequest>
  <https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/get-filehash>
- Email/reminders cloud: Microsoft Graph `sendMail`/To Do/Calendar requieren
  token; sin token se reporta `NEEDS_USER`.
  <https://learn.microsoft.com/graph/api/user-sendmail>
  <https://learn.microsoft.com/graph/todo-concept-overview>
- Browser real: Playwright `BrowserContext`; se usa headless por defecto para
  no interrumpir el escritorio.
  <https://playwright.dev/python/docs/api/class-browsercontext>
- OCR: Tesseract CLI TSV para coordenadas de palabras.
  <https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html>
- RAG local: SQLite FTS5.
  <https://www.sqlite.org/fts5.html>
- Cleanup/rollback: patron de compensating actions/Saga; no se promete rollback
  perfecto cuando una accion no tiene compensacion fiable.
  Garcia-Molina & Salem, "Sagas", 1987.

## Omitido A Proposito

- Authentication propia email/password.
- Voice input/output.
- Draggable camera.
- Floating mobile orb.
- Full-screen voice mode.
- Camara/mic como tools de primer nivel.

Estas capas se pueden agregar despues, pero no pertenecen al nucleo local de
texto/tools que necesitamos estabilizar primero.
