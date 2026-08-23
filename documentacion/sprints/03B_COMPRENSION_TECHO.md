# Goal 03B — Romper el techo de la comprensión

> **Esto es un goal, y este goal no se cierra a la primera.** Se lanza y corre
> hasta cumplirse, iterando: mides, cambias una cosa, vuelves a medir, y sigues.
> No pares a mitad a pedir aprobación ni a preguntar; ante una duda, elige la
> opción más razonable, anótala y sigue.
>
> El goal 03 ya cerró con un rechazo medido. **Éste no puede cerrar igual.** La
> salida honesta sigue existiendo, pero ahora exige más: sólo vale si has
> **movido** el techo y medido el nuevo, no si vuelves a derivar el viejo.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: se abrió con GPT-5.6 Sol y se cerró con **Grok 4.6**.

**Ojo con el nombre.** En la misma carpeta `Programacion` hay un repositorio
llamado `BAXY` a secas: ése es el intento anterior y es **fuente de herencia, no
tu sitio de trabajo**. Todo lo que escribas va en `BAXY Definitivo`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

## Qué es BAXY

Un compañero que vive en el PC de una persona y hace lo que le pide —tipo Jarvis,
local y privado—. Tiene carácter propio, es un «él», tutea, y confirma lo que hizo
comprobándolo: *«Listo, Spotify está abierto y sonando»*. Cuando falla lo dice
plano y con la causa. Nunca inventa que hizo algo, nunca actúa sin que se lo
pidan, nunca manda datos del usuario fuera.

Todo está en `documentacion/00_IDENTIDAD.md`, y **es lectura obligatoria antes de
tocar nada**. No son preferencias: son decisiones tomadas por el dueño con los
cuatro intentos anteriores del proyecto sobre la mesa. Si un diseño tuyo las
contradice, el que cambia eres tú.

## Las cinco leyes

**1. Hereda primero, estado del arte después, construye al final.** En ese orden.
¿Lo resolvió ya un BAXY anterior? Trae esa solución, o la mejor combinación.
¿Está resuelto ahí fuera? Impleméntalo. Construir es el último recurso, y hay que
decir por qué. Y al revés: **que BAXY ya lo haga de una manera no es razón para
conservarla.**

**2. Nada de sobreingeniería.** El mínimo código que cumpla, y que se active sólo
el necesario. **Si añades una capa, retira la que sustituye, en este mismo goal.**
Es la causa de muerte documentada de las cuatro versiones anteriores: tres routers
en serie, ocho capas de reescritura, un `agent.py` de 1.397 líneas contra su
propio objetivo de 400.

**3. Sólo se arregla lo que bloquea.** Lo demás, una línea en
`documentacion/APLAZADOS.md` y sigues.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo.

**5. Cada pieza sustituible, y ninguna más.** La forma —una responsabilidad por
pieza, cero código muerto— aplica a todo. El mecanismo de cambio —la medición que
decide, la declaración en el manifiesto— sólo a las piezas de
`documentacion/03_COSTURAS.md`. **Rellena las filas que toques antes de cerrar.**

Y la consigna: ésta es la **quinta** escritura de BAXY y tiene que ser **la más
rápida de las cinco** — no porque haga menos, sino porque **no vuelve a descubrir
nada que ya se descubrió**.

---

## El objetivo

**≥ 90 % sobre el corpus de paráfrasis frescas del goal 03**, con la tasa partida
por causa y la latencia medida al lado.

Hoy está en **46,0 %**. Y el goal 03 midió que con esta arquitectura no puede
pasar de **84,7 %** aunque la decisión y los vetos fueran perfectos. **Así que
este goal no es afinar: es mover el techo.** Si terminas sin haber cambiado la
arquitectura, has fallado aunque el número suba un poco.

El corpus no se cambia: `artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`,
SHA-256 `761c1bc3…`, 124 filas dentro de catálogo y 36 fuera. Puntúas **esos
mismos bytes**. Si lo amplías, publica el número sobre el original también, o no
hay comparación.

## Lo que el goal 03 ya midió — no lo pagues otra vez

Está entero en `documentacion/base/03_COMPRENSION.md`. Léelo antes de tocar nada.
El resumen que necesitas para no repetir trabajo:

