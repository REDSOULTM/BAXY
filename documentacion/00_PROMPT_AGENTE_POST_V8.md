# BAXY — asegurar la campaña, auditar V8 y atacar la recuperación

Eres el agente responsable de BAXY, en `D:\BAXY\source`. Lee **`goal.md`** entero
antes de tocar nada; su disciplina de medición sigue vigente completa.

**Voz, wake word y STT quedan fuera de tu alcance.** No abras esas campañas ni
cuentes sus defectos como tuyos. Con eso fuera, el §7 no puede declararse
cumplido: dilo en cada informe.

Este prompt tiene cuatro tareas **en orden estricto**. No empieces la siguiente
hasta cerrar la anterior.

---

## 1. Asegura la campaña. Antes que nada.

`git log` dice que el último commit es `1336e199` y `git status` da **~2.093
entradas sucias**. Toda la campaña reciente —el registro R124–R136, los
instrumentos de medición, dos sellos ciegos consumidos y varias reparaciones—
existe **sólo en el árbol de trabajo**. Un `checkout` desafortunado se lo lleva
entero. Esto es riesgo de pérdida total y va antes que cualquier otra cosa.

Qué hacer:

- **Mira antes de añadir.** No hagas `git add -A` a ciegas. Revisa qué hay:
  `git status --porcelain` agrupado por directorio, y `git check-ignore` sobre lo
  dudoso. Busca específicamente pesos de modelo, audio, cachés, `.tmp/`,
  ejecutables compilados (`bin/`, `obj/`) y cualquier cosa con credenciales.
  Si algo grande o secreto no está ignorado, **arregla `.gitignore` primero** y
  dilo en el informe.
- **Compromete en varios commits coherentes**, no en uno gigante: registro y
  documentación; instrumentos de medición; artefactos y recibos; reparaciones de
  runtime con sus pruebas. El objetivo es que un `git log` posterior permita
  entender la campaña, no sólo salvarla.
- Estás en la rama `codex/baxy-portable-structure`. Quédate en ella.
- **No reescribas historia, no fuerces nada, no borres el árbol sucio.**
- Al terminar: `git status` limpio o con sólo lo deliberadamente ignorado, y el
  informe dice cuántos ficheros entraron y qué quedó fuera y por qué.

## 2. Audita a mano el criterio que sostiene el titular de V8

V8 está consumido y su FAIL es definitivo. **No lo reabras, no lo recalcules, no
lo puntúes de nuevo.** Lo que vas a hacer es leer lo que ya está publicado.

R136 auditó a mano el criterio de **fabricación** y encontró que **3 de sus 4
positivos eran falsos positivos del scorer**. Ese mismo scorer produjo el número
que se está usando como titular de la campaña: **20 falsas negativas servibles
de 21**, y **decisión final correcta 1/21**. Ese criterio **no se auditó**.

Un scorer con un 75 % de falsos positivos demostrado en el único criterio
revisado no acredita el otro sin revisarlo.

Qué hacer:

- Lee el **texto visible** de las 21 filas servibles en
  `artifacts/holdout/veto_reach_v8.raw-replies.jsonl`, cruzándolo con
  `veto_reach_v8.json`, `veto_reach_v8.telemetry.jsonl` y
  `veto_reach_v8.turn-audit.jsonl`.
- Para cada fila decide, leyendo: ¿fue realmente una **falsa negativa servible**
  —el catálogo podía servirla y BAXY no la sirvió ni preguntó— o el scorer se
  equivocó? Clasifica también los casos intermedios: preguntó de forma útil,
  eligió otra operación defendible, o el propio corpus etiquetó mal lo servible.
- **Esta lectura no cambia el FAIL de V8 ni ningún umbral.** Publícala como
  auditoría separada, igual que hizo R136, con la tabla fila por fila.
- Publica el resultado en el registro como **R137** y actualiza el ledger.
- Si la auditoría revela que el corpus de V8 etiquetó mal lo «servible», eso es
  un defecto del instrumento y se registra como tal.

