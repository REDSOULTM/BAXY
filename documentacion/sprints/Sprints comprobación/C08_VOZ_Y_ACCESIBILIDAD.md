# C08 — Oír, responder e interrumpir en el producto real

**Ejecutable: Grok 4.6 High; un goal con tramos reanudables.**
Predecesor: C07 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo vigente](../00_PROTOCOLO_EJECUCION.md).

## Objetivo

Cumple el Goal 09 y la accesibilidad de Identidad: BAXY oye su nombre, entiende
ES/EN/spanglish reales, conversa y actúa, narra resultados y permite interrumpirlo.
El control por voz llega al mismo turno que el texto, sin capacidades reservadas
a pantalla, teclado o ratón.

## Lecturas y owners

Filas G09 y narración accesible de G06; R09/R11/R14/R16 y casos acústicos A01–A06.
Ledger 09.5 de voz, herencia de accesibilidad, calibración y muestras de 09.
VoiceEngine, wakeword, ASR/fusión, TTS, ONNX y discovery de runtime; adaptadores
de voz a MissionInput y modos del FieldUi. No copies la muestra Sabina/Zira como
prueba de diversidad humana.

## Tramos de ejecución

A: población/procedencia y calibración wake. B: STT y fin de habla.
C: TTS, interrupción y micrófono/altavoz. D: accesibilidad, paridad y recursos.
Una frontera por ventana; las horas de audio se procesan a archivos en segundo
plano, no se transcriben al chat. Los 60 positivos/12 hablantes son mínimos de
cobertura; calcula además el tamaño que requiera el intervalo de confianza FAR/FRR.
Un contador bruto no sustituye su límite superior ni la prueba física.

## Trabajo

1. Preregistra una población de grabaciones reales diversas: ES latino, inglés,
   spanglish, varios hablantes y acentos, ruido y nombres propios. Usa fuentes
   heredadas disponibles y su procedencia; separa desarrollo y aceptación.
   Como mínimo 60 órdenes/turnos positivos y 12 hablantes, con los tres idiomas
   representados, además del negativo acústico necesario para la calibración.
   Es una cobertura mínima de esta campaña, no una garantía estadística universal.
2. El conductor entrega PCM/audio al mismo límite de captura que alimenta el
   producto, pasando wake, VAD/fin de habla, STT, entrada común, composición y TTS.
   Conserva transcripciones parciales/finales, decisiones, eventos y audio emitido.
   No envíes una transcripción correcta al runtime para aprobar la prueba acústica.
3. Reproduce casos con micrófono y salida de audio reales para cubrir drivers,
   habitación, eco, volumen y audibilidad. El resto puede usar audio grabado en
   el mismo camino PCM; etiqueta qué frontera cubre cada prueba. Automatiza la
   reproducción y captura si el entorno lo permite. No exijas al dueño actuar
   como probador; si falta una preparación física insustituible, documenta el
   bloqueo y su reanudación, sin cerrar la fila.
4. Mide FAR por horas de audio negativo real y FRR por activaciones dirigidas.
   Cumple la promoción de calibración del producto, incluido el límite superior
   de FAR ≤0,1/h y FRR ≤0,05 según su contrato vigente. Congela antes de medir
   el nivel de confianza y duración necesarios; no rebajes esos límites.
   Audio grabado puede procesarse sin esperar esas horas de calendario, si se
   preservan tiempos acústicos. Repetir el mismo clip no crea diversidad ni
   evidencia independiente. No se impone un soak de 24 h.
5. La escucha normal no se habilita fingiendo calibración mediante
   ALLOW_UNCALIBRATED. Un modo explícito de investigación no certifica el producto.
   Repara falsas activaciones y transcripciones como notepad → up pad con
   evidencia, sin hardcodear los textos del examen ni esconder intermitencia.
6. Verifica primer audio/señal desde fin de habla: p50 ≤1,5 s y nunca 3 s en
   silencio; interrupción a mitad de TTS y recuperación de la siguiente orden.
   La entrada de texto también genera habla en el modo que exige Identidad.
7. Recorre las familias de capacidades, confirmaciones, cancelación, memoria y
   Nueva sesión por voz; conserva paridad con texto. Implementa los modos de
   accesibilidad prometidos, incluidos controles actualmente bloqueados,
   sin crear otro motor ni exigir intervención visual para completar una tarea.
8. Declara wake/STT/TTS tras frontera de proceso, hashes y costuras. Mide escucha
   permanente y árbol completo en reposo; revalida C07 tras cambiar un motor.

## Cierre obligatorio

- [ ] A01–A06 y las filas asignadas pasan con audio real diverso; la cobertura
      sintética/PCM/física se publica por separado.
- [ ] Wake/FAR/FRR calibrados y aprobados; bootstrap normal no elude la calibración.
- [ ] STT conserva intención/argumentos suficientes y las tareas se completan;
      transcripción aislada no sustituye resultado final, efecto y voz.
- [ ] Fin de habla→primera señal p50 ≤1,5 s, silencio ≤3 s, interrupción y
      siguiente orden comprobadas con TTS realmente emitido.
- [ ] Todas las capacidades tienen ruta por voz y los modos accesibles funcionan;
      ninguna tarea comprometida exige mirar o pulsar un control inaccesible.
- [ ] Runtime/costuras/consumo medidos; tres ceros, privacidad y límite VRAM intactos.
- [ ] Full y gates reales de voz exigidos verdes; no hay skips de aceptación ni
      ambientales presentados como pass; cambios propios publicados.

Evidencia: artifacts/comprobaciones/C08/. Siguiente: C09.