| Tramo | Pierde de 124 | Estado medido |
|---|---:|---|
| Reconocedor determinista | 12 | Se midió contra su alternativa y **gana**: sirve 26 de 38 donde el modelo sirve 24, en 7 ms contra 2 s. Su techo declinando perfectamente son 3 filas más |
| Recuperación | 7 | **Ya está en su techo**: 91,9 % del camino que atiende, igual que el mejor banco offline (91,1 %). No hay hueco que cerrar |
| Decisión | 17 | Qwen3-4B ya batió al heredado 82 a 63 en decisión cruda |
| **Vetos** | **31** | **Aquí está el margen.** Ver abajo |

Aritmética del techo: regalando decisión y vetos perfectos, **105/124 = 84,7 %**;
con el reconocedor declinando perfectamente, **108 = 87,1 %**. Para 90 % hacen
falta **112**.

**No vuelvas a medir la recuperación ni a reemplazar el reconocedor.** Los dos
están medidos contra su alternativa y ganaron. Tocarlos es gastar el goal.

## Las dos palancas, y por qué son la misma

### 1. Diecisiete filas son un contrato mal escrito, no un fallo del modelo

De las 31 filas que el veto retira, **17 contestan «No puedo X» sobre algo que
BAXY sí sabe hacer**: «No puedo apagar el bluetooth», «No puedo sacar una foto de
la pantalla», «I cannot install VLC on this machine».

La causa está localizada: el veto marca `conversation_kind: "unsupported"`, que
significa *«no está en el catálogo»* — cuando lo que de verdad pasó fue *«no pude
confirmar el dominio»*. Son dos cosas distintas y el contrato del prompt sólo
tiene palabra para una.

Eso viola la identidad de frente: BAXY **dice que no sólo a lo que no sabe hacer**,
y aquí niega una capacidad que tiene. Arreglarlo pide un estado de conversación
nuevo en el contrato. **17 filas de 124 son 13,7 puntos.**

### 2. Las operaciones de argumento libre son sumideros, y por eso existe el veto

`task.create`, `note.create`, `message.send` y `web.search` aceptan **cualquier
texto**. Por eso absorben once de cada veinte peticiones fuera de catálogo:
`task.create("pedir un taxi")` es válido contra su propio schema, así que el
contrato no puede negarlo y hace falta una puerta curada que lo niegue por fuera.

Esa puerta es la que cuesta las 31 filas. **El veto no es el problema: es el
síntoma.** Mientras el dominio de argumentos sea todo el idioma, hace falta algo
externo que adivine el alcance, y adivinar cuesta filas correctas.

La salida es estructural: **que el contrato pueda negar lo que hoy niega la
puerta.** Dominios de argumento acotados donde tenga sentido, enumeraciones donde
el mundo es cerrado, y la puerta encogiendo a medida que el contrato crece. Cada
fila que el contrato rechaza por sí solo es una fila que la puerta ya no tiene que
sobre-vetar.

**Y aquí está el límite que no puedes cruzar:** la cobertura no baja. Acotar un
dominio de argumentos no es quitar una capacidad — es decir con precisión cuál
era. Si al acotar desaparece algo que la persona podía pedir, es una amputación y
está rechazada. El libro de cobertura y su sello están en
`experiments/mind_router_spike/measure_goal03_catalog_coverage.py`: hoy 169
operaciones, 158 alcanzables, 31 familias, sello `dc0a7893…`. **Publícalo antes y
después.**

## Las acciones encadenadas: no las construyes, pero no puedes romperlas

**El corpus del goal 03 no tiene una sola acción compuesta.** Sus 160 filas son
intentos sueltos, y las 23 que listan varias operaciones las listan como
**alternativas aceptables** —el puntuador acierta si coincide cualquiera—, no como
una secuencia a ejecutar. «Conéctate al wifi de casa» vale con
`wifi.connect.named` o con `wifi.connect`; ninguna fila dice «abre Steam y ve a la
biblioteca».

Eso lo deja ciego justo donde más duele. Cuando el goal 01 midió el coste de
consolidar —75,93 % → 62,96 %— nombró dónde se concentraba el daño: **follow-ups,
multilingüe y encadenado**. Vas a reformar los dominios de argumento del catálogo,
que es exactamente esa clase de cambio, con un instrumento que no puede verlo.

Y hay una razón de identidad, no sólo de medición: **encadenar es lo que permite
bajar el catálogo sin bajar cobertura.** Lo que deje de caber en `task.create`
cuando acotes su dominio tiene que absorberlo una cadena. Si nadie lo comprueba,
«la cobertura no baja» se vuelve una afirmación sobre el papel.

**Construir las misiones compuestas sigue siendo del goal 07. Tú no lo haces.** Lo
que sí haces es no dejárselo roto:

