# Goal 9.5.0 — Fuentes del linaje, congeladas

Fecha de corte: **2026-08-30**. Máquina de este goal.

> **Veredicto: `FALLO_DE_AMBIENTE`.** Hay identidad reproducible de lo presente.
> Faltan fuentes declaradas y `Probando Gemma 4` no puede probarse completa.
> No se abre 09.5.1. Receta y prueba de readiness:
> [`artifacts/goal095/environment/09.5.0.md`](../../artifacts/goal095/environment/09.5.0.md).

Este documento no audita temas. Inventaría repositorios y carpetas, los identifica
y dice cuáles son copias. El inventario anterior del Goal 01 sigue en
[`00_MAPA.md`](00_MAPA.md); aquí solo se congela el universo que 09.5 va a
conciliar.

Raíz lógica de las fuentes declaradas: `Programacion\`, hermana de este
repositorio (`BAXY DEFINITIVO`). Las rutas personales no se repiten abajo.

## Método

- Lectura solamente. Ningún `git checkout`, restore, clean ni commit en fuentes
  históricas. `git --no-optional-locks` para no refrescar el índice.
- Dos recuentos de ficheros/bytes a ~90 s: A 02:41 y B 02:45. Cero procesos
  `robocopy`/`xcopy`/FastCopy. Explorer abierto sobre `Programacion`, sin ventana
  de transferencia.
- Git cuando existe; manifiesto SHA-256 ordenado por ruta relativa cuando no.
- Aliases buscados en el nivel superior de `Programacion` y un nivel en el
  escritorio, `ETC`, `D:\` y Documentos. No se recorrió el contenido en el chat.

## Universo declarado (cinco mínimas + Schema)

| Fuente | Presente | Identidad | Ficheros | Bytes | ¿Completa para 09.5.0? |
|---|---|---|---:|---:|---|
| `Programacion\BAXY` | sí | Git `203c34a9` rama `codex/baxy-cross-encoder-r209-handoff` | 116 641 | 25 488 709 507 | sí |
| `Programacion\Carter OS AI` | sí | Git `9cf62d23` rama `feat/gemma4-integration` | 136 316 | 14 935 292 111 | sí |
| `Programacion\FunctionGemma` | sí | manifiesto SHA-256 `ff150df2…619eaa` (sin `.git`) | 1 090 | 34 366 705 385 | sí (sentinelas del mapa 01 presentes; árbol estable) |
| `Programacion\Probando Gemma 4` | sí | manifiesto SHA-256 `72f9e5fc…13c7e71` (sin `.git`) | 36 249 | 3 690 624 981 | **no** |
| `Programacion\Probando schemas` | **no** | — | — | — | **no** |
| Agent Schema / Function Schema (cualquier alias en `Programacion`) | **no** | — | — | — | **no** |

`Probando Gemma 4` está estable en bytes, pero no es el árbol que el Goal 01
midió el 2026-08-16 (`models/` ~17 GiB y `data/` ~39 GiB). Hoy `models/` es un
directorio vacío (0 ficheros, no es junction) y `data/` pesa 247 259 115 bytes.
Eso no prueba una copia terminada: prueba una copia estable e incompleta.

FunctionGemma no trae Git. La procedencia visible es una copia de esta madrugada
(CreationTime 01:48–01:55) que conservó mtimes de junio–julio de 2026. Sentinelas
del mapa 01 presentes: `README_TOOLS.md`, `router\`, `tool_schemas_slim.json`,
`finetune_llm\`, `model\` (16 GGUF, 6,10 GiB).

Carter y BAXY conservan Git sucio. Esa suciedad es evidencia y no se limpió.
Carter no tiene remotos. BAXY apunta a `origin` `https://github.com/REDSOULTM/Baxy.git`
y está `ahead 18` de `origin/codex/baxy-cross-encoder-r209-handoff`. Último
commit en disco: 2026-08-15 «docs: add sprint 11 (validation and close) and the
deferred register».

## Candidatos descubiertos — relacionados, no independientes

