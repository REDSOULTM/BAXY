# Propuesta de método para la comprensión de BAXY (2026-09-25)

Para la sesión Opus 5.5 de la Fase 3.5 / uso real. La escribió una sesión de revisión a pedido del dueño, después
de revisar el trabajo hecho y la tanda 7. No cambia la meta ni el plan de cierre (tandas 11 y 12 ciegas deciden);
cambia **cómo** se arregla entre tanda y tanda. Es una propuesta: si mides algo mejor, gana la medida.

## 1. Por qué cambiar el método

- **La primera pasada no sube.** Tandas nuevas: 52 → 60 → 60 → 66 → 64 %. En la tanda 7 (revisión de la sesión de
  revisión, sin arreglos): sueltos 15/25 (60 %), turnos de conversación 11/25 (44 %), **seguimientos que dependen del
  turno anterior 6/18 (33 %)**. Fallan justo los elípticos más comunes: «¿y el finde?» (definió la palabra), «¿y en
  Mar del Plata?» (⚠), «allá» (Curicó), «actually make it 9», «esa no, otra más movida», «is the entrance free».
- **Cada arreglo es una regla escrita a partir de un ejemplo.** Muestra de la tanda 6: «<título> por <intérprete>» con
  una lista de 50+ palabras prohibidas tras «por»; «quiero el sound de nuevo» con listas de verbos; una regla de risas
  en `llm.py`; «¿hoy es lunes?» en C# de la App con un comentario de que no debe divergir de la mente. Desde 9277c10e:
  `src` +14 093/−2 092, pruebas +19 194, lectura nueva fuera de `semantic/` (103 líneas con regex en `llm.py` y
  `__main__.py`, 12 en la App). Ley 2 de AGENTS.md: si añades una capa, retira la que sustituye.
- **Se siguen inventando datos**: «0 % de lluvia en casa de tu hermana» (lugar desconocido), «Raphinha, 12 goles» como
  máximo anotador de los Lakers.
- **El canal con la ventana se cortó dos veces** (tanda 4b: 9 × 240 s sin respuesta; tanda 7, 00:45) sin diagnóstico.

## 2. Cómo lo resuelve el estado del arte

- **Home Assistant Assist (2026)**: primero las frases deterministas (rápidas, predecibles, obligatorias para lo
  sensible), y **todo lo que no casa pasa al LLM**. Las reglas cubren lo frecuente y lo peligroso, no la cola larga.
- **Rasa CALM**: el LLM lee el mensaje **en el contexto de la conversación** y emite comandos contra flujos
  deterministas; la ejecución no la decide el modelo. Es el diseño de BAXY (la mente propone, el kernel autoriza), y
  su lección es que la comprensión del turno va con la conversación, no con listas de intents.
- **Alexa, contextual query rewriting** (ACL 2023, «Unified Contextual Query Rewriting»): una etapa propia, antes de
  la NLU, reescribe el turno como pedido autónomo (elipsis, correferencia, errores del oído) y decide **cuándo**
  reescribir con una predicción de disparo. En producción bajó los defectos un 16,65 %. La reescritura con LLM y
  ejemplos en contexto funciona sin entrenamiento (arXiv 2502.15009).
- **Seguimiento del estado del diálogo (slot carryover)**: lo que se nombró (ciudad, canción, temporizador, partido)
  queda en un estado estructurado y el turno siguiente lo hereda; es el cuello de botella conocido de la NLU
  conversacional.
- **Generalizar con datos, no con reglas**: la literatura de intents usa paráfrasis generadas por un LLM para
  entrenar el clasificador o para ejemplos en contexto; las reglas «no introducen patrones nuevos».
- **Modelos pequeños con herramientas (BFCL)**: Qwen3-4B con prompt da ~62 % global pero **~35 % en varios turnos**;
  xLAM-2-3b-fc-r ~66 % global y ~56 % multi-turn; Qwen3.5-4B salió el 2026-03-02 con tool calling. El 33 % de los
  seguimientos de la tanda 7 se parece mucho al techo multi-turn del modelo actual.

## 3. Método propuesto (en orden; cada paso se mide con la primera pasada de la siguiente tanda ciega)

