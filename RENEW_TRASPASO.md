# BAXY Renew — traspaso a un chat nuevo (2026-10-15)

Rama `baxy-renew`, worktree `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew`. Último commit al escribir esto:
`6eba9dfb` (voz conectada). La transcripción completa del chat anterior está en
`C:\Users\usuario\.claude\projects\c--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo\3b9a0154-01df-432e-b70a-2765d76906d6.jsonl`.

## La misión, en palabras del dueño

BAXY = el modelo puro (Qwen3.5-4B) + las herramientas y el ecosistema de BAXY, optimizado al máximo para ese modelo.

- **Sin código que ayude al modelo:** nada de regex, reglas semánticas, guardias, vetos ni sobreingeniería.
- **Las mejoras vienen sólo de** la presentación (prompt del sistema, descripciones de herramientas, formato), el
  protocolo y la inferencia.
- **Límite honesto:** lo que el modelo no logre se acepta como límite; BAXY nunca dice algo falso.
- **Regla vital:** antes de implementar cualquier cosa, investigarla con papers, documentación oficial y experiencia
  de usuarios. Nunca improvisar.
- **Ciclo:** lanzar subagentes que auditen, arreglar, medir y re-auditar, hasta que no encuentren nada.
- **Recursos:** como máximo 4 GB de VRAM y 4 GB de RAM.

Decisiones del dueño, tomadas con casillas de opciones:

| Tema | Decisión |
|---|---|
| Multipaso | Bucle nativo |
| Pedido imposible | Decir que no lo hace |
| Volumen sin cantidad | Que decida el modelo |
| Voz | Primero «después»; el 2026-10-15 pidió conectar la wake word y la transcripción (hecho, ver abajo) |

## Qué es Renew hoy

- **Mente (`src/baxy_mind/`):** quedan `__main__.py`, `llm_server.py`, `mind.py`, `protocol.py`, `voice.py` y `data/`.
  Se borraron 142 módulos.
- **Servidor del modelo:** `llama-server` b11609 con `--jinja --reasoning off`, dos huecos (0 = decidir,
  1 = redactar) y `-kvu`.
- **Catálogo:** prefijo de unos 38,9k tokens. Las descripciones van en inglés, en
  `data/tool_descriptions.en.v1.json`, con el formato «Use when / Do not use when / Examples».
- **Bucle nativo:** `turn.continue`, con los resultados como mensajes `role:"tool"`, hasta 6 pasos, y el texto final
  lo escribe el modelo.
- **Lo que se queda en la App (honestidad):** el catálogo tipado, el kernel (riesgo y confirmación), el journal, la
  verificación del proveedor y el enmascarado de datos sensibles.
- **App:** sin atajos, vetos ni redacciones fijas. La lógica del bucle está en `MainWindowViewModel.cs`, en
  `RunNativeToolLoopAsync`, `CaptureLoopStepAsync`, `NextLoopDecisionAsync` y `ResumeAfterConfirmationAsync`.

**Arranque:** `scripts\run_renew.cmd`. Fija las rutas de este PC, compila si hace falta y lanza la App.

- Los modelos están en el M.2 `F:`, no en el HDD `D:`.
- El registro de turnos de la mente está en `%LOCALAPPDATA%\BAXY\renew\turns.jsonl`.

**Banco:** `F:\BAXYeval\renew_bench\bench.py` (90 casos en `cases.json`).

| Corrida | Resultado | p50 de la decisión |
|---|---|---|
| Mejor de práctica, `en02v2` | 85/90 | 0,74 s |
| `HOLD-final` | 53/60 | 0,77 s |

El holdout (`holdout.json`, 60 casos) **ya se usó**: no se ajusta nada mirándolo. La ronda 1 (`bd6a4ba3`) **no se
midió todavía**; corre `py -3.12 -X utf8 bench.py r1 --desc en --temp 0.2`.

## Voz (hecho el 2026-10-15)

**Qué hace `src/baxy_mind/voice.py`:**

- Cadena: micrófono → wake word k4 (`WakewordBaxy/models/final/baxy-wake-k4`, umbral 0,5) → Parakeet Ultra int8
  (`D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli`). Todo en CPU, en un hilo propio.