**Antes de la tarea 3 tienes que poder decir con evidencia leída cuál es la
exactitud servible real.** Si no puedes, no ataques la recuperación todavía: no
sabrías contra qué mides la mejora.

## 3. Ataca la recuperación

V8 midió en ciego las dos mitades del mismo componente:

| Frontera | V8 |
|---|---|
| Recuperación servible | **8/21 (38 %)** |
| Fuera de catálogo con cero candidatos | **0/9 (0 %)** |

Pierde la mayoría de lo que debía encontrar **y** nunca entrega vacío cuando no
hay nada que ofrecer. Las dos mitades importan: la primera impide servir, la
segunda le da al modelo ocasiones de elegir mal que ninguna puerta posterior
puede devolverle.

Reglas de esta tarea:

- **Mide antes de construir**, y mide contra los **cortes de exactitud ya
  existentes**, donde el oráculo dice cuál era la operación correcta.
- **No acortes ni ensanches un shortlist a ojo.** Un recorte sin oráculo tira la
  operación correcta.
- **Comprueba contra lo que hoy funciona antes de adoptar nada.** La vía
  determinista resuelve la mayoría de las peticiones servibles y no puede
  perder ninguna.
- Si el camino resulta ser una arquitectura de recuperación distinta, **investiga
  el estado del arte vigente en vez de asumirlo**, mide en esta máquina, y
  publica también lo que rechaces con su mecanismo entendido.
- **Un cero sobre un corpus que no puede contener el fallo no es evidencia de
  seguridad.** Al tasar cualquier regla, di explícitamente qué población podría
  haberla refutado.

## 4. V9 queda reservado

**No construyas ni selles V9 hasta tener algo que acreditar.** V8 se gastó y
además dejó de acreditar el árbol actual porque se editó un test después de
consumirlo, así que V9 es la única bala que queda para reclamar una mejora de
recuperación.

Cuando llegue el momento:

- **El código de medición y el scorer tienen que estar cerrados y hasheados
  ANTES de sellar.** Ninguna edición posterior, ni de tests ni del scorer, ni
  «para aislar rutas temporales». Si algo hay que tocar, se toca antes.
- La preinscripción declara qué confirma y qué espera que **siga fallando**. No
  puede predecir los dos resultados a la vez.
- Ninguna superficie reutilizada de V1–V8.
- Prevé desde el diseño una **auditoría manual del texto visible** separada del
  scoring, porque V8 demostró que el scorer se equivoca.
- Verifica al terminar que el árbol sellado y el árbol actual siguen siendo el
  mismo hash.

---

## Mecánica de la máquina

- Compuerta: `.\scripts\test_source_quality.ps1 -Mode Full`, **verde antes y
  después de cada tanda**.
- Ejecutar y pytest: `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1` con
  `PYTHONPATH=D:\BAXY\source\src`.
- Ruff: `%LOCALAPPDATA%\BAXYQuality\source-quality-v1`. **No es el mismo
  intérprete** y no tiene pytest.
- Tras cualquier cambio en `src/baxy_mind`, `scripts` o
  `experiments/voice_latency`, **re-pinea el hash del árbol congelado**: cinco
  constantes `EXPECTED_PROGRAM_TREE_SHA256` en `experiments/stt_quality/`, o la
  compuerta se pone roja en `tests/test_stt_quality_evaluators.py`. Comprueba al
  acabar que el pin sigue donde lo dejaste.
- **Sellos ciegos consumidos: V1–V8.** No los reutilices para promover nada.

## Cómo trabajas

Autoridad total. Decide, ejecuta, mide, **publica también lo negativo**. No
cierres ningún defecto aparcándolo: lo que despriorices sigue **abierto y
contado** en `known_defects_open`.

Reporta cada tanda con `Ritmo | Progreso | Errores | Falsos positivos | Tiempo
restante`, más una línea humana y **una frase sobre qué puede hacer hoy una
persona que ayer no podía**. Si no puedes escribirla, la tanda no movió el
bloqueante.

**El porcentaje sólo se mueve con evidencia**, y baja cuando la evidencia muestre
que algo que contabas no estaba cerrado.
