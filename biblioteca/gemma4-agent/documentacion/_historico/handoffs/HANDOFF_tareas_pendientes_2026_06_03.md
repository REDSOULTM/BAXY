# HANDOFF — Tareas pendientes (2026-06-03, pre-compact)

El usuario se fue a dormir y pidió trabajar en automático. "Cuando te diga sigue,
seguí con TODO lo último que pedí." Este doc preserva el estado exacto para
retomar tras el compact sin perder contexto. **Cada agente debe ir haciendo
checkpoints** (pedido explícito del usuario) por si la cuota corta.

## Contexto: lo que el usuario pidió (textual, esta tanda)

1. **PRIVACIDAD — quitar grabación de audio del micrófono.** ACLARACIÓN CLAVE del
   usuario: NO es la capa Jarvis (BehaviorLog/AmbientObserver — esa LE GUSTA, la
   deja; si funciona mal, arreglarla aparte). Lo que quiere quitar es: "se graba el
   micrófono de todo lo que dice el usuario y se guarda en el repo (para testing
   después, pero ya pasamos esa fase, así que grabar al usuario es solo un ataque a
   su privacidad)". → QUITAR la grabación/guardado de audio del mic del usuario.
2. **Logs: empezar de 0.** Respaldar los logs actuales como documentación (archivar),
   luego BORRARLOS, para que cuando corra la app desde hoy no encuentre errores del
   mes pasado mezclados con los nuevos. (Los viejos quedan archivados.)
3. **Borrar el .docx de la raíz** (Gemma4_Agent_Producto_Riesgos_y_Competencia.docx
   + _v2). NOTA: están gitignored (no en repo), son del usuario — borrar del disco.
