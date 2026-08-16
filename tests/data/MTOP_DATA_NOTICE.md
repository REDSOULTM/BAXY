# MTOP en BAXY: procedencia, licencia y frontera de evaluación

## Fuente y atribución

La ampliación `baxy-mtop-v1` deriva de la distribución oficial de **MTOP:
A Comprehensive Multilingual Task-Oriented Semantic Parsing Benchmark**,
publicada por Haoran Li et al. en EACL 2021:

- paper primario: <https://aclanthology.org/2021.eacl-main.257/>
- archivo oficial: <https://dl.fbaipublicfiles.com/mtop/mtop.zip>
- SHA-256 del ZIP oficial:
  `0c086500aed2ed48d3df383c91664b152e4a46e2adef6a635fa16d508ebaec0b`

El README incluido por la fuente describe el formato TSV de ocho columnas, 11
dominios, 117 intents, 78 slots y seis idiomas. También registra una segunda
revisión de datos que añadió el ID multilingüe. Por eso BAXY distingue entre
la versión **v1 de su adaptador** y la revisión de formato que declara el
README oficial; no renombra esa revisión como si fuera un dataset nuevo.

MTOP se distribuye bajo
[Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/)
(`CC BY-SA 4.0`). El corpus derivado de BAXY, cuando se redistribuya, debe
mantener esa licencia, atribución y aviso de modificaciones. BAXY modifica el
material al limitarlo a inglés/español, normalizar espacios y Unicode NFC,
eliminar columnas no necesarias, conservar solo nombres de intent/slots,
proyectar estructuras contra contratos existentes y añadir negativos
`ood_no_effect`. No se afirma patrocinio ni aprobación de los autores.

## Particiones y hashes de desarrollo

Solo `train` y `eval` de inglés y español se leen durante desarrollo:

| Archivo oficial | Filas | Bytes | SHA-256 |
|---|---:|---:|---|
| `en/train.txt` | 15.667 | 7.115.388 | `1c1e137ca0f4d72279b3b4755f8202793b1d24a840e55b3c81e4db289656d692` |
| `en/eval.txt` | 2.235 | 1.019.262 | `950d49197df0ae660c27cf7a33a462b8c41c267ac579db788bd7812daf258a31` |
| `es/train.txt` | 10.934 | 5.544.383 | `de4743f1a1b1998a700d8a325c6bec281117b1477ab6faf34efd21b64a43d738` |
| `es/eval.txt` | 1.527 | 783.911 | `db95e0dacd1d9f5177fe7c4e87d445ec0f9c1eb2143ad73bec2d36f73ab703ee` |

Las cuatro fuentes aportan 30.363 filas. Tras descontaminar particiones, la
salida local reproducible
`%LOCALAPPDATA%\BAXYRuntime\datasets\mtop-v1\derived\mtop_development.v1.jsonl`
tiene 29.976 filas, 24.680.426 bytes y SHA-256
`ed1871262bdb78a53e219ac6ebd7b995879c60eba29ec5d9203217480a142802`.
No se versiona el texto derivado; el manifiesto compacto y portable está en
`artifacts/product/mtop_development_manifest.json`.

La distribución de proyecciones es:

- 12.758 `candidate`: evidencia para recuperar un conjunto pequeño de
  operaciones;
- 471 `candidate_missing_information`: capacidades soportadas a las que les
  falta un argumento requerido; son evidencia para `clarify`, nunca para
  ejecutar;
- 16.739 `ood_no_effect`: 10.432 intents sin capacidad correspondiente y
  6.307 estructuras cuyos slots o composición exceden el contrato;
- 8 `conversation_no_effect`: ayuda conversacional sobre recordatorios, sin
  tool.

La descontaminación conserva `eval` como holdout cuando una identidad textual
exacta también aparece en `train`: retiró 81 filas train de 63 grupos. También
eliminó 293 duplicados exactos dentro de una partición y 13 filas de cuatro
grupos con etiquetas de comportamiento incompatibles. Ningún ID multilingüe
cruza particiones y la salida final tiene cero solapamiento textual normalizado
entre train y validation.

