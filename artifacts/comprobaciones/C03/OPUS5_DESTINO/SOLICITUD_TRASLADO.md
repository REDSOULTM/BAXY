# Solicitud de traslado — un artefacto externo que no está en esta máquina

> **Corrección del dueño.** REDPC es el BAXY **original**. El portátil sólo replicó el repositorio y
> su raíz en `D:` era porque su `C:` estaba lleno. Léase «origen» como la réplica y «destino» como
> esta máquina original. El tramo de C03 desde el 6 de septiembre se ejecutó en la réplica, y por eso
> su evidencia privada y la descarga del modelo decidido quedaron allí.

> **Actualización.** El **segundo** bloqueo, los pesos del modelo decidido, **ya está resuelto**: lo
> restauré yo desde la revisión fijada que el propio repositorio registra, con byte count y SHA-256
> verificados, y el runtime quedó registrado y cargando sano. Queda sólo el paquete privado.

Esta máquina (**REDPC**, raíz `C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo`) está
actualizada a `Goal-c03`, compila en Release y tiene el runtime registrado con el modelo decidido.
Falta una cosa que no viaja por Git y que **no puedo reconstruir sin inventar**.

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

## 2. Los pesos del modelo decidido — RESUELTO, no hace falta trasladarlos

Lo dejo escrito porque el camino sirve para la próxima máquina.

El modelo decidido nunca estuvo en `assets/models`: vivía en
`D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/`, y aquí esa carpeta no existía
porque la descarga del 11 de agosto ocurrió en la réplica. De los 93 ficheros `.gguf` de esta máquina
ninguno era el decidido. Cuidado con uno en particular: `D:/BAXYRuntime/assets/models/Qwen3-4B-Q4_K_M.gguf`
**se llama igual** que el primer candidato de `assets.manifest.json`, pero el propio repositorio lo
identifica como el modelo activo **anterior**, Qwen3 4B Instruct AWQ, SHA `7485fe6f…`. Registrarlo por
nombre habría sido el reemplazo silencioso que el goal prohíbe.

La procedencia atestada estaba versionada en
`artifacts/research/qwen3_4b_instruct_2507_candidate_preregistration_20260811.json`: repositorio de
cuantización `unsloth/Qwen3-4B-Instruct-2507-GGUF`, revisión fijada
`a06e946bb6b655725eafa393f4a9745d460374c9`, 2 497 281 120 bytes, SHA
`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`, licencia Apache-2.0, y el orden
congelado de verificación. Lo restauré siguiendo ese orden: descarga a `.partial`, byte count exacto,
SHA-256 exacto, y sólo entonces renombrado. No es una campaña de modelos nueva ni un cambio de
modelo; es el activo de la decisión 792 puesto donde el propio proyecto lo declara.

Después, `scripts/bootstrap.ps1` falló primero con `runtime_lock_invalid` → `installed_missing`: el
venv de la mente estaba desfasado respecto al `pylock` de los 192 commits nuevos. Bootstrap instaló
lo que faltaba (`pywebrtc-audio 0.2.0+baxy.1`, `sherpa-onnx 1.13.4+baxy.2`) y terminó con «BAXY
arranca: los activos obligatorios y el runtime registrado son validos». Para que el descriptor
resolviera el modelo correcto y no perdiera el wake, declaré ambos en el override oficial
`%LOCALAPPDATA%/BAXYRuntime/assets.local.json`; guardé copia del manifiesto anterior en
`mind-runtime-v1.json.pre-c03-relay.bak`, y `wake_on_start` volvió a `true` como estaba.

Carga verificada con las banderas exactas del producto, copiadas de `src/baxy_mind/llm.py:5520-5562`:
`n_slots = 3`, `n_ctx_slot = 4096`, `model loaded`, `/health` → `status: ok`. VRAM atribuible por
delta: 5528 MiB con el servidor, 2015 MiB sin él, **3513 MiB**, en línea con los 3497,56–3499,56 MiB
de las tandas 1021/1022/1025 y por debajo de la guarda de parada 3800 y del techo de producto 4096.
RAM del servidor 708 MiB. El servidor quedó detenido. Esto es comprobación de runtime, **no una
tanda**: sin panel sellado, sin turnos, sin adjudicación y sin crédito.

El techo de 3072 MiB que fijaba la prerregistración de agosto pertenecía a la aceptación de aquel
experimento, con su propio conjunto de banderas. Esto no es aquel experimento y no declaro cumplida
esa aceptación.

## Mientras tanto

No estoy parado. Lo hecho sin el paquete privado está en
`OPUS5_DESTINO/DESTINO_INVENTARIO.json`, `KNOWLEDGE1025/ADJUDICATION_STATUS.json` y
`AGENDA1024/ROOT_REVIEW_DESTINO.md`. No he escrito ningún crédito nuevo, no he sellado ningún
panel y no he ejecutado ninguna tanda: hacerlo sin registro sería inventar cobertura.
