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
