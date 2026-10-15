# Cómo escalar BAXY desde aquí

Para quien retome BAXY después de la misión de estabilización (2026-10-11). Una página: qué base queda, qué
requisitos quedaron anotados y por dónde se enchufan la transcripción y la palabra de activación.

## La base

- Modelo local Qwen3.5-4B en llama-server, VRAM ≤ 4 GB, sin modelo de visión. Los «ojos» del computer use son el árbol
  de accesibilidad (UIA) más OCR. Ver `computer-use/CONTRATO_VISTA_ACCION.md`.
- Lo que BAXY hace siempre y lo que no hace: `LIMITES_DE_BAXY.md`. Variabilidad medida caso por caso:
  `computer-use/ESTABILIDAD.md` y `ESTABILIDAD.json`.
- Las apps se cubren con mecanismos genéricos y datos por app (`src/baxy_mind/data/app_places.v1.json`,
  `world_acts.v1.json`, `operation_floor.v1.json`). Nunca código que nombre una app.

## Requisitos para crecer sin perder estabilidad

1. **Medir antes y después.** Cada cambio se mide con el banco B ×3 y las tandas ×2. Herramientas en
   `scripts/cu_live` y `scripts/uso_real`. Un caso nuevo entra al banco sólo con 3/3 en vivo. Si no llega con un
   arreglo pequeño y general, se declara límite.
2. **Datos, no reglas.** Una app nueva entra como datos: lugares por dirección, actos que salen al mundo y su
   confirmación. El saldo de reglas de cada rama debe ser ≤ 0 o justificarse con la medida.
3. **Cero falsos éxitos.** El suelo (`operation_floor`) dice lo verificado. Lo no verificado se dice como tal.
4. **No molestar.** Nunca se teclea ni se hace clic en la ventana de la persona. BAXY trabaja delante con su app y
   devuelve el frente.
5. **Hardware.** Subir de 4B o añadir visión exige más de 4 GB de VRAM: es decisión del dueño, no de una rama.
   Antecedentes: `computer-use/DECISION_VISION_V3.md` y `APLAZADOS.md`.
6. **Límites que se podrían abrir con otro modelo o con visión:** arrastrar y soltar, scroll largo en listas
   virtualizadas, clic derecho, la cinta de Office y tareas largas fuera del banco. Cada uno está como límite en
   `LIMITES_DE_BAXY.md`, con el caso en vivo que lo comprueba.

## Transcripción y palabra de activación: dónde se conectan

Quedaron fuera de esta misión por decisión del dueño. El código existe, pero no se midió ni se declara estable.

- **Entrada única de un turno.** `MainWindowViewModel.DispatchMissionInputAsync`
  (`src/Baxy.App/MainWindowViewModel.cs`) pasa por `MissionInputPipeline.DispatchAsync` (`MissionInput.cs`). El texto
  escrito llega por `/turn` (`FieldProductChannel.HandleTurnAsync`). La transcripción ya entra por
  `DispatchTranscriptAsync` con `MissionInputSource.VoiceTranscript`, así que una voz nueva recorre el mismo camino
  que el texto.
- **Transcripción (STT).** `src/baxy_mind/voice.py`, `VoiceEngine`: captura de micrófono, Parakeet con sherpa-onnx y
  `voice.transcript` hacia la App (`MindSidecarClient.TranscriptReceived` → `OnMindTranscript`). El runtime se
  descubre en `MindRuntimeDiscovery.cs` (`stt_dir`, `stt_sha256`). Pendiente anotado: Parakeet confunde «BAXY»
  (`APLAZADOS.md`).
- **Palabra de activación.** `wakeword.py` (`AcousticWakeDetector`), `wake_cascade.py`, `wake_verifier.py` y
  `_acoustic_wake_loop` en `voice.py`. La App recibe `wake_detected` en `MainWindowViewModel`. Pendiente anotado: el
  umbral no se promovió, con 2,5 falsas alarmas por hora (`APLAZADOS.md`).
- **Voz de salida (TTS, dentro del alcance y comprobada).** Cada mensaje de BAXY se dice con `VoiceSpeakAsync` desde
  `MainWindowViewModel.AddMessage` y se corta cuando escribe la persona. En Python: `voice_output.py`, con Piper y
  SAPI de reserva. Contra el eco con micrófono abierto: `_looks_like_echo`, `barge_in` y `voice_aec.py`.
- **Señal temprana de 3 s.** Se mantiene: `Baxy.Kernel/Policy/FirstSignal.cs` y `baxy_mind/first_signal.py`. Una
  entrada por voz debe respetarla igual que el texto.

Para activarlas: medir la tasa de falsas alarmas del wake en el PC del dueño, medir el acierto de Parakeet con sus
frases (sin enviarlas a la web) y añadir al banco casos de voz ×3 antes de declararlas estables.
