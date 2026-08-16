# Sprint 07 — Misiones compuestas

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue — siempre se puede ajustar después. Para sólo si vas a tocar datos
personales del usuario u otros proyectos de la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

Arregla lo que bloquea. Lo que *podría* fallar y nadie ha visto fallar lo anotas
en una línea en `documentacion/APLAZADOS.md` y sigues — el sprint 11 existe para
vaciar esa lista.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## El resultado que cuenta

**La persona pide algo que ninguna operación sola puede lograr, y BAXY lo
consigue.** Encadena varias, en el orden que hace falta, pasando lo que produce
una a la siguiente, y comprueba cada paso.

Apunta a **≥ 90 %** de planes completos y verificados, sin un solo paso huérfano.

Un plan parcial que se ejecuta a medias es peor que no empezarlo: la persona
acaba con el sistema en un estado que no pidió y que no sabe deshacer.

**Este sprint carga con más peso del que parece.** Al decidir el catálogo, el
dueño eligió consolidar —una herramienta hace una cosa— y dijo dónde va todo lo
demás:

> Lo que no se logra con una herramienta, se logra con misiones compuestas: «Abre
> Steam y ve a la biblioteca» → `Open App` → `Click X`.

Es decir: **cada hueco que el sprint 03 deja al consolidar lo cierras tú
encadenando.** Y esa misma frase es una de las tres pruebas que, según el dueño,
justifican el proyecto entero: *abrir un juego y llegar adentro*. Pruébalo con esa
misión literal, sobre Steam de verdad, en esta máquina.

Eso apoya el segundo paso sobre **operar la aplicación abierta** —la cascada
UIA → OCR → visión—, que el dueño declaró **núcleo, no extra**. Sin ella, `Click X`
no existe y las misiones compuestas se quedan en encadenar operaciones del
sistema. Y sin listas de apps a mano: fue un antipatrón que Carter se documentó a
sí mismo, contra su propio valor declarado.

## Qué cubre

Objetivos reales encadenados. La forma típica: una cláusula depende de otra —
«busca X y guárdalo en una nota», «abre Y y súbele el volumen», «mira si tengo Z
y si no, créalo». En español, inglés y spanglish, con las dependencias
implícitas que la gente usa al hablar.

Ejecutadas **end-to-end en esta máquina**, abriendo el producto y verificando
efectos reales. Por texto: la voz es el sprint 09.

## Lo que ya se sabe

**Ya cerró una vez, 6/6 misiones y 25/25 pasos verificados**, sobre un oráculo
disjunto y con cero efectos ambiguos. Pero fue sobre un árbol anterior, y el
primer intento sobre ese mismo árbol había cerrado 2 de 6.

**La causa de aquel 2/6 está aislada y reparada:** una cláusula dependiente
perdía la cabeza de su cláusula gobernante. Ese es el fallo característico aquí —
la segunda mitad de la petición se queda sin el sujeto de la primera.

**Se cerraron dos pérdidas de conservación** que habrían ejecutado un subconjunto
silencioso de la misión pedida. Búscalas de nuevo: es el modo de fallo que más se
repite y el más difícil de ver, porque el sistema informa éxito.

**No reutilices el oráculo que ya se abrió.** Si mides sobre el corpus que se usó
para reparar, el número no significa nada.

## Cómo mides

Sobre misiones frescas, con las dependencias reales. Verifica **cada paso**, no
sólo el resultado final: una misión que acaba bien por casualidad, con un paso
intermedio que falló y nadie miró, no cuenta como completa.

Comprueba que ningún paso queda huérfano — sin ejecutar, sin verificar, o
ejecutado fuera del plan.

## Lo que no puedes romper

Los tres ceros del corte D siguen en pie durante toda la misión: ningún paso
ejecuta un efecto que no se pidió, ninguno se declara hecho sin verificar,
ninguna narración es una constante.

Y la narración durante la misión importa: si BAXY trabaja más de unos segundos
sin salida visible, la persona no sabe si está vivo. Eso conecta con el sprint
08, pero aquí ya se nota.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

Las misiones ejecutadas de verdad en esta máquina, con cada paso verificado y el
resultado publicado. Si alguna no se puede completar, di exactamente dónde se
rompió la cadena y por qué.

## Cuándo has terminado

Cuando puedas pedirle a BAXY algo que requiera tres cosas seguidas, en spanglish,
y las haga las tres, en orden, y te lo cuente en una frase.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
