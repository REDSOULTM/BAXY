# H2 del notebook: las tareas que `final` falló en las dos semillas del holdout v5

Fase 3 («al 100 %»), reparto del líder del 2026-10-24 19:44. Ocho casos: V5E021, V5E023 y V5E029 (uso del PC) y
V5E032, V5E034, V5E040, V5E043 y V5E044 (archivos). Fuentes: `ho5-final-s0-e2e-e2e` (PC, copiada al NB como
`pc-ho5-final-s0-e2e-e2e`) y `ho5-final-s1-e2e-e2e` (NB): `results.jsonl`, `events.jsonl`, `mente/turns.jsonl`,
`app-trace.jsonl`, y el código de `nb-cien` (= int10f 19be8b42a). Tres subagentes de sólo lectura, un caso por fila;
cada línea de código citada se abrió.

## Resumen

| Caso | Qué pide | Causa | De quién | Arreglo | Rama |
|---|---|---|---|---|---|
| V5E021 | «a lo que tiene la calculadora súmale 53» (47 → 100) | `evaluate` borra antes y exige empezar por dígito; el modelo hizo 53+53 (s0) o Enter (s1). Además el Enter pidió el sí porque `KindOf` miraba la Calculadora del caso anterior, ya cerrada | modelo + proveedor | `evaluate` que sigue desde la pantalla si empieza por operador, con `startedFrom` en el recibo; ignorar una app abierta cuyo proceso murió | `nb-w10-calc` |
| V5E023 | «en el Notepad abierto, agrega al final …» | Qwen elige bien (`input.visible.controls`) pero con 0,345/0,363 < 0,4: la duda cuenta como rival el «=» suelto del corte `<function=` y pregunta por texto. Falta `ctrl_end` | mente + catálogo | renormalizar sin los rivales que no eligen nombre (PC, `w10-duda`); `ctrl_end`/`ctrl_home` | PC `w10-duda`; `nb-w10-clic` |
| V5E029 | «modo científico y 2 elevado a 10» | `evaluate` rechaza `^` y sólo va en Estándar; un clic en un rótulo que sólo movió el foco salió `surfaceChanged` | proveedor + modelo | `^` y paréntesis en Científico, error que dice qué rechazó; clic `focusOnly` | `nb-w10-calc`, `nb-w10-clic` |
| V5E032 | mover un .xlsx a una subcarpeta de BAXY-bench | no hay mover por nombre fuera de la carpeta de trabajo; `said_folder` lo ataja bien pero sin salida | catálogo + proveedor | mover/copiar por nombre con `folder`, `subdirectory`, `copy` | `nb-w10-mover` |
| V5E034 | «¿cuántos PDF hay en BAXY-bench\facturas?» | `filesystem.explorer.count` sin `subdirectory`; la rama de lecturas de `said_folder` no ofrece salida | catálogo + App | `subdirectory` en la cuenta (la App la encamina sola) | `nb-w10-cuenta` |
| V5E040 | copiar contrato.txt como contrato-respaldo.txt en BAXY-bench | no hay copiar por nombre (sólo `filesystem.copy` por id en la carpeta de trabajo); s1 inventó un id | catálogo + proveedor | el de V5E032 con `copy` | `nb-w10-mover` |
| V5E043 | crear «Viaje Chiloé 2027» en Documentos y un archivo dentro | NB: «documentos» contaba dos veces y mandaba a `Documentos\Documentos`; la carpeta creada en el turno no entraba en las nombradas; el modelo pasa el nombre dictado a `viaje_chiloe_2027` | App + modelo | el nombre de una carpeta conocida es ella; las carpetas nombradas se leen en cada llamada | `nb-w10-cuenta` |
| V5E044 | gemelo dictado de V5E034 | el de V5E034; en el PC además `Desktop\BAXY-bench` daba dos lugares | catálogo + App + entorno | el de V5E034; de los comienzos de una ruta relativa vale el que la tiene | `nb-w10-cuenta` |

Añadido por el PC al reparto: V5E045 y V5E047 («Documentos\Turnos Farmacia» se leía como `Documents\Turnos`), también
en `nb-w10-cuenta`.

## Lo que no es

- **La confusión entre la carpeta de trabajo y las de la persona** (la causa dominante de la fase 1) ya no aparece: la
  App la ataja en las seis llamadas de V5E032/034/040. Lo que falta es una llamada que sí llegue.
- **Los oráculos** están bien en los ocho. `expected_ops` de V5E032/040 nombra operaciones de la carpeta de trabajo,
  pero ningún script lo lee.

## Entorno

- PC, s0: todos los `app.open` dicen `foregroundHeldBy: «Monitor Configuration • DisplayFusion Pro on Steam»`, una
  ventana oculta al frente. No decidió estos casos; el PC la cierra antes de cada banco.
- PC: existe `%USERPROFILE%\Desktop\BAXY-bench` además de `%USERPROFILE%\BAXY-bench`. Queda como pregunta al dueño.

## Lo que sólo arregla el ajuste fino

- Convertir un nombre dictado en minúsculas en identificador (`Viaje Chiloé 2027` → `viaje_chiloe_2027`, confianza
  0,99 en las dos semillas; con texto escrito no lo hace).
- Elegir Enter o `evaluate("53+53")` sabiendo que la pantalla muestra 47 (V5E021); pulsar un rótulo en vez del botón de
  navegación (V5E029).

## Estado de los arreglos

| Rama | Commit | Pruebas que fallaban antes | Suites | Medida |
|---|---|---|---|---|
| `nb-w10-cuenta` | fd2ed124e | 5 de `SaidFoldersTests`, 1 de `KnownTextAndExplorerCountTests` | App 195, Kernel 741, pytest 647, Providers 3068/3068 | pendiente: casos v5 ×3 y e2e de práctica ×3 en el NB; decision3 ×3 en el PC (cambia el esquema) |
| `nb-w10-mover` (sobre cuenta) | 8780e0f34 | `ANamedFileOfThePersonsIsMovedOrCopiedInsideTheFolderNamed`, `AMoveByNameInTheWorkFolderIsRefusedWithTheCallInTheFolderNamed` | App 196, Kernel 741, `ExternalAdaptersTests` 250, pytest 647 | igual; amplía `filesystem.sandbox.move.named` (copy, folder, subdirectory), sin operaciones nuevas |
