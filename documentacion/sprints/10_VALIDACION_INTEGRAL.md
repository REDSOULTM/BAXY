# Goal 10 — La validación integral del producto

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Esfuerzo de razonamiento: **`high` de suelo**.

**Ojo con el nombre.** En la misma carpeta `Programacion` hay un repositorio
llamado `BAXY` a secas: ése es el intento anterior y es **fuente de herencia, no
tu sitio de trabajo**. Todo lo que escribas va en `BAXY Definitivo`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

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

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden,
y sin saltarte pasos:

1. **¿Ya está resuelto en un BAXY anterior?** Este proyecto se ha escrito cuatro
   veces y muchos problemas ya cayeron. Trae esa solución — o la **mejor
   combinación** de las que hay, que muchas veces es lo que gana.

   **Empieza en [`biblioteca/00_INDICE.md`](../../biblioteca/00_INDICE.md).** Son
   1.350 documentos de las cuatro escrituras anteriores —estudios, auditorías,
   investigaciones encargadas, benchmarks y rechazos con el mecanismo entendido—
   indexados por qué pregunta responde cada área. Si buscas algo concreto,
   [`biblioteca/01_INVENTARIO.md`](../../biblioteca/01_INVENTARIO.md) los lista
   todos con su título y su fecha.

   Abrir una línea de investigación sin haber buscado ahí primero es la forma más
   cara de perder un día.
2. **¿Está resuelto ahí fuera?** Papers, documentación, repositorios, la respuesta
   de alguien que se topó con lo mismo. Si hay una solución conocida y buena,
   **impleméntala** en vez de inventar la tuya.
3. **Sólo si ninguna de las dos**, constrúyelo. Y entonces di en el cierre por qué
   ninguna servía.

Y al revés: **que BAXY ya lo haga de una manera no es razón para conservarla.** La
vara es «¿es la mejor opción conocida hoy?», no «¿es lo que había?». Heredar es
traer lo que funciona, no conservar lo que estaba.

Es una pasada, no una persecución. En cuanto tengas algo que cumple el objetivo,
deja de buscar mejor: perseguir el estado del arte sin parar es una carrera sin
final, y este producto tiene que salir.

**2. Nada de sobreingeniería.** Escribe el mínimo código que cumpla, y que se
active sólo el necesario. Nada de capa sobre capa, ni abstracciones para un
segundo caso que no existe, ni opciones que nadie pidió, ni defensas para fallos
que nadie ha visto ocurrir.

No es estética: es la causa de muerte documentada de las cuatro versiones
anteriores de este mismo proyecto. Carter se diagnosticó a sí mismo —*«el proyecto
crece por acumulación, no por reemplazo»*— con tres routers en serie, ocho capas
de reescritura y un `agent.py` de 1.397 líneas contra su propio objetivo de 400.
Diez de sus dieciséis segundos por turno eran sobrecarga suya.

**Si añades una capa, retira la que sustituye, en este mismo goal.** Un goal que
cierra con menos código del que encontró y el objetivo cumplido es mejor goal.

**3. Sólo se arregla lo que bloquea.** Un fallo que impide usar BAXY o avanzar
este goal se arregla. Una fragilidad teórica o un camino de error que nadie ha
recorrido: una línea en `documentacion/APLAZADOS.md` y sigues. Este Goal 10 cobra
esa lista antes de validar el árbol final, así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera, contando RAM, disco, CPU en reposo y
arranque en frío. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto.

**5. Cada pieza sustituible, y ninguna más.** BAXY no se termina. Dentro de dos
meses saldrá un STT mejor o un modelo más pequeño que entiende igual, y hay que
poder cambiarlo sin reescribir el producto: **el código de hoy no tiene por qué ser
el de mañana**.

Esto va en **dos niveles**, y confundirlos es el error que lleva a la
sobreingeniería que prohíbe la ley 2.

**Nivel 1 — la forma, y aplica a todo lo que escribas.** No cuesta nada: es
escribirlo bien.

