# Sprint 11 — Validación y cierre

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue. Para sólo si vas a tocar datos personales del usuario u otros proyectos de
la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

## Este sprint invierte una regla

Los diez anteriores tenían prohibido perseguir lo que *podría* fallar. Iban
rápido a propósito, y todo lo que olía a fragilidad teórica se anotaba en
`documentacion/APLAZADOS.md` y se dejaba pasar.

**Aquí se cobra esa deuda.** Este es el sprint donde sí se piensa en lo que
todavía no ha roto: el camino de error que nadie recorrió, el provider que falla
a medias, el disco lleno, la ruta que sólo se ejecuta una vez al mes.

Es el último. Después de éste, BAXY es un producto terminado.

## Lo que cuenta

**BAXY aguanta.** No sólo funciona cuando todo va bien: aguanta cuando algo va
mal, y cuando algo va mal sigue sin mentir.

Cuatro frentes, y el orden importa porque el primero paga el resto:

**1. La deuda aplazada.** Abre `documentacion/APLAZADOS.md` y resuélvelo. Cada
entrada acaba en una de tres: arreglada, medida y descartada como irrelevante, o
declarada limitación ambiental con su degradado honesto. Ninguna se queda en
«pendiente».

**2. Los caminos de error.** Ahora sí, deliberadamente: el modelo que no
responde, el que devuelve basura, el provider que informa éxito sin actuar, el
que se ejecuta dos veces, el timeout a media misión, el disco sin espacio, la
sesión que se corta a la mitad. Que ninguno acabe en una afirmación falsa ni en
una constante en pantalla — el estado terminal honesto es la respuesta correcta a
todos ellos.

**3. Regresión completa.** Los diez sprints anteriores midieron cada uno lo suyo,
en momentos distintos, sobre árboles distintos. Vuelve a medirlo todo junto sobre
el árbol final: los cuatro cortes de exactitud, los tres ceros, la latencia, las
misiones, la voz. Un sprint pudo romper lo que otro cerró y nadie lo habría
visto.

**4. Lo que sobra.** Código muerto, dependencias que ya nadie usa, artefactos de
experimentos cerrados, modelos descargados que no se promovieron, documentación
que contradice al producto. BAXY tiene que pesar poco también en disco, y lo que
sobra confunde a quien venga después.

## Cómo decides qué merece arreglo

Aquí sí persigues lo hipotético, pero no todo lo hipotético merece código.

Pregúntate qué pasa **si ocurre**: si el peor caso es que BAXY afirme algo falso,
ejecute algo no pedido o suelte una constante, se arregla — eso rompe un
invariante y no hay grado. Si el peor caso es que se vea feo o vaya lento en una
esquina que nadie visita, se anota y se declara.

Y sigue valiendo el límite de recursos: una defensa que dobla el consumo para
cubrir un caso que ocurre una vez al año no es una mejora del producto.

## Limitaciones: nombrarlas es cerrarlas

Al final quedará algo sin resolver, y eso está bien **si está nombrado**. Cada
limitación restante se declara una por una, con su causa y su degradado.

La frontera es estricta: **ambiental** es sólo aquello cuya causa está fuera del
código de BAXY y BAXY no puede reparar — no hay micrófono, el sistema operativo
no expone la API, el certificado no está comprado. Todo lo demás es un bug, por
antiguo, caro o ajeno que sea. Difícil no lo vuelve ambiental.

Fuera de alcance por decisión del responsable, y por tanto no cuentan como
limitaciones abiertas: el perfil certificado de 4 GB de VRAM y el de 8 GB de RAM,
la instalación limpia y el purge en cuenta desechable, y el certificado de firma.

## Qué entregas

BAXY terminado, y un documento de cierre que diga en qué estado queda: qué se
midió sobre el árbol final y con qué número, qué se arregló de la deuda
aplazada, y qué limitaciones quedan nombradas una por una.

Ese documento es lo que alguien lee para saber si puede confiar en el producto.
Escríbelo para esa persona.

## Cuándo has terminado

Cuando puedas dejar BAXY funcionando en una máquina, irte, volver a la semana, y
que siga sirviendo sin haber mentido ni una vez.

## Cierra

Publica el estado real. Si algo queda abierto, nómbralo — un producto con tres
limitaciones declaradas es entregable; uno con tres limitaciones ocultas, no.
