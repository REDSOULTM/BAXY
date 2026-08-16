# Goal 06 — La voz del producto

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY`. Modelo: GPT-5.6 Sol,
`reasoning.effort: high`.

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

## Las cuatro leyes

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden,
y sin saltarte pasos:

1. **¿Ya está resuelto en un BAXY anterior?** Este proyecto se ha escrito cuatro
   veces y muchos problemas ya cayeron. Trae esa solución — o la **mejor
   combinación** de las que hay, que muchas veces es lo que gana. El goal 01 dejó
   el mapa de qué existe y dónde.
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
recorrido: una línea en `documentacion/APLAZADOS.md` y sigues. El goal 11 existe
para vaciar esa lista, así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera, contando RAM, disco, CPU en reposo y
arranque en frío. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto.

## Y una consigna que une las cuatro

Ésta es la **quinta** escritura de BAXY, y tiene que ser **la más rápida de las
cinco**. No porque haga menos —es la definitiva— sino porque **no vuelve a
descubrir nada que ya se descubrió**.

Cada hora que gastes re-derivando algo que ya está medido en estos repositorios es
una hora que este proyecto ya pagó una vez. Si te encuentras diseñando desde cero
algo que suena a que alguien ya resolvió, para y ve a buscarlo primero.

---

## El objetivo

**Todo lo que la persona lee lo formula el modelo, y está bien escrito.**

Cero respuestas visibles fijas. Ninguna constante en pantalla, ni siquiera como
degradado cuando algo falla. Un «un momento…» invariable es el defecto que el
invariante nombra, no una solución aceptable.

Y una frase por resultado. BAXY hace algo, comprueba que pasó, y lo cuenta en una
frase — no en un párrafo, no en un volcado de estado, no en un JSON traducido a
prosa.

Este goal es donde la identidad de BAXY deja de ser un documento y se vuelve lo
que la persona lee.

## Cómo habla BAXY — decidido, no opinable

**Tiene carácter propio. Es un él, no una herramienta neutra.** Un compañero que
vive en el PC.

**Éste es el registro exacto**, elegido por el dueño sobre otras tres alternativas:

> «Listo, Spotify está abierto y sonando»

Tutea. Es cálido y breve. Y sobre todo **confirma el estado observable**: ni
«Listo» a secas —que no dice qué comprobó— ni un párrafo, ni un personaje haciendo
bromas.

**Al fallar: plano y con la causa.** «No pude: Spotify no responde». Sin disculpas
y sin drama.

**Cuando no entiende: pregunta lo justo.** Una pregunta corta y concreta que
desambigua. Ni interrogatorio ni adivinar.

**Cuando se equivoca: lo dice y reintenta** con la interpretación correcta.

**Dice que no sólo a lo que no sabe hacer** — «eso no lo hago», en vez de
improvisar un apaño que casi funciona.

Que BAXY diga «no pude confirmarlo» **le da confianza al dueño**. Si lo dice a
menudo, el defecto está en la verificación y se arregla allí, no callándolo aquí.

**Y la personalidad vive en el prompt.** Sin fine-tuning: el Baxy anterior ya
conseguía que el modelo dijera «Soy Baxy» sólo con el system prompt. Cambiar el
carácter tiene que ser editar un texto. Si te ves proponiendo entrenar un modelo
para que suene a BAXY, es que el prompt está mal escrito.

## Lo que ya se sabe

**Hay palabras inventadas en la prosa española.** Formadas a partir de raíces
plausibles: «cuecer», «vertir», «tiender», «cosear», «Descalzica», «Inflata»,
«alredad». El guardián por terminaciones no las ve, porque son terminaciones
válidas sobre raíces mal derivadas.

Este síntoma **ya se diagnosticó una vez en esta casa**: FunctionGemma midió que la
cuantización Q2 producía «fysico» y «lumínar» y rompía la persona, y lo resolvió
subiendo a Q4_K_XL QAT (~1,5 GB de VRAM). Es una pista fuerte, **no una conclusión
heredada** — el dueño fue explícito: *«que se evalúe bien y simplemente se elija lo
mejor posible, siempre pensando en el menor uso de recursos que funcione bien»*.

Aquí manda la ley 1: la calidad de prosa española de los modelos pequeños se ha
movido mucho, y la respuesta correcta puede no ser subir la cuantización del que
hay. Mira qué existe hoy antes de gastar VRAM, y mide en español real, no en
benchmarks en inglés.

**Se recuperó una ruta que publicaba una constante.** La ruta visible excepcional
de `message.compose` ya no publica una constante ni pierde confirmaciones:
conserva una cola ordenada y sólo publica prosa formulada y validada por el modelo.
Ése es el patrón — cópialo donde falte, en vez de inventar otro.

**El texto visible se lee a mano.** Una decisión contractual correcta puede
acompañar una respuesta inservible, y ya pasó: preguntas que no preservan la
operación, negativas repetidas, planes que el veto bloqueó narrados como si
hubieran corrido. Un scorer automático no lo detecta; una persona leyendo, sí.

**Cuidado con el detector léxico de éxitos falsos.** Ya produjo un falso positivo
—una referencia a una imagen que la persona había enviado— y el scorer de una
medición anterior se equivocó en 3 de 4 en el único criterio revisado.

## Qué cubre

Todo lo que sale por pantalla: confirmaciones, preguntas de aclaración, negativas,
errores, narración de progreso, resúmenes de misión. En español, inglés y
spanglish, respondiendo en el idioma en que se le habló.

Incluye los casos feos, que es donde aparecen las constantes: el provider que
falla, el timeout, la operación ambigua, la petición fuera de catálogo, el modelo
que devuelve algo inválido. Cada uno necesita prosa formulada, no una plantilla.

**Y la narración de la accesibilidad es parte de esto.** BAXY narra lo que hace, y
esa narración es texto visible como cualquier otro: la formula el modelo, no una
plantilla. No la construyas como un subsistema aparte — es la misma voz.

## Cómo mides

Lee los textos, uno por uno. Busca constantes conocidas en `reply_text`, pero no te
fíes sólo de eso: una constante nueva no está en la lista de constantes conocidas.

Y comprueba que la prosa se sostiene: que las palabras existen, que la frase dice
lo que pasó, y que alguien que no sabe cómo funciona BAXY la entendería.

## Criterios de cierre

- [ ] Cien respuestas seguidas leídas a mano y ninguna suena a máquina rellenando
      un hueco.
- [ ] Cero palabras inventadas en la muestra, con la causa resuelta —modelo,
      cuantización o comprobación— y la decisión justificada midiendo.
- [ ] Cero constantes en pantalla, incluidos los caminos feos y el degradado.
- [ ] La narración de accesibilidad sale por la misma ruta de prosa, sin subsistema
      propio.
- [ ] La personalidad está en el prompt y se puede cambiar editando un texto.

## Cuando lo cumplas

La auditoría del texto visible sobre población real, leída a mano, con las
constantes que quedaban y cómo las quitaste.

Si una ruta no puede formular prosa —porque el modelo no responde a tiempo, por
ejemplo— resuélvelo sin constantes: el problema es el silencio, y una plantilla no
lo arregla, lo disfraza.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
