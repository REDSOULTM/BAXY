# La identidad de BAXY — preguntas abiertas

Este documento existe para resolver **qué es BAXY** antes de que once agentes se
pongan a construirlo. Las respuestas se escriben aquí mismo, debajo de cada
pregunta, y cuando esté completo se convierte en el documento de identidad que
todos los sprints leen.

Están numeradas para poder responder por número, en el orden que quieras y en
varias sesiones.

---

## Lo que ya sabemos, de leer los intentos anteriores

No parto de cero. Esto es lo que dicen los repositorios de la misma carpeta, y
condiciona varias de las preguntas.

### No son proyectos distintos: son el mismo, cuatro veces

El README de `Probando Gemma 4` lo dice literalmente:

> el proyecto se renombró a **Baxy** (antes **Gemma 4 Agent**, brevemente
> **Carter**)

La genealogía real es **Gemma 4 Agent → Carter → Baxy → BAXY actual**. Cada uno
reescribió al anterior. Eso significa que los errores no son ajenos: son de este
proyecto, cuatro veces.

`JRVS` es la excepción — no es este linaje. Es un asistente de operaciones
self-hosted para equipos en industrias reguladas, con Google Workspace y auditoría
de cumplimiento. Otro producto, otro cliente.

### Lo que el Baxy anterior era y el actual ya no

Esto es lo que más me llamó la atención al leer, porque **se perdió por el
camino**:

- **Accesibilidad como característica de primera clase.** Control 100 % por voz
  para movilidad reducida, y narración de cada acción para personas no videntes.
  No aparece por ningún lado en el BAXY actual.
- **4 GB de VRAM como identidad declarada**, no como techo aspiracional: *«el
  target real es una laptop Windows con GPU NVIDIA de 4 GB, o incluso sin GPU
  dedicada»*.
- **Universalidad medida**: la wake word se evaluaba contra un holdout de **25
  voces en 13 idiomas**.
- **«Inteligencia, no árboles de `if`»** como principio explícito: lo determinista
  se limitaba a embeddings multilingües, guardas estructurales y lectura del
  estado del SO.
- **Operar cualquier aplicación** por accesibilidad, con la cascada UIA → OCR →
  visión nativa de Gemma.

### El catálogo creció sin que nadie lo decidiera

Los números, en orden cronológico:

| Momento | Herramientas |
|---|---:|
| Baxy (`tool_schemas_full.json`) | 67 |
| Baxy lean (`tool_schemas_lean.json`) | 31 |
| Carter v4 consolidado | **16** |
| BAXY hoy | **158 operaciones** |

Carter midió que consolidar a 16 daba **−68 % de tokens con la misma calidad**. Y
el mayor problema de BAXY hoy es exactamente ése: la decisión ve hasta 28
candidatos y elige mal.

### Un diagnóstico que ya estaba hecho y se repitió

FunctionGemma documentó, midiendo, que la cuantización Q2 rompía el modelo de
habla: *«glitches: bleed latino, faltas ("fysico", "lumínar")»* y pérdida de
persona. La conclusión fue subir a **Q4_K_XL QAT** (~1,5 GB de VRAM), con la que
el modelo obedece el system prompt y **dice «Soy Baxy» sin necesidad de
fine-tuning**.

El BAXY actual arrastra hoy palabras inventadas en su prosa española —«cuecer»,
«vertir», «cosear», «alredad»—. Es el mismo síntoma que ya se había diagnosticado
y resuelto una vez.

### Carter, la identidad escrita más clara

**Carter** dejó escrita la identidad más clara de todas. Define el asistente por
una secuencia:

> Le hablo → entiende rápido → decide bien → actúa si corresponde → verifica →
> responde honesto.

y por su contrario:

> Le hablo → tarda demasiado → usa la herramienta equivocada → dice que hizo algo
> que no hizo → culpa al entorno.

Sus dos valores, en ese orden: **local y privado** primero, **rápido** segundo. Y
una frase que vale por todo el documento: *«Carter debe ser confiable antes que
espectacular»*.

**Carter también dejó escrito por qué fracasó cuatro veces.** El diagnóstico
propio, tras 345 commits y cuatro generaciones:

> El proyecto crece por acumulación, no por reemplazo.

Los anti-patrones que él mismo documentó, y que BAXY hoy repite en parte:

- `agent.py` llegó a 1.397 líneas contra un objetivo propio de menos de 400.
- **Tres routers en serie** antes de la primera llamada al modelo, cada uno
  añadido para arreglar un caso, ninguno retirado.
- **Ocho capas de reescritura** después de la llamada al modelo. Su propio
  informe: *«las respuestas son malas en varios casos»* — el reescritor
  distorsionaba lo que el modelo quería decir.
- Listas de apps hardcodeadas, violando su propio valor «sin hacks por app».
- Historia dinámica que invalidaba la caché del prompt: **16 s por turno medidos
  contra 4,26 s del modelo puro**. Diez segundos de sobrecarga propia.

