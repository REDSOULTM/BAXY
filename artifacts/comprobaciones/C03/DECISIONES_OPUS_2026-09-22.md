# Decisiones tomadas sin el dueño — Fase 3.5 (Opus 5.5, 2026-09-22)

Criterio (prompt de la sesión): lo ya sellado en el repositorio; si no alcanza, la práctica establecida; entre dos
iguales, la más fácil de revertir y la que nunca afirma un efecto que no ocurrió.

## 1. El tag `opus55-inicio` no existía
Situación: el prompt dice que el punto de partida está marcado con `opus55-inicio`; no estaba en el repositorio.
Opciones: parar; crearlo en el HEAD de partida. Elegido: crearlo (local) en `b5c9fe72`, el cierre del wall del
notebook que el prompt nombra como punto de partida. No se mueve ni se borra. Revertir: nada que revertir.

## 2. Clases de los turnos del guion del 21 que la tabla no nombra así
Situación: la tabla del 21 usa L/C/A/P/M/K; el prompt pide contexto, guarda, paráfrasis, familia, efecto inventado y
fuera de alcance. Elegido (campo `clase` en `contexto/dueno-2026-09-21.turns.jsonl`, checks intactos):
- «me llegó cortado» (turno 3) cuenta como **guarda**: es un detector que se come la charla, igual que «sin pedido».
- Turno 60 (log 230) salió «no encuentro un pedido» sobre charla: **guarda** (la tabla lo agrupa en la fila C 228–231).
- K (turno 35, el título inventado) y las L de lectura de un pedido (15, 22, 23, 58) cuentan como **paráfrasis**: es la
  vía del modelo (lista corta o elección), que es la clase 3 del prompt.
- 40–41 («no lo hiciste», «dímelo tú») cuentan como **contexto**: reconocer lo que pasó en el turno anterior.
- P del notebook (20, confirmación mal formada) y A/M cuentan como **fuera de alcance**: esperan el límite honesto.
Revertir: el commit del baseline (sólo cambia la etiqueta, no el esperado).

## 3. Cómo se llena el hueco: reescritura contextual, no una completion por dominio
Situación: el prompt pide un hueco único que la mente y el shell lean igual; hoy hay dos lectores (el shell concatena
«pedido + Aclaración confiable del usuario: respuesta» y re-decide; la mente tiene `_completed_missing_*` por dominio
y `previous_user_text`). Opciones: (a) otra completion por dominio para cada fallo del 21 (volumen relativo, brillo,
micrófono, búsqueda…); (b) reescritura contextual del turno (práctica establecida en asistentes de diálogo:
*contextual query rewriting*): cuando el turno depende del anterior, se reescribe como pedido autónomo con palabras
del contexto y ese pedido se clasifica por el camino de siempre. Elegida (b), con compuerta determinista de cuándo
reescribir y verificación de que la reescritura sólo usa palabras del contexto (no inventa objeto ni efecto). El shell
manda el objetivo pendiente en `turn.decide` y usa el pedido re-armado que devuelve la mente; deja de concatenar.
Revertir: los commits de la clase 1.

## 4. «Sí, dale» y charla ante una confirmación pendiente
Situación: `ConfirmationReplyParser` sólo aceptaba una palabra («sí», «dale»); «sí, dale» repetía «¿confirmar o
cancelar?» y la charla siguiente también. Elegido: una respuesta hecha sólo de palabras afirmativas confirma la
invocación pendiente (sigue ligada a esa invocación exacta); una charla (turno de conversación) reemplaza la
confirmación no iniciada, que queda cancelada sin ejecutar nada. Es lo más reversible: nunca ejecuta sin un «sí».
Revertir: el commit de la clase 1.

## 5. Réplicas con efectos: ventana guardia y VS Code intocable
Situación: el held-out cerró VS Code dos veces («cerralo» leído como la ventana activa + «sí, dale»). Elegido: (a) en el
producto, un pronombre con antecedente toma el objeto del pedido anterior y nunca «lo que esté delante»; (b) en el
harness, una ventana propia en primer plano durante cada guion y abortar si el proceso raíz de VS Code desaparece.
Revertir: el commit de la clase 1 (el harness conviene conservarlo).

