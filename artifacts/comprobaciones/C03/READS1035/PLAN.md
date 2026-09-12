# READS1035 — cuatro lecturas sin argumentos, de tres categorías, sin tocar el PC

Salen de una medición nueva: `scratchpad/c03-argumentless-reads.py` cruza el catálogo tipado —leído del
propio Core, que publica cada capacidad con su `risk` y su `argumentsSchema.required`— con los literales
que el reconocedor resuelve. Resultado: **28 operaciones de sólo lectura sin argumentos obligatorios**, y
**14 filas abiertas** cuya resolución completa cae dentro de ese conjunto.

De esas 14, cinco son de estado de hardware y están bloqueadas por las tres causas de
`SYSTEM1028/DIAGNOSIS.md`, una es H0675 que el dueño aparcó, y cuatro son de wifi que se aparcan aquí con
razón. Quedan cuatro, de tres categorías distintas, que nunca se han medido en esta máquina.

## Las cuatro de wifi se aparcan, y no por comodidad

`wifi.status` está descrita en el catálogo como «lee dos veces el estado WLAN actual y devuelve conexión
e identidad opaca del perfil **sin exponer SSID ni credenciales**», y `wifi.profile.list` enumera perfiles
«mediante identidades opacas». Es decir: el nombre de la red está deliberadamente fuera del catálogo por
privacidad.

- H0127 `a qué wifi estoy conectado` y H0433 `en que wifi estoy conectado?` piden el nombre.
- H0302 `qué redes wifi hay` pide un escaneo, que no tiene operación.
- H0647 `is the wifi on` sí es contestable, pero sin par pertinente propio en esta tanda.

Acreditar «estás conectado, pero no puedo decirte a qué red» como si respondiera a «a qué wifi estoy
conectado» sería rellenar. Se aparcan con esta razón escrita y se dice el número real de ejecutables: **4**.

## Panel: 12 casos, 24 líneas de wire

| Conducta | Literales | Variantes |
|---|---|---|
| `media_status` — qué suena ahora | H0224 `qué está sonando`, H0543 `qué canción está sonando` | dev-01 ES, dev-02 EN |
| `active_window` — qué ventana está al frente | H0104 `qué ventana está activa` | dev-03 ES, dev-04 EN |
| `notes_list` — qué notas hay guardadas | H0511 `qué notas tengo guardadas` | dev-05 ES, dev-06 EN |
| Límites | — | b-01 cita ajena, b-02 prohibición con consulta |

**Crédito máximo condicionado: 4.** Cada conducta lleva su par propio en los dos idiomas.

## Criterio, escrito antes de ejecutar

Contestar con la lectura observada de la operación que la petición nombra, en el idioma del pedido, y
**sólo con lo que la lectura trae**. Falla: inventar un título, un artista, una ventana o una nota que la
lectura no devolvió; presentar una lista vacía como si tuviera contenido, o al revés; ejecutar un segundo
efecto no pedido; reproducir la instrucción interna o usar vocabulario interno; y publicar una sola
palabra en mayúsculas, que ya está cerrado en fuente.

**Un almacén vacío es una lectura válida.** El perfil del conductor es nuevo, así que la lista de notas
puede estar vacía: decir con verdad que no hay notas guardadas cumple; inventar notas, no. Lo mismo con
la sesión multimedia: si Windows no expone ninguna, decirlo es la respuesta fiel.

Raíz adjudica contra el recibo de la operación leído fresco en la adjudicación, nunca contra un valor
recordado. En los dos límites, publicar la lectura como si se hubiera pedido es fallo del límite.

Pruebas automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
