# C03 — integración242 y fallo físico243–245

DTLN512 sustituye a Speex en la fuente viva. `dtln_aec.py` contiene sólo el
modelo512, dos intérpretes CPU de un hilo y estados separados por sesión.
El audio y el par de comparación conservan el retardo medido de384muestras.
Se comprueban hashes, formas/tipos de tensores, propietario del hilo, tamaño,
valores finitos y salida válida. El cierre libera los dos intérpretes.
La licencia MIT se conserva también en la fuente.

El descriptor declara el directorio y sus dos modelos/licencia. El instalador
explícito `scripts/install_dtln_aec.py` acepta un bundle local o descarga desde
una revisión fija; verifica todo antes de publicar el directorio. Reutiliza
activos idénticos y rechaza un destino distinto. No descarga desde el runtime.
Instalación local efectiva: D:/BAXYRuntime/assets/aec/dtln-512-v1.

El lock incorpora ai-edge-litert2.2.0, backports.strenum1.2.8 y ml_dtypes0.5.4.
Los59 paquetes anteriores permanecen idénticos (LOCK_DELTA.json). Se instaló
el lock completo mediante setup_mind_voice.ps1. Un test esperaba59; se actualizó
a62 y a los tres pins explícitos. El registro de modelo conversacional no cambió.

## Validación de integración

- Siete suites dueñas:163pass/0skips,22.50s (TESTS.log). Incluyen captura,
  voz, AEC, activos, instalación/dependencias y contrato de compuerta de voz.
- Fast verde; build Release5.50s,0advertencias/errores. Ruff adicional del
  test de lock tras actualizar su expectativa: verde. No Full durante reparación.
- Diez señales238,10800bloques: audio limpio idéntico byte a byte y todas
  las guardas idénticas. No se infiere fidelidad ASR de esa paridad.
- Smoke acústico existente:7.21dB, por encima del umbral sin cambiar de6dB.

## Prueba física243: calidad NO aceptada

Componente instalado, sin sustituir el backend por el adaptador experimental.
Cuatro textos187, misma pauta de240,42.144s/1317bloques. Un corte y un texto
«Hola»; cero errores de voz/dispositivo. Volumen/mute exactamente restaurados
a0/true y todos los workers cerrados. Efectos Windows:lista vacía.
DSP media11.15ms,p9923.64ms,máx43.82ms. No UI/LLM ni presupuesto conjunto.
Sin voz humana simultánea controlada; wake sigue sin verificador, sin eludirlo.

244 reproduce1317/1317bloques243 con el componente integrado Y el adaptador182
congelado: limpieza y pares idénticos. Las guardas físicas también coinciden.
245 reproduce la segmentación real y el reconocimiento: corte143, segmento
133–170 inclusive (1.216s),«Hola», VAD máximo diferencial0,9guardas sin cambios.
El fallo existe en la candidata previa: no es una regresión de la integración.

En141–143, VAD0.567/0.753/0.885 y RMS limpio0.01456/0.01332/0.00703 superan
los criterios existentes. Correlaciones0.508/0.433/0.521 inferiores a0.55;
referencia RMS1381/1513/1604PCM disponible. Retardos168/393/310muestras:
no es por superar el historial de250ms. No bajar umbrales para ocultarlo.

Los cuatro audios Piper regenerados difieren entre240 y243, aunque el texto
es igual (GENERATED_COMPARISON.json). El primero tiene81326 frente82862
muestras. No atribuir causalidad sólo al entorno ni decir que el estímulo PCM
fue idéntico. La paridad software se acredita con la MISMA señal grabada244.

## Continuación

Aislar el primer fallo de eco de243 verificando la referencia loopback contra
el PCM Piper243 guardado y la alineación ADC, con240 como control. Sin nueva
síntesis, barrido de modelos/umbrales ni repetir física a ciegas. Determinar
si la variación corresponde a referencia/temporización o al rechazo acústico
antes de editar otra vez. Se conservan todas las regresiones ASR239.

C03 completo sigue abierto: eco robusto, ASR y wake, voz humana física, ocho
rutas, reserva100humana aún sin congelar y100/100, averías/recuperación,
UI+audio+LLM/4GBconjuntos, instalación/runtime, continuidadC04–C09,Full y
publicación fuera main. La integración242 es candidata, no cierre de voz.
