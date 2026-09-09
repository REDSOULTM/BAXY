# C03 — tramo 29: registro reproducible y ventana real

EN_CURSO. El turno anterior fue una respuesta de estado, sin avance de producto.
Este tramo registra el candidato, obtiene evidencia real de UI y corrige una
pérdida demostrada de opciones de recuperación. No es cierre ni aceptación fresca.

## Registro

`scripts/register_mind_runtime.ps1` terminó correctamente. Evidencia en
`astra-runtime-qwen-registered/{BEFORE.json,AFTER.json,RESULT.json,registration.log}`.
Sólo cambiaron `gguf` y `gguf_sha256`; Python, servidor, STT, TTS, wake y ngl se
conservaron. Qwen3-4B-Instruct-2507-Q4_K_M base, sin LoRA. KV q8 es el default
de fuente heredado del tramo28, no una variable temporal.

Registro SHA256: `13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed`.
No hubo publicación en main, commit ni push.

## UI anterior a la corrección de opciones

Primero se ejecutó `py main.py --ui-probe ...` con el mecanismo ya existente.
La sonda cierra la aplicación al terminar: no era un crash ni una interrupción
por VRAM. Se conservan captura DOM, auditorías y procesos en
`astra-runtime-qwen-registered/ui/`. Sesión96464 terminó0;82,59s;3567,76MiB GPU.
Su lectura DOM sola no se presenta como inspección visual; la ventana se cerró
antes de poder capturarla con la skill de Windows.

El perfil real de desarrollo tenía una recuperación de memoria pendiente.
Al pedir «Dime la hora y el estado del audio.» publicó:

> Dime si querés continuar o cancelar la recuperación de la memoria.

No respondió a hora/audio; no se aprueba esa entrada como resultado útil normal.

Después se arrancó `py main.py` sin sonda ni overrides de runtime. La skill
`computer-use` observó la ventana real BAXY, con Qwen3/4b local, entrada de texto,
actividad y activación de voz encendida. Se vio un saludo y un marcador
`composition_failed` al formular la recuperación pendiente. Ese fallo queda
conservado: no se oculta por tener estado recuperable.

Entrada manual «cancelar» → «La cancelación de la memoria se realizó correctamente.»
Se canceló la recuperación pendiente; no se autorizó borrar memoria.

Entrada manual «Dime la hora y el estado del audio.» →

> La hora local es 16:06. El audio está desactivado de muteo y el nivel de volumen es 100.

Inspección visual directa: texto presente en actividad, campo disponible y estado
Idle. Auditoría t2: UTC19:06:51.9177099, offset−180, volumen100,muted:false. La frase
es poco elegante, pero indica muteo desactivado, conserva los valores y responde.
La actividad mantuvo visible el fallo anterior y la cancelación; no se confundió
el marcador de error con una respuesta del modelo.

`manual-ui/` conserva PREREG,PROCESSES,compose-audit,shell-trace,RESULT. Sesión43732
terminó0 tras solicitar fin de observación al monitor propio;143,89s;3589,12MiB
GPU;5697,94MiB RAM. Se inspeccionó la activación y hubo solicitudes reales
voice.start/voice.speak. No se afirma escucha física ni STT por habla sólo por eso.
El monitor terminó exclusivamente los procesos que había lanzado. Registro intacto.

## Causa y corrección

En `llm._compose_situation_payload`, las opciones de confirmación se filtraban
como si siempre fueran confirm/cancel. La situación real ofrecía
continuar/continue/cancelar/cancel, pero el prompt sólo recibía cancelar y el
verificador exigía continuar y cancelar. La auditoría conserva tres borradores
rechazados y el agotamiento resultante.

Se sustituyó ese filtro por `_localized_confirmation_words`, ya utilizado para
validar. Conserva todas las decisiones ofrecidas sin fabricar confirm/cancel
si no existen; continúa respetando el token retry que expone el shell.
No se cambió autorización, kernel, invocación exacta ni las garantías del filtro.
Nueve regresiones cubren ContinueCancel,ContinueRetry y confirmación de una sola
opción en es/en/mixed. Pruebas dueñas:296pass+115subtests,0skip,1,98s, log
`scratchpad/c03-registered-choices-final-tests.log`. Ruff y diff-check verdes.

## En curso

Prueba sin overrides con21 entradas conocidas, seguida de3 averías separadas
reject/timeout/exhaust, cada una restaurada en el mismo proceso/perfil/sesión.
`astra-registered-development-recovery-qwen/`; sesión69360. No son100 nuevos.
Fast de la fuente integrada en `scratchpad/c03-registered-final-fast.log`.
Faltan lectura/adjudicación, comprobación directa del compositor de recuperación
corregido, aceptación100, validación final UI/recuperación y Full, publicación y
contratos posteriores. No hay bloqueo externo.


## Cierre del tramo (C03 sigue abierto)

Panel integrado39turnos:33normales publicados,32útiles y1fallo de naturalidad
(t2:desmudo); no es100fresco.3averías con estado honesto+3restauraciones útiles
por separado; no cuentan como aceptación normal. No hubo mensaje de progreso
narrado separado en esta muestra. Volúmenes80/60/40/restauración100 verificados.
136,17s,3499,56MiB GPU,5546,79MiB RAM;81743terminal0. Registro intacto.

Se reparó también el parser horario para unidades horas/minutos ES/EN y se aclaró
la conservación de24h o AM/PM al convertir. No se acepta una hora distinta ni se
sustituye la respuesta visible por un literal. Prueba directa9/9 con prompt de
opciones completo; todos los intentos previos conservados, incluida ERRATA por
omitir requiredResponseWords en el primer diagnóstico directo.

Fast final82109 terminó0,0errores/advertencias;1184pass+115subtests,0skip. Full aún
no corresponde: desarrollo tiene fallo residual y100/UIfinal pendientes. Informe
PRUEBAS_RUNTIME_REGISTRADO_C03.md enlaza cada entrada/respuesta/adjudicación.
Todos los procesos propios terminales. Siguiente paso exacto en CHECKPOINT.
