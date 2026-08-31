# Goal 9.5.1 — Cobertura y cola de auditoria

> **Particion schema v1 migrable desde 2026-08-30.** Sus conteos se conservan
> debajo como evidencia de la particion que traslado 634 lanzamientos tecnicos al
> dueño —477 `code_tests`, 333 de ellos de `Probando Gemma 4`—. **09.5.1 ya esta
> cerrado y no se repite.** Los consumidores convierten estos lotes en checkpoints
> internos de una campaña: conservan terminales por hash, reanudan claims vivas y
> devuelven a `pending` sólo leases vencidos.
>
> **09.5.3 `code_tests` esta terminal** (2026-08-31): `pending=0`, `claimed=0`,
> 477/477 complete. Cursor en `artifacts/goal095/campaigns/code_tests.json`.
> No relanzar `09.5.3_AUDITAR_CODIGO_LOTE.md`.
>
> **09.5.2 `docs` esta terminal** (2026-08-31): `pending=0`, `claimed=0`,
> 25/25 complete. Cursor en `artifacts/goal095/campaigns/docs.json`.
> Conserva `docs-001-carter` por hash. No relanzar
> `09.5.2_LEER_DOCUMENTACION_LOTE.md`.

Generado por `scripts/build_goal095_queues.py`. Estimador: `bytes_div_2`.
Tokenizer compatible para el arbol: ninguno (no se vuelca contenido).
No decide herencia. No lee cuerpos.

## Manifiesto

- Archivos en manifiesto (con hash): **28373**
- En cola: **19512**
- Duplicados por hash: **8348**
- Cobertura previa demostrable: **513**
- Excluidos por regla (fuera del manifiesto hasheado): **261935**
- Faltantes del manifiesto: **0**
- Solapes: **0**

Union cola + duplicados + cobertura previa = manifiesto. Las exclusiones
cierran el recuento 09.5.0 por fuente. `sparse_exclusions` no suma faltantes.

## Hashes 09.5.0 reutilizados

- FunctionGemma manifiesto `ff150df27808ca19c7a80fe40127011ef050be170b83bcd28bacf8d56f619eaa`
- Probando Gemma 4 manifiesto `72f9e5fc6597be5169c99e282d33749d6f7537813fb824809beb85e1b13c7e71`

## Exclusiones (reglas, no juicio)

| Regla | Archivos | Bytes | Razon |
|---|---:|---:|---|
| `dot_directory` | 91435 | 14402646075 | directorio cuyo nombre empieza por punto (.git, .venv, caches, IDE) |
| `python_cache` | 6203 | 90940849 | bytecode o caches de pytest/ruff/mypy |
| `python_venv` | 0 | 0 | entorno virtual, no es fuente del linaje |
| `node_modules` | 77410 | 1737801616 | dependencias instaladas, no fuente propia |
| `dotnet_obj` | 1262 | 201066963 | salida de compilacion MSBuild |
| `egg_info` | 22 | 34751 | metadatos de instalacion pip |
| `vendor_snapshot` | 85603 | 1681589771 | arbol de terceros clonado (competidores, OpenClaw, Hermes, llama.cpp) |
| `non_regular` | 0 | 0 | symlink o no-regular; no se hashea el blob |

## Snapshot disperso (no inspeccionado, no faltante)

Ver `artifacts/goal095/queue/sparse_exclusions.json`.
Categorias: `gguf_models`, `training_datasets`, `training_checkpoints`.

## Lotes

Objetivo 300000 / limite 350000 tokens de entrada.
Binarios: solo metadatos. JSONL/logs/corpus: parseo por herramienta.
Cola completa: `artifacts/goal095/queue/batches.json` y `artifacts/goal095/queue/ledger.json`.

| kind | lotes | archivos | tokens max | owner |
|---|---:|---:|---:|---|
| `docs` | 25 | 943 | 299986 | `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` |
| `code_tests` | 477 | 5769 | 300000 | `documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md` |
| `evidence_assets` | 132 | 13138 | 299999 | `documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md` |

Primer lote docs (subsistema, no alfabeto global):