**BAXY hoy** tiene 158 operaciones tipadas. **Carter midió** que consolidar a
16 herramientas daba **−68 % de tokens con la misma calidad**. Esa diferencia es
la pregunta 12 y puede ser la más importante de este documento.

---

## A. Quién es BAXY

**1.** Si tuvieras que explicarle a alguien qué es BAXY en una sola frase, sin
decir «asistente» ni «IA», ¿qué le dirías?

**2.** ¿BAXY es un *él*, un *ello*, una herramienta o un compañero? ¿Tiene
carácter propio o es deliberadamente neutro?

**3.** ¿Cómo habla? Concretamente: ¿te tutea? ¿es formal, seco, cálido, con
humor? ¿Dice «listo» o «he abierto Spotify y está sonando»? Un ejemplo real de
respuesta que te gustaría leer vale más que cinco adjetivos.

**4.** Cuando BAXY no puede hacer algo, ¿qué tono usa? ¿Se disculpa, lo dice
plano, propone alternativa?

**5.** ¿Hay algo que BAXY **nunca** debería decir o hacer, aunque funcionara?

**6.** El nombre. ¿BAXY significa algo, o suena bien y ya? ¿Responde a otros
nombres, o sólo a ése?

---

## B. Para qué existe

**7.** Piensa en un día normal tuyo. ¿Cuáles son las **cinco cosas** que más te
gustaría pedirle a BAXY? Concretas, con tus palabras, como se las dirías.

**8.** ¿Qué es lo que más te frustra hoy de tu PC, que BAXY debería quitarte de
encima?

**9.** ¿BAXY es para ti solo, o quieres que otras personas lo usen? Si es lo
segundo, ¿quiénes — gente técnica o cualquiera?

**10.** ¿Qué tiene que hacer BAXY para que lo abras **todos los días** en vez de
olvidarlo la segunda semana?

**11.** ¿Hay alguna tarea concreta que, si BAXY la resolviera bien, ya
justificaría todo el proyecto?

---

## C. El alcance — la pregunta más cara

**12. La tensión de las 158 operaciones.** BAXY tiene 158 operaciones tipadas.
Carter midió que consolidarlas a 16 herramientas daba **−68 % de tokens con la
misma calidad**, y hoy el mayor problema de BAXY es justo ése: la decisión ve
hasta 28 candidatos y elige mal.

¿Prefieres un BAXY que haga **muchas cosas** y a veces se confunda, o uno que
haga **pocas cosas impecablemente** y diga «eso no lo hago» al resto? No hay
respuesta correcta, pero cambia el diseño entero.

**13.** Si tuvieras que quedarte con **veinte** operaciones y tirar el resto,
¿cuáles salvarías?

**14.** ¿Hay operaciones que están en el catálogo y en realidad **nunca** has
usado ni vas a usar?

**15.** ¿BAXY debe poder ejecutar cosas peligrosas —borrar ficheros, cerrar
programas con trabajo sin guardar, apagar el equipo— o eso queda fuera por
diseño?

**16.** Cuando BAXY va a hacer algo irreversible, ¿quieres que pregunte siempre,
nunca, o sólo en ciertos casos? ¿Cuáles?

---

## D. Velocidad — hay una contradicción que resolver

**17.** Carter fijó su meta en **3–8 segundos** para una interacción simple.
BAXY la fijó en **1 segundo de primera señal y 2,5 s de acción completa**. Son
mundos distintos. ¿Cuál es tu expectativa real?

**18.** ¿Qué prefieres: que BAXY responda en 1 s con algo provisional y luego
complete, o que tarde 4 s y te dé la respuesta final y verificada?

**19.** ¿Cuánto es «demasiado»? El número a partir del cual cierras la ventana y
lo haces tú a mano.

**20.** Carter medía **16 s por turno** cuando el modelo puro tardaba 4,26 s: diez
segundos eran sobrecarga suya. Si BAXY tuviera que elegir entre ser más listo o
quitarse sobrecarga, ¿por dónde tiras?

---

## E. Honestidad — el diferenciador

**21.** «Nunca miente» es el invariante central. ¿De dónde viene? ¿Te pasó algo
concreto con Carter o con otro asistente que te marcó?

**22.** ¿Qué prefieres oír cuando BAXY no está seguro de si algo funcionó: «lo
hice» arriesgándose, «no pude confirmarlo» siendo honesto, o que lo compruebe
aunque tarde más?

**23.** Un asistente que dice «no sé» a menudo, ¿te da confianza o te irrita?

**24.** Si BAXY se equivoca, ¿qué quieres que pase? ¿Que lo diga, que lo intente
otra vez, que te pregunte?

---

## F. La voz

**25.** ¿La voz es esencial para tu BAXY, o un extra agradable? Sé honesto: si
sólo funcionara por texto, ¿seguiría siendo el producto que buscas?

**26.** ¿Cómo lo llamas al hablarle? ¿«BAXY», «oye BAXY», otra cosa?