- **Una responsabilidad por pieza.** Si describirla necesita la palabra «y» tres
  veces, son tres piezas. `MainWindowViewModel`, con 3.678 líneas y 169 miembros,
  es el contraejemplo y está en este repositorio.
- **Nadie conoce las tripas de nadie.** Se depende del qué, no del cómo. Si cambiar
  el interior de A obliga a tocar B, no hay borde entre A y B.
- **Las dependencias apuntan hacia dentro.** `Contracts` no depende de nada,
  `Kernel` sólo de `Contracts`. Nunca al revés.
- **Nada global y mutable.**
- **Cero código muerto.** Lo sustituido se borra en el mismo cambio; dos
  implementaciones vivas de lo mismo son la acumulación con otro nombre.

**Nivel 2 — el mecanismo de cambio, y sí cuesta trabajo.** Por eso lo llevan las
piezas del registro de `documentacion/03_COSTURAS.md`: las que de verdad se van a
comparar contra un candidato. Son tres cosas y sin las tres la pieza no es
sustituible de verdad: el borde del nivel 1, **la medición que decide si el
candidato es mejor**, y la declaración en el manifiesto para que el cambio no pueda
ser silencioso.

Lo del medio es lo que suele faltar y lo que de verdad importa: con un corpus y un
número, cambiar de motor es una tarde; con una interfaz preciosa y sin número no
puedes decidir si mejoraste, así que no lo cambias nunca.

Lo que **no** se escribe: una interfaz con un solo implementador «por si algún
día», un registro de plugins, o configuración para elegir entre implementaciones
que no existen. Eso no es modularidad, es peso.

Si este goal toca una pieza del registro, **rellena su fila antes de cerrar**: qué
medición decide un sustituto, qué elegiste y por qué, y la fecha. La fecha importa
— una medición de hace ocho meses decidió entre candidatos que hoy ya no son los
mejores.

## Y una consigna que une las cinco

Ésta es la **quinta** escritura de BAXY, y tiene que ser **la más rápida de las
cinco**. No porque haga menos —es la definitiva— sino porque **no vuelve a
descubrir nada que ya se descubrió**.

Cada hora que gastes re-derivando algo que ya está medido en estos repositorios es
una hora que este proyecto ya pagó una vez. Si te encuentras diseñando desde cero
algo que suena a que alguien ya resolvió, para y ve a buscarlo primero.

---

## Cómo trabajas aquí

No es estilo: es lo que esta máquina y este harness te dan, y lo que este repositorio
ya midió que hace falta decir.

**Persiste hasta el cierre.** Este goal termina cuando sus criterios están marcados o
cuando has medido y publicado que uno es inalcanzable. No devuelvas el control a mitad
para confirmar un plan, pedir permiso ni resumir progreso: son las dos únicas formas de
acabar. Ante una duda, elige la opción más razonable, **anótala** y sigue.

**Cuánto explorar, y cuándo parar.** Busca lo justo para dar el paso siguiente, no un
mapa completo del árbol. Regla de parada: en cuanto puedas nombrar el archivo y la
línea que vas a tocar, deja de buscar y tócalo. Si dos lecturas seguidas no cambian lo
que ibas a hacer, sobra la tercera. Acota las búsquedas a `src tests scripts main.py`
salvo que vayas a la evidencia a propósito, y lee rangos, no ficheros enteros. En la
shell **no existe `rg`**: es PowerShell. Antes de abrir algo grande, mira el tamaño:
`git ls-tree -r -l HEAD -- ruta`.

**Lo que tarda, en segundo plano.** Corridas de medición, compuerta y builds Release se
lanzan en segundo plano y sigues con trabajo independiente; recoges el resultado cuando
llegue, sin sondear en bucle.

**Un solo hilo.** Nada de delegar en sesiones hijas: pagan otra vez contexto y
razonamiento para devolverte un informe que además tienes que leer. Esto se resuelve
aquí. Única excepción: una exploración de sólo lectura acotada cuyo resultado quepa en
rutas + rangos + conclusión.

**Di lo que vas a hacer antes de una tanda larga, y qué salió después.** Una o dos
frases, no un diario. Lo que importa que quede escrito va al repositorio, no al chat.

