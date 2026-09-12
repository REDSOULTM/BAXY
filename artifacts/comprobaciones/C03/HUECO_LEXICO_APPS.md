# El hueco léxico de «Abrir aplicaciones»: la cabeza verbal no es la puerta

Medido con `scratchpad/c03-apps-lexical-probe.py`, función pura, sin GPU. De los 33 abiertos que quedan
en la categoría, 19 no llegan al reconocedor determinista, y el camino determinista cumple tres veces
más que el del modelo. Este documento dice qué se probó, qué se descartó y por qué no se adoptó nada.

## Lo que ya se tolera hoy

```
'abrime la calculadora'            -> ['app.open']
'abrime la calculadora por favor'  -> ['app.open']
'abre steam por favor'             -> ['app.open']
'abre steam please'                -> ['app.open']
'abre a calculadora'               -> ['app.open']   (H0497: llega, y falló por otra causa)
```

La cortesía al final ya está resuelta y el determinante mal escrito no estorba.

## Lo que no llega, agrupado por lo que le falta

| Literal | Qué le falta |
|---|---|
| H0730 `me abrís la calculadora` | clítico delante del verbo, y la forma `abrís` |
| H0348 `abrime la calculadora dale` | cola coloquial `dale` |
| H0487 `Abre steam pls` | cola coloquial `pls` |
| H0165 `avrí la calculadora` | errata en el verbo (`avrí` por `abrí`) |
| H0521 `abres team`, H0386 `Abre stea,`, H0522 `Sí, abre Ste.` | errata en el nombre del destino |
| H0227 `abre Steel.`, H0398 `Sí. Abre Steel.` | destino que no existe: la respuesta veraz es que no está |
| H0147 `open the file explorer`, H0151 `abrí el explorador de archivos` | Explorer no se resuelve por este camino |
| H0289 `abrime el photoshop`, H0558 `abri photoshop` | Photoshop no está instalado aquí |
| H0460 alemán, H0491 italiano, H0668 francés | idiomas fuera de español e inglés |
| H0724 `son las tres abrí la calculadora` | compuesto con reloj: causa B de SYSTEM1028 |
| H0608 `lanzá Mortal Kombat` | juego no instalado |

## Lo que se probó y se retiró sin adoptar

Se añadieron al reconocedor las formas `abris`, `abres`, `abriras`, `abririas`, el clítico opcional
`(?:me|nos)\s+` delante del verbo en las dos gramáticas de apertura, y `dale`/`pls` a las colas de
cortesía. Resultado medido sobre los 742 literales: **delta 0, 0 literales cambiados**.

Las formas nuevas sí funcionan aisladas —`abrís la calculadora` y `abres la calculadora` pasaron a
resolver— pero **`me abres la calculadora` y `abrime la calculadora dale` siguieron sin resolver**, así
que la puerta que los rechaza no es la cabeza verbal ni la cola: hay un guardia anterior, antes de que
esas gramáticas lleguen a mirar. Un cambio con cero efecto medido en la encuesta no se adopta: se
revirtió `effect_intent.py` a su base exacta y el diff contra HEAD es cero.

## Dónde seguir, con el instrumento listo

La siguiente sonda debe localizar ese guardia anterior con `sys.settrace` acotado al módulo sobre
`me abres la calculadora`, que es como se localizó la causa del reloj en
`CUELLO_DE_BOTELLA_RECONOCEDOR.md`. Candidatos por orden: `_strip_request_envelope`, el chequeo de
cabeza `_request_head`/`_head_is`, y `_open_application_spans` antes de su `valid`.

Y una nota de rendimiento honesta: de los 19, sólo cuatro son reparables por léxico limpio —H0730,
H0348, H0487 y, con tolerancia a erratas, H0165—. Los demás son destinos ausentes, idiomas fuera de
alcance o causas ya diagnosticadas en otro sitio. No hay diez requisitos abiertos detrás de este hueco,
así que no justifica infraestructura nueva: justifica un patrón, medido con la sonda antes de gastar
una tanda.