- **Un banco pequeño de misiones compuestas** —del orden de quince, en los tres
  idiomas, con las dependencias implícitas que la gente usa al hablar: «abre Steam
  y ve a la biblioteca», «busca X y guárdalo en una nota», «mira si tengo Z y si no,
  créalo»—. Si el goal 07 o los repositorios anteriores ya tienen uno, **heredalo en
  vez de escribirlo**: el goal 07 cerró una vez con 6/6 misiones y 25/25 pasos
  verificados, y ese material existe.
- **Se mide antes y después de tocar el catálogo**, y se publica igual que el
  corpus principal. No es un objetivo del goal: es una **guarda de regresión**.
- **Si baja, el cambio de catálogo se revierte o se acota** hasta que deje de
  bajar. Un catálogo que sube el acierto en intentos sueltos y rompe el encadenado
  no ha mejorado el producto — ha movido la pérdida a donde este goal no mira.

Aquí, a diferencia del resto del goal, **no persigas una cifra**: persigue que no
baje. Y si sube porque acotar los argumentos hizo más fácil encadenar, dilo — sería
la confirmación de que la palanca era la correcta.

## Lo que ya se midió y se rechazó — no escribas el sexto

Cada línea costó una corrida. Repetirlas es la forma más cara de perder el goal.

- **Cinco diseños de puerta léxica** sobre tres fuentes de vocabulario: R116,
  R117, R124 (dos veces), R126. **No escribas un sexto gate léxico.**
- **Abstención semántica, rechazada dos veces**: BGE-M3 por familia (R236) y un
  clasificador directo de 32 vías (R250).
- **El clasificador supervisado sobre MTOP**, entrenado en este goal 03 con 23.661
  filas etiquetadas contra el propio catálogo: **0,98 de AUC en su distribución y
  0,58 en paráfrasis libre**. Aprende la fraseología de MTOP, no la frontera de
  BAXY. En su punto de operación cambiaría 39 peticiones legítimas por 14 rechazos
  correctos.
- **Un gate derivado del catálogo** llevó el sobreveto de 224/560 a **385/560**.
- **Siete fuentes externas** para las seis operaciones `office.word.*` sin alias
  (R258–R262, R268, R269).
- **Modelos decisores rechazados localmente**: Qwen3.5-4B, Phi-4-mini,
  Qwen3-4B-Instruct-2507. Y Gemma-4-E2B, batido por Qwen3-4B en este goal.

El patrón detrás de los cinco rechazos: **todos intentaban decidir el alcance
mirando la forma del texto.** El goal 03 midió que el alcance no es una propiedad
del texto — es una propiedad del dominio de argumentos del catálogo. Un sexto
mecanismo que mire el texto va a fallar por la misma razón.

## La biblioteca primero, el estado del arte después

**Ley 1, y aquí tiene sitio de sobra.**

`biblioteca/00_INDICE.md` reúne **1.350 documentos** de las cuatro escrituras
anteriores, indexados por qué pregunta responde cada área;
`biblioteca/01_INVENTARIO.md` los lista con título y fecha para buscar por
palabra. Para este goal miran directamente:

- **`biblioteca/gemma4-agent/documentacion/02_router/`** — el router entrenado, su
  historial de sprints, `research/1_toolcalling.md`, `7_nlu.md`,
  `07_SKILL_RETRIEVAL_research.md`, `08_MICROAGENT_RETRIEVAL_research.md`.
- **`biblioteca/carter/la-razon-de-carter/15_skills_para_bench_540.md`** y
  **`06_benchmark_540.md`** — la consolidación a 16 herramientas y su medición.
- **`biblioteca/functiongemma/`** — el fine-tuning del decisor y el gate KVA.

Y el mapa del goal 01: `documentacion/herencia/00_MAPA.md`.

**Cuando la biblioteca se agote, ve fuera — y ahí busca de verdad.** El dueño lo
pidió explícitamente: lo más nuevo del estado del arte, papers incluidos. Las
líneas que tocan este problema y en las que conviene mirar qué hay hoy:

- **Relleno de argumentos con schema forzado.** Decodificación restringida por
  gramática o por JSON Schema. Es la más prometedora de todas para este goal: el
  relleno de argumentos está en **30,8 %** y pregunta lo que ya está dicho en
  **14 de 26** casos (§8). Si eso sube, sube el punta a punta directamente.
- **Detección de fuera de alcance con contratos**, no con clasificadores de texto
  — que es exactamente lo que el goal 03 refutó.
