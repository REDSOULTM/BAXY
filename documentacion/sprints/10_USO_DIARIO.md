# Sprint 10 — Uso diario

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

**BAXY se usa todos los días y no decepciona.**

No es una demo que funciona cuando le preguntas lo correcto. Es un asistente que
alguien abre por la mañana y usa hasta la noche, con lo que se le ocurra, en el
idioma que le salga, y que se gana quedarse instalado.

**Este sprint no es el adorno final: es la prueba del producto.** Cuando al dueño
se le preguntó qué evita una quinta reescritura del proyecto, respondió *que el
producto se use*, y qué tendría que pasar en un año para decir «esto sí quedó»:
*que lo use a diario sin pensarlo*. Los nueve sprints anteriores existen para
llegar hasta aquí; si BAXY sale de este sprint sin usarse, no sirvió ninguno.

Y hay una forma concreta en que este sprint se rompe: **la fricción de arrancarlo
es lo que lo mata**. Por eso BAXY vive en la bandeja del sistema, arranca con
Windows y escucha siempre. Lo que hay que quitarle de encima al usuario, en sus
palabras, es *levantarse del teclado*.

Lee `documentacion/00_IDENTIDAD.md`. Y comprueba en uso —no en el código— tres
decisiones que sólo se verifican viviendo con el producto: los **dos modos**
(normal, que confirma sólo si se destruyen datos; y *bypass*, que se activa con un
ajuste consciente y sigue encendido hasta apagarlo), la **narración** de lo que
hace, y que **buscar en la web** funcione sin que salga nada del usuario.

## Qué haces

Usarlo. De verdad, durante días, para cosas reales. Y arreglar lo que salga.

Esto no es un sprint de medición sobre corpus: los nueve anteriores ya midieron.
Este es el que encuentra lo que ningún corpus contenía, porque el uso real siempre
trae algo que nadie anticipó.

Presta atención a lo que no se mide fácil:

- **Lo que cansa.** Una fricción que aparece cuarenta veces al día importa más
  que un fallo que aparece una vez al mes.
- **Lo que sorprende mal.** Momentos en que BAXY hace algo razonable según su
  lógica y raro según la de la persona.
- **Lo que no se pide dos veces.** Si algo funciona pero cuesta tanto pedirlo que
  la persona deja de usarlo, ese algo no funciona.
- **La memoria y la privacidad.** La persona tiene que poder ver, corregir y
  borrar todo lo que BAXY sabe de ella, y comprobarlo de verdad — no confiar en
  que un botón hace lo que dice.

## Lo que sigue en pie

Todo. Los tres ceros no se relajan porque el sprint sea de uso: cero efectos no
pedidos, cero éxitos no verificados, cero respuestas visibles fijas. La compuerta
sigue verde. Los invariantes de arquitectura siguen siendo invariantes.

Un fallo de honestidad durante el uso diario es un defecto grave, no una anécdota:
significa que los corpus no lo contenían, y eso es exactamente lo que este sprint
existe para encontrar.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

BAXY usable, y el registro honesto de lo que encontraste usándolo: lo que
arreglaste, lo que sigue abierto, y lo que decidiste dejar como está y por qué.

Y la lista de limitaciones que quedan, nombradas una por una. Las que sean
ambientales de verdad —causa fuera del código de BAXY, que BAXY no puede
reparar— se declaran y se cubren con un degradado honesto. Las demás son bugs.

## Cuándo has terminado

Cuando pase una semana de uso diario sin un solo momento en que BAXY afirme algo
que no era cierto, ejecute algo que no le pidieron, o suelte una frase de
plantilla.

Ese día BAXY está entregado.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