1. **Estado del diálogo explícito.** Un objeto por conversación en `semantic/dialogue.py` con lo último nombrado
   por tipo: lugar, fecha, contenido que suena o se pidió, temporizador/alarma/recordatorio creado (con su id), tema
   buscado, última operación y su resultado. Lo escriben los resultados verificados, no el texto de BAXY.
2. **Reescritura contextual por defecto, no por forma.** Se reescribe todo turno que sea corto, sin verbo propio,
   empiece por conector o corrección («y», «¿y…?», «and», «actually», «mejor», «no, …», «esa/eso/otra»), lleve
   deíctico o pronombre («allá», «ahí», «this», «that one») o sea respuesta a una pregunta de BAXY. No se reescribe un
   pedido completo y nuevo. La reescritura la hace el modelo con el estado del paso 1 y el turno anterior, y mantiene
   la verificación que ya existe (sólo palabras del contexto, sin efecto ni objeto inventado). Criterio: «¿y en Mar
   del Plata?» → «¿va a llover el finde en Mar del Plata?», «actually make it 9» → «cambia el temporizador de la pasta
   a 9 minutos».
3. **No inventar.** Si falta un dato de la persona que el pedido necesita (dónde vive la hermana, qué ciudad), se
   pregunta; si la búsqueda no trae nada que responda, se dice «no lo encontré» y nunca se completa con un dato
   de otra fuente o de memoria. Prueba de regresión con los dos casos de la tanda 7.
4. **Cada fallo se clasifica antes de arreglarlo**:
   - contexto → pasos 1–2 (mecanismo, nunca una regla para esa frase);
   - vocabulario o forma nueva → **datos**: el literal y 10–20 paráfrasis (dialectos, spanglish, erratas) al banco de
     intenciones (`intent_bank`, `family_classifier`, `semantic_family_arbiter`), reentrenar y medir;
   - regla determinista → sólo si es frecuente o sensible (volumen, brillo, cerrar, borrar, confirmar), dentro de
     `semantic/`, y retirando la que reemplaza. Presupuesto: publicar en cada tanda cuántas reglas y líneas se
     añadieron y cuántas se retiraron.
5. **Ejemplos en contexto recuperados.** `decide_turn` recibe 5–8 ejemplos parecidos al turno (E5 sobre el banco:
   742, tandas vistas, paráfrasis) con su decisión correcta. Así lo aprendido de una tanda ayuda a frases vecinas sin
   escribir una regla.
6. **Un experimento acotado de modelo (ley 4).** Con el perfil de 4 GB, comparar Qwen3-4B, Qwen3.5-4B y xLAM-2-3b
   sólo en la decisión y la reescritura de los seguimientos de las tandas 1–7 (sólo decisión, sin efectos): calidad,
   latencia, RAM y VRAM. Si ninguno mejora con margen, se sigue con Qwen3-4B y queda escrito.
7. **Consolidar.** La lectura del pedido que entró en `llm.py`, `__main__.py` y la App pasa a `semantic/` (la App
   consume la decisión de la mente, no relee el texto), y las reglas que los pasos 2–5 cubren se retiran medidas con
   las 742, pytest y las tandas.
8. **Diagnosticar el corte del canal** DevTools/WebView2: si le pasa a una persona, BAXY se queda mudo.

## 4. Criterios

- La cifra que manda entre pasos es la **primera pasada de una tanda nunca vista** (y, dentro, los seguimientos).
  Si un paso no la sube, se revierte o se replantea; las tandas repetidas sólo prueban que un arreglo funciona.
- Las tandas 11 y 12 siguen ciegas y deciden el cierre, sin cambios.
- Cada paso en commits chicos, con la cifra y el balance de reglas en el mensaje.

Fuentes: Home Assistant Developer Docs (LLM API) y guías de agente híbrido; Rasa, «Dialogue Understanding» y «LLM
Command Generators»; Amazon Science, «Unified Contextual Query Rewriting» (ACL Industry 2023); arXiv 2502.15009
(reescritura conversacional con ICL); arXiv 2406.17163 (paraphrase and aggregate para intents); BFCL v3 y
comparativas de modelos pequeños con herramientas (2026); Qwen3.5 (qwen.ai, 2026-03-02).
