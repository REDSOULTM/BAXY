# Estado de Sprints comprobación

Fecha de preparación: 2026-09-03. Base inspeccionada: b2505da.
C01 **CERRADO** en `d6500f8` (instrumento fiel; capturas relanzadas contra `384493c`). C02 **EN_CURSO**.
Admisión al Goal 10: **NO_LISTO**.
Siguiente acción: C02 — inventario G01, runtime sin BAXY hermano, descomposición restante, Full×2 + clon.

| Goal | Estado | Evidencia de cumplimiento |
|---|---|---|
| C01 | CERRADO | commit `d6500f8`; `artifacts/comprobaciones/C01/` (COMANDO, launch-1/2 y r01-r06, FULL, REPARACIONES_C02). Recaptura posterior `384493c`. |
| C02 | EN_CURSO | checkpoint abajo; evidencia `artifacts/comprobaciones/C02/` |
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

- Goal / criterios activos: C02 EN_CURSO. C01 permanece cerrado (`d6500f8` / recaptura `384493c`).
- Ruta del prompt íntegro / id de sesión Grok si está disponible: `documentacion/sprints/Sprints comprobación/C02_HERENCIA_Y_BASE.md`
- Fecha del checkpoint / sesión responsable / situación del agente anterior: 2026-09-03; C01 cerrado; C02 arranca en HEAD `384493c`.
- Motivo de interrupción: — (en curso).
- Commit, runtime, entorno y comando de entrada común: HEAD `384493cfe2aeb91d67e0406a9fc1c5a67e14127a`; `main` 2 commits ahead of `origin/main` (ambos C01, ajenos a C02); manifiesto vivo `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` con `llama_server` en `Programacion\BAXY\legacy\...` (accidental). Comando C01: `py main.py --conductor --turns-file artifacts/comprobaciones/C01/launch.turns.jsonl --capture <dir> --timeout-ms 180000`.
- Intento en curso: C02 inventario + runtime reproducible + descomposición restante + Full×2/clon.
- Último caso/cursor, resultado y ubicación de evidencia: baseline C01 en `artifacts/comprobaciones/C01/`; scratch `{SCRATCH}/c02-baseline.txt` pendiente de escribir.
- Fallos confirmados / hipótesis pendientes: R01–R06 FAIL de producto (C03–C05); runtime llama-server apunta al BAXY hermano; G01.09 reabre ~1050 líneas de máquina de estados del ViewModel (APLAZADOS Goal 01); MissionEngine ya tiene un constructor.
- Cambios publicados: ninguno de C02. Los 2 commits locales son de C01 y se preservan.
- Trabajo ya comprobado: nada de C02 aún. C01: FieldProduct 8/8; launch×2; R01–R06; Full 3986 pass / 1 skip .NET, 8792 pass / 3 skip Python (conteos heredados, no de esta corrida).
- Validación ejecutada: ninguna de C02. No reutilizar 3986/8792 ni 3865/8511 como resultado actual.
- Estado durable: perfil `%LOCALAPPDATA%\BAXY\comprobaciones-c01` intacto. No se toca el repo hermano.
- Criterios que invalida el último cambio: —
- Próxima acción concreta: capturar baseline HEAD/runtime; inventario G01 + 09.5; cortar llama-server del BAXY hermano; extraer responsabilidades restantes del ViewModel.
- Contexto: C01 instrumento fiel; no maquillar R01–R06; no borrar trabajo ajeno; no reescribir contratos históricos STT.

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