**El estado, escrito en el repositorio.** La ventana es de 500K y se compacta sola al
80 %: lo que sólo esté en la conversación se pierde. Deja el mapa, la medición y las
decisiones en ficheros a medida que avanzas, y haz commit después de cada paso medido.
Plantilla: `docs/AI_HANDOFF_TEMPLATE.md`.

**Y lo commiteado se empuja, en el mismo momento.** `git push origin main` detrás de
cada commit —no al final del goal—. El dueño trabaja en varias máquinas y lo que no
está en `origin` no existe para las demás: este repositorio llegó a acumular **101
commits sin publicar**, cinco goals de trabajo que vivían en un solo disco. Si el push
lo rechaza porque otra máquina empujó antes, `git pull --rebase origin main`, resuelves
y vuelves a empujar; no lo dejes pendiente.

**Verificas ejecutando, no navegando.** BAXY es un producto de escritorio y aquí no hay
herramientas de navegador. Un cambio de interfaz se comprueba con `py main.py` y con
sus pruebas, y dices qué no pudiste verificar.

---

## El objetivo

**BAXY cumple íntegramente su identidad y responde bien a cada mensaje real que
ha recibido.**

No es una demo que funciona cuando le preguntas lo correcto ni un promedio que
oculta respuestas malas. Es un asistente al que alguien pide cualquier cosa en su
forma natural, que entiende, responde o actúa correctamente y demuestra lo que
afirma.

**Éste no es el adorno final: es la única validación integral del producto.** Cuando al dueño se le
preguntó qué evita una quinta reescritura del proyecto, respondió *que el producto
se use*; y qué tendría que pasar en un año para decir «esto sí quedó»: *que lo use
a diario sin pensarlo*. Los nueve goals anteriores existen para llegar hasta aquí.
Si BAXY sale de éste sin usarse, no sirvió ninguno.

## Cómo se rompe este goal

**La fricción de arrancarlo es lo que lo mata.** Por eso BAXY vive en la bandeja
del sistema, arranca con Windows y escucha siempre. Y lo que hay que quitarle de
encima al usuario, en sus palabras, es *levantarse del teclado*.

Ahí hay una tensión real que este goal tiene que resolver, no esquivar: **arrancar
siempre + escuchar siempre + hablar siempre** contra el presupuesto de recursos. La
salida no es recortar la presencia —ésa es una decisión del dueño— sino conseguir
que la presencia cueste poco. Mide el consumo en reposo y publícalo.

## No se mide por calendario

**Decisiones del dueño, 2026-08-21 y 2026-08-25:** esperar una semana, ejecutar un
*soak*, dejar BAXY 24 horas encendido o imponer cualquier prueba de duración
prolongada queda expresamente fuera de este goal y de los demás. No lo restaures.

La estabilidad se comprueba con escenarios acotados y reproducibles: arranque en
frío, reinicio del proceso, recuperación de fallos y repetición concentrada. El uso
continuado llegará después, cuando el producto terminado se use normalmente; no es
una puerta de entrega.

Lo que el uso real siga encontrando después del lanzamiento entra por
`documentacion/APLAZADOS.md` y se cobra en una tanda de mantenimiento. No desaparece:
deja de ser una puerta antes de entregar.

## Qué haces

Validarlo como producto real y arreglar todo lo que impida que cumpla. La unidad de
trabajo no es una métrica agregada: es **cada mensaje, la respuesta concreta que
BAXY produjo y la verdad que existía cuando la produjo**.

Presta atención a lo que no se mide fácil:

- **Lo que cansa.** Una fricción que aparece cuarenta veces al día importa más que
  un fallo que aparece una vez al mes.
- **Lo que sorprende mal.** Momentos en que BAXY hace algo razonable según su lógica
  y raro según la de la persona.
- **Lo que no se pide dos veces.** Si algo funciona pero cuesta tanto pedirlo que la
  persona deja de usarlo, ese algo no funciona.

Comprueba en producto vivo —no sólo leyendo el código— tres decisiones que sólo se
verifican usándolas:

