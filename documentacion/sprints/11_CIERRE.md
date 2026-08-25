# Goal 11 — El cierre

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Es el último de los once: cuando cierra, BAXY es un
> producto terminado.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: **Grok 4.6**, esfuerzo `high`.

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

La identidad ya fue recorrida decisión por decisión en el Goal 10. Aquí se conserva
esa evidencia y se presenta sin reinterpretarla ni ejecutar una segunda validación.

## Las cinco leyes

**1. Hereda primero, estado del arte después, construye al final.** Si algo sigue
flojo, mira antes en [`biblioteca/00_INDICE.md`](../../biblioteca/00_INDICE.md)
—1.350 documentos de las cuatro escrituras anteriores— y luego si está resuelto ahí
fuera; construir es el último recurso. Que BAXY ya lo haga de una manera no es
razón para conservarla. Pero es una pasada, no una persecución: este goal
**cierra** el producto, no lo reabre.

**2. Nada de sobreingeniería.** Sigue en pie, y aquí es especialmente simple: no
construyas un segundo runner, otra matriz ni un nuevo formato de informe. Enlaza la
evidencia dueña y escribe sólo lo necesario para que otro pueda entenderla.

**3. Sólo se arregla lo que bloquea.** Los diez goals anteriores ya cobraron la
deuda y validaron el producto. Este goal no reabre código por una idea nueva: una
contradicción documental o evidencia ausente bloquea el cierre; lo demás pertenece
a una tanda posterior de mantenimiento.

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

## Cómo trabajas aquí

No es estilo: es lo que esta máquina y este harness te dan, y lo que este repositorio
ya midió que hace falta decir.

**Esfuerzo `high` de suelo.** Súbelo con `/effort xhigh` en el tramo que lo merezca —un
diseño abierto, un fallo que no se explica— y bájalo después. Cada peldaño multiplica
los tokens de razonamiento, y este goal está escrito para `high`.

**Busca y lee con tus tools, no con la shell.** `grep` es ripgrep por dentro: acótalo a
`src tests scripts main.py` salvo que vayas a la evidencia a propósito, y pide rutas
antes que líneas. Lee rangos con `read_file`, no ficheros enteros. En la shell **no
existe `rg`**: es PowerShell, y `run_terminal_command` es para git, pytest, dotnet y
procesos. Antes de abrir algo grande, mira el tamaño: `git ls-tree -r -l HEAD -- ruta`.

**No repitas la validación.** Comprueba por hash y lectura acotada que la evidencia
pertenece al árbol entregado. Si falta una medición, vuelve al Goal 10: no lances aquí
una campaña parcial para rellenar el informe.

**Sin subagentes.** `spawn_subagent` hereda tu modelo: paga otra vez contexto y
razonamiento para devolverte un informe que además tienes que leer. Esto se resuelve en
el hilo principal. Única excepción: una exploración de sólo lectura acotada cuyo
resultado quepa en rutas + rangos + conclusión.

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

**No cambies el producto.** Este goal edita documentación y handoff. Cualquier cambio
en `src`, `main.py` o comportamiento devuelve el trabajo al Goal 10 y exige cerrar de
nuevo su validación integral.

---

## El objetivo

**Cerrar BAXY sin volver a validarlo.** El Goal 10 ya recorrió identidad, corpus,
operaciones, caminos de error, deuda, limpieza y regresión sobre un único árbol
final. Este goal convierte esa evidencia en un estado de producto legible y
publicado.

Tres frentes:

**1. Integridad del cierre.** Comprueba que el commit y los hashes citados por la
evidencia del Goal 10 corresponden al árbol que se entrega y que todos sus criterios
están marcados. Si no corresponden, el Goal 10 no terminó: vuelve a él. No ejecutes
aquí otra campaña para sustituir una evidencia ausente.

**2. Documentación vigente.** Elimina contradicciones entre Identidad, arquitectura,
guías, matriz de corpus, limitaciones y conducta entregada. No cambies la definición
del producto para hacer coincidir un fallo: cualquier discrepancia de conducta
reabre el Goal 10.

**3. Handoff y publicación.** Escribe un documento de cierre corto que enlace la
evidencia completa, explique qué puede hacer BAXY, qué límites ambientales quedan y
cómo se reproduce o mantiene. Deja el repositorio limpio y publicado.

## Cómo decides qué merece arreglo

Aquí no persigues hipótesis ni escribes defensas nuevas. Si descubres un defecto de
producto, documenta el hallazgo y devuelve el trabajo al Goal 10; no lo arregles y
lo declares cerrado sin repetir allí su validación integral.

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

- [ ] El árbol entregado coincide exactamente con el commit y los hashes certificados
      por el Goal 10; todos sus criterios están cerrados y no se sustituyeron por una
      segunda validación parcial.
- [ ] Identidad, arquitectura, corpus, limitaciones y guías describen la conducta
      certificada sin contradicciones ni instrucciones caducadas.
- [ ] El documento de cierre enlaza la matriz de identidad, los 1.947 veredictos
      individuales, las 808 misiones, los 2.036 casos adicionales, la compuerta Full,
      las limitaciones y el procedimiento de reproducción.
- [ ] No se modificó código de producto después del árbol validado. Si se modificó,
      el Goal 10 se reabrió y volvió a cerrar antes de continuar.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuando lo cumplas

BAXY terminado, y un documento de cierre que diga en qué estado queda: qué se midió
sobre el árbol final y con qué número, qué se arregló de la deuda aplazada, y qué
limitaciones quedan nombradas una por una.

Ese documento es lo que alguien lee para saber si puede confiar en el producto.
Escríbelo para esa persona.

No añadas una prueba temporal al cierre: ningún *soak*, espera de 24 horas, noche de
ejecución ni requisito de uso prolongado forma parte de la entrega. El uso normal
posterior aportará esa experiencia sin bloquear el producto.

Publica el estado real. Un producto con tres limitaciones declaradas es entregable;
uno con tres limitaciones ocultas, no.
