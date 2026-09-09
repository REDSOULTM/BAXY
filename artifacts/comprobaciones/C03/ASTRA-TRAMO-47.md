# C03 — tramo47: contexto de explicaciones sencillas — EN_CURSO

Parte de la fuente46 adoptada. El error de gravedad del panel46 ya estaba en
raw pre_veto: no se añadió al validar ni componer. No se cambia el modelo ni se
inventa un filtro sobre Luna/gravedad. Se reutilizan los instrumentos y la solución
de temas nuevos del tramo41, y el contraste documental de modelo/formato33/40.

## Aislamiento

astra-knowledge-context47:16 llamadas cruzan políticas presentes/ausentes y
contexto público de baseline46/corregido46.38,06s,GPU3497,56MiB,RAM3138,84MiB,
registro intacto,exit0. No reproduce Luna. La reconstrucción de cinco pares omite
una respuesta huérfana: BuildMindHistory conserva12mensajes incluyendo input
actual; chat retira el duplicado y recibe5usuarios+6asistentes. Esa comparación
parcial no demuestra la causa del fallo. Sin políticas, cifrado trunca a256tokens
en las dos variantes: no promover esa retirada ni afirmar que el modelo solo cumple.

astra-wire-context47 ejecuta el prefijo10 y tres diagnósticos adicionales con
hook sitecustomize de sólo observación de _post. Captura real en wire-36612.jsonl,
sin modificar payload, respuesta o registro.75,20s,GPU3497,56MiB,RAM5136,50MiB,
exit0; no UI/audio ni benchmark de latencia (hay I/O diagnóstico). La forma del
historial y las políticas quedan comprobadas, no inferidas desde constantes.

astra-wire-replay47 reutiliza tres payloads capturados. Sólo cambia contexto:
capturado, reconstruido del panel fallido con semántica12mensajes y ninguno.
Reproduce literalmente las tres respuestas del panel fallido, incluida Luna.
El contexto vacío elimina ese ejemplo incorrecto conservando instrucciones,
template, temperatura0,seed0 y256tokens.9llamadas,14,73s,GPU3497,56MiB,
RAM2940,19MiB,registro intacto,exit0. No se presenta la reconstrucción del panel
original como captura original. Sí queda reproducido su fallo por una diferencia.

## Reparación

request_reading._TOPIC_TAIL reconoce colas terminales de estilo como
«pero sin tecnicismos», «pero en simple» y sus formas inglesas. El mecanismo
starts_new_definition_topic existente reconoce entonces el tema explícito único
y separa el contexto ajeno sólo para esa generación. No modifica el historial
almacenado ni el pedido original, ni clasifica efectos o introduce nombres de casos.
La cola nueva está anclada al final: referencias posteriores, coordinaciones,
temas ya mencionados y descripciones complejas conservan contexto. No otra capa,
prompt, sampler ni validador de hechos.

Pruebas del lector y payload verifican temas, referencias, ausencia de modificación
del historial entregado y conservación de la petición literal. Primer1123pass
finales/0skips/6,63s. La primera ampliación pasó1117pero se acotó antes de medir:
una cola abierta podía absorber una referencia posterior; dos controles lo evitan.
Otras cinco suites:1822pass,115subtests,0skips,54,03s. Total2945pass,115subtests.
Logs %TEMP%/c03-topic47-owners-payload.log y c03-topic47-related.log.

astra-topic-context47 repite sólo el mismo prefijo10 sobre fuente corregida,
con el mismo hook, modelo y orden.10/10 respuestas útiles. t8 explica cifrado,
t9 respaldo y t10 atracción/tirón, sin el ejemplo falso de Luna. Se aplica la
rúbrica del dueño: una analogía sencilla no exige una explicación exhaustiva.
65,12s,GPU3497,56MiB,RAM4760,80MiB,registro intacto,exit0. No cien reservados,
no UI/audio ni cierreC03. Fast47 verde,build4,54s,0avisos/errores,exit0
(sesión61026); log%TEMP%/c03-topic47-fast.log. Diffcheckverde. No Full.

## Bloqueos siguientes demostrados en la captura

t11 hora/audio/CPU: el shell crea sólo system.time y audio.status antes de llegar
a Python. IsClockAndAudioStatusRequest usa Contains, y
TryExecuteClockAndAudioStatusAsync arma dos pasos fijos. Heredado338e4cb; Python
reconoce tres efectos con la misma entrada. La respuesta admite que no leyóCPU,
pero no cumple la petición. Hipótesis siguiente: retirar atajo duplicado dejando
el plan genérico; no ampliar otro regex de clasificación en C#.

t12 lectura de ruta literal: nativo elige filesystem.read.text. Extracción intenta
usar la ruta como resourceId y queda truncada a35caracteres por el contrato; gate
action_grounding pide otra vez la ruta ya escrita. Hace falta resolver el recurso
antes de leer, no cambiar provider ni aceptar una ruta como identidad de recurso.
No se alcanzó el error previsto de archivo ausente. Cero etiquetas de progreso.
Por eso siguen sin acreditarse progreso/error con prosa; t13 vuelve a dar la hora.

Los procesos de medición69289/67465/39085/47953 y pruebas27035 están cerrados.
No fuente C# cambiada47. Reserva100, UI/voz final, contratos posteriores, limpieza
de ramas nativas antiguas, Full y publicación siguen pendientes en C03.