1. **Los dos modos.** El normal confirma sólo si se destruyen datos; el *bypass* se
   activa con un ajuste consciente y sigue encendido hasta apagarlo.
2. **La narración** de lo que hace, y que BAXY se pueda usar entero sin ver la
   pantalla.
3. **La memoria y la privacidad.** BAXY recuerda preferencias, lo que se le suele
   pedir y la conversación reciente; y la persona puede **ver, editar y borrar** todo
   eso de verdad — no confiar en que un botón hace lo que dice. Y que **buscar en la
   web** funcione sin que salga contenido del usuario.

## El corpus congelado de dos niveles

No vuelvas a mezclar mensajes del usuario con prompts de desarrollo, ejemplos o
datos curados. La proyección reproducible está definida por:

- `scripts/build_observed_user_corpora.py`;
- `tests/data/historical_observed_user_corpora.v1.json`;
- `tests/data/historical_messages.jsonl` y
  `historical_message_mapping.jsonl` como autoridades privadas.

Regenera los JSONL locales con:

```powershell
py scripts\build_observed_user_corpora.py
```

Los derivados contienen texto privado, están ignorados por Git y no se publican.
El manifiesto versionado conserva las reglas, conteos y hashes sin exponerlos.

### Nivel 1 — todos los mensajes reales observados

`historical_observed_product_turns.v1.jsonl` contiene **1.947 ocurrencias reales**:
1.857 de Probando Gemma 4 y 90 de Gemma local. Son 626 textos exactos únicos:
1.078 conversaciones o preguntas, 808 misiones, 56 restricciones, 3 preferencias
y 2 reportes de fallo.

Las repeticiones son parte de la evidencia. **Las 1.947 ocurrencias se reproducen y
evalúan una por una.** Los 626 únicos sirven para diagnosticar y agrupar causas,
pero no permiten ejecutar una vez y dar por aprobadas sus repeticiones.

### Nivel 2 — todas las misiones accionables reales

`historical_observed_user_missions.v1.jsonl` contiene las **808 ocurrencias** que
pidieron una acción: 281 textos únicos, 32 familias de operación y 74 entradas
potencialmente compuestas. Es un subconjunto del Nivel 1, no un dataset sintético.

Cada misión cruza mente, catálogo, autorización, plan, kernel y frontera de
provider. Acertar una etiqueta con `tools_executed: 0` no certifica una misión. Las
lecturas y efectos seguros o reversibles se prueban físicamente; compras, mensajes,
borrados personales y otros efectos peligrosos se recorren con ámbito desechable y
fixture del provider, conservando riesgo, confirmación, parámetros, postcondición y
terminal. Una limitación ambiental se publica aparte y nunca convierte una
capacidad rota en éxito.

### Anillo adicional de generalización

Después de cerrar los dos niveles, ejecuta también los **2.036 contratos canónicos
`product_1_0`** de `historical_missions.jsonl` y los holdouts públicos y frescos
vigentes. Son requisitos y casos curados adicionales: amplían cobertura, pero no se
presentan como mensajes reales ni inflan 1.947 o 808. Las 48 trazas
`trace_only_not_acceptance_commitment` sólo conservan procedencia.

## La identidad completa es el oráculo del producto

Recorre `documentacion/00_IDENTIDAD.md` **decisión por decisión** y construye una
matriz trazable. No basta citar el documento entero. Cada fila debe enlazar la
decisión, los mensajes que la ejercen, la evidencia del producto vivo y su veredicto.

La matriz cubre como mínimo conversación natural y carácter propio; comprensión y
aclaración mínima; ejecución, planes y confirmaciones; verificación antes de afirmar;
estados terminales honestos; iniciativa sólo cuando fue pedida; cero respuestas
visibles fijas; memoria visible, editable y borrable; privacidad local; consulta web
sin enviar contenido del usuario; voz, narración y uso sin mirar la pantalla; modos
normal y *bypass*; interfaz, arranque y presencia ligera; catálogo, autorización,
providers, operaciones compuestas y degradados ambientales. Si Identidad contiene
algo más, también entra: esta lista no la recorta.

