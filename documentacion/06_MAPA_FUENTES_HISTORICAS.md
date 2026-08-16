# Mapa reproducible de fuentes históricas

## Cutoff de BAXY 1.0

- UTC: `2026-07-14T10:51:49.1612548Z`.
- Manifiesto: `artifacts/corpus_cutoff/source_manifest.json`.
- Estado SHA-256: `85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.
- Generador: `scripts/freeze_historical_sources.py`.

Dos ejecuciones consecutivas produjeron el mismo hash de estado. La hora de
generación se excluye intencionalmente del digest; rutas, tamaños, commits,
árboles, estados y hashes de archivos sí forman parte de él.

## Fuentes congeladas

| ID lógico | Tipo | Ancla |
|---|---|---|
| `baxy_cutoff` | Git | commit `02d999dd5141cea4a022833df3c109aeeaec6266` |
| `baxy_legacy_checkpoint` | Git | commit `ee06786be1dcf70988c6890e49beb2388657a198` |
| `probando_gemma4` | Git + overlay | HEAD `f97659ebe1f3c3bcf48e12a9366fa14be1a3a9e9`, 34 entradas |
| `probando_router_corpus_real_logs` | archivo fijo ignorado por Git | 253.276 bytes y SHA-256 |
| `probando_runtime_traces` | archivo fijo ignorado por Git | 14.849.218 bytes y SHA-256 |
| `probando_thesis_deliverables` | manifiesto ignorado por Git | 38 archivos, 13.278.740 bytes |
| `probando_documentation` | manifiesto de archivos | 594 archivos, 137.445.853 bytes |
| `carter_os_ai` | Git + overlay | HEAD `9cf62d236cdef08012897d3c8c680b8afef0d62e`, 56.353 entradas |
| `functiongemma` | manifiesto de archivos | 885 archivos, 1.785.215.157 bytes |
| `carter_os` | manifiesto de archivos | 1 archivo |
| `gemma4_local_history` | manifiesto de archivos | 170 archivos, 31.930.550 bytes |
| `current_codex_thread_prefix` | prefijo append-only | 371.756 bytes previos al cutoff |
| `codex_relevant_root_threads` | 70 prefijos append-only | 417.716.095 bytes previos al cutoff |
| `current_user_request_attachment` | archivo fijo | SHA-256 en el manifiesto |
| `agent_public_manifest` | archivo fijo | 322 sesiones y hashes por segmento |
| `agent_private_manifest` | digest privado | contenido no publicado |
| `agent_final_reports` | digest privado | contenido no publicado |

## Política de inclusión

- Un árbol Git limpio se fija por commit y tree.
- Un árbol Git con cambios se fija por commit/tree más overlay ordenado con
  estado, ruta relativa, tamaño y SHA-256 de todo archivo capaz de contener
  mensajes o evidencia.
- Las rutas ignoradas por Git que sí alimentan el corpus se fijan además como
  archivo o manifiesto explícito. El status se parsea con separadores NUL para
  preservar exactamente espacios, Unicode y renames.
- Las fuentes sin Git se fijan por ruta relativa, tamaño y SHA-256.
- Modelos, runtimes y binarios que no pueden aportar mensajes se resumen por
  conteo/tamaño y no entran al corpus textual.
- El archivo privado de agentes no se copia: el manifiesto público conserva
  `session_id`, `agent_path` y `segment_sha256`; los archivos privados solo
  aportan digest de integridad.
- El manifiesto no contiene rutas absolutas ni menciones a la carpeta privada.
- En sesiones Codex se usa `payload.id` como identidad concreta y
  `payload.parent_thread_id`/`payload.parent_id` para distinguir raíces de
  agentes. `payload.session_id` no basta: un descendiente puede heredar el ID
  de la raíz. Los 70 hilos incluidos son raíces propiedad del usuario; los
  descendientes de agentes se excluyen del corpus de mensajes del usuario.

## Reproducción

Desde la raíz del repositorio:

```powershell
python scripts\freeze_historical_sources.py
```

Si las fuentes del cutoff no cambiaron, el valor `sha256=` debe ser
`85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.

## Estado

El límite de contenido está congelado y el corpus fue extraído. Cada mensaje
conserva la ruta lógica, ubicación y hash del archivo de procedencia; véase
`documentacion/07_LEDGER_REQUISITOS_HISTORICOS.md`.

La revisión semántica derivada v2 no modifica este límite: mantiene el mismo
manifiesto, hash de estado y 122.744 ocurrencias. Al separar contratos por
alcance las consolida en 14.836 mensajes/IDs —12.036 de producto y 2.800 de
traza— y 2.083 misiones canónicas; los tres mensajes adicionales frente al
snapshot previo no representan fuentes nuevas. El compromiso funcional de BAXY
1.0 es español, inglés y spanglish, incluidos code-switch y errores de STT de
esos idiomas. Las lenguas inequívocamente ajenas permanecen en las fuentes y
mappings como trazabilidad `trace-only`, sin sumar cobertura de aceptación.

La etiqueta derivada `language` es heurística y no define por sí sola ese
alcance: mensajes objetivo breves también pueden aparecer como `other`. La
clasificación de aceptación se resuelve mediante revisión semántica auditada.