## 6. Capas y destinatario del corpus histórico
Situación: la meta pide filtrar a lo dicho a BAXY en es/en. Elegido (`scripts/semantic_corpus.py`): idioma re-etiquetado
con `wordfreq` (voto por palabra entre es, en y pt/it/fr/de/ca/nl/ro), fuera lo que no es es/en/mezcla; destinatario:
fuera las fuentes `codex/*` (sesiones con los agentes: 1 503 de las 1 866 `observed_user` canónicas), las clases
`engineering_instruction`/`product_requirement`, marcado de harness y código. Capa C por fuente (router FunctionGemma,
train_v3, router_corpus de Gemma 4, benches/auditorías de Carter); B el resto no observado. Los 742 son capa A y se
juzgan contra la decisión que el registro acreditó; una fila abierta no cuenta como entendida. Descartes guardados con
motivo y muestra (privado, `%LOCALAPPDATA%\BAXY\semantic-corpus-v1\`). Revertir: el script (no toca `src`).

## 7. Proyección del catálogo actual sobre el oráculo
Situación: el oráculo (`historical_message_mapping.jsonl`) habla 43 familias del catálogo del goal 03; el producto
sirve 204 operaciones. Elegido: `_FAMILY_RULES` en `semantic_corpus.py`, pública (p. ej. `media.play.*` → `media.play`,
`window.*`/`input.*` → `window.manage`). Un efecto compuesto cuenta bien sólo si cubre todas las familias esperadas.
Revertir: editar esa tabla (cambia la cifra, no el producto).

## 8. Etiquetas a mano del registro real de BAXY Definitivo
Situación: los 95 turnos reales del registro privado (sesiones del 21) no tienen oráculo. Elegido: etiqueta por turno
según la tabla de PRUEBA_DUENO_2026-09-21_NOCHE.md, los commits sellados d8eb88367/0758398ed y D23 (motor → cualquier
turno honesto vale; «pon algo en Netflix» puede preguntar); los «sí/no» a una confirmación del shell quedan fuera
(los decide el shell, no la mente). Se reproducen con su historial original. Privado:
`semantic-corpus-v1\labels_real_log.json`. Revertir: borrar ese fichero.

## 9. Re-etiquetas del oráculo viejo (sólo capas B y C; la A nunca se re-etiqueta)
Situación: `historical_message_mapping.jsonl` llama «conversación» a pedidos claros al PC («abre el panel de control»,
«click the OK button») y a preguntas de información que la política sellada contesta buscando (KNOWLEDGE1473,
d8eb88367). Elegido, a la vista y contado en cada puntuación (`semantic_corpus.relabel`): RL1 — pregunta de
información esperada como conversación: también vale `web.search`; RL2 — orden al PC esperada como conversación:
vale cualquier efecto o una sola pregunta, no una conversación. Muestra de 50 re-etiquetas al azar para el dueño en
`%LOCALAPPDATA%\BAXY\semantic-corpus-v1\relabel_sample.json`. Baseline b5c9fe72: B 4 re-etiquetas, C 153. Revertir:
quitar `relabel` (cambia la cifra, no el producto).

## 10. «Ponme daredevil en disney»: reproducir, no límite
Situación: el prompt de la sesión pedía límite honesto «mientras no exista el motor»; pero el catálogo sirve
`streaming.play.named` con `disney_plus` (VIDEO1947/1949, verifica que el video avanza) y el commit sellado d8eb88367
hizo que «ponme/poneme/pone» reproduzcan. Elegido lo sellado: se espera reproducir (no se inventa ninguna operación y
un fallo de reproducción se dice como fallo verificado). Revertir: la etiqueta de `log:56` en
`labels_real_log.json`.

## 11. Filas acreditadas que la referencia ya decidía mal
Situación: la réplica sólo-decisión de los 742 sobre b5c9fe72 decide H0086, H0254 y H0690 («bajá/baja el volumen a N»)
como `package.install` (el lector de winget de REOPEN1993 toma «bajar» por «descargar»), aunque el registro las
acreditó como volumen. Elegido: esas filas se juzgan contra lo acreditado (etiqueta `audio.volume`), no contra la
decisión rota de la referencia; así el baseline las cuenta mal y el arreglo (léxico de ajustes: nada llamado
«volumen» se instala) las cuenta bien. Revertir: quitar las tres etiquetas.

## 12. Capa B: un ejemplo de documento cuenta sólo si tiene forma de turno
Situación: tras los filtros de idioma y destinatario, 88 de las 108 filas de la capa B eran criterios de aceptación y
notas técnicas cosechadas como «misión» («OCR PaddleOCR crop 600×200», «Offload parcial CPU+GPU», «monitoreo de GPU»);
el oráculo esperaba un efecto porque nombran una familia, y la capa medía eso (S2: 30/106). Nadie se lo dijo a BAXY.
Elegido (meta: «filtrado … a lo dicho a BAXY»): en la capa B, una fila es un turno sólo si abre —tras un vocativo o
muletilla— con una pregunta, un pedido o un verbo en imperativo y no lleva notación técnica
(`semantic_corpus.speech_act_of`, escrita para el corpus, independiente de los lectores del producto). Salen 89 filas
(`addressee_document_not_a_turn` 49, `addressee_document_technical_notation` 40); quedan 20. La capa C (frases dichas a
asistentes) no se toca: la regla tiraba 1 276 frases reales («clickeá aceptar», «avre spotify»). Muestra de 50 al azar
para el dueño: `%LOCALAPPDATA%\BAXY\semantic-corpus-v1\speech_rule_sample.json`. S2 con el corpus nuevo: B 10/20.
Revertir: quitar la rama `layer_of(row) == "B"` de `addressee_of` y reconstruir (cambia la cifra, no el producto).

## 13. Misión compuesta con una parte que BAXY no hace: ofrecer la parte posible
Situación: «abre Steam, ve a biblioteca y busca Batman», «abre Paint y dibuja un gato», «abre Spotify y baja el
volumen» terminaban en «no puedo abrir Steam ni…»: negaban la cláusula posible (límite falso, contrario a «cero
afirmaciones falsas»). La causa principal: `_catalog_unavailable_turn_decision` leía la frase entera como nombre de juego.
Opciones: (a) ejecutar la parte posible sin preguntar — descartada: hace sólo una parte de lo pedido sin que la persona
lo sepa (la conservación compuesta sellada lo prohíbe); (b) límite plano — es falso; (c) aclaración que cita las dos
partes con las palabras de la persona y pregunta si hace la posible. Elegido (c), lo más reversible: nada corre en ese
turno; el `objective` devuelto es sólo la parte probada, así un «sí» ejecuta eso y un «no, dejalo» no hace nada (el hueco
ya no toma un rechazo como respuesta). La frase no afirma que el resto sea imposible («no lo hago en el mismo pedido»),
porque puede ser posible por separado («cuánto es 25 por 4»). El cierre de catálogo ya no aplica a una compuesta.
Revertir: quitar `partial_offer` en `_decide_turn_result` y la condición `compound_clauses` del cierre de catálogo.

## 14. Dos etiquetas mías del registro real que contradecían la tabla del dueño
Situación: en §8 etiqueté log:177 («cuál fue la 1era iteración de un zombie en la historia») y log:70 (la fecha de
lanzamiento de un videojuego y su autor) como conversación, y log:179 («cuál fue el 1er libro de zombies»), con la misma forma, como
`web.search`. La tabla del dueño (PRUEBA_DUENO_2026-09-21_NOCHE.md, turnos 174–181, «primera iteración / primer libro»)
dice: «para hechos verificables, web.search antes de afirmar; hechos datados → búsqueda». Elegido: las dos pasan a
`web.search`, como la tabla. No tapa una regresión: la etiqueta vieja era la que contradecía la especificación; el
lector nuevo (`record_fact_query`) es el que la cumple. Cuenta: 2 filas de la capa A, ambas a la vista aquí. Revertir:
devolver las dos claves de `labels_real_log.json` a `conversation`.