## Cada respuesta se juzga individualmente

El modelo que ejecute este goal debe revisar **cada respuesta de BAXY**, no sólo el
resumen del runner. Esto incluye las 1.947 ocurrencias reales, los 2.036 contratos
adicionales, los holdouts y los escenarios físicos. Por cada respuesta deja un
registro con:

- mensaje exacto, respuesta exacta y trazas de operación o plan;
- contrato esperado independiente de la salida que se está juzgando;
- hechos del sistema y fuentes disponibles en el instante de la respuesta;
- veredicto `pass` o `fail`, razón concreta y evidencia que lo sostiene;
- comprobación de pertinencia, naturalidad, idioma, honestidad, acción pedida,
  riesgo, confirmación, verificación y estado terminal, según aplique.

El juicio semántico agregado nunca puede tapar una respuesta individual. `review`,
`unresolved`, “parece razonable”, similitud textual, mayoría de votos o promedio no
son estados de aprobación. Si el juez no puede demostrar que la respuesta es
correcta, esa fila no pasa.

Las respuestas sobre hechos dinámicos reciben una comprobación especialmente
estricta. “¿Qué hora es?”, fecha, clima, estado de una aplicación, contenido del
portapapeles o cualquier dato cambiante se contrasta con una lectura autoritativa
capturada en ese mismo turno y con zona horaria y tolerancia explícitas. Una hora
plausible pero incorrecta falla. Una acción afirmada sin postcondición falla. Una
respuesta relacionada con la pregunta pero factual o lógicamente falsa falla.

El evaluador puede procesar registros por lotes para trabajar con un contexto
seguro, pero emite y persiste **un veredicto razonado por ocurrencia**. Además revisa
manualmente una muestra estratificada de aprobados y el 100 % de los fallos. El
planner evaluado nunca es su propio oráculo.

## Aquí la ley 1 mira hacia fuera

Este goal es el único que compara BAXY con lo que la gente usa de verdad. El
montaje estándar de asistente local llega hoy a 1–2 s extremo a extremo con 12 GB de
VRAM y un modelo de 8B; BAXY apunta a 4 GB. Si llegas a algo comparable con una
cuarta parte de la memoria, eso es un resultado — publícalo.

Y si al usarlo descubres que una pieza tuya es notablemente peor que lo que
cualquiera se instala en una tarde, cámbiala. Que la hubiéramos construido nosotros
no es un argumento.

## La latencia de BAXY se acerca al suelo del modelo

El modelo pequeño no es una cifra bonita en el manifiesto: se elige para que la
persona reciba antes la primera señal, la decisión y la respuesta completa. Si la
orquestación consume el ahorro del modelo, BAXY incumple aunque el LLM aislado sea
rápido.

La evidencia vigente ya demostró el estándar alcanzable el 2026-07-30. Con payloads
byte-idénticos, mismo servidor, sampler, seed, presupuesto, slots y 32 pares ABBA, el
delta BAXY−directo fue p50 **−6,0 ms**, IC95 [−72,6, +71,3] ms: la sobrecarga no era
separable de cero. Hereda el método y su evidencia; no inventes un benchmark más
favorable: [`07_LATENCIA_END_TO_END.md`](../01_ARQUITECTURA/GUIA_AGENTES_IA/07_LATENCIA_END_TO_END.md)
§ «Overhead con cargas byte-idénticas» y
[`REGISTRO_DE_MANTENIBILIDAD.md`](../01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md)
§ «Fase correctiva y hallazgo de producto».

Mide dos costes distintos y nunca los mezcles:

1. **Sobrecarga de infraestructura:** mismo payload exacto enviado directamente al
   runtime del modelo y a través de BAXY. Incluye Python, HTTP, serialización,
   transporte y composición que no sea inferencia.
2. **Amplificación arquitectónica:** diferencia entre una inferencia directa mínima
   capaz de resolver el caso y el turno completo de BAXY. Toda llamada adicional al
   LLM, retry, reformulación, veto, grounding o generación serial cuenta aquí,
   aunque el servidor la etiquete como “tiempo de modelo”. No se puede esconder
   sumándola al baseline.

