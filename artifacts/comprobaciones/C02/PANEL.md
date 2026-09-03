# C02 — paquete para verificación (no abrir los `.log` binarios)

Commit publicado de cierre: `7d2842107da26a50648a60b3f6ec73ee80d06020` en `origin/main`.
Fuente medible idéntica a Full `605e486` (`src tests scripts main.py assets.manifest.json`).
C03 no está empezado.

Lee estos UTF-8, no `full-*.log` (mezclan UTF-8 y UTF-16LE):

| Qué | Dónde |
|---|---|
| Full ×2 + clon, skips, 0 fail | [FULL.md](FULL.md), [full-decoded.txt](full-decoded.txt) |
| Runtime declarado + hashes | [RUNTIME.md](RUNTIME.md) |
| Conductor + lectura real + R01 | [LAUNCH.md](LAUNCH.md), `launch-1/events.jsonl` |
| Inventario G01 + 4 herencias + 09.5 | [INVENTARIO.md](INVENTARIO.md) |
| Linaje STT / FieldUi / SessionOptions | [LINEAGE.md](LINEAGE.md) |
| Prueba por prueba | [G02_09.md](G02_09.md) |
| Relevo independiente | [RELEVO.md](RELEVO.md) |
| Matriz G01/G02/X03 | `documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md` |
| Estado | `documentacion/sprints/Sprints comprobación/05_ESTADO_Y_CONTINUACION.md` |

Observaciones del plan ya comprobadas:

1. Raíz `BAXY Definitivo`, rama `main`, status vacío, `rev-list origin/main..main` = 0.
2. Filas G01.01–G01.10, G02.01–G02.10, X03 CUMPLIDO con evidencia actual o procedencia.
3. Dueños: pytest asset_resolution 8 pass; Integration Discovery/Plan/Memory/FieldUi 26 pass; Kernel MissionEngine 17 pass.
4. Manifiesto `baxy-mind-runtime-v1`; SHA python/gguf/llama/stt/wake coinciden; cero `\Programacion\BAXY\` en runtime.
5. Full gate_passed ×3; .NET 3996/0 fail/1 skip; Python 8793/3 y clon 8785/11 env.
6. Conductor arranca; `system.time` verified; prosa R01 «No pude» es FAIL de producto.
7. Publicado. C03 no.
