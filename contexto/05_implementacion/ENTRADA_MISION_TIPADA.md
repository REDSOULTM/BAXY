# Entrada de mision tipada

Fecha del corte: 2026-07-15.

## Alcance implementado

- `MissionInput` admite exactamente dos procedencias: `Text` y
  `VoiceTranscript`.
- La GUI actual envuelve el borrador como `Text` y lo entrega a una sola ruta:
  validacion, routing natural existente y ejecucion del `MainWindowViewModel`.
- La API interna admite una transcripcion ya producida como `VoiceTranscript`
  por esa misma ruta. La procedencia no selecciona parsers, frases, riesgo ni
  politica de confirmacion.
- Ambas procedencias rechazan antes de ejecutar las entradas vacias, con NUL,
  UTF-16 mal formado o de mas de 4096 caracteres. Ese limite conserva el
  `MaxLength` y contador que ya tenia el compositor WPF; no reutiliza el limite
  UTF-8 mas estrecho y especifico del parser de memoria. El schema existente de
  `note.create` admite hasta 65.536 bytes UTF-8 de contenido.
- La operacion, el riesgo canonico y la politica de confirmacion se obtienen del
  mismo catalogo productivo. Las operaciones privadas conservan la seleccion
  de wire operation ya usada por el protector de memoria.
- Un centinela de arquitectura enumera los archivos con regex de idioma y falla
  si aparecen fuera de la capa interina declarada. No se agregaron frases ni
  operaciones para cerrar esta costura.

## No acreditado por este corte

> Estado histórico supersedido el 2026-07-16 por ADR-0007. Lo siguiente
> describe únicamente el corte del 2026-07-15; la implementación y evidencia
> vigentes están en `../03_investigacion/VOZ_ESTADO_DEL_ARTE_2026-07-16.md`.

`VoiceTranscript` es solamente una frontera tipada para una transcripcion
futura. Este corte no implementa ni simula captura de microfono, VAD, wake word,
STT, TTS, AEC, barge-in o una experiencia de voz. Tampoco aporta corpus
acustico ni pruebas fisicas de voz.

Por lo tanto, Must 7 sigue pendiente. Para aprobarlo todavia hacen falta el
pipeline de voz real, mediciones y gates fisicos representativos en espanol,
ingles y spanglish, incluidos code-switch y errores reales de STT.

## Evidencia automatizada acotada

- `MissionInputPipelineTests` compara texto/transcripcion para intencion,
  argumentos, riesgo y confirmacion en espanol, ingles y spanglish.
- La matriz negativa demuestra rechazo identico y ausencia de ejecucion para
  entradas invalidas. La GUI conserva un borrador rechazado y muestra una guia
  fija que no reproduce su contenido.
- Los recorridos existentes de notas, estado local, audio y memoria siguen
  pasando por `MainWindowViewModel`; no se agregaron parsers alternativos por
  procedencia.
- La evidencia conjunta de las cuatro costuras está en
  `artifacts/product/architecture_seams_gate.json`.