Para conversación, aclaración, acción simple, misión compuesta y camino de error,
publica por separado, como mínimo: tiempo hasta primera señal visible, decisión de la
mente, Core/provider, primera respuesta sustantiva y respuesta terminal; p50, p95 y
máximo; caliente y frío; número de inferencias, tokens y retries. El tiempo propio de
un provider externo —por ejemplo esperar una ventana— se informa aparte y no se usa
para absolver a la mente.

El criterio es acercarse **todo lo físicamente posible**, no cumplir un techo cómodo:

- el delta de infraestructura con payload equivalente no muestra sobrecarga positiva
  estadísticamente significativa; BAXY−directo p50 no supera **+25 ms** y el límite
  superior de su IC95 no supera **+100 ms**;
- cada inferencia adicional o tramo serial del camino crítico tiene una necesidad
  demostrada mediante ablación: si retirarlo mantiene identidad, exactitud,
  honestidad, seguridad y verificación, se retira;
- cada retry es un fallo que se elimina o se justifica con una condición real y
  acotada; un retry sistemático jamás es latencia inherente del modelo;
- el beneficio de promover un modelo más pequeño se demuestra extremo a extremo
  sobre el mismo corpus y hardware. Si BAXY absorbe esa ganancia con orquestación, la
  promoción no cuenta como mejora.

No se compra velocidad rompiendo la identidad: no se eliminan verificación,
confirmaciones necesarias, privacidad, naturalidad ni corrección. Entre dos caminos
que pasan todos los criterios gana el de menor latencia completa, y el otro se borra.

## Cómo se arreglan los defectos

De verdad: nada de bajar el umbral que lo detectó, marcar `skip`/`xfail`, mover a
pendientes ni envolverlo en un fallback. Lo que nadie ha visto ocurrir se anota y
se sigue.

Está prohibido enseñar el examen: nada de frases, hashes, `message_id` ni respuestas
históricas dentro del runtime. Cada fallo se reduce a una familia de conducta y se
arregla en su dueño: mente, router, catálogo, policy, planner, kernel, handler,
provider o compositor. Los holdouts frescos tienen que demostrar que generalizó.

Un fallo de honestidad o una respuesta individual incorrecta es un defecto grave,
no una anécdota ni un porcentaje aceptable. Se arregla y la corrida final completa
se repite sobre el árbol corregido.

## Lo que sigue en pie

Todo. Los tres ceros no se relajan porque el goal sea de uso. La compuerta sigue
verde. Los invariantes de arquitectura siguen siendo invariantes.

## Dónde está este goal ahora

Reinicio limpio (2026-08-29) desde el cierre del Goal 9. El inventario
heredar/descartar está en
[`artifacts/goal10/inherit-discard.v1.md`](../../artifacts/goal10/inherit-discard.v1.md).
El handoff vivo está en
[`artifacts/goal10/HANDOFF.md`](../../artifacts/goal10/HANDOFF.md).

La evidencia de agentes anteriores (r120, r121–r123, dosis 2026-08-24) es
histórica: no certifica este corpus. No se presenta como resultado de esta corrida.

## Recuento de cierre (dueño)

In-scope = español, inglés o spanglish **y** no ambiental.
El recuento de fail del Goal 10 **omite** (no convierte en pass) las filas
ambientales y los otros idiomas reales (de/fr/it/pt). Esas filas conservan fail
individual. Las ambientales van al Goal 11.
BAXY no promete idiomas fuera de es/en/spanglish.
`system.power` en este host queda fail-closed; no se invoca en vivo.

## Criterios de cierre

- [x] El builder reproduce el manifiesto publicado: **1.947 / 626** en Nivel 1 y
      **808 / 281** en Nivel 2, con hashes coincidentes, mapping único y 0 conflictos
      de contrato.
- [ ] Una corrida final completa sobre el runtime y modelo locales actuales produce
      una respuesta real para cada una de las **1.947 ocurrencias**. No se deduplican
      ejecuciones, no falta ni sobra un `message_id`, y hay 0 `review`, 0 unresolved,
      0 exclusiones automáticas, 0 timeouts ocultos y 0 skips.