4. **Borrar design_handoff_carter_field/** — "esa GUI ya está implementada al 100%,
   no es necesario tenerla en el repo". (Ya se movió a documentacion/_historico/
   handoffs/carter_field/ en la consolidación — hay que BORRARLA de ahí también.)
5. **TESIS DEL CURSO (lo grande):** el usuario copió al repo el archivo
   `Chat de WhatsApp con 202610.8016  PORTAFOLIO DE PROYECTOS.zip` (en la raíz,
   gitignored). Es el chat de WhatsApp del curso donde le piden desarrollar ESTA
   tesis. Dentro hay PDFs adjuntos + toda la conversación. Pide: LEER todo, y
   HACER todo lo que se pide ahí (informes, PPTs, documentos, etc.), documentarlo.
   "Necesito tener todo eso, satisfacé todo esto."
6. **Multiples agentes con CHECKPOINTS** por si la cuota corta → poder seguir donde
   se quedó. Trabajar en automático ("confío en ti").

## Reglas de criterio (el usuario duerme, decidir solo, lado seguro)
- Reversible > destructivo. Confirmar antes de borrar algo del usuario NO se puede
  (duerme) → para lo SUYO (docx, zip), borrar solo lo que pidió explícito; el resto
  gitignored se deja.
- Validar que nada rompa (import gemma4_agent OK, suite verde) tras cambios de código.
- Commits temáticos con Co-Authored-By: Claude Opus 4.8.

---

## ESTADO POR TAREA

### A1 — PRIVACIDAD (grabación de audio del mic) — EN PROGRESO
HALLAZGOS (medidos):
- **0 .wav tracked en git** (`git ls-files "*.wav"` = 0). Los 1214 .wav del árbol son
  DATASETS DE EVAL en `data/` (wake_universal_eval/positives 500, rirs 270,
  stt_eval/real_es 180, stt_eval/audio 120, stt_eval/real_mic 98, backgrounds 40).
  Esos son data de test, gitignored, NO son grabación-en-vivo del usuario → NO tocar
  (son el dataset reproducible de STT/wake).
- La grabación EN VIVO del usuario: `gemma4_agent/voice/tts.py:395-419` hace lazy
  import de `from .recorder import VoiceRecorder` + `_recorder.capture_tts_chunk()`.
  PERO `gemma4_agent/voice/recorder.py` NO EXISTE → el import falla → `_recorder=None`
  → hoy NO graba nada por esa vía (ya está roto/muerto).
- Carpeta `gemma4_agent/captures/` existe (posible destino de capturas).
- FALTA VERIFICAR: dónde se guarda la grabación del mic en la sesión de VOZ real
  (pipeline.py tiene `_capture_buf` línea 506 — el buffer de captura para STT).
  Buscar si el pipeline o el launcher escriben el audio capturado a disco
  (data/stt_eval/real_mic/ tiene 98 .wav — ¿se siguen generando en runtime?).
QUÉ HACER:
  - Encontrar el punto donde el audio del mic del usuario se ESCRIBE a disco en
    runtime (no en el dataset de eval). Candidatos: pipeline.py (_capture_buf →
    ¿se vuelca a real_mic/?), tts.py recorder (ya muerto), launcher/voice_runner.
  - Quitar/gatear ese guardado (default OFF). NO romper el pipeline de STT (el
    audio se usa en memoria para transcribir; solo NO debe PERSISTIRSE a disco).
  - Las menciones de "grabar para testing" → gate GEMMA4_SAVE_MIC_AUDIO default OFF
    o quitar la escritura directamente.
  - Verificar import + que la voz siga funcionando (no romper STT).

### A2 — LOGS desde 0 — PENDIENTE
- Logs viven en: `~/.gemma4/logs/` (vi `_pre_session/full.log`, `chat.log` en
  ResourceWarnings) + `gemma4_agent/logs/` (gitignored) + posible `logs/` raíz (ya
  borrado en la limpieza). El trace va a config.trace_path.
- HACER: (1) RESPALDAR los logs actuales a documentacion/_historico/logs_archivados_
  2026-06-03/ (o un zip) — "respaldalos como documentación". (2) BORRAR los logs
  activos para empezar de 0. Confirmar dónde escribe la app (config.py: trace_path,
  ~/.gemma4/logs/). NO borrar la config, solo los .log/.jsonl de traza viejos.

### A3 — Borrar docx raíz + design_handoff — PENDIENTE
- `Gemma4_Agent_Producto_Riesgos_y_Competencia.docx` + `_v2.docx` (raíz, gitignored)
  → borrar del disco (el usuario lo pidió explícito). Los `~$*.docx` locks ya se
  borraron antes.
- `design_handoff_carter_field/` (raíz) — en la consolidación se movió a
  `documentacion/_historico/handoffs/carter_field/`. El usuario quiere borrarla del
  repo (GUI ya implementada 100%). → git rm de documentacion/_historico/handoffs/
  carter_field/ + borrar el dir físico raíz design_handoff_carter_field/ (tiene
  prototype/ .jsx que tampoco se necesita).

### B — TESIS DEL CURSO (lo grande) — PENDIENTE, no empezado
- El .zip: `Chat de WhatsApp con 202610.8016  PORTAFOLIO DE PROYECTOS.zip` en la raíz
  (gitignored, NO subir al repo — es personal del usuario).
- PASO 1: descomprimir el zip a una carpeta temporal FUERA del repo o en un dir
  gitignored (ej _tesis_curso/ que se agrega a .gitignore). Leer: el _chat.txt de
  WhatsApp + TODOS los PDFs adjuntos.
- PASO 2: entender qué pide el curso (informes, PPTs, documentos, formato, fechas de
  entrega, requisitos). Hacer un INVENTARIO de entregables.
- PASO 3: ejecutar cada entregable con AGENTES (uno por entregable) que hagan
  CHECKPOINTS (escribir progreso a un archivo de estado por entregable, para retomar
  si la cuota corta). Generar los informes/PPTs/docs que pidan.
- DÓNDE GUARDAR: una carpeta del usuario, ej `_tesis_curso/entregables/` (gitignored,
  es trabajo académico personal, NO va al repo del software). Documentar qué se hizo.
- CAVEAT: generar .docx/.pptx requiere python-pptx/python-docx (el agente tiene la
  tool office). Verificar deps.

## ORDEN sugerido al retomar ("sigue")
1. A1 (privacidad — lo más importante): hallar + quitar guardado de audio del mic.
2. A3 (borrados rápidos: docx + design_handoff).
3. A2 (logs: archivar + borrar).
4. Commit de A1+A2+A3.
5. B (tesis): descomprimir zip → leer → inventariar → ejecutar con agentes+checkpoints.

## NO romper / gotchas
- gemma4_agent debe importar OK tras cualquier cambio de código (test rápido).
- La voz/STT debe seguir funcionando (A1 solo quita la PERSISTENCIA del audio, no la
  captura-en-memoria para transcribir).
- El zip y los .docx son del usuario → NO subir al repo (gitignore ya cubre *.zip).
- Estado git al pre-compact: rama Dev, working tree limpio (último commit:
  chore gitignore zips/personales). Todo lo previo de la sesión commiteado.
