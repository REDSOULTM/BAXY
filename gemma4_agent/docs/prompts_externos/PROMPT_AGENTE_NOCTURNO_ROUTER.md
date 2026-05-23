# MISIÓN AUTÓNOMA NOCTURNA — LLEVAR EL ROUTER DE GEMMA4 AL MÁXIMO ABSOLUTO

Vas a trabajar **SIN PARAR** hasta lograr el mejor resultado posible del router de
tools de Gemma4 Agent. El usuario se va a dormir. Tenés **permiso TOTAL** sobre la
máquina: instalar dependencias gratuitas, correr cualquier comando, modificar
cualquier archivo del proyecto Gemma4. Trabajá toda la noche. Cuando el usuario
despierte, quiere ver el máximo resultado posible y la bitácora completa de todo lo
que intentaste.

**NO te detengas a preguntar. NO cierres sesión "para que el usuario revise". NO
declares victoria temprano. Iterá cientos o miles de veces si hace falta.** La única
forma válida de terminar es alcanzar el techo real demostrado con datos (ver
"CRITERIO DE PARADA").

---

## ═══════════════════════════════════════════════════════════════
## LA ÚNICA REGLA INVIOLABLE (más importante que cualquier número)
## ═══════════════════════════════════════════════════════════════

El router debe ser una **SOLUCIÓN UNIVERSAL**: funcionar en **CUALQUIER idioma** y
con **CUALQUIER forma de hablar** del usuario. Por eso está **TERMINANTEMENTE
PROHIBIDO**:

- regex que dependa de **palabras concretas** como mecanismo de decisión
- hardcode / listas de keywords / diccionarios `prompt → tool`
- cualquier truco que haga que el router funcione solo con "X palabra" o con un
  tipo de usuario y no con otro
- memorizar las frases del corpus de prueba (eso ES el hardcode prohibido)

La decisión de **qué tool va** debe salir del **SIGNIFICADO** del pedido: embeddings
multilingües, anclas/centroides de intención semántica, clasificación por similitud.
Nunca del léxico. Si necesitás "más cobertura", se logra con **mejores anclas y
descripciones semánticas**, NUNCA con más keywords.

### REGLA DE ORO
Un **80% honesto y universal VALE MÁS que un 95% logrado con hacks/keywords/overfit**.
Si para subir el número tenés que violar la regla universal, **NO lo hagas**. Preferí
el número más bajo pero limpio. Si te descubrís escribiendo una lista de palabras
para "ganar puntos", **detenete y borralo**. El usuario prefiere un router que
generalice a todos los humanos antes que un número inflado que solo sirve para el
español o para frases vistas.

---

## ═══════════════════════════════════════════════════════════════
## CRITERIO DE PARADA (cómo saber cuándo es el techo de VERDAD)
## ═══════════════════════════════════════════════════════════════

**NO pares por cansancio, ni por "ya está bien", ni por "es suficiente".** Solo podés
declarar "este es el techo" cuando se cumpla **TODO** lo siguiente:

1. **Hiciste al menos 4 intentos ADICIONALES y DISTINTOS** (enfoques diferentes, no
   el mismo cambio repetido con otro número) y **NINGUNO** mejoró la métrica de
   holdout. Ejemplo: si llegás a 80% y tras 4 enfoques realmente distintos seguís en
   ~80%, recién ahí 80% es el techo legítimo. Si llegás a 80% y solo probaste 1
   cosa, **NO es el techo: seguí**.
2. **Cada uno de esos 4+ intentos quedó documentado** en la bitácora: qué probaste,
   qué número dio en dev y holdout, por qué no funcionó.
3. **Los casos que siguen fallando los clasificaste** como "irresoluble justificado"
   (con la razón escrita) vs "fallo real". Si quedan **fallos reales**, NO es el
   techo: seguí.

**Mientras se te ocurra UN enfoque que no probaste, NO es el techo.** Obligate a
pensar en MUCHOS enfoques distintos antes de rendirte. Lista no exhaustiva:

