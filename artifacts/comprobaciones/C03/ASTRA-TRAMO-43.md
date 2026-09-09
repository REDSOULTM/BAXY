# C03 — tramo 43 completado; goal EN_CURSO

Tramo anterior: progreso (adjudicación de integrated-real22 y checkpoint 42).
Sin bloqueo externo; no cierre ni nuevo Full.

La traza integrated-real22, request_id 75, propone audio.status dos veces ante
«no silencies el audio» y el contrato rechaza esa observación no solicitada.
El detector de prohibición de la presentación ya reconoce el texto, pero su
clasificación sin efectos se reabre ante el catálogo. No es un fallo del provider.

Comparaciones locales sin ejecución de funciones:

- astra-negative-current-selection: 12 controles consumidos/sintéticos, política
  original 10/12, instrucción explícita de alcance 11/12. El caso original sigue
  fallando. 24 llamadas, 17,33 s, GPU 3497,56 MiB, registro intacto, exit 0 (15703).
  El catálogo conserva 26 candidatos reales de t20 y dos controles; historial
  reconstruido, no captura exacta del cable. Primer setup falló por superar 28
  candidatos antes de iniciar modelo/prerregistro; log conservado.
- astra-negative-no-history: misma selección sin historial, 11/12; sigue fallando
  el caso original. 12 llamadas, 10,45 s, GPU 3495,56 MiB, registro intacto,
  exit 0 (85059). Acertar Ponlo sin contexto no acredita resolución del referente.
- No se adoptan instrucciones extra ni se retira historial. Tras dos intentos
  sin resolver la causa, cambia la hipótesis.

Herencia adoptada: effect_intent.explicit_negative_constraint, del tramo 37,
reutiliza vocabulario compartido de acciones y morfología negativa; excluye
preguntas, declaraciones y compuestos. Ya gobierna constraint_ack, medido en
tramos 36/37. Ahora su resultado cerrado no se reabre por selección de una
operación cercana. No se añade léxico, detector, inferencia ni frase visible.
Las demás peticiones conservan interpretación, recuperación y autorización.

Contraste actual heredado: INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md y
INVESTIGACION_MODELO_C03.md (consulta 2026-09-06): ficha Qwen exacta, function
calling, formato restringido y réplica dotTXT. El protocolo garantiza forma,
no corrección semántica; la medición local rechaza cambiar prompt/contexto aquí.
La biblioteca 1_toolcalling.md es antecedente Gemma, no receta Qwen.

Fuente editada: __main__.py conserva la clasificación negativa ya cerrada antes
de los dos clasificadores. Cinco pruebas exigen no seleccionar ni observar después
de una prohibición completa, conservando el historial y el texto para la respuesta.
La validación y medición integrada figuran abajo; los procesos ya terminaron.

## Resultados de integración y fuente final

Las cinco nuevas pruebas pasan; junto con controles existentes: 16 pass,
893 deselected, 1,68 s. El primer intérprete de calidad no tenía pytest: se usa
el runtime existente. Dos fallos del fixture nuevo (forma de descriptor) se
corrigieron antes del verde; logs conservados, no fallos de producto ocultos.

closed-prohibition11: 8/11 respuestas útiles, exit 0 (99570), 99,22 s,
GPU 3497,56 MiB, RAM 5839,52 MiB, registro intacto. t5 reconoce la prohibición
y agrega un estado coherente con la lectura anterior; no se suspende por mera
redacción. t8 pide confirmar una consulta ya formulada; t9 no responde; t10
devuelve error de interpretación. t11 recupera la sesión y devuelve la hora.

Se probó retirar historial sólo de la generación constraint_ack, heredando la
representación medida36. closed-prohibition7 conserva los primeros siete inputs:
5/7 útiles, 63,08 s, GPU 3497,56 MiB, RAM 5034,97 MiB, registro intacto,
1566 exit 0. t5 promete presencia permanente sin interrupciones; t6 promete
audio fuerte y claro en lugar de limitarse a no silenciar. **Variante rechazada**:
se revierte únicamente ese cambio. La fuente adoptada conserva el historial.
No reabrir esta variante por preferencia de estilo; su resultado local fue peor.

Siete suites sobre la fuente adoptada: 2836 pass, 0 skips, 56,19 s
(29146 exit 0), scratchpad/c03-tranche43-owner.log. Fast sobre esa fuente:
verde, build 4,21 s, 0 avisos/errores (32384 exit 0),
scratchpad/c03-tranche43-fast.log. La variante descartada también pasó 2836 tests
y Fast: esos verdes no bastaron para aceptar su conducta.
Sin cambios C#; se conserva validación .NET de42. No Full/UI actuales.
Pines adoptados: scratchpad/c03-tranche43-adopted-pins.log; coinciden con los
anteriores a la variante. llm vuelve a 5420ee567d2ba107d1f3e7900340bbad388226205b169c357dd51120e30a3399;
__main__ queda aa290163fbf9ff44bc5e3a1de5bfa32e155168fc4ff21e9e524d9b222958ad56.

Todos los procesos propios están cerrados, incluidos1566/56058/5777.
El emparejado inicial de11 se pidió prematuramente
con8turnos y falló; se esperó el mismo proceso, que terminó, y se emparejaron11.

Próximo bloqueo demostrado por inspección local: effect_intent._has_contradictory_correction
marca como revocación cualquier «, no» o «y no», aunque cambie el objeto (hora/Steam).
La pregunta negativa también recibe CompoundEffectContract(1,()) como una prohibición.
Selector nativo aislado acierta estos tres controles; no reparar mediante otro prompt.
Hay que distinguir prohibición de pregunta y revocación del mismo efecto de restricción
independiente, conservando los controles de correcciones reales y peticiones parciales.

Corpus: los 1860 request_start del trace heredado sólo contienen type/chars/preview,
sin canal ni autor. No certifican autoría humana. Las rutas de las sesiones Gemma
no están en C:/Users/usuario/.gemma4 ni D:/Perfil/.gemma4; el corpus congelado conserva
los literales. Usar manifiestos/snapshots para continuar procedencia, no inventarla.

PRUEBAS_PROHIBICIONES_Y_ALCANCE_C03.md: 36 llamadas del modelo y 18 respuestas
del producto, con entradas literales, fallos y enlaces a payloads. No son casos
frescos ni un porcentaje de C03. Sin commit/push, main intacta, sin bloqueo externo.
