# Actualización176 — etapas de AEC3 verificadas; no adopción

Fuente172 sigue vigente; pruebas130/Fast verdes.173 físico2/4 cortes.
17415mediciones,17518observaciones y1766etapas completados exit0.
176 salida final bitidéntica a174; mezcla pierde más palabras en residual que
en lineal, que tampoco conserva todo y deja pasar eco149. No quitar supresión.
PRUEBAS_AEC173_175.md/PRUEBAS_AEC176.md y TRAMO172_176_PINS.json fijan evidencia.
Build9568/evaluación83450 terminados y recogidos; ningún proceso propio pendiente.
Siguiente: relación temporal real de far-end/near129 y convergencia176; no asumir
que speaking coincide con sonido. Reutilizar build176; no tunear sin causa.
No fuente/runtime/promoción/Full nuevos. C03 íntegro EN_CURSO.

# Actualización175 — AEC3 elimina eco pero pierde palabras en mezcla

174 terminó exit0 (15557):15 mediciones; replaySpeex149 bitidéntico.
175 terminó exit0 (41409):18 observaciones locales sobre el mismo PCM.
AEC3 por defecto no se adopta: mezcla falla con ambos reconocedores y normalización.
PRUEBAS_AEC173_175.md contiene comparaciones y textos completos.
176 compilación diagnóstica en curso, sesión9568, log TEMP/c03-linear176-build.log.
Expone salida lineal y métricas; no cambia supresión ni producto. Recoger esa
sesión antes de iniciar otra; después verificar paridad final y observar etapas.
No App/modelo/captura activos; no Full. Resto de C03 íntegro.

# Actualización 173–174 — audio todavía falla; comparación AEC3 aislada

Fuente172: 130 pruebas pasan, 0 skips, 7,36 s. Fast55364 terminó exit0,
Release2,73 s, cero avisos/errores; log copiado al snapshot172.
Ensayo173 terminó: dos eventos de interrupción, saludo y primera hora ES
cortados; inglés y última hora ES sin evento. No prueba de contenido completo.
Driver41212 y captura20590 terminaron exit0; no sesiones propias pendientes.
El contador corregido no resuelve los cortes. No alterar umbrales ni repetir UI.
174 descarga aislada pywebrtc-audio0.2.0 para comparar AEC3 con grabaciones
conservadas y controles de voz cercana sintética. No runtime ni fuente cambiados.
Turno anterior: informe de estado, sin progreso de producto; esta continuación
reanuda experimento seguro. Goal activo y alcance completo conservado.

# Handoff C03 — fuente164 — 2026-09-07 — EN_CURSO

Tarea 01a07974-2a33-7ed3-ba87-2436944e8115; continuación íntegra de
01a074f6-9e0e-7fb3-8282-a6b706198a7e. Goal activo, Goal-c03,
HEAD 2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Sin commit/push/main/subagentes.
Preservar WIP ajeno y evidencia. No bloqueo externo. Última pregunta del dueño
pide explicación de avance/plazo, no cancela el goal; se respondió con estado y
pendientes, sin porcentaje ni plazo inventado. Confirmación de tres ingleses
«Son turnos validos» ya registrada; no preguntar ni extenderla a los742.

## Estado y decisiones

- Fuente164: main prepara el remuestreador antes de iniciar el lector JSONL.
  Corrige bloqueo nativo SciPy/_fblas161;162 precoz pasa y165 producto pasa
  voice.start4,281s/cierre17,110s sin errores. No cambiar protocolo:163 también
  bloquea con ReadFile. DSP/umbrales de147 se conservan.
- UI166 real: tres relojes ES/EN/mezcla útiles y verificados en
  1325,475/1045,566/1043,858ms; voiceon, sin reinicios. Pico3499,504MiBVRAM,
  5964,531MiBRAM. Audio263,89s/0overflows/restauración exacta0/mutedtrue.
- Audio NO aceptado: ASR167 no recupera esas cuatro salidas completas.
  Fullsidecar168 reproduce dos salidas cortadas por barge_in, errorTTS null.
-169 captura arrays sólo DESPUÉS del primer barge; saludo cortado1,485s.
 170: historia del guard bitidéntica al ring, mejor correlación0,349731 con
 retardo903muestras dentro de250ms; ampliar a4s no mejora. No bajar umbral0,55
 ni repetir fases151. Por qué falla la separación acústica sigue abierto.
- Wake App heredado permite manifiesto no aprobado;169 registra wake y «Yeah.»
 sin petición de entrada guionada. No aceptación humana ni operaciones ejecutadas.

## Validación y evidencia

Runtime Python: `-m pytest tests/test_sidecar_lifecycle.py tests/test_protocol.py
tests/test_voice_capture_clock.py tests/test_speex_aec.py tests/test_mind_voice_runtime.py
tests/test_piper_tts.py tests/test_neural_speech_output.py tests/test_goal06_voice.py
tests/test_asset_resolution.py -q`:191pass,0skips,19,14s. Regresión fría antes:
1fail11,03s. `scripts/test_source_quality.ps1`: Fast exit0, Release3,56s,
0warnings/errors. Logs en astra-source164-snapshot. No Full durante reparación.

TRAMO158_170_PINS.json:114 ficheros públicos y37 privados verificados; pins143–157
también intactos. No editar scripts/informes fijados. Informes nuevos:
ASTRA-TRAMO-162_165.md, ASTRA-TRAMO-166_168.md, ASTRA-TRAMO-169_170.md.
Ningún proceso propio pendiente:165/166/167/168/169/170 terminados y recogidos.

## Siguiente acción y cierre restante

Empezar por astra-analysis170/RESULTS.json y los inputs privados de su PREREG.
Contrastar AEC/adaptación/doble habla con la señal exacta antes de editar; probar
que una solución conserva interrupciones reales. No otra corrida general de UI
ni nuevos prompts/modelos para explicar un corte cuya cancelación ya está registrada.

Pendientes íntegros: audio físico e ingreso de voz; consolidar ocho rutas en el
candidato final; seleccionar/congelar100 humanos y adjudicar100/100; averías
aparte; promoción reproducible y regresión de roles; continuidadC04–C09;
Full final entero y publicación fuera de main. Reserva239 revisados,100 aún
sin congelar/ejecutar. RESERVA_PREVIEW155.md fija duplicados/contextos dudosos.
Qwen3.5/PiperJohn/Speex sólo candidato; manifiesto registrado sigue13b971b3…
sin promoción. No confundir paneles técnicos con reserva humana.
