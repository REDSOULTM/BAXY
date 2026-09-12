# CLOCK1034 — los diez abiertos ejecutables de «Hora y fecha», sin tocar el PC

Categoría `clock`: 23 casos, 3 cubiertos, 20 abiertos. **Diez de esos veinte resuelven `system.time` en
el reconocedor determinista**, medido con `scratchpad/c03-open-mass-by-reach.py`, y la operación es de
sólo lectura: no hay app que abrir, ni ventana que traer al frente, ni efecto que reconciliar. Después de
cuatro tandas peleando con el estado de las ventanas, esta es la masa abierta más limpia que queda.

El mecanismo ya tiene conducta acreditada en la categoría: la fecha local en `STATUS_BATCH752B` (H0180,
H0499) y hora más batería en el producto 546 (H0079). Por eso se usa el tramo grande y no la primera
tanda de diagnóstico.

**Diez literales, y se declara el número real.** Los otros diez abiertos quedan aparcados con razón, en
el mapa del panel: dos son la palabra «tiempo» sola —ambigua entre reloj y clima—, cuatro están en
portugués, alemán, francés e italiano, dos no llegan al reconocedor por léxico, uno pide una resta de
tiempo que no es lectura de reloj y no tiene operación, y uno es una errata doble que pertenece a la
reparación léxica.

## Panel: 22 casos, 44 líneas de wire

| Bloque | Casos | Acredita |
|---|---|---|
| Literales de hora | H0126, H0223, H0449, H0450, H0498, H0586, H0600, H0602, H0700, H0727 | sí, hasta 10 |
| Controles cubiertos de fecha | H0180 `qué fecha es`, H0499 `mostrame la fecha` | no |
| Variantes ES | dev-01 `me decís la hora`, dev-03 `qué hora tenés`, dev-05 `a qué hora estamos` | no |
| Variantes EN | dev-02, dev-04, dev-06 | no |
| Límites | -01 cita ajena, -02 condición futura, -03 pregunta de capacidad, -04 prohibición | nunca |

**Crédito máximo condicionado: 10.** Los dos controles ya están cubiertos y no cobran dos veces; si la
lectura de fecha se rompiera, se vería aquí.

## Criterio, escrito antes de ejecutar

La hora publicada tiene que coincidir **al minuto** con la lectura observada que el recibo liga a esa
invocación, en el idioma del pedido. Raíz adjudica contra el recibo leído fresco en la adjudicación, no
contra un valor recordado. Falla: inventar una cifra, presentar UTC como hora local, ejecutar un segundo
efecto no pedido, inventar un antecedente, reproducir la instrucción interna de reintento o usar
vocabulario interno. Un terminal sin frase publicada falla. La coincidencia entre turnos cuyo literal
sellado y cuya lectura observada son los mismos no falla por sí sola, con el mismo razonamiento sellado
en REPAIR1033.

En los cuatro límites, publicar la hora como si se hubiera pedido es fallo del límite.

Pruebas automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
