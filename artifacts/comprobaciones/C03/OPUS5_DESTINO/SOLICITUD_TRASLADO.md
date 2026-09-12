# Solicitud de traslado — dos artefactos externos que no están en este PC

Este PC (**REDPC**, raíz `C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo`) ya está
actualizado a `ed305c38` de `Goal-c03` por fast-forward, sin perder nada, y compila en Release.
Faltan dos cosas que no viajan por Git y que **no puedo reconstruir sin inventar**.

## 1. El paquete privado del relevo — bloquea la cobertura

- **Nombre:** `C03_OPUS5_RELEVO_PRIVADO.zip`
- **SHA256 esperado:** `95bc3f239a2e5c013469d26143b55e7223b4c254300ea15ae59651259fd8c704`
- **Tamaño:** 2 025 743 bytes, 96 entradas
- **Ruta en el PC origen:** `C:/Users/usuario/AppData/Local/BAXY/C03-opus5-transfer-20260911/C03_OPUS5_RELEVO_PRIVADO.zip`
- **Dónde dejarlo aquí:** cualquier carpeta nueva; por ejemplo
  `C:/Users/usuario/AppData/Local/BAXY/C03-opus5-relevo-destino/`. No hace falta que sobrescriba nada.

**Búsqueda hecha antes de pedirlo:** búsqueda recursiva por nombre exacto del ZIP y de
`TRANSFER_MANIFEST.json` en `C:/Users`, `D:`, `E:`, `F:`, `G:` y `J:` — cero resultados.
`%LOCALAPPDATA%/BAXY` existe con 1489 directorios, pero ninguno `C03-*-private`,
`C03-*-proposal` ni `C03-opus5-transfer-20260911`; su evidencia local más reciente es del
6 de septiembre. Este PC nunca vio las tandas 1010–1027.

**Qué bloquea exactamente:**

| Necesito | Fichero dentro del ZIP | Para qué |
|---|---|---|
| Los 25 terminales de la tanda 1025 | `localappdata/BAXY/C03-knowledge1025-private/run/capture/events.jsonl` | Cerrar los 11 veredictos que quedan y fijar el texto verbatim de los 9 fallos ya juzgados |
| El registro de la encuesta | `localappdata/BAXY/C03-survey-requirements336-private/requirements.jsonl` (SHA `1a7ec3d381e4d972cb0bbdf9c55ed632216618e932614e31d2ea602a74a3eae6`) | Escribir `verification_status` y causas por `case_id`; y **sellar cualquier panel nuevo**, porque los literales exactos de los 742 casos sólo están ahí |
| El parche 1024 | `repair.patch` `b45ff88467f3ea281fb59520687a59bc7b96ad8e5f0f6f507807aa92ea4dd493` y `effect_intent.py` propuesto `868a2e327e81197093f62510b3d0091987b52b7222d552d72486d63d88929b1b` | Revisar el diff real antes de integrar, en vez de reimplementarlo a ciegas |
| Diarios y capturas 1021/1022/1025, diagnóstico 1023, propuesta 1024, `authority/` | resto del ZIP | Correlacionar auditorías y conservar la autoridad de la entrega |

`SURVEY_TAXONOMY846.json`, que sí está versionado, sólo lleva `case_id`, categoría y estado.
No contiene ningún literal. Por eso ninguna tanda nueva puede sellarse todavía: sellar sin el
literal exacto sería fabricar el material, y el goal lo prohíbe.

## 2. Los pesos del modelo decidido — bloquea la ejecución en GPU

- **Decisión 792:** Qwen3-4B-Instruct-2507 Q4_K_M, SHA256
  `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
- **No está en este PC.** Hay cuatro GGUF en `D:/BAXYRuntime/assets/models` y **ninguno** es ése:

  | Fichero | SHA256 |
  |---|---|
  | `granite-4.2-3b-Q4_K_M.gguf` | `e0406663…78e7d5` (es el que está registrado ahora) |
  | `Qwen3-4B-Q3_K_M.gguf` | `e78ff54a…2b2486` |
  | `Qwen3-4B-Q4_K_M.gguf` | `7485fe6f…34fdf5` |
  | `Qwen3-4B-Q5_K_M.gguf` | `37edbd37…79695` |

  El tercero **se llama igual** que el candidato de `assets.manifest.json`, así que registrarlo por
  nombre daría un modelo distinto con aspecto correcto. No lo hago: sería el reemplazo silencioso
  que el goal prohíbe.
- El backend sí coincide con la decisión: `llama-server.exe` de `llama-b9980-cuda12.4` tiene el
  SHA `38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e` esperado.
- `assets.manifest.json` dice, para este activo, que **BAXY no descarga modelos automáticamente**:
  se restaura el GGUF atestado o se declara su ruta en el override local. No hay mecanismo oficial
  del proyecto que lo adquiera por red, así que no invento uno.
- **Qué necesito:** el fichero de pesos con ese SHA, en `D:/BAXYRuntime/assets/models/` o en
  cualquier ruta que me digas. Al recibirlo lo registro con
  `scripts/register_mind_runtime.ps1` y verifico el hash antes de cualquier tanda.

El hardware de este PC es compatible sin campaña nueva: RTX 4060 Ti con 16 380 MiB de VRAM y
32 530 MiB de RAM, contra picos históricos de 3499 MiB de VRAM y 2467 MiB de RAM. Las guardas
heredadas (4000 MiB libres al arrancar, 768 MiB mínimo, parar a 3800 MiB de VRAM, 900 s por tanda,
120 000 ms por turno) se conservan tal cual.

## Mientras tanto

No estoy parado. Lo hecho sin estos dos artefactos está en
`OPUS5_DESTINO/DESTINO_INVENTARIO.json`, `KNOWLEDGE1025/ADJUDICATION_STATUS.json` y
`AGENDA1024/ROOT_REVIEW_DESTINO.md`. No he escrito ningún crédito nuevo, no he sellado ningún
panel y no he ejecutado ninguna tanda: hacerlo sin registro sería inventar cobertura.