| Candidato | Qué es | Relación |
|---|---|---|
| `Programacion\BAXY DEFINITIVO` | sitio de trabajo | no es fuente histórica |
| `Programacion\ETC (No relacionado con baxy)` | 33 hijos inmediatos de curso/herramientas | excluido por nombre y por contenido de primer nivel; 0 hits de linaje |
| `D:\BAXY` | árbol de julio (attestations, experimental_assets, `source`, stub `FunctionGemma`) | **relacionado** con la generación 5, no un sexto producto |
| `D:\BAXY\source` | Git del mismo remoto y la misma rama que `Programacion\BAXY`, HEAD distinto `c57c7aff` (2026-08-22) | snapshot distinto, no duplicado por hash/HEAD |
| `D:\BAXY\FunctionGemma` | 3 ficheros, 6 760 611 bytes, manifiesto `eddf65f7…24579a` | **no** es duplicado de `Programacion\FunctionGemma` (1 090 ficheros / `ff150df2…`) |
| `D:\BAXYRuntime` | runtime y datasets del producto actual | sidecar ya nombrado en el mapa 01; no es una generación |
| acceso directo `BAXY.lnk` en el escritorio | `Baxy.Setup.exe --launch` del instalado | producto instalado, no fuente |

`D:\BAXY` no se recorrió entero: 4 directorios bajo `source\.tmp\` devolvieron
acceso denegado (restos de pytest). No se usa como evidencia independiente.

No apareció JRVS en `Programacion`. No apareció ninguna carpeta cuyo nombre sea
alias de Carter, BAXY o Schema aparte de las ya tabuladas.

La generación «Schema Agent» citada en
[`../25_INTEGRACION_GENERACIONAL_CARTER_SCHEMA_BAXY.md`](../25_INTEGRACION_GENERACIONAL_CARTER_SCHEMA_BAXY.md)
se inspeccionó en 2026-07-22 **dentro del historial Git de BAXY**, no como
carpeta hermana. Eso no localiza la copia que el dueño nombra Agent/Function
Schema ni `Probando schemas`. 09.5.0 las declara ausentes.

## Estabilidad y no mutación

| Árbol | Snapshot A = B (ficheros y bytes) | Git HEAD/rama/status antes = después |
|---|---|---|
| `BAXY` | sí | sí (`status` SHA-256 `b0508200…0351f4`) |
| `Carter OS AI` | sí | sí (`status` SHA-256 `3adb0157…d5a3cf`) |
| `FunctionGemma` | sí | no aplica |
| `Probando Gemma 4` | sí | no aplica |
| `D:\BAXY` | sí (con los 4 errores ACL repetidos) | `source` no se usó como fuente mutada |

Los `.git\index` de BAXY y Carter tienen mtime 02:19–02:20, anterior a esta
sesión. El preflight no los reescribió.

## Artefactos

Todo bajo [`artifacts/goal095/`](../../artifacts/goal095/):

- `environment/sources_index.json` — índice máquina del veredicto
- `environment/09.5.0.md` — `FALLO_DE_AMBIENTE` y receta
- `environment/size_snapshot_a.json`, `size_snapshot_b.json`, `size_stability.json`
- `environment/git_identity_before.json`, `git_identity_after.json`, `git_before_after.json`
- `sources/FunctionGemma.sha256.jsonl` + `.summary.json`
- `sources/Probando_Gemma_4.sha256.jsonl` + `.summary.json`
- `sources/D_BAXY_FunctionGemma.sha256.jsonl` + `.summary.json`
- `scripts/hash_tree.py` — receta reproducible del manifiesto

## Qué queda cerrado y qué no

Cerrado: inventario de lo **presente**, relaciones de copias, identidad Git o
SHA-256, prueba de que esta sesión no mutó los Git históricos.

No cerrado: las cinco rutas mínimas más Schema no están todas presentes y
completas. 09.5.1 no arranca.

Siguiente prompt, **el mismo**: [`../sprints/09.5.0_FUENTES_Y_AMBIENTE.md`](../sprints/09.5.0_FUENTES_Y_AMBIENTE.md).
Después de un ambiente verde, el siguiente lote es
[`../sprints/09.5.1_MANIFIESTO_Y_COLAS.md`](../sprints/09.5.1_MANIFIESTO_Y_COLAS.md).
