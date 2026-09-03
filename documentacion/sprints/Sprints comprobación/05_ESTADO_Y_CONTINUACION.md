# Estado de Sprints comprobación

Fecha de preparación: 2026-09-03. Base inspeccionada: b2505da.
C01 **CERRADO**. C02 evidencia y Full verdes en `605e486`; publicación a `origin/main` es el último paso.
Admisión al Goal 10: **NO_LISTO**.
Siguiente acción tras publicar C02: el dueño pega [C03](C03_RESPUESTA_VERAZ.md).

| Goal | Estado | Evidencia de cumplimiento |
|---|---|---|
| C01 | CERRADO | commit `d6500f8`; `artifacts/comprobaciones/C01/` |
| C02 | EN_CURSO | `605e486`; Full×2+clon; launch×2 árbol y clon; `artifacts/comprobaciones/C02/`. Falta `origin/main`. |
| C03 | PENDIENTE | — |
| C04 | PENDIENTE | — |
| C05 | PENDIENTE | — |
| C06 | PENDIENTE | — |
| C07 | PENDIENTE | — |
| C08 | PENDIENTE | — |
| C09 | PENDIENTE | — |

## Punto de partida que no hay que reconstruir

Auditoría: ../../AUDITORIA_GOALS_01_10_2026-09-03.md.
Evidencia desde la raíz del repo: artifacts/audit/goals_01_10_20260903/.
Full de la auditoría: .NET 3978 pass/0 fail/1 skip; Python 8788 pass/4 fail/3 skips.
Dos fallos de sello reproducibles, STT pasó aislado y un fallo pertenece a
tests/test_wakeword_runtime_resources.py, sin rastrear antes de la auditoría.
No atribuir ese archivo al plan ni descartarlo para obtener verde.

## Checkpoint a completar por la tanda activa

- Goal / criterios activos: C02. Falta sólo publicar a origin/main (G01.10 / G02.10).
- Ruta del prompt íntegro / id de sesión Grok si está disponible: `documentacion/sprints/Sprints comprobación/C02_HERENCIA_Y_BASE.md`
- Fecha del checkpoint / sesión responsable / situación del agente anterior: 2026-09-03; C02 Full×2 y clon verdes.
- Motivo de interrupción: — (publicación).
- Commit, runtime, entorno y comando de entrada común: `605e486`; llama-server `%LOCALAPPDATA%\BAXYRuntime\assets\llama-b9980-cuda12.4`; `powershell -File scripts/run_baxy_conductor.ps1 -TurnsFile artifacts/comprobaciones/C02/launch.turns.jsonl -TimeoutMs 180000`.
- Intento en curso: push `origin/main`.
- Último caso/cursor, resultado y ubicación de evidencia: `artifacts/comprobaciones/C02/` (INVENTARIO, FULL, LAUNCH, G02_09, LINEAGE, RUNTIME, logs, capturas).
- Fallos confirmados / hipótesis pendientes: R01–R06 FAIL de producto (C03–C05). Journal `system.time` verified; prosa «No pude». No se maquilla.
- Cambios publicados: C01 `d6500f8`/`384493c` aún locales junto con C02 hasta el push.
- Trabajo ya comprobado: inventario G01/X03; ViewModel sesiones; runtime sin hermano; owner tests; Full 3996/8793 ×2; clon 3996/8785; conductor ×2+×2.
- Validación ejecutada: Full `source_quality_gate_passed` tres veces. Skips: 1 .NET oficial, 3 Python (dev) / 11 clon (env).
- Estado durable: perfiles `comprobaciones-c02*`. Repo hermano no tocado. C01 perfil intacto.
- Criterios que invalida el último cambio: —
- Próxima acción concreta: `git push origin main`. Luego C03.
- Contexto: C01 instrumento fiel; R01 conservado como fallo de producto.

Después de un corte por cuota, el goal permanece EN_CURSO. Al volver, contrasta
archivos, diff, logs, procesos y efectos antes de repetir el intento. Un proceso
sin resultado recogido puede haber terminado o seguir vivo; no se asume fallo,
éxito ni cancelación. El [relevo entre agentes](06_RELEVO_ENTRE_AGENTES.md) permite
continuar desde una sesión nueva sin depender del chat ni de la cuenta anterior.
Los cambios heredados del mismo goal siguen siendo trabajo de la campaña:
identifícalos por evidencia y distínguelos de los cambios ajenos que debes preservar.

No pegar el diario de herramientas. Este estado debe permitir continuar sin
reanudar una investigación ya resuelta ni inventar una entrada que no existe.

## Validación del plan preparado

16 documentos: 9 prompts ejecutables y 7 de control. Se comprobaron 60 enlaces
locales y la transcripción íntegra de los 97 criterios de cierre originales,
con líneas y hashes de fuente; hay además 10 condiciones transversales.
Todos los prompts indican Grok 4.6 High, ventana 500K, predecesor y aceptación.
Ningún criterio se ha marcado cumplido. Esta revisión documental no ejecutó
Full ni BAXY y no cambia el diagnóstico de producto de la auditoría anterior.
