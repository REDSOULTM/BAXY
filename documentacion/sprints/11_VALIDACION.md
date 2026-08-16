# Goal 11 — La validación y el cierre

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Es el último de los once: cuando cierra, BAXY es un
> producto terminado.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: GPT-5.6 Sol, `reasoning.effort: high`.

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
cuatro intentos anteriores del proyecto sobre la mesa.

Aquí tiene además un uso extra: **la identidad es la lista de comprobación final**.
Recórrela entera contra el producto terminado. Cada decisión que hay escrita ahí o
está cumplida, o está declarada como limitación con su causa.

## Las cinco leyes, con una invertida

**1. Hereda primero, estado del arte después, construye al final.** Si algo sigue
flojo, mira antes en [`biblioteca/00_INDICE.md`](../../biblioteca/00_INDICE.md)
—1.350 documentos de las cuatro escrituras anteriores— y luego si está resuelto ahí
fuera; construir es el último recurso. Que BAXY ya lo haga de una manera no es
razón para conservarla. Pero es una pasada, no una persecución: este goal
**cierra** el producto, no lo reabre.

**2. Nada de sobreingeniería.** Sigue en pie, y aquí es la más importante de todas.
Este goal persigue lo hipotético, y ése es exactamente el terreno donde se generan
capas que nadie necesita. Cada defensa que escribas tiene que corresponder a algo
que puede ocurrir de verdad y que rompe un invariante — no a un escenario que se te
ocurrió.

**3. Sólo se arregla lo que bloquea — ésta se invierte.** Los diez goals anteriores
tenían prohibido perseguir lo que *podría* fallar. Iban rápido a propósito y todo lo
que olía a fragilidad teórica se anotaba en `documentacion/APLAZADOS.md`. **Aquí se
cobra esa deuda.**

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Y una
defensa que dobla el consumo para cubrir un caso que ocurre una vez al año no es
una mejora del producto.

**5. Cada pieza sustituible, y ninguna más.** Aquí te toca la parte de cobrar:
`documentacion/03_COSTURAS.md` no puede quedar con una fila vacía. Cada pieza del
registro necesita la medición que decide su sustituto, lo elegido hoy y la fecha.
Ése es el documento que permite mejorar BAXY dentro de dos meses sin reescribirlo.

Y **cero código muerto**, que en este goal es un frente entero: una pieza
sustituida se borra, no se queda detrás de una bandera. Dos implementaciones vivas
de lo mismo son la acumulación con otro nombre.

Y la consigna que une las cinco: ésta es la **quinta** escritura de BAXY y tiene
que ser **la más rápida de las cinco**. No porque haga menos —es la definitiva—
sino porque no vuelve a descubrir nada que ya se descubrió.

---

## El objetivo

**BAXY aguanta.** No sólo funciona cuando todo va bien: aguanta cuando algo va mal,
y cuando algo va mal sigue sin mentir.

Cuatro frentes, y el orden importa porque el primero paga el resto.

**1. La deuda aplazada.** Abre `documentacion/APLAZADOS.md` y resuélvelo. Cada
entrada acaba en una de tres: arreglada, medida y descartada como irrelevante, o
declarada limitación ambiental con su degradado honesto. Ninguna se queda en
«pendiente».

**2. Los caminos de error.** Ahora sí, deliberadamente: el modelo que no responde,
el que devuelve basura, el provider que informa éxito sin actuar, el que se ejecuta
dos veces, el timeout a media misión, el disco sin espacio, la sesión que se corta a
la mitad. Que ninguno acabe en una afirmación falsa ni en una constante en pantalla
— el estado terminal honesto es la respuesta correcta a todos ellos.

**3. Regresión completa.** Los diez goals anteriores midieron cada uno lo suyo, en
momentos distintos, sobre árboles distintos. Vuelve a medirlo todo junto sobre el
árbol final: los cortes de exactitud, los tres ceros, la latencia, las misiones, la
voz. Un goal pudo romper lo que otro cerró y nadie lo habría visto.

**4. Lo que sobra.** Código muerto, dependencias que ya nadie usa, artefactos de
experimentos cerrados, modelos descargados que no se promovieron, documentación que
contradice al producto.

Ese cuarto frente es la ley 2 cobrada al final, y es más importante de lo que
parece: el proyecto se ha reescrito **cuatro veces** por acumulación, y el dueño
puso ahí su línea roja — lo único que, si vuelve a pasar, significaría que este BAXY
también falló es **que vuelva a apilarse**. Sal de este goal con menos código,
menos capas y menos ficheros de los que encontraste. Si no puedes, di por qué.

## Cómo decides qué merece arreglo

Aquí sí persigues lo hipotético, pero no todo lo hipotético merece código.

Pregúntate qué pasa **si ocurre**: si el peor caso es que BAXY afirme algo falso,
ejecute algo no pedido o suelte una constante, se arregla — eso rompe un invariante
y no hay grado. Si el peor caso es que se vea feo o vaya lento en una esquina que
nadie visita, se anota y se declara.

## Limitaciones: nombrarlas es cerrarlas

Al final quedará algo sin resolver, y eso está bien **si está nombrado**. Cada
limitación restante se declara una por una, con su causa y su degradado.

La frontera es estricta: **ambiental** es sólo aquello cuya causa está fuera del
código de BAXY y BAXY no puede reparar — no hay micrófono, el sistema operativo no
expone la API, el certificado no está comprado. Todo lo demás es un bug, por
antiguo, caro o ajeno que sea. Difícil no lo vuelve ambiental.

Fuera de alcance por decisión del dueño, y por tanto no cuentan como limitaciones
abiertas: el perfil certificado de 4 GB de VRAM y el de 8 GB de RAM, la instalación
limpia y el purge en cuenta desechable, y el certificado de firma.

## Criterios de cierre

- [ ] `APLAZADOS.md` **vacío**: cada entrada arreglada, descartada con medición, o
      declarada limitación ambiental con su degradado.
- [ ] Los caminos de error recorridos a propósito, y ninguno acaba en afirmación
      falsa ni en constante.
- [ ] Regresión completa sobre el árbol final, todo medido junto y publicado.
- [ ] Menos código, menos capas y menos ficheros que al empezar — o la explicación
      de por qué no.
- [ ] `00_IDENTIDAD.md` recorrida entera: cada decisión, cumplida o declarada.
- [ ] **`03_COSTURAS.md` sin una sola fila vacía**: cada pieza con su medición, lo
      elegido hoy y la fecha. Es lo que permite mejorar BAXY dentro de dos meses sin
      reescribirlo.
- [ ] Cero código muerto, cero implementaciones dobles de lo mismo, cero banderas
      que guardan una versión anterior «por si acaso».
- [ ] El documento de cierre escrito.

## Cuando lo cumplas

BAXY terminado, y un documento de cierre que diga en qué estado queda: qué se midió
sobre el árbol final y con qué número, qué se arregló de la deuda aplazada, y qué
limitaciones quedan nombradas una por una.

Ese documento es lo que alguien lee para saber si puede confiar en el producto.
Escríbelo para esa persona.

La prueba final es ésta: dejar BAXY funcionando en una máquina, irse, volver a la
semana, y que siga sirviendo sin haber mentido ni una vez.

Publica el estado real. Un producto con tres limitaciones declaradas es entregable;
uno con tres limitaciones ocultas, no.
