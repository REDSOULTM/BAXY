---
name: voice-record-transcribe
description: Record audio from microphone and transcribe via Whisper STT. Save transcript to a file. Confirm device before recording.
priority: medium
metadata:
  examples:
    - "grabá lo que voy a dictar y transcribilo a texto"
    - "grabá una nota de voz y pasala a texto escrito"
    - "registrá mi dictado por micrófono y transcribilo"
    - "record my voice memo and transcribe it to text"
    - "grave minha nota de voz e transcreva para texto"
  when_to_use:
    - "el usuario va a dictar algo después y quiere que quede como texto"
    - "convertir lo dicho por el micrófono en un archivo de texto"
  limitations:
    - "no es para silenciar o activar el micrófono"
    - "no es para mutear o desmutear el micrófono en una llamada"
    - "not for muting or unmuting the microphone"
    - "no es para extraer o leer texto de un archivo, pdf o documento ya existente"
    - "not for extracting or reading text from an existing file, pdf or document"
requires:
  os: [windows]
---

# Voice record & transcribe

Tools: `voice`, `filesystem`, `verify`. Honesty-critical: no (read-only sobre el mic; el output va a disco).

Usar cuando: "grabá lo que digo", "transcribí mi voz", "tomá nota de lo que diga", "anotá esto" (cuando es claramente input por voz). Si el usuario YA dijo el texto en el turn actual, NO grabar — usá `memory` o `filesystem.write` para guardar lo que ya tenés. La gracia de este skill es grabar **algo que va a decir después**.

## Steps

1. **Verificar disponibilidad.** `voice(action="status")`. Si Vosk + Whisper + Piper no están cargados, devolver `needs_dependency` con el install hint. NO intentar grabar sin el stack listo.
2. **Confirmar device.** Listar inputs disponibles si la config lo permite. Reportar cuál se usará: "Voy a grabar desde el mic '<device name>'. Decime 'empezá' cuando estés listo."
3. **Activar grabación.** `voice(action="trigger")` (push-to-talk: arma una sola captura). O si el modo es always-on: `voice(action="start")` (mic loop wake-word listening).
4. **Whisper transcribe.** El stack STT corre solo cuando detecta speech. El transcript llega vía events (no es síncrono para tools). Recoger el resultado y reportar.
5. **(Opcional) Guardar a archivo.** Si lo pidió: `filesystem(action="write", path="<path.txt>", content="<transcript>")`. Verificar con `filesystem.verify` (write ya hace stat post-write).

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Voice stack OK, listo a grabar | "Listo, grabando desde <device>. Hablá." |
| Voice stack no cargado | "Vosk/Whisper no están cargados. Activalos con `voice(action="start")`." |
| Grabación + transcripción OK + guardado | "Grabé y guardé en <path>: '<preview>'" |
| Transcripción ambigua / vacía | "No entendí lo que se dijo. ¿Probás de nuevo más cerca del mic?" |

## Anti-patterns

- ❌ Empezar a grabar sin confirmar device (graba la wrong source).
- ❌ Reportar "grabé X" cuando Whisper falló (queda como UNVERIFIED).
- ❌ Sobrescribir un archivo existente sin advertir.
- ❌ Grabar sin notificar al usuario que está siendo grabado.
