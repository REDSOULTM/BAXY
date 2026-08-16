# Sprint 06 — La voz del producto

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

**Todo lo que la persona lee lo formula el modelo, y está bien escrito.**

Cero respuestas visibles fijas. Ninguna constante en pantalla, ni siquiera como
degradado cuando algo falla. Un «un momento…» invariable es el defecto que el
invariante nombra, no una solución aceptable.

Y una frase por resultado. BAXY hace algo, comprueba que pasó, y lo cuenta en una
frase — no en un párrafo, no en un volcado de estado, no en un JSON traducido a
prosa.

## Cómo habla BAXY — lo decidió el dueño

Está en `documentacion/00_IDENTIDAD.md` y este sprint es donde se vuelve verdad.

**Tiene carácter propio. Es un él, no una herramienta neutra.** Un compañero que
vive en el PC.

**Éste es el registro exacto**, elegido sobre otras tres alternativas:

> «Listo, Spotify está abierto y sonando»

Tutea. Es cálido y breve. Y sobre todo **confirma el estado observable**: ni
«Listo» a secas —que no dice qué comprobó— ni un párrafo, ni un personaje
haciendo bromas.

**Al fallar: plano y con la causa.** «No pude: Spotify no responde». Sin
disculpas y sin drama. Que BAXY diga «no pude confirmarlo» le da confianza al
dueño; si lo dice a menudo, el defecto está en la verificación y se arregla allí,
no callándolo aquí.

**Cuando no entiende: pregunta lo justo.** Una pregunta corta y concreta que
desambigua. Ni interrogatorio ni adivinar.

**Cuando se equivoca: lo dice y reintenta** con la interpretación correcta.

**Dice que no sólo a lo que no sabe hacer** — «eso no lo hago», en vez de
improvisar un apaño que casi funciona.

**Y la personalidad vive en el prompt.** Sin fine-tuning: el Baxy anterior ya
conseguía que el modelo dijera «Soy Baxy» sólo con el system prompt. Cambiar el
carácter tiene que ser editar un texto. Si te ves proponiendo entrenar un modelo
para que suene a BAXY, es que el prompt está mal escrito.

## Lo que ya se sabe

**Hay palabras inventadas en la prosa española.** Formadas a partir de raíces
plausibles: «cuecer», «vertir», «tiender», «cosear», «Descalzica», «Inflata»,
«alredad». El guardián por terminaciones no las ve, porque son terminaciones
válidas sobre raíces mal derivadas. Hace falta comprobación de elección de
palabra, o un modelo que no las produzca.

Este síntoma **ya se diagnosticó una vez en este proyecto**: FunctionGemma midió
que la cuantización Q2 producía «fysico» y «lumínar» y rompía la persona, y lo
resolvió subiendo a Q4_K_XL QAT (~1,5 GB de VRAM). Es una pista fuerte, no una
conclusión heredada — el dueño fue explícito: *«que se evalúe bien y simplemente
se elija lo mejor posible, siempre pensando en el menor uso de recursos que
funcione bien»*. Mide antes de gastar VRAM.

**Se recuperó una ruta que publicaba una constante.** La ruta visible excepcional
de `message.compose` ya no publica una constante ni pierde confirmaciones:
conserva una cola ordenada y sólo publica prosa formulada y validada por el
modelo. Ese es el patrón — cópialo donde falte.

**El texto visible se lee a mano.** Una decisión contractual correcta puede
acompañar una respuesta inservible, y ya pasó: preguntas que no preservan la
operación, negativas repetidas, planes que el veto bloqueó narrados como si
hubieran corrido. Un scorer automático no lo detecta; una persona leyendo, sí.

**Cuidado con el detector léxico de éxitos falsos.** Ya produjo un falso positivo
—una referencia a una imagen que la persona había enviado— y el scorer de una
medición anterior se equivocó en 3 de 4 en el único criterio que se revisó.

## Qué cubre

Todo lo que sale por pantalla: confirmaciones, preguntas de aclaración,
negativas, errores, narración de progreso, resúmenes de misión. En español,
inglés y spanglish, respondiendo en el idioma en que se le habló.

Incluye los casos feos, que es donde aparecen las constantes: el provider que
falla, el timeout, la operación ambigua, la petición fuera de catálogo, el
modelo que devuelve algo inválido. Cada uno de esos necesita prosa formulada, no
una plantilla.

## Cómo mides

Lee los textos, uno por uno. Busca constantes conocidas en `reply_text`, pero no
te fíes sólo de eso: una constante nueva no está en la lista de constantes
conocidas.

Y comprueba que la prosa se sostiene: que las palabras existen, que la frase dice
lo que pasó, y que alguien que no sabe cómo funciona BAXY la entendería.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

La auditoría del texto visible sobre población real, leída a mano, con las
constantes que quedaban y cómo las quitaste. Si una ruta no puede formular prosa
—porque el modelo no responde a tiempo, por ejemplo— resuélvelo sin constantes:
el problema es el silencio, y una plantilla no lo arregla, lo disfraza.

## Cuándo has terminado

Cuando puedas leer cien respuestas seguidas de BAXY y ninguna suene a máquina
rellenando un hueco.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
