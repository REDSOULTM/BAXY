# APPS1029 — cerrar lo ejecutable de «Abrir aplicaciones»

Categoría `apps_open`: 54 casos, 14 cubiertos, 40 abiertos. Es la mayor masa abierta que **ya llega al
reconocedor determinista**: 21 de sus 40 abiertos resuelven `app.open` o `game.launch` sin pasar por el
modelo, medido con `scratchpad/c03-open-mass-by-reach.py` sobre la línea base del reconocedor. En
SYSTEM1028 el camino determinista cumplió 9 de 14 y el del modelo 3 de 15, así que esta es la palanca.
El mecanismo `app.open` ya tiene crédito adjudicado en esta categoría con identidad de proceso y
ventana verificada (`APP_REPEAT955`, `APP_OPEN853`), luego se usa el tramo grande permitido y no la
primera tanda de diagnóstico.

**17 literales ejecutables de los 21 que llegan.** Cinco quedan aparcados con razón declarada antes de
ejecutar, no rellenados ni convertidos en variantes:

| Literal | Por qué se aparca |
|---|---|
| H0461 `che, abrime el chrome` | Es una de las **18 filas sin marca** original: sigue siendo límite, no crédito. Su destino se ejercita como variante dev-03, que tampoco suma al 742. |
| H0083 `lanzá Mortal Kombat en Steam` | `game.launch` sobre un juego que esta máquina no tiene instalado; exige sesión y entitlement de Steam, fuera de la política de instalación. |
| H0608 `lanzá Mortal Kombat` | Mismo motivo, y sin resolución determinista del destino. |
| H0691 `no, mejor abrí firefox` | Firefox no está instalado aquí, y el literal es además una corrección sin antecedente: dos conductas en un caso. |
| H0183 `abrí la calculadora y decime qué hora es` | Es el compuesto de reloj cuya primera transformación incorrecta ya está diagnosticada y sin reparar (causa B de `SYSTEM1028/DIAGNOSIS.md`). Va en la tanda de reparación. |

Los otros 19 abiertos de la categoría no llegan al reconocedor —erratas y variantes ortográficas de
«steam» y «calculadora», idiomas no pedidos, explorador de archivos, Photoshop— y son el material de la
reparación léxica siguiente, no de esta tanda.

## Una conducta, dos salidas, las dos veraces

`app_open_named_installed`: dejar abierta la app instalada que la petición nombra y **reportar con
verdad la salida**. Si el producto la lanzó, que la lanzó; si ya estaba en ejecución, que ya estaba,
sin afirmar un lanzamiento que no hizo. `AlreadyRunning`/`ReusedExisting` es una salida de primera
clase del contrato (`AppOpenHandler.cs:59`, `WindowsInstalledApplicationOpenProvider.cs:596`) con su
propio recibo verificado, y ya obtuvo crédito así en esta categoría (H0166 en `APP_REPEAT955`).

## Entorno declarado antes de ejecutar, y por qué

Chrome, Discord, Steam, Windows Settings y un Notepad **ya estaban en ejecución** cuando se selló este
panel, arrancados por el usuario de esta máquina fuera del árbol de procesos medido. Calculator, Paint
y Windows Terminal **no** estaban en ejecución.

Esto no es comodidad: está medido. `WindowsInstalledApplicationOpenProvider` arranca con
`UseShellExecute = false`, así que la app queda descendiente de `baxy-core.exe` y su memoria GPU cuenta
contra la guarda heredada de 3800 MiB, que el muestreador atribuye por PID al árbol. Con el mismo
contador de Windows que usa la guarda («GPU Process Memory / Dedicated Usage»,
`scratchpad/c03-app-gpu-cost.py`) esta máquina mide:

| Destino | GPU dedicada | RSS |
|---|---:|---:|
| Steam (10 procesos) | 644,39 MiB | 1170,98 MiB |
| Windows Store | 196,25 MiB | 314,12 MiB |
| Paint | 194,29 MiB | 167,67 MiB |
| Notepad | 85,73 MiB | 212,35 MiB |
| Windows Terminal | 57,43 MiB | 110,81 MiB |
| Windows Settings | 16,62 MiB | 175,93 MiB |
| Calculator | 13,10 MiB | 105,77 MiB |
| Chrome (14 procesos) | 7,55 MiB | 1666,45 MiB |
| Discord (6 procesos) | 0,00 MiB | 928,75 MiB |
| Mapa de caracteres | 0,00 MiB | 21,47 MiB |

Con el pico de 3494,93 MiB de SYSTEM1028, lanzar Steam dentro del árbol daría ~4139 MiB y **rompería la
guarda**. No se toca la guarda ni se falsifica un pin: se declara el entorno y se sella. Los destinos
que sí se lanzan dentro del árbol suman como máximo 3494,93 + 13,10 + 194,29 + 57,43 + 7,55 = 3767 MiB
en el peor caso —si Windows atribuyera al árbol incluso las apps que activa el servicio AppX—, por
debajo de la guarda. Windows Store queda fuera del panel por su coste.

## Panel

27 casos, 54 líneas de wire, 27 `session.new` normales, 0 confirmaciones, 0 inyecciones.

| Bloque | Casos |
|---|---|
| Literales calculadora | H0251 (lanzamiento real), H0497, H0575, H0588, H0683 |
| Literales de app única | H0085 Discord, H0706 Configuración |
| Literales Steam | H0015, H0055, H0134, H0136, H0315, H0317, H0391, H0418, H0544, H0653 |
| Variantes de lanzamiento | dev-01 ES Paint, dev-02 EN Windows Terminal |
| Variantes de ya en ejecución | dev-03 EN Chrome, dev-04 ES Discord, dev-05 EN Steam |
| Límites | boundary-01 prohibición, -02 cita, -03 condición futura, -04 narrativa, -05 instrucción incrustada |

**5 variantes, no 10–15, y se declara el número real.** Cada variante necesita una redacción que no
duplique un literal y un destino instalado que el presupuesto de GPU medido admita; con Store y Paint
al límite y Firefox ausente, los destinos nuevos disponibles son los cinco que van. Las variantes no
suman al 742 y los límites nunca suman.

Las dos salidas quedan con su par propio: lanzamiento real con dev-01 (ES) y dev-02 (EN); ya en
ejecución con dev-03 (EN), dev-04 (ES) y dev-05 (EN). No se hereda ningún par de tandas anteriores.

**Crédito máximo condicionado: 17. Crédito actual 0.**

## Criterio, escrito antes de ejecutar

Raíz adjudica contra el recibo de la operación —identidad de proceso y ventana observada— leído fresco
en la adjudicación, no contra valores recordados. Falla: afirmar un lanzamiento que no ocurrió, nombrar
otro destino que el pedido, ejecutar un segundo efecto no pedido, inventar un antecedente o una cifra,
y usar frase visible fija. En los cinco límites, cualquier apertura es fallo del límite.

Sin fixtures, sin valores prefijados, sin contexto añadido y sin respuestas de texto fijo esperadas.
Material sellado antes de ejecutar; los criterios no se cambian después de ver resultados. Pruebas
automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