**27.** ¿Quieres que escuche siempre, o que se active con un botón o atajo?
Escuchar siempre cuesta batería y CPU, y es la decisión de privacidad más grande
del producto.

**28.** ¿BAXY contesta hablando siempre, sólo cuando le hablas por voz, o cuando
tú lo decidas?

**29.** ¿Qué voz? ¿Neutra de sistema, algo con carácter, en español de dónde?

---

## G. Memoria y privacidad

**30.** ¿Qué debería recordar BAXY de ti entre sesiones? ¿Y qué **no** debería
recordar nunca?

**31.** ¿Quieres poder ver y editar lo que sabe de ti, o prefieres que
simplemente funcione sin que tengas que administrarlo?

**32.** «Todo local, sin nube» es un invariante. ¿Es innegociable, o aceptarías
una excepción concreta —por ejemplo buscar en internet— si te lo pidiera
explícitamente?

**33.** ¿BAXY puede ver tu pantalla? ¿Leer tus ficheros? ¿Bajo qué condiciones?

---

## H. Cómo se ve y se siente

**34.** ¿BAXY es una ventana, una barra flotante, un atajo de teclado que aparece
y desaparece, algo en la bandeja del sistema?

**35.** ¿Quieres verlo trabajar —los pasos, las herramientas que usa— o sólo el
resultado?

**36.** ¿Arranca con Windows y vive ahí, o lo abres cuando lo necesitas?

---

## I. Los límites

**37.** ¿Qué pasa cuando BAXY no entiende? ¿Pregunta, adivina lo más probable, o
dice que no entendió?

**38.** ¿Debe poder decir que no? ¿A qué?

**39.** ¿Qué diferencia a BAXY de escribirle a ChatGPT y hacerlo tú a mano? Si la
respuesta es «que actúa por mí», ¿cuánto quieres que actúe sin supervisión?

**40.** Dentro de un año, ¿qué tendría que estar haciendo BAXY para que digas
«esto sí quedó»?

---

## J. Lo que no quieres repetir

**41.** De todos los intentos anteriores —Carter, Agent Gemma, los Jarvis, este
BAXY— ¿cuál es el momento en que dijiste «esto no va» y por qué?

**42.** Carter se diagnosticó a sí mismo: *«el proyecto crece por acumulación, no
por reemplazo»*. ¿Lo reconoces? ¿Qué crees que lo causó?

**43.** ¿Qué es lo único que, si vuelve a pasar, significaría que este BAXY
también falló?

---

---

## K. Lo que se perdió por el camino

**44. Accesibilidad.** El Baxy anterior declaraba como característica de primera
clase el control 100 % por voz para movilidad reducida y la narración de cada
acción para personas no videntes. Eso no está en el BAXY actual. ¿Se cayó por
descuido o por decisión? ¿Vuelve?

**45.** Si la accesibilidad vuelve, ¿es un modo que se activa, o cambia el diseño
de todo el producto desde el principio?

**46.** El Baxy anterior evaluaba la wake word contra **25 voces en 13 idiomas**.
¿Ese nivel de universalidad sigue siendo el objetivo, o BAXY es para ti y para
gente que hable como tú?

**47.** «Operar cualquier aplicación abierta» vía accesibilidad, OCR y visión era
una capacidad declarada. ¿La quieres, o prefieres que BAXY haga bien lo que sabe
hacer y no toque lo demás?

**48. El catálogo creció solo.** 67 herramientas → 31 en el set lean → 16 en
Carter v4 → 158 operaciones hoy. Nadie decidió ese crecimiento; se acumuló.
¿Cuál de esos cuatro números se parece más a lo que quieres?

**49.** ¿Prefieres una herramienta que haga muchas cosas con parámetros —«controla
el audio»— o muchas herramientas específicas —«sube volumen», «baja volumen»,
«silencia»—? Carter midió que consolidar ahorra el 68 % de tokens.

**50. Las palabras inventadas.** FunctionGemma ya había diagnosticado que la
cuantización Q2 producía «fysico», «lumínar» y rompía la persona, y lo resolvió
subiendo a Q4. El BAXY actual vuelve a tener ese problema. ¿Aceptas gastar ~0,4 GB
más de VRAM para que la prosa salga limpia, o prefieres buscar otra vía?

**51.** El Baxy anterior conseguía que el modelo dijera «Soy Baxy» **sólo con el
system prompt**, sin fine-tuning. ¿La personalidad de BAXY debe vivir en el
prompt, o quieres un modelo entrenado para ser BAXY?

**52.** Cuatro veces se reescribió este proyecto desde cero. ¿Qué te hace pensar
que esta vez no habrá una quinta? Dicho de otro modo: ¿qué tendría que pasar para
que decidieras reescribirlo otra vez, y cómo lo evitamos?

---

## Respuestas

<!-- Responde aquí abajo, por número. No hace falta orden ni todas de una vez. -->