- mejores anclas de intención (más frases-ejemplo, más idiomas en los centroides)
- reescribir las descripciones de las tools de estilo-implementación a
  estilo-intención (qué problema del usuario resuelve cada tool)
- **usar el contexto del turno anterior** (campo `prev`, ver abajo) en el harness
- re-ponderar / normalizar embeddings, combinar varias señales semánticas
- probar OTRO modelo de embeddings multilingüe (hay varios open-source gratuitos)
- separar la decisión en etapas (¿necesita tool sí/no? → ¿qué dominio? → ¿qué tool?)
- clustering de los misses por causa raíz semántica para atacar el grupo más grande
- una segunda señal: similitud del query contra ejemplos de uso de cada tool
- calibrar umbrales con datos (no a ojo), midiendo dev y holdout en cada cambio

---

## ═══════════════════════════════════════════════════════════════
## MÉTODO (medí, no creas — está en el CLAUDE.md del repo)
## ═══════════════════════════════════════════════════════════════

### Set de prueba (ground truth)
`gemma4_agent/data/router_eval_corpus.curated.jsonl` — **1733 casos**, ground-truth
**curado y verificado a mano por Opus** (100% etiquetado, coherente, 0 tools
inválidas). Cada fila:

```json
{"q": "...", "expected": ["tool", ...], "source": "...", "label_origin": "...", "prev": "<turno anterior, si existe>"}
```

- `expected: []` → un router correcto **NO** ofrece tool de dominio (smalltalk,
  preguntas de conocimiento que el LLM responde solo, directivas de comportamiento).
  Es una clase válida y deliberada (~465 filas) para medir que el router **no
  sobre-dispara**.
- `expected: ["a","b"]` → **lista de tools aceptables**: con que el router meta
  **una** de ellas en el subset, es acierto.
- `prev` → el **turno anterior real** del usuario (1332 filas lo tienen). El runtime
  SÍ tiene este contexto. **USALO** (ver abajo).

Harness: `scripts/router_eval.py` (`--split dev|holdout|both`).

### ANTIOVERFIT OBLIGATORIO — holdout ciego
- Desarrollá y tuneá **SOLO contra el 80% dev**. El **20% holdout es CIEGO**: solo lo
  medís para reportar, NUNCA para ajustar.
- El corpus **NO es la solución**: está PROHIBIDO memorizar esas 1733 frases.
- La métrica que importa es la del **HOLDOUT** (frases nunca vistas en desarrollo).
- Si `dev` sube pero `holdout` no → **overfitteaste**: revertí ese cambio.
- Validá universalidad además con **frases que VOS inventes en 6+ idiomas**
  (es, en, pt, fr, de, it) que NO estén en ningún log. Si dev sube pero las frases
  nuevas multi-idioma no mejoran → no es universal, revertí.

### Baseline actual medido (punto de partida)
- TOOL RECALL dev ≈ 0.859, holdout ≈ 0.845
- NO-TOOL keep ≈ 0.18  ← **casi sin atacar, gran oportunidad**

Hay **DOS frentes** abiertos:
- **(a) TOOL RECALL** (~0.845): la tool necesaria a veces no entra al subset.
- **(b) NO-TOOL keep** (~0.18): el router ofrece tools de más en smalltalk/conversación.
  Atácalo con la clase semántica chitchat/self/knowledge, **SIN keywords**. Subir
  esto sin bajar el recall es alto impacto.

### PALANCA DE ALTO POTENCIAL — el contexto previo (`prev`)
El router hoy se mide **SIN** el turno anterior. Muchísimos misses (≈67% del techo:
"ciérralo", "haz lo mismo", "mutea", "devuélvelo a 26", "acepta términos") son
**irresolubles aislados**, PERO el runtime SÍ tiene historial. El corpus ya trae el
campo `prev` con ese contexto real.

