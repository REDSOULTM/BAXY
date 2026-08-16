# Goal 07 — Las misiones compuestas

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

**La persona pide algo que ninguna operación sola puede lograr, y BAXY lo
consigue.** Encadena varias, en el orden que hace falta, pasando lo que produce una
a la siguiente, y comprueba cada paso.

Apunta a **≥ 90 %** de planes completos y verificados, sin un solo paso huérfano.

Un plan parcial que se ejecuta a medias es peor que no empezarlo: la persona acaba
con el sistema en un estado que no pidió y que no sabe deshacer.

## Este goal carga con más peso del que parece

Al decidir el catálogo, el dueño eligió consolidar —una herramienta hace una
cosa— y dijo dónde va todo lo demás:

> Lo que no se logra con una herramienta, se logra con misiones compuestas: «Abre
> Steam y ve a la biblioteca» → `Open App` → `Click X`.

Es decir: **cada hueco que el goal 03 deja al consolidar lo cierras tú
encadenando.** Y esa misma frase es una de las tres pruebas que, según el dueño,
justifican el proyecto entero: *abrir un juego y llegar adentro*. Pruébalo con esa
misión literal, sobre Steam de verdad, en esta máquina.

Eso apoya el segundo paso sobre **operar la aplicación abierta** —la cascada
UIA → OCR → visión—, que el dueño declaró **núcleo, no extra**. Sin ella `Click X`
no existe y las misiones compuestas se quedan en encadenar operaciones del sistema.

Y sin listas de apps a mano: fue un antipatrón que Carter se documentó a sí mismo,
contra su propio valor declarado. Una lista de apps es la forma más rápida de que
este goal parezca cumplido y no lo esté.

## Dónde mirar el estado del arte, aquí

Dos piezas de este goal son problemas resueltos fuera y conviene no reinventarlas:

- **La planificación y ejecución de pasos encadenados con verificación por paso.**
  Hay mucho escrito y mucho probado. Trae el patrón que funcione y que quepa en la
  ley 2 — un plan es una lista de pasos, no un motor de workflows.
- **Operar una aplicación por accesibilidad.** UI Automation de Windows, la
  cascada a OCR cuando el árbol no expone el control, y visión como último
  recurso. El Baxy anterior ya lo tenía declarado; averigua qué implementó de
  verdad (el goal 01 lo dejó mapeado) y compáralo con lo que se usa hoy.

## Lo que ya se sabe

**Ya cerró una vez, 6/6 misiones y 25/25 pasos verificados**, sobre un oráculo
disjunto y con cero efectos ambiguos. Pero fue sobre un árbol anterior, y el primer
intento sobre ese mismo árbol había cerrado 2 de 6.

**La causa de aquel 2/6 está aislada y reparada:** una cláusula dependiente perdía
la cabeza de su cláusula gobernante. Ése es el fallo característico aquí — la
segunda mitad de la petición se queda sin el sujeto de la primera.

**Se cerraron dos pérdidas de conservación** que habrían ejecutado un subconjunto
silencioso de la misión pedida. Búscalas de nuevo: es el modo de fallo que más se
repite y el más difícil de ver, porque el sistema informa éxito.

**No reutilices el oráculo que ya se abrió.** Si mides sobre el corpus que se usó
para reparar, el número no significa nada.

## Qué cubre

Objetivos reales encadenados. La forma típica: una cláusula depende de otra —
«busca X y guárdalo en una nota», «abre Y y súbele el volumen», «mira si tengo Z y
si no, créalo». En español, inglés y spanglish, con las dependencias implícitas que
la gente usa al hablar.

Ejecutadas **end-to-end en esta máquina**, abriendo el producto y verificando
efectos reales. Por texto: la voz es el goal 09.

## Lo que no puedes romper

Los tres ceros siguen en pie durante toda la misión: ningún paso ejecuta un efecto
que no se pidió, ninguno se declara hecho sin verificar, ninguna narración es una
constante.

Y la narración durante la misión importa: si BAXY trabaja más de unos segundos sin
salida visible, la persona no sabe si está vivo. El listón del dueño es **3 s sin
señal**. Eso conecta con el goal 08, pero aquí ya se nota.

## Criterios de cierre

- [ ] ≥ 90 % de misiones completas y verificadas sobre misiones frescas, con **cada
      paso** verificado — no sólo el resultado final.
- [ ] Cero pasos huérfanos: sin ejecutar, sin verificar, o ejecutados fuera del plan.
- [ ] «Abre Steam y ve a la biblioteca» funciona sobre Steam de verdad, en esta
      máquina.
- [ ] La cascada UIA → OCR → visión funciona sin una sola app codificada a mano.
- [ ] Ninguna misión pasa más de 3 s sin salida visible.
- [ ] Los tres ceros intactos durante toda la misión.

## Cuando lo cumplas

Las misiones ejecutadas de verdad en esta máquina, con cada paso verificado y el
resultado publicado. Si alguna no se puede completar, di exactamente dónde se
rompió la cadena y por qué.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
