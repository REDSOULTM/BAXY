# Plan de cierre del goal «al máximo» (escrito antes de abrir nada)

Pre-registro del análisis del holdout v4, fijado antes de abrirlo (2026-10-22).

## Qué se congela antes de abrir

- HEAD final de `renew-maximo` (todas las tandas que se queden, fusionadas; suites verdes en las dos máquinas sobre
  ese mismo commit).
- Laya: `layam-long-s1-Q8_0.gguf` (el mismo en las tres configuraciones que la usan) y umbrales 0,4 / 0,6.
- Catálogo de cada configuración: `pc-system-one` → `renew_v4\catalog-base.json`; `renew-maximo` → el volcado del
  HEAD final (`renew_v4\catalog-final.json`, con `effects`).

## Las tres configuraciones

| Nombre | Código | System One | Catálogo |
|---|---|---|---|
| `s1off` | `pc-system-one` 86991ca9d (worktree `BAXY-Renew-base`) | apagado (sin BAXY_S1_*) | catalog-base |
| `s1on` | `pc-system-one` 86991ca9d | encendido (0,4 / 0,6 / corrige, Laya Q8) | catalog-base |
| `maximo` | `renew-maximo` HEAD final | encendido, como lo arranca `run_renew.cmd` | catalog-final |

## Bancos y reparto

| Banco | Dónde | Réplicas | Métrica primaria |
|---|---|---|---|
| Decisión (720) | PC semillas 0 y 1, NB semilla 2 (`BAXY_RENEW_SEED`; en `pc-system-one` la semilla es 0 fija, así que sus réplicas son de máquina) | 3 por configuración | aciertos; secundarias: acciones equivocadas, preguntas, p50 |
| Escenas (90) | PC | 1 por configuración | aciertos; molestas y riesgo solo |
| E2E (72) | NB | 1 por configuración | casos cumplidos; pass por familia |
| Falsedades (36) | PC (dueño fuera) o NB | 1 por configuración | falsedades claras leídas a mano + juez 35B |

Intercalado: dentro de cada banco, las configuraciones se alternan (s1off, s1on, maximo, s1off…), nunca una entera
tras otra.

## Análisis (pareado.py del NB)

- Comparaciones: `maximo` frente a `s1on` (lo que ganó el goal) y `s1on` frente a `s1off` (lo que gana System One).
- Decisión: Δ con IC95 por bootstrap pareado sobre los 720 ítems, McNemar exacto por mayoría, Holm entre las dos
  comparaciones. Gemelos de dictado: error estándar agrupado por pareja.
- Escenas, e2e y falsedades: descriptivo con IC (potencia baja por diseño; guarda de regresión).
- Se informa todo, gane o pierda. Nada se reajusta después de abrir.

## Orden del cierre

1. Suites: PC (Kernel, Contracts, Setup, App, pytest) y NB (Providers entero) sobre el mismo commit.
2. Recursos con `measure_resources.py` nuevo (pico durante turnos), voz y S1, en las dos máquinas.
3. Holdout v4: comprobar sha256 del 7z contra `metas.json`, extraer en `renew_v4\holdout\abierto\`, correr el plan.
4. Prueba en vivo en el PC (dueño sin jugar): Spotify, Steam, abrir y cerrar apps, buscar, volumen, ventanas; restaurar.
5. `INFORME_MAXIMO.md` y mensaje al dueño.
6. Lo que espera el oído del dueño: rama `voz-maximo` (9.3), pasos de Supertonic (9.1), muestras en
   `F:\BAXYeval\renew_v4\voz\muestras`.

## Cambios aceptados del NB (buzón 2026-10-22 17:07), antes de abrir

1. **Réplicas simétricas en decisión**: `s1off` y `s1on` corren desde copias de la mente de 86991ca9d con la semilla
   parcheada (s0/s1/s2, `--src` de bench_decision; las prepara el NB y las copia por scp), de modo que las tres
   configuraciones usan semillas 0/1/2.
2. **E2E**: `s1off` ×1, `s1on` ×2, `maximo` ×2 (semillas 0/1; en 86991ca9d por la copia parcheada), intercaladas
   s1on/maximo; ~2,8 h en el NB. Se informa la media y pass^2.
3. **Exclusiones fijadas ahora**: un caso con `setup_fallido` es VOID (fuera de las configuraciones comparadas, no
   fallo); una corrida con el frente sostenido por una ventana invisible (GameInputSvc) se repite entera antes de mirar
   sus aciertos. Nada más se excluye.
4. **Jueces congelados**: los de e2e y falsedades son los de hoy; ningún cambio de scripts de puntuación después de abrir.
5. **NB**: el holdout e2e/falsedades se corre con una copia F:→D: hecha tras extraer; se anotan el sha256 del original y
   de la copia y el número de rutas sustituidas, sin leer el texto de los casos.
6. **Métrica secundaria pre-registrada** en decisión: acciones equivocadas ejecutadas, con su McNemar; los gemelos de
   dictado con error estándar agrupado por pareja.

## Cambio del dueño (2026-10-22 ~19:10)

El latido queda apagado y fuera del goal: **no se corren las escenas del holdout v4** (90). Decisión, e2e y falsedades se
corren como está escrito.

## Añadido al congelar (2026-10-23 02:5x), antes de ver ningún resultado del holdout

- HEAD final: `renew-maximo` 452854a18 (código = `fin` 371f4de72). Catálogo final = `catalog-int8.json` (el Kernel no
  cambió de int8 a fin), sha256 b3184bed…315f; `catalog-base.json` 4441e3b8…5495; Laya 12658256…bdbf; piso de
  confirmación 0,95 (por defecto en el código).
- **Un solo juez para la decisión**: el juez de `bench_decision.py` de 86991ca9d no conoce el cambio de nombre de los
  argumentos de `filesystem.sandbox.diff.named` (P212 de práctica). Para que las tres configuraciones se puntúen igual,
  cada corrida se **re-juzga** con el juez del HEAD final (`scripts/renew/bench_decision.py` y
  `catalog_equivalence.json` de 452854a18) desde los argumentos guardados; se informan las dos cifras (juez propio y
  juez común) y la comparación usa el común.
- Sin escenas (latido apagado). Decisión: PC semillas 0 y 1, NB semilla 2; orden en el PC s1off, s1on, maximo por
  semilla.