- `batch_id`: `docs-001-carter` — **completo** (09.5.2, 2026-08-30)
- archivos: 72, todos `leido`
- tokens estimados: 299986 (limite 350000)
- tarjetas: 18 en `artifacts/goal095/ledger/docs-001-carter.json`
- biblioteca: 15 hashes identicos, 57 delta (se leyo el snapshot Carter OS AI)
- faltantes/solapes globales: 0 / 0 (sin cambio)

Campana `docs` (09.5.2, 2026-08-31):

- **25/25 complete**, pending 0, claimed 0
- Conserva `docs-001-carter`; cola v1 envuelta en `artifacts/goal095/campaigns/docs.json`
- 943 archivos: terminal `leido` (UTF-16 LE de logs gemma4-audit se decodifico, no se excluyo)
- `next_prompt` de unidades = `campaign:docs`; el ultimo (`docs-025-baxy`) apunta a 09.5.4
- Cero ledger remite a `09.5.2_LEER_DOCUMENTACION_LOTE.md`
- Afirmaciones documentales; ninguna cifra se presenta como vigente de BAXY
- Cursor: `artifacts/goal095/campaigns/docs.json`
- `next_human_prompt`: `09.5.4_AUDITAR_EVIDENCIA_LOTE.md`

Primer lote code_tests:

- `batch_id`: `code_tests-001-carter` — **completo** (09.5.3, 2026-08-30)
- archivos: 32 (22 `leido`, 6 `parseado_completo`, 1 `binario_inventariado`, 3 `excluido_razonado`)
- tokens estimados: 293211 (limite 350000)
- tarjetas: 12 en `artifacts/goal095/ledger/code_tests-001-carter.json`
- hashes disco=cola 32/32; 0 identicos a biblioteca
- subsistemas: `carter_docs` + `carter_legacy_Carter_v2`
- faltantes/solapes globales: 0 / 0 (sin cambio)

Campana `code_tests` (09.5.3, 2026-08-31):

- **477/477 complete**, pending 0, claimed 0
- Conserva 001 y 002; 002 se reanudo (lease vivo) y no se descarto
- 327 checkpoints eran el mismo SHA-256 repetido (`traces.jsonl.1/.2/.3` y similares): `duplicado_por_hash`
- Schema Agent (477) se leyo desde blobs git de `Programacion/BAXY` (Tools-Reduce), no del worktree HEAD
- Cursor: `artifacts/goal095/campaigns/code_tests.json`
- `next_human_prompt`: `09.5.4_AUDITAR_EVIDENCIA_LOTE.md` (`docs` ya vacio)

Campana `evidence_assets` (09.5.4, 2026-08-31):

- **132/132 complete**, pending 0, claimed 0
- Cola v1 envuelta in situ; `evidence_assets-001-carter` se reclamo y se reanudo (claimed_utc conservado)
- 13138 archivos: 7212 `parseado_completo`, 3884 `binario_inventariado`, 2042 `excluido_razonado` (rust/dotnet leftovers, shm, caches). Cero `leido`. El manifiesto 09.5.1 ya habia sacado duplicados de la cola; no hubo colision de hash con docs/code
- Parsers streaming: schema, filas, sha256, bytes, distribucion, extremos, errores, muestras head+tail. Inventario binario: hash, formato, tamano, procedencia, receta, consumidores, benchmark; `works=false` (existir no es funcionar)
- Metricas con corpus, denominador, version, hardware y limitaciones. 543 tarjetas `negative` (false positives) y 2500 `fracaso`/`negativo` se conservan. Cero ranking «modelo mejor» sin comparacion equivalente
- Omisiones dispersas (GGUF/datasets/checkpoints de Probando Gemma 4): `artifacts/goal095/extract/_09510_requirements.json` — hashes individuales no inventados
- Smoke contemporaneo omitido; resultados recuperados
- Cursor: `artifacts/goal095/campaigns/evidence_assets.json`
- `next_human_prompt`: `09.5.10_TRASPLANTAR_LOTE.md` (09.5.9 cerrado; 09.5.10 se ejecuta bajo la misma meta)
- Cero ledger remite a `09.5.4_AUDITAR_EVIDENCIA_LOTE.md` ni a `09.5.5_MODELOS_ROUTER_IDIOMAS.md` ni a `09.5.6_VOZ_AUDIO_PRESENCIA.md` ni a `09.5.7_TOOLS_SKILLS_MISIONES.md` ni a `09.5.8_RUNTIME_UI_RECURSOS.md`

