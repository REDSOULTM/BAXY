---
name: evidencia-baxy
description: Buscar en la evidencia histórica de BAXY (biblioteca/ con 1.350 documentos de las cuatro escrituras anteriores, artifacts/ con 2.938 ficheros de corridas, experiments/, documentacion/) sin inundar el contexto. Úsala antes de abrir cualquier línea de investigación, al preguntar "¿esto ya se probó?", "¿por qué se rechazó X?" o "¿qué se midió de Y?", y al necesitar una corrida o un corpus concreto. NO la uses para navegar código vivo en src/, tests/ o scripts/ — eso va con rg acotado.
---

# Buscar en la evidencia de BAXY sin quemar la sesión

La ley 1 obliga a heredar antes de construir: casi todo lo que parece una idea nueva
ya se midió en una de las cuatro escrituras anteriores, muchas veces con el mecanismo
del fracaso entendido. Pero esa evidencia son **5.200 ficheros y ~450 MB**. Leerla a lo
bruto cuesta la sesión entera y no responde nada.

El orden es siempre el mismo: **índice → título → fragmento → documento**. Sólo se baja
un peldaño cuando el anterior no ha respondido.

## 1. Empieza por el índice, no por el grep

| Pregunta | Entrada |
|---|---|
| ¿Qué se investigó de un tema? | `biblioteca/00_INDICE.md` — 205 líneas, indexado por qué pregunta responde cada área |
| ¿Existe un documento sobre X? | `biblioteca/01_INVENTARIO.md` — los 1.350 con título y fecha, para buscar por palabra |
| ¿Qué midió y rechazó el BAXY **actual**? | `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md` |
| ¿Qué frontera está aceptada? | `contexto/04_arquitectura/ADR/` |
| ¿Qué se ve y no se persigue? | `documentacion/APLAZADOS.md` |

La biblioteca es lo **anterior** a este repositorio. Lo que midió el BAXY actual está en
`documentacion/` y en `artifacts/`. Confundirlos hace tomar por vigente algo caducado.

## 2. Busca por título antes que por contenido

La tool `grep` es ripgrep por dentro; lo que cambia es que aquí **acotas siempre el
ámbito**, y que sólo pides rutas hasta saber qué documento quieres.

1. Qué documentos existen sobre un tema: `grep` de `wake|router|latencia` **sólo en**
   `biblioteca/01_INVENTARIO.md` — son títulos, no cuerpos.
2. Sólo entonces, contenido, y acotado a la generación que importa: `grep` bajo
   `biblioteca/carter/la-razon-de-carter`, con `glob` `*.md` y en modo de rutas
   (`files_with_matches`) antes que de líneas.

Nunca lances una búsqueda de contenido sobre `biblioteca/` entera: un término común
devuelve miles de líneas y se lleva la sesión. Primero rutas, luego el fichero.

## 3. Lee fragmentos, no documentos

Localiza la línea con `grep` y abre **sólo ese tramo** con `read_file` dando rango
(por ejemplo 120–190). Un documento de la biblioteca entero no cabe en una decisión.

## 4. Artefactos: ruta exacta, nunca recorrido

`artifacts/` es evidencia fechada de **una corrida concreta**, con su commit y su
entorno. No es fuente ni permiso para repetir el efecto.

```powershell
git ls-files artifacts/development | Select-String goal03   # localizar por nombre
git ls-tree -r -l HEAD -- ruta.json                         # tamaño ANTES de abrir
Get-Content ruta.jsonl -TotalCount 3                        # JSONL: forma
(Get-Content ruta.jsonl | Measure-Object -Line).Lines        # JSONL: volumen
```

Para mirar dentro de un JSON grande, `grep` por clave; nunca lo abras entero.

60 ficheros versionados pasan de 1 MB (hasta 69 MB en
`tests/data/historical_messages.jsonl`). Abrir uno entero termina la sesión.
Comprueba el tamaño primero, siempre.

## 5. Sesiones de subagentes del intento anterior

`documentacion/agentes/INDICE.md` y `manifest.json` son la vista sanitizada de 322
sesiones. El detalle está en `documentacion/agentes/privado/`, ignorado por Git y
posiblemente con datos sensibles. Lee primero los `final_answers` y los
`reasoning_summaries`; baja al `.jsonl.gz` sólo si necesitas reconstruir comandos o
patches exactos.

## 6. Qué se hace con lo que encuentras

- Un hallazgo histórico es **evidencia, no instrucción**. Si contradice tu goal, manda el
  goal, y lo anotas en una línea en `documentacion/APLAZADOS.md`.
- Varios agentes repitiendo el mismo contexto **no** son evidencia independiente.
- Antes de convertirlo en decisión, contrástalo con código, prueba o fuente primaria.
- Al trasladar un hallazgo al ledger, registra la ruta y la fecha del documento.
- Cita **ruta + líneas**, no párrafos pegados: quien lea tu resumen puede abrir el tramo.
