# Estado para el dueño — 12 de septiembre, madrugada: de 130 a 137

**137/742 cubiertos, 605 abiertos, 109 altas en 24 h, 0/35 categorías cerradas.** Siete filas nuevas en
esta tanda de trabajo, todas con ejecución real sellada en el producto. C03 no está completado y no lo
declaro.

## Lo que más rinde no era ejecutar más, era saber qué elegir

Hice un instrumento que cruza dos cosas que estaban separadas: cuántos abiertos tiene cada categoría y
cuántos de ellos **ya llegan al reconocedor determinista**. De los 612 abiertos, 157 llegaban y 455
caían al modelo. Y el camino determinista cumple tres veces más. Así que el trabajo se ordena por
abiertos que ya llegan, y eso puso «Abrir aplicaciones» primero: 21 de sus 40 abiertos resolvían solos.

Esa categoría pasó de 14 a 21 cubiertos.

## Una cosa que estuvo a punto de arruinar la tanda, y se midió antes

Steam gasta 644 MiB de memoria de GPU, y el producto abre las apps como procesos hijos suyos. Si Steam
se abría dentro de la tanda medida, el árbol habría llegado a 4139 MiB y habría roto la guarda de 3800
que heredé. No toqué la guarda: dejé Steam abierto de antes, lo declaré en el sello y el runner lo
comprueba. Lo mido con el mismo contador de Windows que usa la guarda, no con una estimación.

## El hallazgo grande: BAXY exigía el foco para creer que una app está abierta

En la primera tanda, la calculadora y la configuración fallaban siempre: «no pude verificar el
resultado». Y la calculadora **sí se abría** — su proceso arrancó a las 01:50:51, dentro de la ventana
de la tanda. El motivo: los tres proveedores de apertura sólo aceptaban como prueba que la ventana
tuviera el **primer plano**, y Windows no le concede el foco a un proceso que no lo tiene.

Lo confirmó una tanda entera perdida: se abrió el panel de «Configuración rápida» de Windows, que se
queda con el foco y no lo suelta, y las diecisiete vueltas fallaron —incluidas Steam y Discord, que
ocho minutos antes habían verificado bien— con las tres apps visibles en pantalla. Esa tanda la declaré
invalidada por el escritorio, sin crédito y sin tocar el registro: no se puede juzgar conducta con ese
material.

Cambié la regla: BAXY pide el foco y ya no lo exige. La prueba de que una app está abierta es que tiene
una ventana visible del proceso que el recibo identifica. Compilé por el arranque del propio producto,
arrancó y contestó, y la tanda siguiente lo confirmó: la calculadora y la configuración **verifican**, y
cuatro filas cobraron.

## Lo segundo que arreglé, y por qué todavía no cobra

Las once veces que BAXY abrió Steam recibió el mismo dato: «ya estaba en ejecución». Lo dijo tres veces
y se lo calló ocho, publicando «Abrí Steam.» sobre un programa que llevaba horas abierto. No mentía por
maldad: ese dato no estaba en ninguna lista de hechos obligatorios, así que omitirlo era legal.

Lo hice obligatorio. Dejó de mentir en las siete vueltas y los tres controles que ya funcionaban
siguieron intactos. Pero pasó algo que no acredito: las siete frases salieron **idénticas entre sí** y
con la forma de la instrucción interna que las corrige. Tú pediste cero respuestas visibles fijas, y
siete frases iguales lo son. Escribí ese criterio **antes** de ejecutar y no lo voy a relajar ahora que
me estorba.

Lo bueno es que ya sé por dónde va la solución, y está medido: las tres respuestas veraces **y
distintas** salieron del primer borrador, sin instrucción correctiva. La instrucción es lo que
homogeniza. La próxima reparación hace que el hecho viaje como hecho y el borrador lo diga solo.

También encontré el defecto espejo: en un caso dijo «ya tengo la calculadora abierta» cuando la acababa
de abrir él. El mismo control, en la otra dirección.

## Ritmo, sin adornos

Siete filas en esta sesión con cuatro tandas reales. A ese ritmo los 605 abiertos no se cierran pronto y
no te voy a dar una fecha inventada. Lo que acelera es esto mismo: cada reparación transversal convierte
lotes enteros de fallos en cobertura, y las dos de hoy dejan 7 literales de Steam esperando una tercera
vuelta que ya está diagnosticada.

Pruebas automatizadas, Fast y Full siguen omitidas por tu instrucción: omitidas, no verdes.
