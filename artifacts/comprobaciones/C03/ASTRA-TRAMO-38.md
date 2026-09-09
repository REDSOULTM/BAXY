# C03 — tramo 38, 2026-09-06

Reparada la identidad de salida de audio: el dato faltaba antes del compositor.
WindowsCoreAudioPlatform lee PKEY_Device_FriendlyName del mismo IMMDevice;
AudioStatusReceipt → AudioStatusResult → compositor conserva EndpointName.
No se añaden operaciones, respuestas fijas ni consultas de nombre a las mutaciones.
Herencia y contraste: INVESTIGACION_IDENTIDAD_AUDIO_C03.md.

Pruebas literales y dictámenes: PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md.
Producto registrado: tres consultas conocidas, tres útiles; 3497,56MiB de VRAM.
138 pruebas de proveedor y131 integración pasan sin skips; Fast verde,0errores/avisos.
Core NativeAOT publicado localmente antes de medir. No Full final ni nueva UI.

Dos sondas comparables de prosa de conocimiento: diez y cinco llamadas. La variante
de una frase mejora definiciones breves, pero pedir detalle sigue truncándose por
max_tokens128. No se promovieron variantes. Siguiente hipótesis: presupuesto de
salida efectivo, no más redacción a ciegas. Véase checkpoint para reanudar.

Goal-c03; main/modelo/registro intactos. C03 EN_CURSO, sin bloqueo externo.
No hay reserva de100aceptada ni publicación propia todavía.
