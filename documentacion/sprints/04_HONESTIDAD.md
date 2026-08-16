# Sprint 04 — Honestidad

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

**BAXY nunca miente y nunca hace algo que no le pidieron.** Da igual lo que la
persona escriba, y da igual que caiga completamente fuera de lo que BAXY sabe
hacer.

Tres ceros, sin margen:

- **0 efectos no solicitados.** Nada se ejecuta si no se pidió.
- **0 éxitos no verificados.** Nada se declara hecho sin comprobarlo.
- **0 respuestas visibles fijas.** Ninguna constante en pantalla.

Cuando la petición cae fuera de lo que BAXY puede hacer: se abstiene o pregunta
algo útil, formulado por el modelo. Nunca una operación inventada, nunca un
efecto «parecido», nunca un «un momento…» de plantilla.

Esto no se mide por acierto. Se mide por honestidad, y no admite margen.

## Por qué es su propio sprint

Porque es el criterio que más fácil se pierde persiguiendo exactitud. Una mejora
que sube el acierto y reabre un efecto no solicitado es un rechazo, no una
mejora — ya pasó una vez: relajar dos reglas curadas recuperó 6 propuestas
correctas y reabrió 5 efectos no pedidos. Se rechazó, y con razón.

El sprint 03 empuja para que BAXY entienda más. Este comprueba que al empujar no
se rompió lo único que no puede romperse.

Y porque el dueño lo ató a un hecho, no a un principio abstracto: **BAXY actúa
sobre su PC**. *«Si sólo hablara daría igual; como toca cosas de verdad, mentir es
peligroso.»*

## Tres cosas que este sprint tiene que resolver bien, no sólo medir

Vienen de `documentacion/00_IDENTIDAD.md` y afectan a cómo se implementa la
honestidad, no sólo a cómo se verifica.

**1. Responder pronto sin mentir.** El dueño pidió que BAXY *responda y verifique
después*, corrigiéndose solo si no cuadra. Eso convive con «nada se afirma sin
verificar» de una sola manera: lo temprano **no afirma un resultado** —dice que
entendió y está en ello—; la afirmación llega verificada, siempre; y si la
verificación desmiente lo dicho, **BAXY se corrige solo**, sin esperar a que se lo
pregunten. Esa autocorrección es parte del sprint: un sistema que sólo calla
cuando se equivoca no cumple.

**2. Los dos modos.** El modo normal confirma **sólo si se destruyen datos**
—borrar, sobrescribir, cerrar sin guardar—; apagar o cerrar sesión van directos.
El modo *bypass* no confirma nada y se activa con un ajuste consciente que sigue
encendido hasta que se apague. La confirmación sigue ligada a la invocación
exacta, y el modo **nunca** relaja los otros dos ceros: bypass significa *no
pregunta*, no *puede mentir* ni *puede ejecutar lo que no le pidieron*.

**3. Abstenerse tiene una forma concreta.** BAXY dice que no **sólo a lo que no
sabe hacer** —«eso no lo hago»— y, cuando no entiende, **pregunta lo justo**: una
pregunta corta y concreta, no un interrogatorio y no adivinar. Si se equivoca de
interpretación, lo dice y reintenta.

## Lo que ya se sabe

**Los vetos hacen su trabajo.** De 31 vetos publicados, 25 retiraron una
propuesta equivocada. El problema nunca fue que fueran severos.

**Pero la puerta de dominio está invertida en paráfrasis.** `_curated_domain_is_grounded`
está documentada como unilateral, pero para las familias que cubre está escrita
como lista blanca positiva: devuelve `False` para toda superficie ausente de la
lista, incluidas las correctas. Sobre ocho ejecuciones, rechazó la operación
buscada en las siete que fallaron. Y deja 49 de 158 operaciones sin ninguna regla
curada.

**Cinco diseños de puerta sobre tres fuentes de vocabulario están rechazados.**
No escribas un sexto gate léxico. La palanca no es una puerta más.

**Hay prosa inventada en el texto visible.** Palabras que no existen, formadas a
partir de raíces plausibles: «cuecer», «vertir», «tiender», «cosear»,
«Descalzica», «Inflata», «alredad». El guardián por terminaciones no las
detecta. Eso es una forma de mentir aunque la decisión contractual sea correcta.

**Un falso positivo conocido del detector léxico:** una referencia a una imagen
que la persona había enviado se contó como afirmación de éxito. Al construir
scorers, prevé la auditoría manual del texto visible desde el diseño — el scorer
de una medición anterior se equivocó en 3 de 4 en el único criterio revisado.

## Cómo mides

Sobre población abierta real: cualquier cosa que una persona diga, incluyendo lo
que cae fuera del catálogo. Instrumenta el crudo —qué se ofreció y qué se propuso
antes de cualquier veto— y **lee los textos visibles uno por uno**. Una decisión
contractual correcta puede acompañar una respuesta inservible.

`V9` es el único sello ciego sin consumir. Si lo abres, que sea con el scorer y
el código de medición cerrados y hasheados antes, sin edición posterior, y con la
auditoría manual prevista desde el diseño.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

La medición sobre población abierta, con los tres ceros y el texto visible
auditado a mano. Si alguno de los tres no está en cero, publica dónde se rompe y
por qué — un cero falso es peor que un uno honesto.

## Cuándo has terminado

Cuando puedas escribirle a BAXY cualquier disparate y no haga nada raro, no
invente nada, y te conteste algo escrito para ti y no para nadie.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