- [ ] El modelo que ejecuta el goal deja **1.947/1.947 veredictos individuales** con
      respuesta, contrato, evidencia factual del turno, `pass`/`fail` y razón. La
      corrida final tiene 1.947 pass y 0 fail; todo hecho dinámico fue contrastado
      con una fuente autoritativa contemporánea.
- [ ] Las **808/808 misiones accionables** cruzan la tubería real exigida. Operación
      o plan, parámetros, riesgo, confirmación, autorización, postcondición,
      verificación y terminal son correctos en cada fila; no hay operación no pedida
      ni éxito no verificado.
- [ ] Los **2.036 contratos canónicos adicionales `product_1_0`** y los holdouts
      públicos y frescos vigentes están verdes y también tienen veredicto individual
      por respuesta, publicados por separado de la métrica de mensajes reales.
- [ ] `00_IDENTIDAD.md` está recorrida entera en una matriz: **cada decisión** tiene
      evidencia de producto vivo y veredicto aprobado. Los dos modos, narración,
      memoria, privacidad, voz, interfaz, arranque, presencia ligera y operaciones
      compuestas se comprobaron usándolos, además de lo que el documento contenga.
- [ ] Cero respuestas visibles fijas y ningún arreglo dependiente de un literal del
      corpus; los holdouts demuestran generalización.
- [ ] Arranque en frío, reinicio del proceso, recuperación de fallos y repetición
      concentrada están comprobados con escenarios acotados. **No hay soak, espera de
      24 horas ni requisito de duración prolongada.**
- [ ] La latencia se publicó contra el modelo directo con cargas equivalentes y
      metodología emparejada: delta BAXY−directo p50 ≤+25 ms, límite superior IC95
      ≤+100 ms y ninguna sobrecarga positiva estadísticamente significativa.
      Conversación, acciones y misiones
      informan primera señal, decisión y terminal con p50/p95/máximo, frío/caliente,
      llamadas, tokens y retries.
- [ ] La amplificación arquitectónica frente a una inferencia directa equivalente
      está publicada y minimizada. Cada llamada o tramo serial adicional conserva una
      ablación que demuestra que retirarlo rompe un criterio del producto; no queda
      ningún retry sistemático ni sobrecarga evitable que absorba la ventaja del
      modelo pequeño.
- [ ] Los caminos de error se recorrieron a propósito: modelo ausente o inválido,
      provider que falla o miente, duplicación, timeout, disco sin espacio y sesión
      interrumpida. Ninguno termina en afirmación falsa, acción doble o constante.
- [ ] `APLAZADOS.md` está vacío: cada entrada fue arreglada, descartada con medición
      o declarada limitación ambiental con degradado honesto.
- [ ] `03_COSTURAS.md` no tiene filas vacías; no queda código muerto, implementación
      duplicada, bandera que preserve una versión sustituida ni documentación que
      contradiga el producto.
- [ ] Evidencia privada cruda y resumen versionable publicados con hashes, conteos
      por clase/familia/estado, lista de pruebas físicas y fixtures, y registro de
      cada fallo, causa y arreglo dueño.
- [ ] `scripts/test_source_quality.ps1 -Mode Full` verde sobre el árbol final.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuando lo cumplas

BAXY queda validado mensaje por mensaje, no “bien en promedio”: 1.947 respuestas
reales individualmente correctas, las 808 misiones cerradas por la tubería adecuada
y toda su identidad demostrada sobre el mismo árbol final. Entrega números, hashes,
veredictos y fallos que hubo que corregir.

Las limitaciones que queden se nombran una por una: las ambientales de verdad
—causa fuera del código de BAXY que BAXY no puede reparar— llevan degradado honesto.
Las demás son bugs.

No cierres dejando hallazgos nuevos en `documentacion/APLAZADOS.md`: resuélvelos o
clasifícalos según el criterio anterior. Lo que aparezca después del lanzamiento
entra en una tanda de mantenimiento nueva.