**Modificá `scripts/router_eval.py` para pasar `prev` al router cuando exista**, y
medí el router **CON contexto** — así medís cómo funciona de verdad en producción, no
descontextualizado. Esta es probablemente la palanca más grande para pasar de ~0.85 a
~0.95+ **sin un solo keyword**. El router debe entender el `prev` por **significado**
(embeddings del turno anterior + actual), no por reglas léxicas.

---

## ═══════════════════════════════════════════════════════════════
## EL CICLO QUE REPETÍS SIN PARAR (cientos / miles de veces)
## ═══════════════════════════════════════════════════════════════

1. Medí dev + holdout: `python scripts/router_eval.py --split both`
2. Agrupá los misses por **CAUSA RAÍZ semántica** (no por frase suelta).
3. Elegí **UN enfoque universal nuevo** para el grupo más grande de misses.
4. Implementalo (100% semántico, **sin keywords**).
5. Re-medí dev + holdout + tus frases nuevas multi-idioma.
6. ¿Mejoró **holdout** sin violar la regla universal?
   - **SÍ** → dejalo y **CORRÉ LOS TESTS** (paso 7).
   - **NO** o fue por hack → **revertí** y probá OTRO enfoque.
7. Corré la suite de no-regresión (deben quedar **TODOS verdes**, cero regresión):
   ```
   python -m pytest gemma4_agent/test_router.py gemma4_agent/test_router_corpus.py \
     gemma4_agent/test_router_v2.py gemma4_agent/test_intent_router.py \
     gemma4_agent/test_tool_call_rescue.py -q
   ```
   El bench Carter (540/540) debe quedar intacto.
8. Anotá el intento en la **bitácora** (qué probaste, número dev/holdout, veredicto).
9. Si mejoraste, **commiteá** con métricas y el porqué.
10. Volvé al paso 1.

**Repetí hasta que se cumpla el CRITERIO DE PARADA. NO antes.**

---

## ═══════════════════════════════════════════════════════════════
## RESTRICCIONES (del proyecto — son ley)
## ═══════════════════════════════════════════════════════════════

- **NO TOQUES** el proyecto Carter original:
  `C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI`
- **NO TOQUES** `gemma4_agent/data/carter_import/` (copias read-only para reproducir).
- Todo OSS y gratis (sin APIs de pago). Si la única opción buena es paga, decílo y no
  la implementes.
- Uso universal multi-usuario / multi-idioma (es la regla inviolable de arriba).
- Cero regresión en los tests existentes ni en el bench Carter 540/540.

---

## ═══════════════════════════════════════════════════════════════
## ENTREGABLES (cuando de VERDAD sea el techo)
## ═══════════════════════════════════════════════════════════════

1. **El mejor router posible**, 100% semántico/universal, cero keywords-hack.
2. **Reporte HONESTO** con:
   - número final de **holdout** (la métrica real),
   - cuántos intentos hiciste en total,
   - la **bitácora** de enfoques probados y descartados (qué, cuánto dio, por qué no),
   - los casos que quedan como **"irresoluble justificado"** con su razón,
   - separación clara entre **"resuelto"** y **"techo real"**.
3. **Tests verdes** + bench Carter 540/540 intacto.
4. **Commits** con métricas y el porqué de cada cambio (cerrar con
   `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`).
5. Si llegaste a un número y se mantuvo tras 4+ enfoques distintos, **decílo claro**:
   "este es el techo, lo probé de N formas, acá está la evidencia".

---

## ═══════════════════════════════════════════════════════════════
## RECORDATORIO FINAL
## ═══════════════════════════════════════════════════════════════

- Trabajá **sin parar**. El usuario está durmiendo. No esperes confirmaciones.
- **Iterá cientos o miles de veces.** El mejor resultado posible probablemente
  aparece después de muchísimos intentos, no de los primeros.
- **La única regla es la universalidad.** Cualquier mejora que viole eso no cuenta,
  aunque suba el número.
- **Sé honesto con los números.** No infles. Un techo bien documentado es un
  resultado valioso; un número falso no.
- Medí siempre dev **y** holdout. El holdout manda.

**Empezá ahora y no pares hasta el techo real. Buenas noches al usuario.**
