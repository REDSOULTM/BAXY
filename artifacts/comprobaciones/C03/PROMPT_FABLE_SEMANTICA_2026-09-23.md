# Prompt para Fable 5.1 (Hive) — «Semántica al estado del arte, unificada y legible»

Copiar desde la línea `---8<---` hasta el final y pegarlo tal cual como primer mensaje de la sesión de Fable 5.1
del miércoles 2026-09-23, ANTES de retomar el computer use. El prompt está escrito para ese modelo: contexto
explícito con rutas, objetivo medible, restricciones duras, orden de trabajo, entregables y criterio de cierre.
Fable planifica y ejecuta; el dueño sólo responde lo que el prompt marca PREGUNTAR.

---8<---

Sos Fable 5.1 trabajando en el repositorio `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama
`codex/kiro-goal-c03` (leé entero `AGENTS.md`, `documentacion/00_IDENTIDAD.md` y
`artifacts/comprobaciones/C03/DECISIONES_DUENO_2026-09-20.md` antes de tocar nada; respetá las reglas duras del
§7 de `artifacts/comprobaciones/C03/PLAN_POSTGOAL_2026-09-20.md`).

## Misión (una sola)

Llevar la **capa semántica de BAXY** —todo lo que decide qué quiso decir la persona antes de que actúe el
modelo— al estado del arte, **unificada en un solo lugar y legible por cualquier agente**, sin perder ni una
capacidad ya sellada. El dueño lo resume así: «que BAXY siempre conteste bien y siempre haga lo que se le pide».
Hoy esa capa está repartida y es frágil: cada fallo real se parcha con un regex nuevo y el siguiente pedido con
otra redacción vuelve a fallar. Ejemplos reales del 2026-09-21 (registro privado
`%LOCALAPPDATA%\BAXY\dev-mente-v2\conversation\conversation.v1.jsonl`, sesiones del dueño 16:02–16:10 y de su
madre 19:27–19:41), ya arreglados uno a uno en `0758398ed` y `d8eb88367`, y que NO deben volver a pasar con otra
redacción: «abre una busqueda de power automate en mi navegador» dio una pregunta sí/no que «Si»/«Confirmo» no
cerraban; «Hazla, te dije que si mil veces» → «No pude entender»; «ponme daredevil en disney» → «No puedo…»;
«Si tuvieras un sueño…» → «No puedo tener un sueño tal como fue pedido»; «dame info de la migraña» → «No pude
entender»; «ponme word» → pregunta absurda; «hazme un currículum» → rechazo; «¿Quieres que te cree un documento
en Word?» → «si» → la misma pregunta.

## Lo que la prueba del dueño del 2026-09-21 (noche) demostró — léelo primero

`artifacts/comprobaciones/C03/PRUEBA_DUENO_2026-09-21_NOCHE.md`: 60 turnos reales, 38 mal. El fallo dominante NO es
un literal sin leer: es el **contexto**. BAXY pregunta «¿cuánto?», el dueño dice «20», y BAXY pregunta «¿quieres
que ajuste el volumen?» y luego no entiende «sí»; dice «no, en YouTube» a una pregunta de BAXY y BAXY vuelve a
preguntar; «investigala» / «activalo» / «súbelo a 100» pierden el antecedente de uno o dos turnos atrás; frases de
charla («me gusta crear cosas como tú») disparan «En eso no encuentro un pedido para mí». Y lo peor: «Claro, ya le
hice click» con cero operaciones (efecto inventado). Regla del dueño (turno 164): «BAXY debe funcionar de forma
generalizada, no sólo para los 742 casos: esos son ejemplos de los cuales se debe generalizar». Por eso `read(text,
history, catalog)` recibe el historial de verdad y el harness corre **conversaciones enteras**, no literales sueltos.

## Dónde vive hoy la semántica (inventario de partida; verificalo con `Grep`)

- `src/baxy_mind/effect_intent.py` (~20 000 líneas): lectores por regex (`*_request`, `resolve_explicit_effects`,
  `resolve_explicit_clarification_intent`, `known_unsupported_effect_request`, `conversation_only_content_request`,
  `_entity_lookup_query`, `_topic_research_query`, lectores de mensajería, Steam, wifi, audio, streaming, etc.).
- `src/baxy_mind/__main__.py`: decisión determinista de turno (`_explicit_stable_no_effect_turn_decision` con ~30
  predicados, `_explicit_turn_decision`, `_closed_unsupported_request`), grounding de argumentos
  (`_explicit_arguments_from_evidence`, `_ground_explicit_arguments`, completions con historial), selección.
- `src/baxy_mind/llm.py`: hechos de causa (`_CAUSE_FACT`), instrucciones por operación, vetos del compositor
  (`_payload_fact_defect`, `missing_name`, `extra_claim`…), formas de presentación.
- `src/baxy_mind/planner.py`: alias de enumerados, predecesores condicionales.
- `src/Baxy.App/`: `UserMessagePolicy`, `MindClarificationPolicy`, `ObservedResponseLiterals`,
  `ConfirmationReplyParser`, `NaturalMemoryRequestParser`, `NaturalSystemStatusRequestParser`.
- Pruebas: `tests/test_effect_intent.py` (1880), `tests/test_turn_policy.py` (1041), `tests/test_c03_*`,
  `tests/test_reopen1993_*`, `tests/test_fase*`, `tests/test_owner_session_2026_09_21_browser_search.py` (51),
  `tests/test_generalization_*`, y las cien (`artifacts/comprobaciones/C03/cien-v18.turns.jsonl`, CIEN.md).

## Qué tiene que quedar (entregables)

1. **Un solo lugar.** Un paquete `src/baxy_mind/semantic/` (o el nombre que justifiques) con UNA puerta de
   entrada (`read(text, history, catalog) -> Reading`) y adentro, por dominio, módulos cortos y homogéneos
   (`messaging.py`, `apps.py`, `media.py`, `web.py`, `files.py`, `system.py`, `knowledge.py`, `dialogue.py`…),
   cada uno con: la tabla de formas aceptadas (español rioplatense y neutro con voseo/tú, inglés, sin tildes, con
   errores típicos del oído de BAXY), las guardas (qué NO es), y sus ejemplos como tests. Nada de regex sueltos
   en `__main__.py`/`llm.py`: esos archivos consumen `semantic`, no leen texto.
2. **Legible.** Un `documentacion/SEMANTICA.md` que cualquier agente entienda en diez minutos: la lista de
   intenciones, de dónde sale cada una, cómo se resuelve un antecedente («abrilo», «hazla», «la que tú quieras»),
   cómo se prioriza (efecto explícito > aclaración tipada > conocimiento/redacción > límite conocido > modelo), y
   la regla del dueño 2026-09-19 («lo mal dicho lo arregla BAXY») y D24 (actuar con contexto determinista o
   candidato único; preguntar sólo con ambigüedad real).
3. **Estado del arte, no más parches.** Normalización única (fold, tildes, clíticos «ponme/poneme/pone», voseo,
   typos por edición ≤2 sobre nombres del catálogo), gramática por intención en vez de una alternancia por
   frase, y un corpus de regresión que se ejecute offline en segundos: los 742 literales del registro privado
   (`%LOCALAPPDATA%\BAXY\C03-survey-requirements336-private\requirements.jsonl`), las cien, y las conversaciones
   reales del registro privado del perfil `dev-mente-v2` (agregá un lector que las convierta en casos
   esperados; los finales que fueron malos son el «no debe» de cada caso). El harness corre cada conversación
   **turno a turno con el historial acumulado** (pregunta de BAXY → respuesta corta → pedido completado; anáforas
   «lo/la/eso/investigala/activalo»; «ahora lo mismo en X»; «para/deshazlo»), no los literales aislados; los
   guiones contextuales del notebook (`artifacts/comprobaciones/C03/contexto/*.turns.jsonl`) son parte del corpus.
   Publicá el harness (`scripts/semantic_replay.py`) y su tabla de aciertos antes y después, por conversación.
4. **Sin regresiones y con sellos.** Fast/Full verdes sin relajar nada (`scripts/test_source_quality.ps1 -Mode
   Full`, tier pytest con el python del runtime `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\
   python.exe -X utf8 -m pytest -p no:cacheprovider tests`), `repin_program_identity.py` antes de cada Full
   (sellos que hashean el árbol), cien 100/100 tras cada cambio de mente (`scripts/run_baxy_conductor.ps1` con
   `cien-v18.turns.jsonl`, comparada contra la anterior en CIEN.md), y una tanda sellada por dominio migrado si
   la migración cambia una lectura acreditada. Nunca `git add .`, nunca squash/rebase, nunca editar `src` con
   algo corriendo, ningún envío real fuera de los destinos de prueba (Música, Ron92, la casilla 302).

## Orden de trabajo

1. Medí primero: construí el harness de replay y publicá la tabla de fallos actual (por dominio y por tipo de
   fallo: no leído, leído mal, aclaración innecesaria, límite falso, final infiel). Sin esa tabla no diseñes.
2. Diseñá la arquitectura de `semantic/` en `documentacion/SEMANTICA.md` (borrador) y pedí al dueño SOLO las
   decisiones que cambien comportamiento visible (PREGUNTAR, una vez cada una, con opciones y tu recomendación).
3. Migrá dominio por dominio, con los tests viejos verdes y los nuevos escritos, commit por dominio con la cifra
   del harness en el mensaje. Los lectores viejos se eliminan cuando el nuevo los cubre; no dejes dos caminos.
4. Cerrá con Full verde, cien 100/100, sellos re-anclados, `SEMANTICA.md` final, y un informe con cifras
   (aciertos del harness antes/después, tests, cien) en `artifacts/comprobaciones/C03/SEMANTICA_<fecha>.md`.
   Reportá al dueño al cierre de cada dominio con cifras, no con narrativa.

## Lo que no hay que hacer

- No tocar el motor de computer use (`fable/computer-use-engine`) en esta sesión ni fusionarlo: es la sesión
  siguiente.
- No cambiar el catálogo de operaciones, los riesgos ni los contratos sellados; la semántica decide, no ejecuta.
- No «arreglar» un fallo añadiendo un regex más en el sitio viejo: cada arreglo entra en `semantic/` con su test
  y su fila del harness.
- No relajar pruebas (skip/xfail/umbrales) ni re-anclar sellos para tapar una regresión real.

Empezá leyendo los ficheros indicados, corré el harness inicial y presentame la tabla y el plan de dominios antes
de migrar nada.