- **Predicción selectiva y calibración de la abstención**: decidir *cuándo* no
  decidir, con umbral medido en vez de elegido.
- **Recuperación y reordenado de herramientas** a escala de catálogo.

No cites de memoria: busca, lee, y si adoptas algo di de dónde salió. Y si lo que
encuentras ya está medido y rechazado arriba, no lo vuelvas a correr.

## Cómo iteras

Una cosa cada vez, con el número antes y después. El corpus tiene 160 filas y la
corrida es barata: no acumules cinco cambios y midas al final, porque entonces no
sabes cuál movió qué.

Instrumenta el crudo —qué se ofreció y qué se propuso **antes** de que ningún veto
lo toque— y **lee los textos visibles**. Una decisión contractual correcta puede
acompañar una respuesta inservible; ya pasó en este proyecto y por eso el goal 03
encontró tres estados de máquina inventados.

Y no midas sobre el corpus que el componente ya posee. `V9` sigue siendo el único
sello ciego sin consumir: no lo abras hasta tener un candidato que acreditar.

## Lo que no puedes romper

**Los tres ceros.** Cero efectos no pedidos, cero éxitos no verificados, cero
respuestas visibles fijas. Ganar acierto reabriendo un efecto no solicitado es un
rechazo, no una mejora — el goal 03 midió que hoy son 3 a 5 de 36 las decisiones
que *habrían* ejecutado un efecto que nadie pidió, con la puerta puesta. Ese
número no puede subir.

**La cobertura no baja.** Publica el libro y su sello antes y después. Y recuerda
que el libro cuenta **alcanzabilidad**, no comportamiento: una operación puede
seguir alcanzable «como paso de una cadena» sobre el papel y encadenarse peor en
la práctica. Por eso el banco de misiones compuestas es parte de esta regla, no un
extra.

**El listón del silencio.** 3 segundos. Hoy el p50 es 2,08 s con el equipo
tranquilo y **3,7–4,0 s mientras la persona usa el PC**, que es cuando lo va a
usar. Si tu cambio sube el acierto y empeora eso, no ha mejorado el producto.

## Criterios de cierre

- [ ] **≥ 90 %** sobre el corpus del goal 03, mismos bytes, partido por causa.
- [ ] **El techo re-medido y movido**, con la aritmética publicada igual que la del
      goal 03: cuánto pierde cada tramo y cuál es su límite ahora.
- [ ] Las **17 filas del contrato** resueltas: BAXY deja de decir «no puedo» sobre
      lo que sabe hacer, con el estado de conversación nuevo y su prueba.
- [ ] **Cobertura y cuenta antes y después**, con el sello del libro: no bajó.
- [ ] **El banco de misiones compuestas medido antes y después: no bajó.** Si bajó,
      el cambio de catálogo se acotó hasta que dejó de bajar, y está dicho cuánto
      se cedió.
- [ ] La **puerta curada más pequeña que antes**, o retirada, con el sobreveto
      medido en los dos casos.
- [ ] **Latencia junto al acierto**, p50 y p90, con el equipo cargado y tranquilo.
- [ ] Los **tres ceros intactos**, y las decisiones que habrían ejecutado un efecto
      no pedido en 3–5 de 36 o menos.
- [ ] Publicado **qué heredaste de la biblioteca y qué del estado del arte**, con
      la fuente. Y lo que probaste y no funcionó, con su mecanismo.
- [ ] Las filas de `03_COSTURAS.md` que toques, rellenas.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuándo puedes cerrar sin el 90 %

Sólo de una forma, y es más estrecha que la del goal 03: **habiendo movido el
techo y medido el nuevo.**

Si tras acotar los dominios de argumento y arreglar el contrato el techo pasa de
84,7 % a —digamos— 93 % y el producto se queda en 88 %, eso es un cierre honesto:
la arquitectura ya no es el límite y lo que falta está nombrado.

Si el techo sigue en 84,7 % porque no cambiaste nada estructural, **no has cerrado
el goal**: has vuelto a medir el del goal 03. Sigue iterando.

Y si al mover el techo descubres que el 90 % exige romper la cobertura o los tres
ceros, **dilo con el número** y para. Esa también es una respuesta, y es de las que
el dueño necesita para decidir — pero tiene que venir con la medición que la
sostiene, no con una impresión.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un goal que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo — pero este goal existe precisamente porque el
anterior ya usó esa salida. Gástala sólo si te la has ganado.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
