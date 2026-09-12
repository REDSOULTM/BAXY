# Estado para el dueño — 12 de septiembre, relevo completo y primera tanda propia

**130/742 cubiertos, 612 abiertos, 102 altas en 24 h, 0/35 categorías cerradas.** El tramo pasó de 126
a 130 con una tanda real sellada y medida en esta máquina. C03 no está completado y no lo declaro.

## El traslado funcionó

El ZIP llegó íntegro: SHA y tamaño exactos, y las 95 entradas verificadas una a una contra su
manifiesto. Lo extraje en carpeta nueva sin sobreescribir nada tuyo. El registro de la encuesta
apareció con el SHA declarado, 742 filas, 126 cubiertos y 616 abiertos: exactamente lo prometido.

## Lo que se cerró sin volver a ejecutar nada

Leí los 25 terminales de la tanda 1025 y la cerré por completo: 13 cumplen, 12 fallan. Su crédito
sigue siendo 3, el que ya estaba escrito, y los contadores no se movieron por esa adjudicación.

Los fallos son de dos clases claras. Hechos inventados sobre obras: Marvel vs. Capcom fechado en 2000
cuando el estreno original fue arcade en 1998; Doom Eternal atribuido a Bethesda Game Studios, a 2023
y a enemigos alienígenas cuando es id Software, Bethesda Softworks, 20 de marzo de 2020 y demonios;
Chell descrita como hombre y Portal como mundos alternativos. Y referente ausente inventado: tres de
cuatro casos respondieron hablando de la identidad de BAXY en vez de preguntar de quién se hablaba.
Contrasté cada fecha y cada estudio con fuentes primarias antes de darlos por fallidos.

Tres casos cumplen y siguen abiertos, y quiero que quede claro por qué: su literal está bien, pero la
conducta no dejó dos variantes en pie, y sin par no hay crédito. Preferí eso a inflar el contador.

## La primera tanda medida aquí

Sellé 31 casos antes de ejecutar, sobre los abiertos de estado de hardware y sistema. Salió limpia:
exit 0, 31 terminales, cero violaciones, 154 segundos, VRAM 3494 MiB y RAM 2587 MiB, las dos por
debajo del techo. 14 cumplen, 17 fallan, **+4 cubiertos**: memoria instalada por dos vías, espacio
libre en disco, y nombre de máquina con usuario.

Dos respuestas me gustaron especialmente porque son veraces donde era fácil mentir: a «está cargando
la batería» contestó que este equipo no tiene batería y está en corriente, que es exactamente cierto;
y dio la ocupación real de VRAM. Ninguna de las dos cobra, porque sus variantes fallaron, pero
demuestran que el mecanismo está.

Cinco abiertos de esa categoría los aparqué con razón, no los rellené: resolución de pantalla, Hz del
monitor, número de monitores y versión de Python instalada **no tienen operación en el catálogo**.
Serían infraestructura nueva y son cuatro casos, muy por debajo de los diez que tú pusiste como
mínimo. Por eso la categoría no puede cerrarse todavía, y lo digo en vez de forzarlo.

## Lo más útil que encontré

Los 17 fallos no son 17 problemas: son tres, y en los tres el compositor de prosa hace lo correcto con
lo que recibe. El problema está antes, en la decisión.

1. Una lectura que **sí está** en el catálogo se clasifica como fuera de catálogo. «Cuánto espacio
   queda en C» dijo que no podía, y «cuánto espacio libre tengo en disco» lo dio, en la misma tanda.
   Seis casos así.
2. En una petición de dos mitades se pierde la mitad de la hora, y entonces el texto **la inventa**:
   publicó «Hoy es 5 de abril de 2025» cuando era el 12 de septiembre de 2026. Sus dos variantes
   eligieron la otra salida, decir que la hora no estaba disponible. Ninguna de las dos vale.
3. Para una pregunta sobre la GPU se pidió el resumen general, que no incluye GPU, y luego se declaró
   sin acceso. Ese mismo resumen traía el estado de batería que otros dos turnos habían declarado
   imposible. El producto tenía el dato en la mano y lo negó.

Ninguna de las tres necesita infraestructura nueva. Repararlas rinde más que otra tanda ancha, porque
atraviesan varias categorías. La tanda de reparación necesita los seis casos que hoy funcionan como
controles de no regresión: no quiero cambiar la decisión y perder lo que ya cobra.

También dejé demostrado, ejecutando las funciones puras sin GPU, que la ruta de aclaración por
referente ausente existe, está sana y **no se alcanza**: el reconocedor que la dispara sólo cubre
órdenes de apertura tipo «ábrelo». No la amplié porque «su» en español es también tratamiento formal y
una regla amplia rompería «¿Cuál es su nombre?» dirigido a BAXY, en una categoría con 7 cubiertos.

## Dos cosas que corregí de mí mismo

Debilité una comprobación del runner heredado creyendo que era imposible de cumplir, y estaba
equivocado: el producto sustituye el Core junto a `Baxy.exe` por el publicado al arrancar, así que la
comprobación original era correcta. La revertí. Antes de eso, una primera medición se detuvo a 1,3
segundos justo por ese motivo; la conservé como evidencia en lugar de borrarla.

## Ritmo

102 altas en 24 h, por encima del mínimo de 20 sin Full. Pero de esas, sólo 4 son de esta sesión: el
resto viene del tramo anterior. A este ritmo real, con tandas de 30 casos que rinden 4 créditos, los
612 abiertos no se cierran pronto, y no te voy a dar una fecha inventada. Lo que sí acelera es
reparar las tres causas: los 17 fallos de hoy no eran 17 problemas distintos.

Pruebas automatizadas, Fast y Full siguen omitidas por tu instrucción: omitidas, no verdes.