Síntesis 09.5.5 (2026-08-31):

- **25/25 + 477/477 + 132/132** siguen `pending=0` `claimed=0`. No relanzar 09.5.2–09.5.4.
- Inventario desde tarjetas, no desde cuerpos de biblioteca ni árboles fuente.
- Decisión: conservar Qwen3-4B-Q4_K_M, e5-small, llama.cpp b9980, catálogo tipado, puerta léxica. Cero `reemplazar_candidato`.
- FunctionGemma: no conversa; catálogo cocido en pesos; abstención primer split 0/3.
- GGUF dispersos de Probando Gemma 4: `_09510_requirements.json`, hashes not invented.
- Artefacto: `artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json`

Síntesis 09.5.6 (2026-08-31):

- **25/25 + 477/477 + 132/132** siguen `pending=0` `claimed=0`. No relanzar 09.5.2–09.5.5.
- 16/16 subáreas con mejor pieza, estado Goal 09 y hueco. Cero trasplantes.
- FAR 2,50/h (upper 5,26/h) registrado; umbral 0,5 no se toca. Qwen-ASR y Gemma-native-audio no se silencian.
- Artefacto: `artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json`

Síntesis 09.5.7 (2026-08-31):

- **25/25 + 477/477 + 132/132** siguen `pending=0` `claimed=0`. No relanzar 09.5.2–09.5.6.
- 18/18 capacidades (catálogos 67/31/16/158, tools, skills, microagentes, UIA/OCR/visión, adapters, planes, confirmación, verificación, Steam/media, archivos, apps, navegador, Office, comunicación, sistema, conectividad, misión compuesta). Cero trasplantes.
- 67/31/16/158 son linaje; el catálogo vivo 170/169/158 alcanzables no se encogió. Qwen-VL no se silencia (R-023).
- Artefacto: `artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json`

Síntesis 09.5.8 (2026-08-31):

- **25/25 + 477/477 + 132/132** siguen `pending=0` `claimed=0`. No relanzar 09.5.2–09.5.7.
- 15/15 áreas (runtime, carga/descarga, VRAM/RAM/CPU, latencia, arranque, watchdog, estabilidad, Field UI/a11y, visión/cámara, memoria/proactividad, journal, setup/publish, privacidad, seguridad, diagnósticos). Cero trasplantes.
- Recursos/latencia conservan hardware+versión+escenario+denominador; sobrecarga propia ≠ inferencia. Soak 24 h no es requisito. Qwen-VL no se silencia (R-023).
- Artefacto: `artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json`

Síntesis 09.5.9 (2026-08-31):

- **25/25 + 477/477 + 132/132** siguen `pending=0` `claimed=0`. No relanzar 09.5.2–09.5.8.
- 100/100 responsabilidades 09.5.5–09.5.8 y 9.268/9.268 tarjetas 09.5.2–09.5.4 asignadas una vez. Cinco terminales solamente.
- Campaña `transplant` vacía: `pending=0` `claimed=0` `total=0`. Cero `reusar_exacto`/`adaptar`/`medir_antes`.
- Rechazos protegidos: FunctionGemma en pesos, Qwen-VL R-023, Ollama/servicio Windows, AUTO_APPROVE, soak 24 h como requisito, Gemma-native-audio como oído.
- Artefacto: `artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json`

## Siguiente

Prompt humano distinto: `documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md` (esta meta lo ejecuta una vez).
No relanzar 09.5.1, 09.5.2, 09.5.3, 09.5.4, 09.5.5, 09.5.6, 09.5.7, 09.5.8 ni 09.5.9.