MTOP no ofrece etiquetas directas de política conversacional. El adaptador
solo deriva `clarify` cuando una variante única y ya soportada carece de campos
requeridos, y `plan` cuando esa variante necesita una secuencia de operaciones
existente en BAXY. La derivación queda marcada como
`baxy_contract_projection`, no como verdad aportada por MTOP.

## Cero expansión de capacidades

El mapa revisado es
`src/baxy_mind/data/mtop_turn_evidence_map.v1.json`. Cada operación candidata
se valida contra las 169 operaciones con `ToolExposure.Public` del catálogo
real de BAXY. Un intent no listado, una composición anidada o un slot que el
contrato no cubre cae en `ood_no_effect`.

Una proyección `candidate` es solo evidencia semántica. El registro fija
`execution_authority: false`; la selección del LLM, el grounding del contrato,
la política de confirmación, la ejecución y la verificación independiente
siguen siendo obligatorios. Ni el intent de MTOP ni una similitud textual
pueden autorizar efectos.

## Sello y no-fuga de `test`

`tests/data/mtop_test_seal.v1.json` se generó directamente sobre bytes de los
miembros `mtop/en/test.txt` y `mtop/es/test.txt`. Durante el sellado:

- no se decodificó ninguna línea;
- no se inspeccionó ninguna columna, utterance, intent, slot ni label;
- cada identidad opaca deriva de locale, ordinal y SHA-256 de la línea cruda;
- el sello conserva únicamente tamaños, CRC, recuentos y hashes.

El sello cubre 4.386 líneas inglesas y 2.998 españolas, 7.384 en total. Ese
recuento no constituye una evaluación ni revela sus etiquetas.

No existe un comando `materialize-test` para el conjunto oficial. El gate final
debe llamar a `evaluate_test_once` desde un evaluador cuyo código y artefactos
estén congelados en un prerregistro `baxy.mtop-test-preregistration.v1`. Antes
de abrir el ZIP, esa frontera:

- vuelve a verificar ZIP, mapa, catálogo, sello y cada artefacto congelado;
- crea con `CREATE_NEW` un claim derivado del sello y de una huella local
  anonimizada, independiente del `run_id` y de la ruta de salida;
- conserva las filas decodificadas únicamente en memoria;
- admite solo un reporte agregado sin textos, IDs, ejemplos ni resultados por
  fila, y aplica los pisos/techos prerregistrados;
- deja el claim y un recibo `completed` o `failed` incluso si el evaluador
  falla, por lo que un crash tampoco habilita un segundo intento.

Las rutas alternativas solo existen para fixtures sintéticos. Un ledger local
evita repeticiones accidentales o concurrentes en esta máquina; impedir que
alguien borre deliberadamente ese ledger o copie el dataset a otra máquina
requeriría un servicio remoto append-only. A fecha de este aviso, el test
oficial **no fue materializado, decodificado ni ejecutado**.

## Reproducción

```powershell
$python = 'experiments\mind_router_spike\.venv\Scripts\python.exe'
$dataset = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\datasets\mtop-v1'
$derived = Join-Path $dataset 'derived'
New-Item -ItemType Directory -Path $derived -Force | Out-Null

& $python scripts\build_mtop_turn_evidence.py seal-test `
  --archive "$env:TEMP\baxy-mtop-license-probe.zip" `
  --output tests\data\mtop_test_seal.v1.json

& $python scripts\build_mtop_turn_evidence.py build-development `
  --dataset-root $dataset `
  --output (Join-Path $derived 'mtop_development.v1.jsonl') `
  --manifest artifacts\product\mtop_development_manifest.json `
  --test-seal tests\data\mtop_test_seal.v1.json
```

El segundo comando abre exclusivamente los cuatro archivos de desarrollo.
`--help` expone solo `seal-test` y `build-development`; el test oficial no
puede persistirse como JSONL desde esta herramienta.