- La segmentación es la de `WakewordBaxy/probar_baxy.py`.
- La llamada «Baxy» se quita **por tiempo, no por texto**: se descartan las palabras de Ultra que empezaron más de
  0,25 s antes del disparo. Medido con las grabaciones del dueño: «Baxy» empieza entre 0,5 y 0,75 s antes del disparo.
- Hace falta quitarla porque la confirmación de riesgo de la App sólo acepta un «sí» limpio.

**Protocolo:**

- La mente atiende `voice.start` (modos `wake` o `direct`), `voice.stop`, `voice.status` y `voice.cancel`.
- Envía `voice.transcript` y los eventos `voice.event` `wake_detected`, `partial` y `state`.
- **No hay TTS:** el hello no ofrece `voice.speak` y la App no le pide hablar.
- `protocol.write_message` escribe con un lock.

**Verificado:**

- Con las grabaciones reales del dueño, pasadas como si fueran el micrófono:
  - «Baxi, abre Steam.» → «abre Steam.»
  - «Hola. Maxi. Abre Spotify and Pause.» → «Abre Spotify and Pause.»
  - Un «Baxi» suelto → no envía nada.
  - El modo directo transcribe una orden y vuelve a esperar «Baxy».
- La App lanzada publica `wake_listening: true`, `mic_available: true` y `mind_ready: true`. La mente usa unos 1,05 GB
  de RAM privada con Ultra cargado.

**Falta:**

- La prueba en vivo del dueño con el micrófono.
- Medir la RAM total contra el límite de 4 GB: llama-server marcó 5,7 GB privados; hay que ver cuánto es RAM real.

**Dependencias:**

- `kaldi-native-fbank==1.22.3` se instaló en el Python del runtime (`%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1`).
  Ese Python es compartido con BAXY Definitivo.
- `pylock.runtime-win-x64.toml` todavía no la incluye.

## Lo primero para el chat nuevo

1. **Falsedades vistas en uso real (2026-10-15, 01:52–01:55).** Siguen el orden de `conversation.v1.jsonl`, en
   `%LOCALAPPDATA%\BAXY\dev-mente-v2\conversation`:
   - BAXY dijo «¡Listo! Ya he abierto Steam… Doom Eternal» sin haber ejecutado nada (ruta `conversation`). Esto rompe
     «BAXY nunca dice algo falso». Hay que investigar por qué el modelo cuenta acciones que no llamó y arreglarlo con
     presentación o protocolo.
   - Con una confirmación pendiente, «cierra chrome» recibió «No puedo cerrar Chrome porque mi última orden pendiente
     era cerrar la ventana 18titans». Hay que revisar cómo se reemplaza un plan pendiente.
2. **Medir la ronda 1** (`r1`) y comparar con `en02v2`.
3. **Ciclo de re-auditoría con agentes**, hasta que no encuentren nada:
   - Código muerto: unas 7 200 líneas de la App, 27 JSON huérfanos, 508+8 pruebas de Python y 32 pruebas .NET de
     integración.
   - `bootstrap.ps1` todavía importa `baxy_mind.voice`; ahora existe, pero hay que revisar qué espera.
4. **Optimizaciones pendientes:**
   - Hora local en avisos y recordatorios: el modelo no convierte a UTC (`dueUtc`), así que conviene que el catálogo
     acepte la hora local.
   - Sacar del prompt la lista de 522 apps.
   - Guardar y restaurar el hueco en disco.
   - Perfil de 4 GB: IQ4_XS con un solo hueco.
   - Redactar dentro del bucle.

## Trampas de este entorno

- **Git Bash:** un heredoc pierde las barras invertidas dobles. Para editar con Python, escribe el script en un `.py`
  y usa rutas con `/`.
- **Saltos de línea:** git guarda LF y los `.cs` tienen BOM. Conserva los dos al editar.
- **Compilación:**
  - `vswhere.exe` no está en el PATH; `run_renew.cmd` lo agrega.
  - Si Baxy.exe tiene tomados los archivos, `main.py` cierra la ventana antes de copiar.
- **Manifiesto compartido:** `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` es de BAXY Definitivo; no se edita.
  Renew usa sus propias variables `BAXY_RENEW_*` y las de `BAXY_MIND_*` que fija el lanzador.
