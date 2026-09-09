# C03 — observación independiente y respuestas de voz compuestas —191–193

Fuente192 adopta localmente la retirada de dos respuestas TTS fijas. El motor
de voz conserva eventos de escucha/transcripción dudosa; la aplicación redacta
su respuesta mediante la cola y política compartidas. No hay cambio de AEC,
umbrales, modelo, voces o manifiesto registrado. Audio183 sigue pendiente.

## Observación191: no confundir transcripción con corte

Nemotron ya instalado, CPU6/greedy/auto, flush0,66s; mismo PCM original187 y
ventanas físicas189, crudo y normalizado.16lecturas sin pistas; sesión51364exit0.
Se conservan todas las variantes en astra-observe191, no sólo las favorables.

| Salida | Origen | Crudo | Normalizado |
|---|---|---|---|
| 1 | original | Tolah, Aki Baxir, ¿en qué te puedo ayudar hoy | Tollah, aki Vaxi, ¿en qué te puedo ayudar hoy |
| 1 | loopback | Tolah, aquí Baxir, ¿en qué te puedo ayudar hoy | Tolah, aquí Vaksi, ¿en qué te puedo ayudar hoy |
| 2 | original | Son las 105 | Son las 105 |
| 2 | loopback | Son las 105 | Son las 105 |
| 3 | original | It is ten fity six | It is ten fics |
| 3 | loopback | It is ten fifty six | It is ten fifty six |
| 4 | original | Son las 1056 | Son las 1056 |
| 4 | loopback | Son las 1056 | Son las 1056 |

La hora inglesa se recupera completa en loopback crudo/normalizado, donde
Parakeet189 sólo reconoció «It is ten». Esto sustenta que esa lectura incompleta
no acredita otro corte. No borra el barge_in183 ni certifica toda la voz.
Nemotron también comete errores(«105» para10:55); tampoco es observador infalible.

## Cambio192 y ownership

VoiceEngine ya no pronuncia literalmente «Sí.» ni «¿Puedes repetirlo?».
Emite wake y ignored/transcript_doubtful como antes. TurnVisibleFacts transforma
sólo esos dos eventos en borradores conversation/clarification con causas
voice_wake_listening/voice_transcript_uncertain. Wake_detected, fondo ignorado,
turno no autorizado y barge_in no generan una respuesta añadida.

MainWindowViewModel usa PendingModelMessageQueue existente; no espera al modelo
en el callback UI. No inventa un pedido con la petición anterior: userText vacío,
sin contexto previo. El aviso caduca si cambia el turno; el acuse de wake también
si termina escucha. Pedir repetición sigue permitido después de cerrar captura.
La publicación compartida es la que conserva políticas y solicita TTS.
Llm proyecta las causas observadas como hechos; no fija la frase que se publica.

## Validación

Rojo antes de fuente:2fallos/85deseleccionados/1,15s, ambas frases fijas emitidas.
Primer Python falló por import pytest ausente; primer .NET por referencia vieja
del método renombrado. Se corrigieron ambos y se guardan sus logs.

Python registrado: `-m pytest tests/test_mind_voice_runtime.py
tests/test_compose_contract.py -q`:113pass,0skips,6,94s.
.NET Release filtro VoiceFeedbackTests|ModelMessage|FieldProductHonestTerminal:
14pass0skips808ms; tras añadir como controles las dos respuestas reales193,
16pass0skips946ms(sesión11832exit0). Incluye caducidad por nueva petición/fin de
escucha, ausencia de respuestas por ruido/intermedios y aceptación de prosa
compuesta. No es prueba acústica ni UI real.

`scripts/test_source_quality.ps1`: Fast32127exit0, todas las etapas verdes;
Release17,10s,0avisos/errores. Después sólo se añadieron dos TestCase literales,
compilados y ejecutados en el pase16. No nuevo Full durante reparación.

## Modelo real193

LlmRuntime.compose_user_message actual, Qwen3.5 override/perfil existente,
hechos nuevos y userText vacío; guardas/reintentos normales, sin prompts nuevos.
Sin App/UI/audio/operaciones. Se capturan payloads HTTP y respuestas completas.

| Evento | Respuesta literal | Tiempo | Adjudicación |
|---|---|---:|---|
| wake | Estoy listo para ayudarte con lo que necesites. | 0.547s | Acuse de disponibilidad útil; no afirma ejecución. |
| uncertain | ¿Podrías repetir lo que dijiste? | 0.344s | Pide repetir lo no entendido, sin inventar contenido. |

Comando193exit0;6,093s total,GPU3171,56MiB,RAM3203,63MiB,registro intacto.
Estas mismas dos frases fueron aceptadas por el compositor/política C# en el
pase16. No se presentan como prueba de publicación de la cola con UI real,
audio físico, reserva humana o ocho rutas finales.2/2 nativas útiles.

## Herencia y continuación

Se localizó sólo en lectura scripts/stt_real_voice_eval.py de Probando Gemma4.
Declara corpus data/stt_eval/real_mic/manifest.tsv y real_es, pero el manifest
real_mic no existe en esa ruta. No se deduce procedencia ni disponibilidad de
audios por el reporte histórico. No se tocó otro repositorio ni se descargó nada.

Siguiente: comprobar publicación por el recorrido App/cola sobre fuente192 y
continuar el bloqueo acústico183 con señales conservadas; DTLN128 aún experimental,
mezcla129 sigue discrepante. No regenerar187 para resolver la lectura inglesa:
191 ya aporta el observador independiente. No ejecutar scripts con hashes172.
Pendientes íntegros C03: ocho rutas finales,100humanos congelados y100/100, averías,
voz/entrada/wake/UI/4GB, promoción/instalación/continuidadC04–C09, Full y publicación.
